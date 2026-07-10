#!/usr/bin/env bash
# common.sh — shared library for the BIC one-shot env scripts.
#
# Sourced by doctor.sh / up.sh / status.sh / down.sh / restart.sh.
# All BIC bring-up knowledge is ENCODED HERE (ports, containers, health,
# self-heal), so the human entry point stays "clone meta -> make up".
#
# Design constraints:
#   - bash 3.2 safe (stock macOS): NO associative arrays, NO ${v,,}.
#   - Sourcing this file has NO side effects beyond defining vars/functions.
#   - Every mutating action goes through do_run() so DRY=1 prints instead of runs.
#
# Authoritative port table: ops/port-allocation-2026-07-10.md (mirror of
# BIC-infra/README §Port allocation). Keep this file in sync with that doc.

# ----------------------------------------------------------------------------
# Locations
# ----------------------------------------------------------------------------
_bic_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# scripts/bic-env/ -> repo root is two levels up.
BIC_META_DIR="$(cd "${_bic_here}/../.." && pwd)"

# BIC_ROOT: where the sibling repos (BIC-lab-service, ...) live.
# Default = parent of the meta checkout (the intended coworker layout, where
# meta is cloned next to the service repos). Override when your checkout differs.
BIC_ROOT="${BIC_ROOT:-$(cd "${BIC_META_DIR}/.." && pwd)}"

# Chem source dir (台架 runs the feat/compound-names worktree; infra image is a
# fallback). Override with CHEM_DIR=...
if [ -z "${CHEM_DIR:-}" ]; then
  if [ -d "${BIC_ROOT}/.wt/chem-95" ]; then
    CHEM_DIR="${BIC_ROOT}/.wt/chem-95"
  else
    CHEM_DIR="${BIC_ROOT}/BIC-chem-service"
  fi
fi

# Infra repo (docker compose for bic-* containers). Override with INFRA_DIR=...
if [ -z "${INFRA_DIR:-}" ]; then
  for _cand in "${BIC_ROOT}/infra" "${BIC_ROOT}/BIC-infra" "${BIC_ROOT}/../infra"; do
    if [ -d "${_cand}" ]; then INFRA_DIR="$(cd "${_cand}" && pwd)"; break; fi
  done
  INFRA_DIR="${INFRA_DIR:-${BIC_ROOT}/infra}"
fi

# Profile: minimal (Mind mocked + local MinIO) is the coworker default.
# full-real reads the repos' existing .env values and never overrides them.
BIC_PROFILE="${BIC_PROFILE:-minimal}"

# DRY: `make up DRY=1` prints mutating actions instead of running them.
DRY_RUN="${DRY:-${DRY_RUN:-0}}"

# tmux session that hosts the app processes.
BIC_TMUX="${BIC_TMUX:-bic-services}"

# ----------------------------------------------------------------------------
# Output helpers (colour only on a TTY, honour NO_COLOR)
# ----------------------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YEL=$'\033[33m'
  C_BLU=$'\033[34m'; C_DIM=$'\033[2m'; C_BLD=$'\033[1m'; C_RST=$'\033[0m'
else
  C_RED=''; C_GRN=''; C_YEL=''; C_BLU=''; C_DIM=''; C_BLD=''; C_RST=''
fi

# Global counters (checks mutate these directly — never call check fns in $()).
BIC_OK=0; BIC_WARN=0; BIC_FAIL=0

section() { printf '\n%s%s== %s ==%s\n' "${C_BLD}" "${C_BLU}" "$1" "${C_RST}"; }

ok()   { BIC_OK=$((BIC_OK + 1));     printf '  %s✓%s %s\n' "${C_GRN}" "${C_RST}" "$1"; }
warn() { BIC_WARN=$((BIC_WARN + 1)); printf '  %s!%s %s\n' "${C_YEL}" "${C_RST}" "$1"; }

# fail "<what is wrong>" "<fix command>"  — every red card carries its own fix.
fail() {
  BIC_FAIL=$((BIC_FAIL + 1))
  printf '  %s✗%s %s\n' "${C_RED}" "${C_RST}" "$1"
  if [ -n "${2:-}" ]; then
    printf '      %s→ fix:%s %s\n' "${C_DIM}" "${C_RST}" "$2"
  fi
}

note() { printf '  %s· %s%s\n' "${C_DIM}" "$1" "${C_RST}"; }

# ----------------------------------------------------------------------------
# do_run — the single mutation gate. DRY=1 prints, else executes.
# ----------------------------------------------------------------------------
do_run() {
  if [ "${DRY_RUN}" = "1" ]; then
    printf '  %s[dry]%s' "${C_YEL}" "${C_RST}"
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

# do_sh — same gate for a shell one-liner (pipes/redirects). Use sparingly.
do_sh() {
  if [ "${DRY_RUN}" = "1" ]; then
    printf '  %s[dry]%s %s\n' "${C_YEL}" "${C_RST}" "$1"
    return 0
  fi
  bash -c "$1"
}

# ----------------------------------------------------------------------------
# HTTP / proxy helpers — local services must be hit with --noproxy '*'
# (the box's 127.0.0.1:7890 proxy otherwise swallows localhost).
# ----------------------------------------------------------------------------
http_code() {
  curl -s --noproxy '*' --max-time "${2:-5}" -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || echo 000
}
http_body() {
  curl -s --noproxy '*' --max-time "${2:-5}" "$1" 2>/dev/null || true
}
http_code_ct() { # -> "<code> <content-type>"
  curl -s --noproxy '*' --max-time "${2:-5}" -o /dev/null -w '%{http_code} %{content_type}' "$1" 2>/dev/null || echo "000 -"
}

# The proxy prefix BE must launch with (unset so it can reach localhost/lab/MQ).
PROXY_VARS="all_proxy http_proxy https_proxy ALL_PROXY HTTP_PROXY HTTPS_PROXY"
unset_proxy_prefix() { printf 'unset %s && ' "${PROXY_VARS}"; }

# ----------------------------------------------------------------------------
# Port / process inspection
# ----------------------------------------------------------------------------
# port_owner <port> -> "<command> <pid>" for the LISTEN socket, or "" if free.
port_owner() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR==2{print $1" "$2; exit}'
}
port_pid()  { port_owner "$1" | awk '{print $2}'; }
port_cmd()  { port_owner "$1" | awk '{print $1}'; }
port_free() { [ -z "$(port_owner "$1")" ]; }

# is_our_process <pid> — true when the process cmdline / cwd sits under BIC_ROOT
# (i.e. one of our uvicorn/vite/mock processes), so up/restart may recycle it.
is_our_process() {
  local pid="$1" args cwd
  [ -n "${pid}" ] || return 1
  args="$(ps -o command= -p "${pid}" 2>/dev/null || true)"
  case "${args}" in
    *"${BIC_ROOT}"*) return 0 ;;
    *uvicorn*app.main*|*mars-interface-mock*|*vite*) return 0 ;;
  esac
  cwd="$(lsof -a -p "${pid}" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1)"
  case "${cwd}" in
    "${BIC_ROOT}"*) return 0 ;;
  esac
  return 1
}

# ----------------------------------------------------------------------------
# Docker helpers
# ----------------------------------------------------------------------------
docker_up() { docker info >/dev/null 2>&1; }
# container_running <name>
container_running() { docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$1"; }
# container_exists <name> (any state)
container_exists() { docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$1"; }
# container_on_port <hostport> -> first running container publishing it
container_on_port() { docker ps --filter "publish=$1" --format '{{.Names}}' 2>/dev/null | head -1; }

# ----------------------------------------------------------------------------
# Registries (encode the whole topology). Lines are "|"-separated records.
# ----------------------------------------------------------------------------
# Infra containers we manage:  name|primary_port|label
infra_containers() {
  cat <<'REC'
bic-postgres|5432|Postgres (shared infra)
talos-postgres|5433|Postgres (talos — apps use this)
bic-redis|6379|Redis
bic-rabbitmq|5672|RabbitMQ (AMQP 5672 / mgmt 15672)
bic-minio|9000|MinIO (S3 9000 / console 9001)
REC
}

# Authoritative port table:  port|kind|expect|label
#   kind=docker -> LISTEN owner must be docker; kind=app -> our host process.
port_table() {
  cat <<'REC'
5432|docker|bic-postgres|Postgres (shared infra)
5433|docker|talos-postgres|Postgres (talos, apps use this)
6379|docker|bic-redis|Redis
5672|docker|bic-rabbitmq|RabbitMQ AMQP
15672|docker|bic-rabbitmq|RabbitMQ mgmt
9000|docker|bic-minio|MinIO S3 API
9001|docker|bic-minio|MinIO console
18080|docker|keycloak|Keycloak (8080+10000)
6006|docker|bic-phoenix|Phoenix UI
4317|docker|bic-phoenix|Phoenix OTLP
8192|app|lab|Lab service (Nexus)
8800|app|BE|Agent backend
5173|app|portal|Portal (Vite)
8010|app|chem|Chem service
8011|ext|mind|Mind capture proxy (external bridge to orin, full-real only)
REC
}

# The six managed services (for status / health):
#   name|port|repo|health_url   (port "-" and url "-" => no HTTP surface)
services() {
  cat <<REC
lab|8192|BIC-lab-service|http://localhost:8192/health
BE|8800|BIC-agent-service|http://localhost:8800/health
portal|5173|BIC-agent-portal|http://localhost:5173/src/main.tsx
keycloak|18080|-|http://localhost:18080/realms/bic/.well-known/openid-configuration
chem|8010|${CHEM_DIR}|http://localhost:8010/health
mock|-|mars_interface_mock|-
REC
}

# Keycloak dev users that up.sh seeds (idempotently).
# shellcheck disable=SC2034  # consumed by up.sh via `for u in ${KC_DEV_USERS}`
KC_DEV_USERS="wenlong valen"
KC_DEV_PASSWORD="${KC_DEV_PASSWORD:-bic_local_dev}"
KC_ADMIN_USER="${KC_ADMIN_USER:-admin}"
KC_ADMIN_PASSWORD="${KC_ADMIN_PASSWORD:-bic_local_dev}"
KC_REALM="${KC_REALM:-bic}"
KC_CLIENT="${KC_CLIENT:-bic-portal}"

# git_sha <dir> -> short sha or "-"
git_sha() { git -C "$1" rev-parse --short HEAD 2>/dev/null || echo "-"; }
git_branch() { git -C "$1" branch --show-current 2>/dev/null || echo "-"; }

# repo_dir <name> -> absolute path under BIC_ROOT
repo_dir() { printf '%s/%s\n' "${BIC_ROOT}" "$1"; }

# print_context — one-line banner so every command states where it is looking.
print_context() {
  printf '%sBIC_ROOT%s=%s  %sprofile%s=%s  %sdry%s=%s\n' \
    "${C_DIM}" "${C_RST}" "${BIC_ROOT}" \
    "${C_DIM}" "${C_RST}" "${BIC_PROFILE}" \
    "${C_DIM}" "${C_RST}" "${DRY_RUN}"
}
