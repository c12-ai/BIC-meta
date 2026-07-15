#!/usr/bin/env bash
# BIC V2 field routine update — deterministic replacement for the README's
# Claude prompt. Runs on the OPERATOR's workstation (needs: git, gh (authed),
# ssh access to the field box). The field box only ever sees compose pull/up.
#
#   ./update.sh                 survey -> guards -> build -> roll -> verify
#   ./update.sh --dry-run       survey + guards only; print the plan, touch nothing
#   ./update.sh --ack-compat    acknowledge the lab/shared-types compat warning
#   ./update.sh --only be,portal  restrict to named services
#   ./update.sh rollback <svc> <sha>   re-pin one service to a previous sha and up
#
# Judgment stays with humans: the script HALTS (fail-loud) on the two things it
# cannot decide — mock compatibility when lab/protocol code changed, and new
# .env.example keys missing from the field .env.
set -euo pipefail

FIELD_SSH="${FIELD_SSH:-orin-tail}"
FIELD_HOST_IP="${FIELD_HOST_IP:-192.168.12.150}"
# Operator's local service-repo checkout (portal/be/lab/chem/mock). Override with
# REPO_BASE=/path/to/repos or BIC_ROOT; autodetected from common layouts otherwise.
REPO_BASE="${REPO_BASE:-${BIC_ROOT:-}}"
if [ -z "$REPO_BASE" ]; then for _c in "$HOME/Work/BIC/talos" "$HOME/Development/BIC" "$HOME/BIC"; do
  [ -d "$_c/BIC-agent-portal" ] && { REPO_BASE="$_c"; break; }
done; fi
# Portal image is site-agnostic since BIC-agent-portal#86 (runtime config via
# /env.js): shared tags (latest / sha-<full sha>), no per-site build variants.
ORG=c12-ai

# svc key -> repo dir | gh repo | container | compose dir | health url (on field) | port
# Order = ROLL order, dependency-safe (consumer after provider): the mock must know
# lab's skill set before lab rolls; lab's API/skills must be live before the BE that
# drives them; BE+lab endpoints must exist before the portal that calls them.
SVCS=(mock chem lab be portal)
repo_dir()   { case "$1" in be) echo BIC-agent-service;; portal) echo BIC-agent-portal;; lab) echo BIC-lab-service;; chem) echo BIC-chem-service;; mock) echo mars_interface_mock;; esac; }
container()  { case "$1" in be) echo bic-agent-service;; portal) echo bic-agent-portal;; lab) echo bic-lab-service;; chem) echo bic-chem-service;; mock) echo bic-robot-mock;; esac; }
compose_dir(){ case "$1" in be) echo agent-service;; portal) echo portal;; lab) echo lab-service;; chem) echo chem-service;; mock) echo robot-mock;; esac; }
health_url() { case "$1" in be) echo http://localhost:8800/health;; portal) echo http://localhost:15173/;; lab) echo http://localhost:8192/health;; chem) echo http://localhost:8010/health;; mock) echo "";; esac; }

GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; NC=$'\033[0m'
ok()   { echo "${GREEN}  ✓${NC} $*"; }
err()  { echo "${RED}  ✗ $*${NC}" >&2; }
info() { echo "${DIM}· $*${NC}"; }
die()  { err "$*"; exit 1; }

fssh() { ssh -o BatchMode=yes "$FIELD_SSH" "$@"; }

DRY=0; ACK_COMPAT=0; ONLY=""
if [ "${1:-}" = "rollback" ]; then
  svc="${2:?usage: update.sh rollback <svc> <full-sha>}"; sha="${3:?full sha required (image tags are sha-<full sha>)}"
  cdir="$(compose_dir "$svc")"; [ -n "$cdir" ] || die "unknown svc $svc"
  tag="sha-${sha}"
  info "rollback $svc -> $tag"
  if [ "$svc" = portal ]; then
    fssh "cd ~/bic-v2 && sed -i \"s|^PORTAL_IMAGE_TAG=.*|PORTAL_IMAGE_TAG=${tag}|\" .env"
  else
    die "non-portal rollback: edit ~/bic-v2/${cdir}/docker-compose.yml image tag to ${tag} manually (compose uses :latest; pin explicitly), then re-run roll"
  fi
  fssh "cd ~/bic-v2 && docker compose -f ${cdir}/docker-compose.yml --env-file .env pull -q && docker compose -f ${cdir}/docker-compose.yml --env-file .env up -d"
  exit 0
fi
while [ $# -gt 0 ]; do case "$1" in
  --dry-run) DRY=1;; --ack-compat) ACK_COMPAT=1;; --only) ONLY="$2"; shift;;
  *) die "unknown arg $1";;
esac; shift; done

in_scope() { [ -z "$ONLY" ] || echo ",$ONLY," | grep -q ",$1,"; }

# ── 1. survey ────────────────────────────────────────────────────────────────
info "survey: field-deployed sha vs origin/main"
declare -A DEPLOYED MAIN CHANGED
for s in "${SVCS[@]}"; do
  in_scope "$s" || continue
  rd="$REPO_BASE/$(repo_dir "$s")"
  [ -d "$rd" ] || { err "$s: repo dir missing ($rd)"; continue; }
  git -C "$rd" fetch -q origin
  MAIN[$s]="$(git -C "$rd" rev-parse origin/main)"
  # All services (portal included since #86) carry the OCI revision label. A
  # pre-#86 portal image lacks it — do the one-time migration in README §portal
  # runtime config first.
  DEPLOYED[$s]="$(fssh "docker inspect $(container "$s") --format '{{index .Config.Labels \"org.opencontainers.image.revision\"}}'" 2>/dev/null || true)"
  dep="${DEPLOYED[$s]:-unknown}"
  if [ -n "$dep" ] && [ "$dep" != unknown ] && git -C "$rd" merge-base --is-ancestor "$dep" "${MAIN[$s]}" 2>/dev/null && [ "$(git -C "$rd" rev-parse "$dep")" != "${MAIN[$s]}" ]; then
    # runtime-relevant? skip if every changed path is CI/docs
    if git -C "$rd" diff --name-only "$dep..${MAIN[$s]}" | grep -qvE '^(\.github/|docs/|.*\.md$)'; then
      CHANGED[$s]=runtime
      ok "$s: ${dep:0:7} -> ${MAIN[$s]:0:7} (runtime changes)"
    else
      CHANGED[$s]=ci-only
      info "$s: ${dep:0:7} -> ${MAIN[$s]:0:7} is CI/docs-only — skipping"
    fi
  elif [ "$dep" = unknown ] || [ -z "$dep" ]; then
    err "$s: deployed sha unknown — inspect manually"
  else
    ok "$s: up to date (${dep:0:7})"
  fi
done
UPDATES=(); for s in "${SVCS[@]}"; do [ "${CHANGED[$s]:-}" = runtime ] && UPDATES+=("$s"); done
[ ${#UPDATES[@]} -gt 0 ] || { ok "nothing to update"; exit 0; }

# ── 2. guards (the judgment calls — halt, don't guess) ──────────────────────
if [ "${CHANGED[lab]:-}" = runtime ] || [ "${CHANGED[mock]:-}" = runtime ]; then
  st="$REPO_BASE/BIC-shared-types"
  [ -d "$st" ] && git -C "$st" fetch -q origin
  if [ "$ACK_COMPAT" -ne 1 ]; then
    err "lab/mock runtime change detected — confirm the mock handles any NEW skill types"
    err "(shared-types pin + handlers; e.g. following-phase skills). Re-run with --ack-compat"
    err "after a human/LLM verified compatibility. Rolling lab ahead of the mock breaks live runs."
    exit 2
  fi
  ok "compat acknowledged (--ack-compat)"
fi

# ── 2a. guard: mock roll must not fight the real robot on the cmd queue ─────
# mock.sh up refuses when ${ROBOT_ID}.cmd already has a consumer, but a roll
# goes through bare `compose up -d` and bypasses it (2026-07-14 orin: real
# mars_interface + mock both consuming talos.001.cmd, commands split round-
# robin; BIC-meta#314). Expected consumers = 1 iff the mock container is
# running; anything above is a foreign consumer — halt, don't recreate it.
if [ "${CHANGED[mock]:-}" = runtime ]; then
  info "guard: cmd-queue consumer mutex (mock roll)"
  mutex="$(fssh bash -s <<'RSCRIPT'
envf=~/bic-v2/.env
mq="$(grep -m1 '^MQ_CONTAINER=' "$envf" | cut -d= -f2-)"; mq="${mq:-bic-rabbitmq}"
rid="$(grep -m1 '^MOCK_ROBOT_ID=' "$envf" | cut -d= -f2-)"; rid="${rid:-talos.001}"
out="$(docker exec "$mq" rabbitmqctl list_queues name consumers 2>/dev/null)" || { echo "ERR - $rid"; exit 0; }
n="$(printf '%s\n' "$out" | awk -v q="${rid}.cmd" '$1==q{print $2}')"
e=0; docker ps --format '{{.Names}}' | grep -qx bic-robot-mock && e=1
echo "${n:-0} $e $rid"
RSCRIPT
)"
  read -r mx_n mx_e mx_rid <<<"$mutex"
  [ "$mx_n" != ERR ] || die "cannot read ${mx_rid}.cmd consumers off the field rabbitmq — fix MQ before rolling the mock"
  if [ "$mx_n" -gt "$mx_e" ]; then
    die "${mx_rid}.cmd has ${mx_n} consumer(s), expected ${mx_e} (mock container $([ "$mx_e" = 1 ] && echo running || echo absent)) — a real robot (mars_interface) or another consumer is live; rolling the mock would split commands nondeterministically. Hand over first (robot-mock/mock.sh down) or re-run with --only excluding mock."
  fi
  ok "cmd-queue mutex clean (${mx_rid}.cmd consumers ${mx_n}, expected ${mx_e})"
fi

info "guard: field .env has every key from the field package .env.example"
missing="$(grep -oE '^[A-Z_]+=' ops/field/.env.example | sort -u | while read -r k; do
  fssh "grep -q '^${k}' ~/bic-v2/.env" || echo "${k%=}"
done)" || true
[ -z "$missing" ] || die "field .env missing keys (set values first): $missing"
ok "env keys complete"

# ── 2b. guard: field compose/config matches the repo ────────────────────────
# Drift here is exactly what shipped the 2026-07-14 orin outage: `up -d` trusts
# the FIELD's compose, and orin's copies predated the auth/CORS wave. Repo is
# the authority — sync with a timestamped backup. Scripts are checked but only
# reported (an executable swap deserves human eyes).
info "guard: field compose/config files match the repo"
local_hash() { md5 -q "$1" 2>/dev/null || md5sum "$1" | cut -d' ' -f1; }
sync_field_file() { # <path relative to ops/field/ and to ~/bic-v2/> [report-only]
  rel="$1"; mode="${2:-sync}"
  lh="$(local_hash "ops/field/$rel")"
  rh="$(fssh "md5sum ~/bic-v2/$rel 2>/dev/null | cut -d' ' -f1" || true)"
  if [ "$lh" = "$rh" ]; then ok "$rel in sync"; return 0; fi
  if [ "$mode" = report-only ]; then
    err "$rel DRIFTED from the repo — review and sync it manually (executable: not auto-synced)"
    return 0
  fi
  if [ "$DRY" -eq 1 ]; then err "$rel drifted — would back up field copy and sync the repo version"; return 0; fi
  fssh "cp ~/bic-v2/$rel ~/bic-v2/$rel.bak-\$(date +%Y%m%d-%H%M%S) 2>/dev/null || true"
  scp -q "ops/field/$rel" "${FIELD_SSH}:bic-v2/$rel"
  ok "$rel synced (field copy backed up)"
}
# ALL services' compose files, not just this round's — a drifted compose on an
# out-of-scope service is a landmine for its next roll. Out-of-scope syncs land
# on disk and apply at that service's next `up`.
for s2 in "${SVCS[@]}"; do sync_field_file "$(compose_dir "$s2")/docker-compose.yml"; done
sync_field_file keycloak/docker-compose.yml
sync_field_file keycloak/realm-bic.json
sync_field_file deploy.sh report-only
sync_field_file scripts/reset.sh report-only

# ── 2c. guard: bic-agent-service client exists in the field realm ───────────
# Realm import only runs on a fresh keycloak DB — an already-imported field
# realm never gains the client from realm-bic.json (2026-07-14: missing on orin).
info "guard: bic-agent-service keycloak client"
client_state="$(fssh bash -s <<'RSCRIPT'
envf=~/bic-v2/.env
g() { grep -m1 "^$1=" "$envf" | cut -d= -f2-; }
kc="$(g KC_CONTAINER_NAME)"; kc="${kc:-bic-keycloak}"
docker exec "$kc" /opt/keycloak/bin/kcadm.sh config credentials   --server http://localhost:8080 --realm master   --user "$(g KEYCLOAK_ADMIN)" --password "$(g KEYCLOAK_ADMIN_PASSWORD)" >/dev/null 2>&1   || { echo LOGIN_FAILED; exit 0; }
if docker exec "$kc" /opt/keycloak/bin/kcadm.sh get clients -r bic -q clientId=bic-agent-service --fields clientId 2>/dev/null | grep -q bic-agent-service; then
  echo EXISTS
else
  echo MISSING
fi
RSCRIPT
)"
case "$client_state" in
  EXISTS) ok "client exists" ;;
  MISSING)
    if [ "$DRY" -eq 1 ]; then err "client MISSING — would create it (kcadm, secret from field .env)"; else
      created="$(fssh bash -s <<'RSCRIPT'
envf=~/bic-v2/.env
g() { grep -m1 "^$1=" "$envf" | cut -d= -f2-; }
kc="$(g KC_CONTAINER_NAME)"; kc="${kc:-bic-keycloak}"
sec="$(g BIC_AGENT_SERVICE_CLIENT_SECRET)"
{ [ -n "$sec" ] && [ "$sec" != "__FILL_ME__" ]; } || { echo NO_SECRET; exit 0; }
docker exec "$kc" /opt/keycloak/bin/kcadm.sh create clients -r bic   -s clientId=bic-agent-service -s 'name=BIC Agent Service' -s protocol=openid-connect   -s enabled=true -s publicClient=false -s serviceAccountsEnabled=true   -s standardFlowEnabled=false -s directAccessGrantsEnabled=false   -s clientAuthenticatorType=client-secret -s "secret=$sec" >/dev/null 2>&1   && echo CREATED || echo CREATE_FAILED
RSCRIPT
)"
      case "$created" in
        CREATED) ok "client created (secret from field .env)" ;;
        NO_SECRET) die "BIC_AGENT_SERVICE_CLIENT_SECRET unset in field .env — fill it, then re-run" ;;
        *) die "kcadm create failed — provision manually per ops/field/README §keycloak" ;;
      esac
    fi ;;
  *) die "kcadm admin login failed — check KEYCLOAK_ADMIN(_PASSWORD) in field .env" ;;
esac

[ "$DRY" -eq 1 ] && { info "dry-run: would build+roll: ${UPDATES[*]}"; exit 0; }

# ── 3. build ─────────────────────────────────────────────────────────────────
for s in "${UPDATES[@]}"; do
  gr="$ORG/$(repo_dir "$s")"
  info "build $s ($gr @ main)"
  gh workflow run docker-build.yml --repo "$gr" --ref main
done
sleep 10
for s in "${UPDATES[@]}"; do
  gr="$ORG/$(repo_dir "$s")"
  for _ in $(seq 1 60); do
    st="$(gh run list --repo "$gr" --workflow docker-build.yml --limit 1 --json status,conclusion --template '{{range .}}{{.status}}:{{.conclusion}}{{end}}')"
    [ "${st%%:*}" = completed ] && break
    sleep 15
  done
  [ "$st" = "completed:success" ] || die "$s image build failed: $st"
  ok "$s image built"
done

# ── 4. roll + health-gate ────────────────────────────────────────────────────
for s in "${UPDATES[@]}"; do
  cdir="$(compose_dir "$s")"
  if [ "$s" = portal ]; then
    # Pin the exact build (shared sha tag since #86) — deterministic roll and
    # a sed-able rollback anchor.
    fssh "cd ~/bic-v2 && sed -i \"s|^PORTAL_IMAGE_TAG=.*|PORTAL_IMAGE_TAG=sha-${MAIN[portal]}|\" .env"
  fi
  info "roll $s"
  fssh "cd ~/bic-v2 && docker compose -f ${cdir}/docker-compose.yml --env-file .env pull -q && docker compose -f ${cdir}/docker-compose.yml --env-file .env up -d"
  hu="$(health_url "$s")"
  if [ -n "$hu" ]; then
    healthy=0
    for _ in $(seq 1 40); do
      fssh "curl -s -o /dev/null -w '%{http_code}' --max-time 3 $hu" | grep -q 200 && { healthy=1; break; }
      sleep 2
    done
    [ "$healthy" -eq 1 ] || die "$s failed health gate after roll — rollback: ./update.sh rollback $s ${DEPLOYED[$s]:0:7}"
    ok "$s healthy"
  fi
done

# ── 5. verify ────────────────────────────────────────────────────────────────
info "verify: stack status"
fssh "cd ~/bic-v2 && ./deploy.sh status" | tail -7
if [ "${CHANGED[be]:-}" = runtime ] || [ "${CHANGED[lab]:-}" = runtime ]; then
  info "verify: MQ consumers"
  fssh "docker exec bic-rabbitmq rabbitmqctl list_queues name consumers 2>/dev/null" | grep -E "agent.task.status\b|results\b|\.cmd\b" || true
fi
if [ "${CHANGED[portal]:-}" = runtime ]; then
  # /env.js is the runtime contract (#86): it must carry the field authority
  # and BE origin, or the SPA boots with an empty OIDC authority (fail-loud
  # by design) — a green /health does not cover this.
  info "verify: portal runtime config (/env.js)"
  ej="$(fssh "curl -s --max-time 5 http://localhost:15173/env.js" || true)"
  echo "$ej" | grep -q "OIDC_AUTHORITY: \"http://${FIELD_HOST_IP}:18080/realms/bic\"" \
    || die "portal /env.js lacks the field OIDC_AUTHORITY — compose env keys not applied? got: $(echo "$ej" | tr '\n' ' ' | cut -c1-160)"
  echo "$ej" | grep -q "API_BASE_URL: \"http://${FIELD_HOST_IP}:8800\"" \
    || die "portal /env.js lacks the field API_BASE_URL — compose env keys not applied?"
  ok "portal /env.js carries the field runtime config"
fi
# ── 5b. verify: auth posture ─────────────────────────────────────────────────
# Green /health never covers auth or CORS (the 2026-07-14 outage rolled straight
# through it): probe the three ways the wave can break — enforcement gate,
# service token, browser preflight.
info "verify: auth posture (401 gate / service token / CORS preflight)"
fssh bash -s -- "$FIELD_HOST_IP" <<'RSCRIPT' || die "auth verify FAILED (see line above) — rollback hints in the roll section"
set -u
FIELD_IP="$1"; envf=~/bic-v2/.env
g() { grep -m1 "^$1=" "$envf" | cut -d= -f2-; }
lp="$(g LAB_PORT)"; lp="${lp:-8192}"
bp="$(g BE_PORT)"; bp="${bp:-8800}"
pp="$(g PORTAL_PORT)"; pp="${pp:-15173}"
kp="$(g KEYCLOAK_PORT)"; kp="${kp:-18080}"
LAB="http://localhost:${lp}"; ORIGIN="http://${FIELD_IP}:${pp}"

code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$LAB/preparations/racks")"
[ "$code" = 401 ] || { echo "FAIL: tokenless lab call expected 401, got $code (LAB_AUTH_MODE off? stale compose?)"; exit 1; }
echo "  ✓ tokenless lab call -> 401 (enforcement on)"

sec="$(g BIC_AGENT_SERVICE_CLIENT_SECRET)"
tok="$(curl -s --max-time 15 -X POST "http://localhost:${kp}/realms/bic/protocol/openid-connect/token"   -d grant_type=client_credentials -d client_id=bic-agent-service   --data-urlencode "client_secret=${sec}"   | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')"
[ -n "$tok" ] || { echo "FAIL: service token mint failed (client missing / secret mismatch)"; exit 1; }
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 -H "Authorization: Bearer $tok" "$LAB/preparations/racks")"
[ "$code" = 200 ] || { echo "FAIL: service-token lab call got $code (lab KEYCLOAK_ISSUER_URL must byte-match token iss)"; exit 1; }
echo "  ✓ service token -> lab 200"

for tgt in "$LAB/preparations/racks" "http://localhost:${bp}/sessions"; do
  hdrs="$(curl -s -D - -o /dev/null --max-time 5 -X OPTIONS "$tgt"     -H "Origin: ${ORIGIN}" -H "Access-Control-Request-Method: GET"     -H "Access-Control-Request-Headers: authorization")"
  echo "$hdrs" | head -1 | grep -q " 200" || { echo "FAIL: preflight $tgt not 200 (origin ${ORIGIN})"; exit 1; }
  echo "$hdrs" | grep -qi "^access-control-allow-origin:" || { echo "FAIL: preflight $tgt has no allow-origin for ${ORIGIN} — CORS_ALLOW_ORIGINS mismatch"; exit 1; }
done
echo "  ✓ CORS preflight (portal origin ${ORIGIN}) -> lab + BE both allowed"
RSCRIPT

ok "update complete: ${UPDATES[*]}"
for s in "${UPDATES[@]}"; do echo "  $s: ${DEPLOYED[$s]:0:7} -> ${MAIN[$s]:0:7}"; done
