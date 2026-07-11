#!/usr/bin/env bash
#
# BIC V2 field deployment orchestrator (orin-tail, 192.168.12.150).
#
# One-command field flow after the package is transferred:
#     ./deploy.sh login      # docker login ghcr.io from the local PAT file
#     ./deploy.sh up          # preflight -> init-data -> sequential health-gated up
#
# Subcommands: login | pull | preflight | init-env | init-data | up | down | status | logs
#
# Design rules:
#   * Never prints a secret. The GHCR token and .env values are read, never echoed.
#   * Exclusive V2 ports are checked free before `up` (aborts on any occupant).
#   * Shared infra (postgres/redis/minio/rabbitmq) is only checked ALIVE, never
#     taken over.
#   * init-data is idempotent (CREATE DATABASE IF NOT EXISTS equivalent; mc mb
#     --ignore-existing).
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BIC_V2_ENV:-$HERE/.env}"

# Up order (down is the reverse). keycloak first (auth), portal last (nothing
# depends on it).
SERVICES=(keycloak chem-service lab-service agent-service portal)

# ---------------------------------------------------------------------------
# output helpers
# ---------------------------------------------------------------------------
c_red=$'\033[31m'; c_grn=$'\033[32m'; c_yel=$'\033[33m'; c_dim=$'\033[2m'; c_off=$'\033[0m'
ok()   { printf '%s  ✓%s %s\n' "$c_grn" "$c_off" "$*"; }
warn() { printf '%s  ! %s%s\n' "$c_yel" "$*" "$c_off"; }
err()  { printf '%s  ✗ %s%s\n' "$c_red" "$*" "$c_off" >&2; }
info() { printf '%s· %s%s\n' "$c_dim" "$*" "$c_off"; }
die()  { err "$*"; exit 1; }

# ---------------------------------------------------------------------------
# config load
# ---------------------------------------------------------------------------
load_env() {
  if [ -f "$ENV_FILE" ]; then
    # Parse KEY=VALUE literally (NOT `source`): the same file feeds
    # `docker compose --env-file`, so values are unquoted and may contain spaces,
    # `=`, or shell metacharacters (passwords). read splits on the FIRST `=` only.
    local k v
    while IFS='=' read -r k v; do
      [[ "$k" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
      export "$k=$v"
    done < <(grep -vE '^[[:space:]]*(#|$)' "$ENV_FILE")
  else
    warn "no $ENV_FILE yet — using built-in field defaults (run: ./deploy.sh init-env)"
  fi
  # Port + container defaults (mirrors the compose defaults; overridable in .env).
  LAB_PORT="${LAB_PORT:-8192}"
  BE_PORT="${BE_PORT:-8800}"
  PORTAL_PORT="${PORTAL_PORT:-15173}"
  CHEM_PORT="${CHEM_PORT:-8010}"
  KEYCLOAK_PORT="${KEYCLOAK_PORT:-18080}"
  INFRA_NET="${INFRA_NET:-infra-net}"
  PG_CONTAINER="${PG_CONTAINER:-bic-postgres}"
  REDIS_CONTAINER="${REDIS_CONTAINER:-bic-redis}"
  MINIO_CONTAINER="${MINIO_CONTAINER:-bic-minio}"
  MQ_CONTAINER="${MQ_CONTAINER:-bic-rabbitmq}"
  POSTGRES_USER="${POSTGRES_USER:-postgres}"
  MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
  # V2 databases / buckets (init-data ensures these).
  BE_PG_DATABASE="${BE_PG_DATABASE:-talos_agent_db}"
  LAB_PG_DATABASE="${LAB_PG_DATABASE:-labrun_v2_db}"
  KEYCLOAK_DB="${KEYCLOAK_DB:-keycloak_db}"
  BE_S3_BUCKET="${BE_S3_BUCKET:-tlc-images}"
  LAB_S3_BUCKET="${LAB_S3_BUCKET:-labrun}"
  CHEM_S3_BUCKET="${CHEM_S3_BUCKET:-labassistant}"
  GHCR_USER="${GHCR_USER:-Valen-C12}"
  GHCR_TOKEN_FILE="${GHCR_TOKEN_FILE:-$HOME/.config/bic-v2/ghcr.token}"
  # Expand a leading ~ (the literal .env parser does not do tilde expansion).
  GHCR_TOKEN_FILE="${GHCR_TOKEN_FILE/#\~/$HOME}"
  CURL=(curl -fsS --noproxy '*' --max-time 5)
}

# host-facing health endpoint per service
health_url() {
  case "$1" in
    keycloak)      echo "http://localhost:${KEYCLOAK_PORT}/realms/bic/.well-known/openid-configuration" ;;
    chem-service)  echo "http://localhost:${CHEM_PORT}/health" ;;
    lab-service)   echo "http://localhost:${LAB_PORT}/health" ;;
    agent-service) echo "http://localhost:${BE_PORT}/health" ;;
    portal)        echo "http://localhost:${PORTAL_PORT}/" ;;
  esac
}
exclusive_ports() { echo "$LAB_PORT $BE_PORT $PORTAL_PORT $CHEM_PORT $KEYCLOAK_PORT"; }
# First-boot health-gate budget per service (seconds). Keycloak imports the realm
# + migrates its DB on first boot (~60–90s); BE/lab run alembic upgrade.
health_timeout() {
  case "$1" in
    keycloak)      echo 180 ;;
    agent-service) echo 120 ;;
    lab-service)   echo 120 ;;
    *)             echo 60 ;;
  esac
}
# Shared infra host ports (must already be alive). Overridable via SHARED_PORTS so
# an isolated rehearsal can point at throwaway infra on offset ports.
shared_ports()    { echo "${SHARED_PORTS:-5432 6379 9000 5672}"; }

compose() { docker compose -f "$HERE/$1/docker-compose.yml" --env-file "$ENV_FILE" "${@:2}"; }

# ---------------------------------------------------------------------------
# portable port probing (works on the field's Linux and on a dev macOS box)
# ---------------------------------------------------------------------------
port_in_use() {
  local p="$1"
  # ss first: kernel netlink sees root-owned listeners (docker-proxy) without
  # privileges; unprivileged lsof silently misses other users' sockets and
  # false-negatives every shared-infra port on the field box.
  if command -v ss >/dev/null 2>&1; then
    ss -ltnH "( sport = :$p )" 2>/dev/null | grep -q .
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null && { exec 3>&- 3<&-; return 0; } || return 1
  fi
}
port_occupant() {
  local p="$1"
  # same ss-first ordering as port_in_use (unprivileged lsof can't name
  # root-owned occupants; ss at least reports the pid when visible)
  if command -v ss >/dev/null 2>&1; then
    ss -ltnpH "( sport = :$p )" 2>/dev/null | grep -oE 'users:\(\("[^"]+",pid=[0-9]+' | sed -E 's/users:\(\(//; s/pid=/pid /' | tr '\n' ' '
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$p" -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print $1"(pid "$2")"}' | sort -u | tr '\n' ' '
  fi
}

# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------
require_token_file() {
  local tf="$GHCR_TOKEN_FILE"
  if [ ! -s "$tf" ]; then
    err "GHCR token file missing or empty: $tf"
    cat >&2 <<EOF

  Create a classic Personal Access Token with ONLY the read:packages scope:
      https://github.com/settings/tokens/new?scopes=read:packages&description=bic-v2-orin
  then place it (600 perms), value only, no newline fuss:
      install -m 600 /dev/stdin "$tf"   # paste token, Ctrl-D
  (This must be created by hand by the token owner; it never lives in git.)
EOF
    return 1
  fi
}

cmd_login() {
  require_token_file
  info "docker login ghcr.io as ${GHCR_USER} (token from $GHCR_TOKEN_FILE, not echoed)"
  docker login ghcr.io -u "$GHCR_USER" --password-stdin < "$GHCR_TOKEN_FILE"
  ok "logged in to ghcr.io"
}

cmd_pull() {
  local svcs=("${@:-${SERVICES[@]}}")
  for s in "${svcs[@]}"; do info "pull $s"; compose "$s" pull; done
  ok "images pulled"
}

cmd_preflight() {
  local fail=0
  info "token file check"
  if [ -s "$GHCR_TOKEN_FILE" ]; then ok "GHCR token present ($GHCR_TOKEN_FILE)"; else
    err "GHCR token missing/empty ($GHCR_TOKEN_FILE) — run: ./deploy.sh login"; fail=1
  fi
  info "exclusive V2 ports free ( $(exclusive_ports) )"
  for p in $(exclusive_ports); do
    if port_in_use "$p"; then
      err "port $p OCCUPIED by: $(port_occupant "$p")— stop the occupant (e.g. retire V1) before up"; fail=1
    else ok "port $p free"; fi
  done
  info "shared infra ports alive ( $(shared_ports) )"
  for p in $(shared_ports); do
    if port_in_use "$p"; then ok "shared port $p alive"; else
      err "shared infra port $p has no listener — bring up shared infra first"; fail=1
    fi
  done
  [ "$fail" -eq 0 ] || die "preflight FAILED — aborting"
  ok "preflight PASSED"
}

cmd_init_data() {
  info "postgres databases (idempotent CREATE)"
  for db in "$BE_PG_DATABASE" "$LAB_PG_DATABASE" "$KEYCLOAK_DB"; do
    if docker exec "$PG_CONTAINER" psql -U "$POSTGRES_USER" -tAc \
         "SELECT 1 FROM pg_database WHERE datname='$db'" 2>/dev/null | grep -q 1; then
      ok "database $db present"
    else
      docker exec "$PG_CONTAINER" psql -U "$POSTGRES_USER" -c "CREATE DATABASE \"$db\"" >/dev/null
      ok "database $db created"
    fi
  done
  info "minio buckets (idempotent mc mb --ignore-existing)"
  # minio/mc's entrypoint is `mc`, so override it to run a shell loop.
  docker run --rm --entrypoint sh --network "$INFRA_NET" \
    -e MC_HOST_fld="http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@${MINIO_CONTAINER}:9000" \
    minio/mc -c 'for b in '"$BE_S3_BUCKET $LAB_S3_BUCKET $CHEM_S3_BUCKET"'; do mc mb --ignore-existing "fld/$b" >/dev/null && echo "  ✓ bucket $b"; done' \
    || warn "minio bucket ensure skipped/failed (check MINIO_ROOT_PASSWORD / $MINIO_CONTAINER on $INFRA_NET)"
  info "redis index assignments (indices always exist; recorded for the ledger): BE=${BE_REDIS_DB:-3} lab=${LAB_REDIS_DB:-4}"
  ok "init-data done"
}

wait_health() {
  local svc="$1" url tries=0 max="${2:-60}"
  url="$(health_url "$svc")"
  info "health-gate $svc ($url)"
  until "${CURL[@]}" "$url" >/dev/null 2>&1; do
    tries=$((tries+1))
    [ "$tries" -ge "$max" ] && { err "$svc not healthy after ${max}s"; return 1; }
    sleep 1
  done
  ok "$svc healthy"
}

cmd_up() {
  if [ "$#" -gt 0 ]; then           # single service
    compose "$1" up -d
    wait_health "$1" "$(health_timeout "$1")" || die "$1 failed health gate"
    return
  fi
  cmd_preflight
  cmd_init_data
  for s in "${SERVICES[@]}"; do
    info "up $s"
    compose "$s" up -d
    wait_health "$s" "$(health_timeout "$s")" || die "$s failed health gate — stopping rollout (fix, then re-run)"
  done
  ok "all ${#SERVICES[@]} services up and healthy"
  cmd_status
}

cmd_down() {
  if [ "$#" -gt 0 ]; then compose "$1" down; return; fi
  for ((i=${#SERVICES[@]}-1; i>=0; i--)); do
    info "down ${SERVICES[$i]}"; compose "${SERVICES[$i]}" down || true
  done
  ok "V2 stack down (shared infra untouched)"
}

cmd_status() {
  printf '%-16s %-24s %s\n' SERVICE CONTAINER HEALTH
  for s in "${SERVICES[@]}"; do
    local cid state="down" hc
    cid="$(compose "$s" ps -q 2>/dev/null | head -1)"
    if [ -n "$cid" ]; then
      state="$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || echo '?')"
    fi
    if "${CURL[@]}" "$(health_url "$s")" >/dev/null 2>&1; then hc="${c_grn}healthy${c_off}"; else hc="${c_yel}--${c_off}"; fi
    printf '%-16s %-24s %b\n' "$s" "${cid:0:12}[$state]" "$hc"
  done
}

cmd_logs() { compose "${1:?usage: logs <service>}" logs -f --tail=100; }

# init-env: derive shared infra creds from the field's V1 env, generate V2-new
# secrets, write $ENV_FILE (600). Never echoes a value.
cmd_init_env() {
  local src="${V1_ENV_FILE:-$HOME/bic/.env}"
  local tmpl="$HERE/.env.example"
  [ -f "$tmpl" ] || die "missing template $tmpl"
  [ -e "$ENV_FILE" ] && die "$ENV_FILE already exists — refusing to overwrite (edit it directly or remove first)"
  umask 077
  cp "$tmpl" "$ENV_FILE"
  local missing=0
  # shared infra creds: copy by key name from the V1 env if present
  if [ -f "$src" ]; then
    info "deriving shared infra creds from $src"
    for key in POSTGRES_USER POSTGRES_PASSWORD REDIS_PASSWORD MINIO_ROOT_USER MINIO_ROOT_PASSWORD MQ_USER MQ_PASSWORD; do
      local val
      val="$(grep -E "^(export )?${key}=" "$src" 2>/dev/null | tail -1 | sed -E "s/^(export )?${key}=//; s/^\"//; s/\"$//; s/^'//; s/'$//")"
      if [ -n "$val" ]; then
        set_env_key "$key" "$val"; ok "$key ← $src"
      else
        warn "$key not found in $src — left as placeholder"; missing=$((missing+1))
      fi
    done
  else
    warn "no $src — all shared creds left as placeholders (set V1_ENV_FILE=... or edit $ENV_FILE)"
    missing=$((missing+1))
  fi
  # V2-new secret: keycloak admin password (generated, on-site only)
  if command -v openssl >/dev/null 2>&1; then
    set_env_key KEYCLOAK_ADMIN_PASSWORD "$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"
    ok "KEYCLOAK_ADMIN_PASSWORD generated on-site"
  else
    warn "openssl absent — set KEYCLOAK_ADMIN_PASSWORD by hand"; missing=$((missing+1))
  fi
  chmod 600 "$ENV_FILE"
  ok "wrote $ENV_FILE (600)"
  if [ "$missing" -gt 0 ]; then
    warn "$missing value(s) still need manual attention — review $ENV_FILE for __FILL_ME__ and field-only keys (BE_LLM_*, MIND_HOST)"
  fi
  info "review $ENV_FILE, then: ./deploy.sh login && ./deploy.sh up"
}

# set_env_key KEY VALUE — in-place replace in $ENV_FILE without echoing VALUE
set_env_key() {
  local key="$1" val="$2" tmp
  tmp="$(mktemp)"
  KEY="$key" VAL="$val" awk '
    BEGIN{k=ENVIRON["KEY"]; v=ENVIRON["VAL"]; done=0}
    $0 ~ "^"k"=" { print k"="v; done=1; next }
    { print }
    END{ if(!done) print k"="v }
  ' "$ENV_FILE" > "$tmp"
  mv "$tmp" "$ENV_FILE"
}

usage() {
  cat <<EOF
BIC V2 field deploy — usage: ./deploy.sh <command> [service]

  init-env      derive .env from ~/bic/.env + generate V2 secrets (run once)
  login         docker login ghcr.io from \$GHCR_TOKEN_FILE ($GHCR_TOKEN_FILE)
  preflight     check exclusive ports free + shared infra alive + token present
  init-data     idempotent: create V2 dbs + minio buckets
  pull [svc]    docker compose pull (all services or one)
  up [svc]      preflight -> init-data -> sequential health-gated up (or one svc)
  down [svc]    stop V2 stack (reverse order) — shared infra untouched
  status        per-service container state + health
  logs <svc>    follow a service's logs
EOF
}

main() {
  local cmd="${1:-}"; shift || true
  load_env
  case "$cmd" in
    init-env)  cmd_init_env "$@" ;;
    login)     cmd_login "$@" ;;
    preflight) cmd_preflight "$@" ;;
    init-data) cmd_init_data "$@" ;;
    pull)      cmd_pull "$@" ;;
    up)        cmd_up "$@" ;;
    down)      cmd_down "$@" ;;
    status)    cmd_status "$@" ;;
    logs)      cmd_logs "$@" ;;
    ""|-h|--help|help) usage ;;
    *) err "unknown command: $cmd"; usage; exit 2 ;;
  esac
}

# Only run when executed directly — sourcing (e.g. the pre-flight self-test)
# loads the functions without running a command.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi
