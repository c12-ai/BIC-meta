#!/usr/bin/env bash
# doctor.sh — READ-ONLY full checkup of the BIC bench.
#
# Never mutates anything (safe to run against a live, in-use bench). Every red
# card prints the exact command to fix it. Verdict = GREEN when 0 red cards.
#
# Encodes tonight's real traps:
#   - anything still listening on retired 5433 (post-#153 apps must use 5432)
#   - proxy vars poisoning localhost calls
#   - portal "200 but white screen" (checks /src/main.tsx returns JS, not just /)
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

printf '%s%sBIC doctor%s  (read-only)\n' "${C_BLD}" "${C_BLU}" "${C_RST}"
print_context

# --- 1. Tooling ------------------------------------------------------------
section "Toolchain"
for t in docker node pnpm uv curl lsof jq tmux; do
  if command -v "$t" >/dev/null 2>&1; then
    ok "$t ${C_DIM}$( "$t" --version 2>/dev/null | head -1 )${C_RST}"
  else
    case "$t" in
      jq)   fail "$t missing" "brew install jq" ;;
      node|pnpm) fail "$t missing" "brew install node && npm i -g pnpm  (or use nvm)" ;;
      uv)   fail "$t missing" "curl -LsSf https://astral.sh/uv/install.sh | sh" ;;
      *)    fail "$t missing" "install $t" ;;
    esac
  fi
done

# --- 2. Docker daemon ------------------------------------------------------
section "Docker daemon"
if docker_up; then
  ok "docker daemon reachable"
else
  fail "docker daemon not running" "open -a Docker  # then wait ~20s and re-run make doctor"
fi

# --- 3. Proxy poisoning ----------------------------------------------------
section "Proxy environment"
_poison=0
for v in all_proxy http_proxy https_proxy; do
  val="${!v:-}"          # indirect expansion (bash 3.2+): value of $all_proxy etc.
  case "${val}" in
    *127.0.0.1:7890*|*localhost:7890*) _poison=1 ;;
  esac
done
if [ "${_poison}" = "1" ]; then
  ok "proxy vars point at 127.0.0.1:7890 — handled (BE starts with 'unset ${PROXY_VARS%% *} ...'; health uses --noproxy)"
else
  ok "no localhost-poisoning proxy vars set"
fi

# --- 4. Infra containers ---------------------------------------------------
# Here-doc loop (not a pipe) so ok/fail run in THIS shell and counters update.
section "Infra containers (docker)"
if docker_up; then
  while IFS='|' read -r name port label; do
    [ -n "${name}" ] || continue
    if container_running "${name}"; then
      ok "${name} up  ${C_DIM}(${label}, :${port})${C_RST}"
    elif container_exists "${name}"; then
      fail "${name} exists but stopped (${label})" "docker start ${name}"
    else
      fail "${name} missing (${label})" "cd ${INFRA_DIR} && make up   # or: make up  (auto-creates it)"
    fi
  done <<EOF
$(infra_containers)
EOF
else
  fail "docker daemon down — cannot check containers" "open -a Docker"
fi

# --- 5. Per-port lsof vs authoritative table -------------------------------
section "Ports vs authoritative table (ops/port-allocation-2026-07-10.md)"
while IFS='|' read -r port kind expect label; do
  [ -n "${port}" ] || continue
  owner="$(port_owner "${port}")"
  cmd="$(printf '%s' "${owner}" | awk '{print $1}')"
  pid="$(printf '%s' "${owner}" | awk '{print $2}')"
  if [ -z "${owner}" ]; then
    case "${kind}:${expect}" in
      app:mind) note "${port} free — ${label} (only in full-real profile)" ;;
      *)        note "${port} free — ${label} (start with: make up)" ;;
    esac
    continue
  fi
  case "${kind}" in
    docker)
      case "${cmd}" in
        com.docke*|docker*) ok "${port} docker — ${label}" ;;
        ssh)  fail "${port} held by ssh TUNNEL (pid ${pid}), shadowing ${expect} — ${label}" \
                   "kill ${pid}   # then: docker start ${expect}" ;;
        *)    fail "${port} held by FOREIGN '${cmd}' (pid ${pid}), expected docker ${expect} — ${label}" \
                   "lsof -nP -iTCP:${port} -sTCP:LISTEN   # inspect owner; do NOT kill others' processes" ;;
      esac
      ;;
    app)
      if is_our_process "${pid}"; then
        ok "${port} ours '${cmd}' (pid ${pid}) — ${label}"
      else
        fail "${port} held by FOREIGN '${cmd}' (pid ${pid}) — expected our ${label}" \
             "lsof -nP -iTCP:${port} -sTCP:LISTEN   # our services would collide; relocate the other or free it"
      fi
      ;;
    ext)
      # External/optional dependency (e.g. Mind capture proxy) — any listener is fine.
      ok "${port} present '${cmd}' (pid ${pid}) — ${label}"
      ;;
  esac
done <<EOF
$(port_table)
EOF

# --- 6. Postgres single instance (#153) — 5433 retired, DBs on 5432 --------
section "Postgres (:5432 single instance; 5433 retired)"
# Stale-.env guard: after #153 the apps must point at bic-postgres:5432. A
# leftover PG_PORT=5433 in a repo .env would send an app at the retired
# instance — catch it here before it silently hits pre-#153 data.
pgport="$(app_pg_port)"
if [ "${pgport}" = "5432" ]; then
  ok "apps' PG_PORT is 5432 (no stale .env pointing at retired 5433)"
else
  fail "apps' PG_PORT=${pgport} is retired (#153) — must be 5432" \
       "set PG_PORT=5432 in BIC-agent-service/.env and BIC-lab-service/.env"
fi
# 5433 must have NO listener: a survivor talos-postgres or an ssh tunnel means
# an app with a stale .env could silently hit pre-#153 data. (port_owner now
# tolerates a free port at the source, so no `|| true` needed here.)
owner5433="$(port_owner 5433)"
if [ -n "${owner5433}" ]; then
  pid5433="$(printf '%s' "${owner5433}" | awk '{print $2}')"
  fail "5433 has a listener (${owner5433}) — retired port, apps must use 5432" \
       "docker stop talos-postgres 2>/dev/null || kill ${pid5433}   # ssh tunnel case"
else
  ok "5433 has no listener (retired)"
fi
if container_running bic-postgres; then
  dbs="$(docker exec bic-postgres psql -U postgres -tAc \
        "SELECT datname FROM pg_database WHERE datname IN ('talos_agent_db','labrun_db');" 2>/dev/null || true)"
  for db in talos_agent_db labrun_db; do
    if printf '%s\n' "${dbs}" | grep -qx "${db}"; then
      ok "database ${db} exists on bic-postgres:5432"
    else
      fail "database ${db} MISSING on bic-postgres:5432" \
           "docker exec bic-postgres psql -U postgres -c 'CREATE DATABASE ${db};'"
    fi
  done
  # Guard against the wrong-instance swap trap: agent schema must actually live here.
  if docker exec bic-postgres psql -U postgres -d talos_agent_db -tAc \
       "SELECT 1 FROM information_schema.tables WHERE table_name='sessions'" 2>/dev/null | grep -q 1; then
    ok "talos_agent_db on 5432 carries the agent schema (sessions table)"
  else
    fail "talos_agent_db on 5432 has NO agent schema — empty shell, apps may point at the wrong instance" \
         "restore from ~/Work/BIC/db-backups-20260710 or run alembic upgrade head in BIC-agent-service"
  fi
else
  fail "bic-postgres container not running" "docker start bic-postgres"
fi

# --- 7. Keycloak -----------------------------------------------------------
section "Keycloak (:18080)"
kc="$(container_on_port 18080)"
if [ -n "${kc}" ]; then
  ok "container ${kc} publishes 18080"
else
  warn "no container publishes 18080 (issuer check below is the source of truth)"
fi
issuer="$(http_body "http://localhost:18080/realms/${KC_REALM}/.well-known/openid-configuration" | jq -r .issuer 2>/dev/null || true)"
if [ "${issuer}" = "http://localhost:18080/realms/${KC_REALM}" ]; then
  ok "realm ${KC_REALM} live, issuer=${issuer}"
else
  fail "keycloak realm ${KC_REALM} not answering (issuer='${issuer:-none}')" \
       "make up   # seeds keycloak; or see ops/run-latest-2026-07-10.md §5"
fi

# --- 8. Service health -----------------------------------------------------
section "Service health"
while IFS='|' read -r name port _ url; do
  [ -n "${name}" ] || continue
  case "${name}" in
    mock)
      if pgrep -f 'mars-interface-mock' >/dev/null 2>&1; then
        ok "mock alive (MQ consumer, no HTTP port)"
      else
        fail "mock not running (MQ consumer)" "make restart-mock"
      fi
      ;;
    portal)
      read -r code ct <<EOF2
$(http_code_ct "${url}")
EOF2
      case "${code} ${ct}" in
        "200 "*javascript*) ok "portal :5173 serves JS (real load, not a white screen)" ;;
        200*) fail "portal :5173 up but /src/main.tsx not JS (white-screen risk — deps not installed?)" \
                   "cd $(repo_dir BIC-agent-portal) && pnpm install && pnpm dev" ;;
        *)    fail "portal :5173 down (code ${code})" "make restart-portal" ;;
      esac
      ;;
    keycloak)
      : # already checked above
      ;;
    chem)
      code="$(http_code "${url}")"
      if [ "${code}" = "200" ]; then
        ok "chem :8010 healthy"
      else
        warn "chem :8010 down (code ${code}) — optional; ELN naming lazy-skips (make restart-chem to start)"
      fi
      ;;
    *)
      code="$(http_code "${url}")"
      if [ "${code}" = "200" ]; then
        ok "${name} :${port} healthy"
      else
        fail "${name} :${port} down (code ${code})" "make restart-${name}"
      fi
      ;;
  esac
done <<EOF
$(services)
EOF

# --- 9. Repos present ------------------------------------------------------
section "Repos under BIC_ROOT"
for r in BIC-lab-service BIC-agent-service BIC-agent-portal mars_interface_mock; do
  d="$(repo_dir "$r")"
  if [ -d "${d}/.git" ]; then
    ok "$r @ $(git_branch "${d}") $(git_sha "${d}")"
  else
    fail "$r not found at ${d}" "scripts/bootstrap.sh all   # clones missing repos; or set BIC_ROOT=/path/to/your/checkout"
  fi
done

# --- Verdict ---------------------------------------------------------------
printf '\n%s%s== Verdict ==%s\n' "${C_BLD}" "${C_BLU}" "${C_RST}"
printf '  %s%d ok%s  %s%d warn%s  %s%d red%s\n' \
  "${C_GRN}" "${BIC_OK}" "${C_RST}" \
  "${C_YEL}" "${BIC_WARN}" "${C_RST}" \
  "${C_RED}" "${BIC_FAIL}" "${C_RST}"
if [ "${BIC_FAIL}" -eq 0 ]; then
  printf '  %s%sDOCTOR: GREEN%s — bench is up. Troubleshooting: ops/run-latest-2026-07-10.md\n' \
    "${C_BLD}" "${C_GRN}" "${C_RST}"
  exit 0
else
  printf '  %s%sDOCTOR: %d RED%s — fix the cards above (each has a → fix command).\n' \
    "${C_BLD}" "${C_RED}" "${BIC_FAIL}" "${C_RST}"
  exit 1
fi
