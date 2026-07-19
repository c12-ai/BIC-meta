#!/usr/bin/env bash
# relay-deploy.sh — Mac-relay deploy for cross-border field boxes (aws-test 首用).
#
# Born 2026-07-19 from the env-staging deploy postmortem. Every preflight check
# below exists because its ABSENCE cost real wall-clock that day:
#
#   P1  EC2 (cn-northwest-1) pulling ghcr.io directly is cross-border: tens of
#       minutes with zero progress. Fix = THIS script: the Mac pulls via its
#       proxy (~40s for three images), then `docker save | ssh docker load`
#       (domestic leg, ~1-2 min). The box never talks to ghcr.
#   P2  Operator IP not in the AWS security-group whitelist -> ssh channels
#       DIE SILENTLY mid-command (no keepalive => a 41-minute hang that looked
#       like "slow"). Fix = preflight checks the office-ips managed prefix
#       list and every ssh here carries ServerAliveInterval.
#   P3  update.sh rebuilds images on every re-run (no --roll-only), so each
#       recovery attempt burned another CI wave. Fix = this script never
#       builds; it deploys what main's docker-build workflows already pushed,
#       and refuses stale images instead (fail loud, remediation printed).
#   P4  Killed/hung runs leave duplicate `docker compose pull` processes on
#       the box, silently competing for bandwidth. Fix = preflight sweeps them.
#   P5  containerd-store multi-arch tags: a bare `docker save` exports EVERY
#       platform manifest incl. blobs the Mac never pulled -> broken tar on
#       load ("content digest ... not found"). Fix = save --platform.
#   P6  `cmd | tail` style piping masks exit codes (two "successes" that day
#       were failures). Fix = pipefail + explicit per-step rc handling.
#
# Known residual (documented, NOT handled here): update.sh's unconditional
# compose sync clobbers aws-test's site-local `KC_PROXY_HEADERS: xforwarded`
# line in keycloak/docker-compose.yml — re-add it after any update.sh run
# until the per-site knob ruling lands.
#
# Usage:
#   FIELD_SSH=aws-test ops/field/relay-deploy.sh [--dry-run] [--force]
#                                                [--only lab,be,portal,mock]
#                                                [--fix-ip] [--reset]
#
#   --dry-run   preflight + survey only; print the plan, transfer nothing
#   --force     relay + roll even when the box already runs the target digest
#   --only      restrict to named services (default: lab,be,portal + mock
#               only when its container is already running — consumer mutex)
#   --fix-ip    if the current public IP is missing from the office-ips
#               prefix list, ADD it (otherwise just red-card + remediation)
#   --reset     after a green verify, run the box's scripts/reset.sh all
#               (dataset=test both sides — destructive to bench state)
#
# ── Colleague quickstart (nothing here is Wenlong's-Mac-specific) ────────────
# Required locally:
#   - docker (Docker Desktop; any store — --platform save is feature-detected)
#   - gh CLI, authenticated with c12-ai access (`gh auth login`)
#   - an ~/.ssh/config entry for the box + the team key, e.g.:
#         Host aws-test
#           HostName ec2-43-192-79-141.cn-northwest-1.compute.amazonaws.com.cn
#           User ubuntu
#           IdentityFile ~/.ssh/c12_northwest.pem   # team key — ask ops
# Optional:
#   - aws CLI with China-partition creds (default profile): enables the IP
#     whitelist preflight + --fix-ip. WITHOUT it the script still runs — the
#     ssh reachability probe is the authoritative gate (office IPs are already
#     whitelisted); you only lose the "is it the whitelist?" diagnosis.
# Runs on macOS stock bash 3.2 (no associative arrays / GNU-only tools used).
set -euo pipefail

FIELD_SSH="${FIELD_SSH:-aws-test}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=10 -o ServerAliveCountMax=3)
OFFICE_PREFIX_LIST="${OFFICE_PREFIX_LIST:-pl-0ebfc997aed4672cb}"   # office-ips (cn-northwest-1)
AWS_REGION="${AWS_REGION:-cn-northwest-1}"
LOG_FILE="${LOG_FILE:-/tmp/relay-deploy-$(date +%Y%m%d-%H%M%S).log}"

DRY=0; FORCE=0; FIX_IP=0; DO_RESET=0; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --force)   FORCE=1 ;;
    --fix-ip)  FIX_IP=1 ;;
    --reset)   DO_RESET=1 ;;
    --only)    ONLY="${2:?--only needs a list}"; shift ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
  shift
done

# ── logging: every line timestamped, mirrored to $LOG_FILE ───────────────────
log()  { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG_FILE"; }
ok()   { log "  ✓ $*"; }
fail() { log "  ✗ $1"; [ -n "${2:-}" ] && log "      → fix: $2"; FAILED=1; }
step() { log ""; log "===== $* ====="; }
die()  { fail "$1" "${2:-}"; log "ABORT — log: $LOG_FILE"; exit 1; }
FAILED=0

fssh() { ssh "${SSH_OPTS[@]}" "$FIELD_SSH" "$@"; }

# svc -> image ref / container / compose dir. Case functions, not `declare -A`:
# macOS stock bash is 3.2 (no associative arrays) and colleagues may not have
# a homebrew bash on PATH.
container_of() {
  case "$1" in
    lab) echo bic-lab-service ;; be) echo bic-agent-service ;;
    portal) echo bic-agent-portal ;; mock) echo bic-robot-mock ;;
  esac
}
compose_of() {
  case "$1" in
    lab) echo lab-service ;; be) echo agent-service ;;
    portal) echo portal ;; mock) echo robot-mock ;;
  esac
}
image_ref() { # portal is pinned by main's full sha; others ride :main / :latest
  case "$1" in
    lab)    echo "ghcr.io/c12-ai/bic-lab-service:main" ;;
    be)     echo "ghcr.io/c12-ai/bic-agent-service:main" ;;
    portal) echo "ghcr.io/c12-ai/bic-agent-portal:sha-${PORTAL_SHA}" ;;
    mock)   echo "ghcr.io/c12-ai/mars_interface_mock:latest" ;;
  esac
}

# ═════════════════════════════════════════════════════════════════════════════
step "STEP 0: preflight (local tooling / GitHub / AWS whitelist / ssh / box)"

command -v docker >/dev/null || die "docker CLI missing" "install Docker Desktop"
docker info >/dev/null 2>&1 || die "docker daemon not running" "open -a Docker"
ok "docker daemon up"

command -v gh >/dev/null || die "gh CLI missing" "brew install gh && gh auth login"
gh auth status >/dev/null 2>&1 || die "gh not authenticated" "gh auth login"
ok "gh authenticated"

# GitHub API reachability + a real permission probe (private repo read).
if gh api repos/c12-ai/BIC-meta --jq .full_name >/dev/null 2>&1; then
  ok "GitHub API reachable + c12-ai read permission"
else
  die "GitHub API unreachable or no c12-ai access" "check network/proxy; gh auth status"
fi

# ghcr pull permission: manifest inspect of a private image (fast, no download).
if docker manifest inspect ghcr.io/c12-ai/bic-agent-service:main >/dev/null 2>&1; then
  ok "ghcr.io pull permission (manifest inspect OK)"
else
  log "  · ghcr auth missing — attempting login via gh token"
  if gh auth token | docker login ghcr.io -u "$(gh api user --jq .login)" --password-stdin >/dev/null 2>&1 \
     && docker manifest inspect ghcr.io/c12-ai/bic-agent-service:main >/dev/null 2>&1; then
    ok "ghcr.io login refreshed via gh token"
  else
    die "cannot read ghcr.io/c12-ai images" "docker login ghcr.io with a read:packages PAT"
  fi
fi

# AWS whitelist (P2): the box's security group admits the office-ips prefix
# list only — an unlisted operator IP means ssh dies/hangs, often silently.
MYIP="$(curl -s --max-time 8 https://checkip.amazonaws.com.cn || curl -s --max-time 8 https://api.ipify.org || true)"
[ -n "$MYIP" ] || die "cannot determine public IP" "check network"
log "  · public IP: $MYIP"
if ! command -v aws >/dev/null 2>&1 || ! aws sts get-caller-identity --region "$AWS_REGION" >/dev/null 2>&1; then
  # NOT fatal: the ssh probe below is the authoritative gate (office IPs are
  # pre-whitelisted). Without aws creds you only lose the whitelist DIAGNOSIS
  # — if ssh then fails/hangs, the whitelist is the first suspect.
  log "  · aws CLI unavailable/no China-partition creds — skipping whitelist check (ssh probe decides)"
else
  if aws ec2 get-managed-prefix-list-entries --region "$AWS_REGION" \
       --prefix-list-id "$OFFICE_PREFIX_LIST" --query 'Entries[].Cidr' --output text 2>/dev/null \
       | tr '\t' '\n' | grep -qx "${MYIP}/32"; then
    ok "IP ${MYIP} is in the office-ips whitelist"
  elif [ "$FIX_IP" = 1 ]; then
    VER="$(aws ec2 describe-managed-prefix-lists --region "$AWS_REGION" --prefix-list-ids "$OFFICE_PREFIX_LIST" --query 'PrefixLists[0].Version' --output text)"
    aws ec2 modify-managed-prefix-list --region "$AWS_REGION" --prefix-list-id "$OFFICE_PREFIX_LIST" \
      --current-version "$VER" --add-entries "Cidr=${MYIP}/32,Description=relay-deploy $(date +%F)" >/dev/null
    ok "IP ${MYIP}/32 ADDED to office-ips (was missing)"
    sleep 5
  else
    die "IP ${MYIP} NOT in office-ips prefix list — ssh will hang/die silently" \
        "re-run with --fix-ip, or: aws ec2 modify-managed-prefix-list --region ${AWS_REGION} --prefix-list-id ${OFFICE_PREFIX_LIST} --current-version <V> --add-entries Cidr=${MYIP}/32,Description=..."
  fi
fi

# ssh reachability + remote docker permission + disk.
if fssh 'echo ok' >/dev/null 2>&1; then
  ok "ssh ${FIELD_SSH} reachable"
else
  die "ssh ${FIELD_SSH} unreachable" \
      "1) IP whitelist (see above / --fix-ip)  2) ~/.ssh/config needs:  Host ${FIELD_SSH} / HostName ec2-43-192-79-141.cn-northwest-1.compute.amazonaws.com.cn / User ubuntu / IdentityFile ~/.ssh/c12_northwest.pem (team key — ask ops)"
fi
fssh 'docker info >/dev/null 2>&1' || die "remote user cannot run docker" "usermod -aG docker on the box"
ok "remote docker permission"
REMOTE_FREE_GB="$(fssh "df -BG /var/lib/docker 2>/dev/null | awk 'NR==2 {print \$4}' | tr -d G")"
[ "${REMOTE_FREE_GB:-0}" -ge 5 ] && ok "remote /var/lib/docker free: ${REMOTE_FREE_GB}G" \
  || fail "remote docker disk low (${REMOTE_FREE_GB:-?}G)" "docker system prune on the box"

# Residual pull sweep (P4): kill leftover compose pulls from dead runs.
# [d] bracket trick: without it the pattern matches the remote shell CARRYING
# this very command, and pkill kills its own parent (P7, found testing this).
RESIDUAL="$(fssh 'pgrep -fc "[d]ocker compose.*pull" || true')"
if [ "${RESIDUAL:-0}" -gt 0 ]; then
  fssh 'pkill -f "[d]ocker compose.*pull" || true'
  ok "killed ${RESIDUAL} residual remote pull process(es)"
else
  ok "no residual remote pulls"
fi

[ "$FAILED" = 1 ] && die "preflight failed — fix the red cards above"

# ═════════════════════════════════════════════════════════════════════════════
step "STEP 1: survey (target = origin/main heads; skip services already there)"

PORTAL_SHA="$(gh api repos/c12-ai/BIC-agent-portal/commits/main --jq .sha)"
log "  · portal main sha: ${PORTAL_SHA:0:12}"

# default service set: lab/be/portal always; mock only when already running
# (its consumer-mutex with the real robot is owned by whoever started it —
# recreating a RUNNING mock preserves the single-consumer property).
if [ -n "$ONLY" ]; then
  IFS=',' read -ra SVCS <<< "$ONLY"
else
  SVCS=(lab be portal)
  if fssh 'docker ps --format "{{.Names}}" | grep -qx bic-robot-mock'; then SVCS+=(mock); fi
fi

PLAN=()
for s in "${SVCS[@]}"; do
  ref="$(image_ref "$s")"
  running_created="$(fssh "docker image inspect '$ref' --format '{{.Created}}' 2>/dev/null" || echo absent)"
  # True up-to-date detection happens in STEP 3 by image-ID comparison after
  # the (cheap, proxied) Mac pull; the survey only reports what the box runs.
  log "  · $s: box image created=${running_created}"
  PLAN+=("$s")
done
log "  · plan: relay+roll -> ${PLAN[*]} (use --force to re-roll up-to-date services)"

if [ "$DRY" = 1 ]; then log ""; log "DRY RUN — stopping before transfer. Log: $LOG_FILE"; exit 0; fi

# ═════════════════════════════════════════════════════════════════════════════
step "STEP 2: Mac pull (linux/amd64, via local proxy)"

for s in "${PLAN[@]}"; do
  ref="$(image_ref "$s")"
  t0=$(date +%s)
  docker pull --platform linux/amd64 -q "$ref" >/dev/null || die "pull failed: $ref" "check ghcr auth / proxy"
  created="$(docker image inspect "$ref" --format '{{.Created}}')"
  ok "$s pulled in $(( $(date +%s) - t0 ))s (created=$created)"
done

# ═════════════════════════════════════════════════════════════════════════════
step "STEP 3: relay Mac -> ${FIELD_SSH} (save --platform | gzip | ssh docker load)"

for s in "${PLAN[@]}"; do
  ref="$(image_ref "$s")"
  # skip when the box already has this exact image ID (unless --force)
  local_id="$(docker image inspect "$ref" --format '{{.Id}}')"
  box_id="$(fssh "docker image inspect '$ref' --format '{{.Id}}' 2>/dev/null" || echo none)"
  if [ "$local_id" = "$box_id" ] && [ "$FORCE" = 0 ]; then ok "$s already on the box (image ID match) — skip transfer"; continue; fi
  t0=$(date +%s)
  # P5: --platform is load-bearing on containerd stores (multi-arch tags).
  # P5: --platform is load-bearing on containerd stores (multi-arch tags), but
  # the flag only exists on newer Docker — feature-detect and fall back (on
  # graph-driver stores the pulled tag is single-platform, so bare save is safe).
  if docker save --help 2>/dev/null | grep -q -- --platform; then
    SAVE_CMD=(docker save --platform linux/amd64 "$ref")
  else
    SAVE_CMD=(docker save "$ref")
  fi
  out="$("${SAVE_CMD[@]}" | gzip -1 | fssh 'gunzip | docker load' 2>&1 | tail -1)" \
    || die "relay failed for $s: $out" "check ssh stability (whitelist!) and remote disk"
  case "$out" in *"Loaded image"*) ;; *) die "unexpected docker load output for $s: $out" ;; esac
  ok "$s relayed in $(( $(date +%s) - t0 ))s"
done

# ═════════════════════════════════════════════════════════════════════════════
step "STEP 4: roll services on ${FIELD_SSH} (compose up -d --pull never)"

fssh "cd ~/bic-v2 && sed -i \"s|^PORTAL_IMAGE_TAG=.*|PORTAL_IMAGE_TAG=sha-${PORTAL_SHA}|\" .env"
ok "portal tag pinned: sha-${PORTAL_SHA:0:12}"
for s in "${PLAN[@]}"; do
  cdir="$(compose_of "$s")"
  out="$(fssh "cd ~/bic-v2 && set -a && . ./.env && set +a && docker compose -f ${cdir}/docker-compose.yml up -d --pull never 2>&1 | tail -1")" \
    || die "compose up failed for $s: $out"
  ok "$s: $out"
done

# ═════════════════════════════════════════════════════════════════════════════
step "STEP 5: verify (health, image freshness, stage gate, reset contract)"

log "  · waiting up to 90s for health probes"
deadline=$(( $(date +%s) + 90 )); ALL_OK=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  unhealthy="$(fssh 'docker ps --format "{{.Names}} {{.Status}}"' | awk -v list="${PLAN[*]}" '
    BEGIN { split(list, a, " "); m["lab"]="bic-lab-service"; m["be"]="bic-agent-service"; m["portal"]="bic-agent-portal"; m["mock"]="bic-robot-mock" }
    { st[$1]=$0 }
    END { for (i in a) { c=m[a[i]]; if (!(c in st)) { print c" MISSING"; next } if (c != "bic-robot-mock" && st[c] !~ /healthy/) print st[c] } }')"
  [ -z "$unhealthy" ] && { ALL_OK=1; break; }
  sleep 5
done
if [ "$ALL_OK" = 1 ]; then ok "all rolled containers healthy"; else die "unhealthy after 90s: $unhealthy" "docker logs <container> on the box"; fi

for s in "${PLAN[@]}"; do
  ref="$(image_ref "$s")"; c="$(container_of "$s")"
  run_img="$(fssh "docker inspect $c --format '{{.Image}}'")"
  want_img="$(fssh "docker image inspect '$ref' --format '{{.Id}}'")"
  [ "$run_img" = "$want_img" ] && ok "$s runs the relayed image" || fail "$s container is NOT on the relayed image" "docker compose up -d --force-recreate on the box"
done

# stage gate: a gated image with missing APP_ENV/.env.prod crash-loops with FATAL.
gate="$(fssh 'for c in bic-lab-service bic-agent-service bic-robot-mock; do docker logs --tail 50 $c 2>&1 | grep -m1 "FATAL: APP_ENV" && echo "$c GATE-FAIL"; done; true')"
[ -z "$gate" ] && ok "no stage-gate FATALs in service logs" || die "stage gate firing: $gate" "check compose APP_ENV + lib/stage.env mount (BIC-meta#336)"

# reset contract (non-destructive probe): missing dataset must 422.
code="$(fssh 'curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8800/reset -H "Content-Type: application/json" -d "{}"')"
[ "$code" = 422 ] && ok "reset contract: missing dataset -> 422" || fail "reset probe returned $code (expected 422)" "is the new BE image actually running?"

if [ "$DO_RESET" = 1 ]; then
  log "  · --reset: running the box's scripts/reset.sh all (dataset=test)"
  fssh 'cd ~/bic-v2 && ./scripts/reset.sh all' 2>&1 | tail -3 | tee -a "$LOG_FILE"
fi

[ "$FAILED" = 1 ] && die "verify finished with red cards"
log ""
log "DONE — deployed ${PLAN[*]} to ${FIELD_SSH}. Full log: $LOG_FILE"
