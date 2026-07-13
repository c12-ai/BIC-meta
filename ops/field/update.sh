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
REPO_BASE="${REPO_BASE:-/Users/wenlongwang/Work/BIC/talos}"
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
  svc="${2:?usage: update.sh rollback <svc> <sha>}"; sha="${3:?sha required}"
  cdir="$(compose_dir "$svc")"; [ -n "$cdir" ] || die "unknown svc $svc"
  tag="sha-${sha}"
  [ "$svc" = portal ] && tag="field-${sha:0:7}"
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
  if [ "$s" = portal ]; then
    DEPLOYED[$s]="$(fssh "grep -m1 '^PORTAL_IMAGE_TAG=' ~/bic-v2/.env" | sed 's/.*field-//')"
  else
    DEPLOYED[$s]="$(fssh "docker inspect $(container "$s") --format '{{index .Config.Labels \"org.opencontainers.image.revision\"}}'" 2>/dev/null || true)"
  fi
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
info "guard: field .env has every key from the field package .env.example"
missing="$(grep -oE '^[A-Z_]+=' ops/field/.env.example | sort -u | while read -r k; do
  fssh "grep -q '^${k}' ~/bic-v2/.env" || echo "${k%=}"
done)" || true
[ -z "$missing" ] || die "field .env missing keys (set values first): $missing"
ok "env keys complete"

[ "$DRY" -eq 1 ] && { info "dry-run: would build+roll: ${UPDATES[*]}"; exit 0; }

# ── 3. build ─────────────────────────────────────────────────────────────────
for s in "${UPDATES[@]}"; do
  gr="$ORG/$(repo_dir "$s")"
  info "build $s ($gr @ main)"
  if [ "$s" = portal ]; then
    gh workflow run docker-build.yml --repo "$gr" --ref main \
      -f image_variant=field \
      -f vite_api_base_url="http://${FIELD_HOST_IP}:8800" \
      -f vite_lab_api_base_url="http://${FIELD_HOST_IP}:8192" \
      -f vite_oidc_authority="http://${FIELD_HOST_IP}:18080/realms/bic"
  else
    gh workflow run docker-build.yml --repo "$gr" --ref main
  fi
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
    fssh "cd ~/bic-v2 && sed -i \"s|^PORTAL_IMAGE_TAG=.*|PORTAL_IMAGE_TAG=field-${MAIN[portal]:0:7}|\" .env"
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
  info "verify: portal bundle bake"
  n="$(fssh "asset=\$(curl -s http://localhost:15173/ | grep -oE '/assets/[^\"]+\.js' | head -1); curl -s http://localhost:15173\$asset | grep -coE 'localhost:18080'" || true)"
  [ "${n:-0}" = 0 ] && ok "portal bundle clean (0x localhost:18080)" || die "portal bundle contains localhost:18080 — wrong build args"
fi
ok "update complete: ${UPDATES[*]}"
for s in "${UPDATES[@]}"; do echo "  $s: ${DEPLOYED[$s]:0:7} -> ${MAIN[$s]:0:7}"; done
