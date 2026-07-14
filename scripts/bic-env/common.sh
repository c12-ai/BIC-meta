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

# Machine-local overrides (gitignored): .bic-env in the meta root can pin
# BIC_ROOT / BIC_PROFILE / CHEM_DIR for THIS machine, so a bare `make up` works
# on non-standard layouts. Write it with defaulting syntax so real env vars
# still win, e.g.:  export BIC_ROOT="${BIC_ROOT:-/path/to/repos}"
# Motivating incident (2026-07-10): autodetect resolved a meta checkout's
# parent dir that held STALE template repos, and `make update` ran alembic
# against the live DB from an old branch.
if [ -f "${BIC_META_DIR}/.bic-env" ]; then
  # shellcheck source=/dev/null
  . "${BIC_META_DIR}/.bic-env"
fi

# BIC_ROOT: where the service repos (BIC-lab-service, ...) live.
# Autodetect the two known layouts (keep in sync with the top-level Makefile):
#   nested  — repos cloned INSIDE the meta checkout (BIC/BIC-agent-service, ...)
#   sibling — meta cloned NEXT TO the repos (the coworker story's default)
# Override with BIC_ROOT=... when neither fits.
if [ -z "${BIC_ROOT:-}" ]; then
  if [ -d "${BIC_META_DIR}/BIC-agent-service" ]; then
    BIC_ROOT="${BIC_META_DIR}"
  else
    BIC_ROOT="$(cd "${BIC_META_DIR}/.." && pwd)"
  fi
fi

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

# Profile: aws (default) — cloud Mind + real AWS S3 (a1-site 口径; no route or
# forwarder, both are public-internet direct). Alternatives:
#   minimal   — Mind mocked + local MinIO (coworker / offline default)
#   full-real — orin LAN real Mind + orin MinIO (tailscale route + :9000 forwarder)
BIC_PROFILE="${BIC_PROFILE:-aws}"

# ----------------------------------------------------------------------------
# aws profile constants — cloud Mind + real AWS S3 (a1-site 口径). Public-internet
# direct: no /32 route, no minio forwarder, no orin leg. Every value is
# ${VAR:-default} so a site can override any of them via env / .bic-env.
# ----------------------------------------------------------------------------
AWS_MIND_HOST="${AWS_MIND_HOST:-52.83.119.132}"
AWS_MIND_PORT="${AWS_MIND_PORT:-8010}"
# BE/lab .env form (with scheme):
AWS_S3_ENDPOINT_URL="${AWS_S3_ENDPOINT_URL:-https://s3.cn-northwest-1.amazonaws.com.cn}"
# mock form (host:port, no scheme; pair with S3_SECURE=true):
AWS_S3_ENDPOINT_HOST="${AWS_S3_ENDPOINT_HOST:-s3.cn-northwest-1.amazonaws.com.cn}"
AWS_S3_REGION="${AWS_S3_REGION:-cn-northwest-1}"
AWS_S3_BUCKET="${AWS_S3_BUCKET:-aichemengine-release-bundles}"
# Dedicated S3 credentials file (holds S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY).
# Kept OUT of the repo; its contents are never echoed. Missing/empty => a red
# card (fail-loud), never a silent skip.
AWS_S3_CREDS_FILE="${AWS_S3_CREDS_FILE:-${HOME}/.config/bic-v2/s3-bic.env}"

# ----------------------------------------------------------------------------
# Mind / orin-tail real-service path (2026-07-13, see scripts/bic-env/mind.sh)
# Real Mind lives on the LAB network; off-lab benches reach it through the
# orin-tail tailscale node (c12-workstation), which advertises 192.168.12.0/24.
# ----------------------------------------------------------------------------
MIND_LAB_IP="${MIND_LAB_IP:-192.168.12.104}"   # real Mind box (lab LAN)
MIND_PORT="${MIND_PORT:-8002}"
ORIN_TS_IP="${ORIN_TS_IP:-100.114.189.44}"     # orin-tail tailnet address
ORIN_LAB_IP="${ORIN_LAB_IP:-192.168.12.150}"   # orin on the lab LAN = presign host
MINIO_FWD_PAT='minio[-_]forward'               # pgrep pattern for the :9000 forwarder

# be_mind_mock -> intent from BE .env MIND_MOCK_MODE: "true" | "false" | "unset"
be_mind_mock() {
  local f v
  f="$(repo_dir BIC-agent-service)/.env"
  [ -f "${f}" ] || { echo unset; return; }
  v="$(sed -n 's/^MIND_MOCK_MODE=//p' "${f}" | head -1 | sed 's/#.*//' | tr -d '[:space:]')"
  case "${v}" in
    true|True|TRUE|1)    echo true ;;
    false|False|FALSE|0) echo false ;;
    *)                   echo unset ;;
  esac
}

# tcp_open <host> <port> [timeout_s]
tcp_open() { nc -z -G "${3:-2}" "$1" "$2" >/dev/null 2>&1; }

# minio_fwd_pid -> pid of a running minio forwarder ("" if none)
minio_fwd_pid() { pgrep -f "${MINIO_FWD_PAT}" 2>/dev/null | head -1 || true; }

# mind_route_ok — host route for the Mind box goes via a tailscale utun
# (needed off-lab: the local LAN is also 192.168.12.x, so without the /32 the
# connected /24 wins and .104 resolves to a dead local ARP).
mind_route_ok() {
  route -n get "${MIND_LAB_IP}" 2>/dev/null | grep -q 'interface: utun'
}

# orin_lab_ip_is_local — this box already answers for ORIN_LAB_IP (presign host)
orin_lab_ip_is_local() { ifconfig 2>/dev/null | grep -q "inet ${ORIN_LAB_IP} "; }

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
# NB: on connection failure curl still prints its -w output ('000') before
# exiting non-zero, so a plain `|| echo 000` would double-print ('000000').
http_code() {
  local c
  c="$(curl -s --noproxy '*' --max-time "${2:-5}" -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || true)"
  printf '%s\n' "${c:-000}"
}
http_body() {
  curl -s --noproxy '*' --max-time "${2:-5}" "$1" 2>/dev/null || true
}
http_code_ct() { # -> "<code> <content-type>"
  local c
  c="$(curl -s --noproxy '*' --max-time "${2:-5}" -o /dev/null -w '%{http_code} %{content_type}' "$1" 2>/dev/null || true)"
  printf '%s\n' "${c:-000 -}"
}

# The proxy prefix BE must launch with (unset so it can reach localhost/lab/MQ).
PROXY_VARS="all_proxy http_proxy https_proxy ALL_PROXY HTTP_PROXY HTTPS_PROXY"
unset_proxy_prefix() { printf 'unset %s && ' "${PROXY_VARS}"; }

# ----------------------------------------------------------------------------
# Port / process inspection
# ----------------------------------------------------------------------------
# port_owner <port> -> "<command> <pid>" for the LISTEN socket, or "" if free.
# lsof exits 1 on a free port; callers run under `set -euo pipefail`, so the
# pipeline must not propagate that (a free port is a valid answer, not an error).
port_owner() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR==2{print $1" "$2; exit}' || true
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
# Stale-.env guard input (#153) — the only Postgres is bic-postgres:5432;
# talos-postgres:5433 is retired. This reads the apps' PG_PORT so doctor can
# red-card a stale .env still pointing at 5433. It is a guard input, NOT a
# "which Postgres" selection knob (that mechanism went away when #153
# collapsed the bench to a single instance).
# ----------------------------------------------------------------------------
# app_pg_port -> host port from the first PG_PORT= found (.env before
# .env.example, agent before lab), default 5432.
app_pg_port() {
  local f p
  for f in "$(repo_dir BIC-agent-service)/.env" "$(repo_dir BIC-lab-service)/.env" \
           "$(repo_dir BIC-agent-service)/.env.example" "$(repo_dir BIC-lab-service)/.env.example"; do
    [ -f "${f}" ] || continue
    p="$(sed -n 's/^PG_PORT=//p' "${f}" | head -1)"
    if [ -n "${p}" ]; then printf '%s\n' "${p}"; return 0; fi
  done
  echo 5432
}

# ----------------------------------------------------------------------------
# Registries (encode the whole topology). Lines are "|"-separated records.
# ----------------------------------------------------------------------------
# Infra containers we manage:  name|primary_port|label
infra_containers() {
  cat <<'REC'
bic-postgres|5432|Postgres (single instance — apps use this; #153)
bic-redis|6379|Redis
bic-rabbitmq|5672|RabbitMQ (AMQP 5672 / mgmt 15672)
bic-minio|9000|MinIO (S3 9000 / console 9001)
REC
}

# Authoritative port table:  port|kind|expect|label
#   kind=docker -> LISTEN owner must be docker; kind=app -> our host process.
port_table() {
  cat <<'REC'
5432|docker|bic-postgres|Postgres (single instance, apps use this)
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
# bic-agent-service confidential client that up.sh seeds (service account for
# agent-service -> lab-service machine tokens). Dev-default secret matches the
# ${BIC_AGENT_SERVICE_CLIENT_SECRET:...} fallback in BIC-infra
# keycloak/realm-bic.json; production overrides via env.
KC_SERVICE_CLIENT="${KC_SERVICE_CLIENT:-bic-agent-service}"
# shellcheck disable=SC2034  # consumed by up.sh
KC_SERVICE_CLIENT_SECRET="${BIC_AGENT_SERVICE_CLIENT_SECRET:-bic-agent-service-dev-secret}"

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
