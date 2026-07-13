#!/usr/bin/env bash
# up.sh — idempotent one-shot bring-up with self-heal.
#
# Safe to re-run: anything already healthy is skipped. `make up DRY=1` prints
# every mutating action instead of running it (used to validate the plan without
# touching a live, in-use bench).
#
# Order (from ops/run-latest-2026-07-10.md): docker -> infra -> wait-for-pg ->
# db-create -> keycloak seed -> dep sync -> tmux lab->BE->portal->mock->chem,
# each gated on a REAL health check.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

printf '%s%sBIC up%s   ' "${C_BLD}" "${C_BLU}" "${C_RST}"
print_context
[ "${DRY_RUN}" = "1" ] && note "DRY run — printing planned actions, nothing is executed"

# BIC_ONLY=<svc> (set by restart.sh) scopes this run to one app service:
# skip infra/db/keycloak/dep sections and start only that service.
ONLY="${BIC_ONLY:-}"

# Repo paths (always defined — used by both the dep-sync and app-launch phases).
lab="$(repo_dir BIC-lab-service)"
be="$(repo_dir BIC-agent-service)"
portal="$(repo_dir BIC-agent-portal)"

# ---------------------------------------------------------------------------
# wait helpers — poll a readiness condition (NOT a blind sleep). In DRY mode
# nothing was started, so they just announce and return.
# ---------------------------------------------------------------------------
wait_http() { # <url> <timeout_s>
  local url="$1" t="${2:-60}" i=0
  if [ "${DRY_RUN}" = "1" ]; then note "[dry] would wait (<=${t}s) for ${url} == 200"; return 0; fi
  while [ "${i}" -lt "${t}" ]; do
    [ "$(http_code "${url}")" = "200" ] && return 0
    i=$((i + 1)); sleep 1
  done
  return 1
}
wait_pg() { # <timeout_s>
  local t="${1:-30}" i=0
  if [ "${DRY_RUN}" = "1" ]; then note "[dry] would wait (<=${t}s) for bic-postgres pg_isready"; return 0; fi
  while [ "${i}" -lt "${t}" ]; do
    docker exec bic-postgres pg_isready -U postgres >/dev/null 2>&1 && return 0
    i=$((i + 1)); sleep 1
  done
  return 1
}

# === Full-bring-up sections (skipped when scoped to a single service) ======
if [ -z "${ONLY}" ]; then
# ===========================================================================
section "1. Docker daemon"
if docker_up; then
  ok "docker daemon reachable"
else
  do_run open -a Docker
  if [ "${DRY_RUN}" != "1" ]; then
    i=0; while [ "${i}" -lt 40 ] && ! docker_up; do i=$((i + 1)); sleep 1; done
    if docker_up; then ok "docker daemon came up"; else fail "docker did not start" "open -a Docker manually"; exit 1; fi
  fi
fi

# ===========================================================================
section "2. Infra containers"
missing=""
while IFS='|' read -r name _ _; do
  [ -n "${name}" ] || continue
  if container_running "${name}"; then
    ok "${name} running"
  elif container_exists "${name}"; then
    do_run docker start "${name}"
  else
    missing="${missing} ${name}"
  fi
done <<EOF
$(infra_containers)
EOF
if [ -n "${missing}" ]; then
  if [ -d "${INFRA_DIR}" ]; then
    note "missing containers:${missing} — creating via infra compose"
    do_sh "cd '${INFRA_DIR}' && make up"
  else
    fail "infra containers missing:${missing} and no infra repo at ${INFRA_DIR}" \
         "clone BIC-infra next to the repos, or set INFRA_DIR=/path/to/infra, then: cd \$INFRA_DIR && make up"
  fi
fi

# Keycloak container (name varies; detect by published port).
if [ -n "$(container_on_port 18080)" ]; then
  ok "keycloak container up ($(container_on_port 18080))"
elif container_exists bic-keycloak; then
  do_run docker start bic-keycloak
else
  fail "no keycloak on :18080" \
       "cd ${INFRA_DIR} && make up   # or run the keycloak container per ops/run-latest-2026-07-10.md §5"
fi

# ===========================================================================
section "3. Postgres readiness (bic :5432)"
if wait_pg 30; then
  ok "bic-postgres accepting connections"
else
  fail "bic-postgres not ready after 30s" "docker logs bic-postgres --tail 50"
fi

section "4. Databases"
existing=""
if container_running bic-postgres; then
  # read-only probe — safe to run even under DRY so the plan is truthful
  existing="$(docker exec bic-postgres psql -U postgres -tAc \
    "SELECT datname FROM pg_database WHERE datname IN ('talos_agent_db','labrun_db');" 2>/dev/null || true)"
fi
for db in labrun_db talos_agent_db; do
  if printf '%s\n' "${existing}" | grep -qx "${db}"; then
    ok "database ${db} present"
  else
    do_run docker exec bic-postgres psql -U postgres -c "CREATE DATABASE ${db};"
  fi
done

# ===========================================================================
section "5. Keycloak seed (realm ${KC_REALM}, dev users, portal redirectUris, service client)"
if wait_http "http://localhost:18080/realms/${KC_REALM}/.well-known/openid-configuration" 40; then
  ok "realm ${KC_REALM} live"
  kc="$(container_on_port 18080)"
  kc="${kc:-bic-keycloak}"
  KCADM="/opt/keycloak/bin/kcadm.sh"
  # login
  do_run docker exec "${kc}" "${KCADM}" config credentials \
    --server http://localhost:8080 --realm master \
    --user "${KC_ADMIN_USER}" --password "${KC_ADMIN_PASSWORD}"
  # dev users (create if missing, idempotent)
  for u in ${KC_DEV_USERS}; do
    have=""
    if [ "${DRY_RUN}" != "1" ]; then
      have="$(docker exec "${kc}" "${KCADM}" get users -r "${KC_REALM}" -q username="${u}" --fields username 2>/dev/null | grep -c "\"${u}\"" || true)"
    fi
    if [ "${have:-0}" != "0" ]; then
      ok "user ${u} exists"
    else
      do_run docker exec "${kc}" "${KCADM}" create users -r "${KC_REALM}" \
        -s username="${u}" -s enabled=true
      do_run docker exec "${kc}" "${KCADM}" set-password -r "${KC_REALM}" \
        --username "${u}" --new-password "${KC_DEV_PASSWORD}"
    fi
  done
  # portal redirectUris / webOrigins (ensure both localhost + 127.0.0.1:5173)
  if [ "${DRY_RUN}" != "1" ]; then
    cid="$(docker exec "${kc}" "${KCADM}" get clients -r "${KC_REALM}" -q clientId="${KC_CLIENT}" --fields id --format csv --noquotes 2>/dev/null | tr -d '\r' || true)"
    uris="$(docker exec "${kc}" "${KCADM}" get "clients/${cid}" -r "${KC_REALM}" --fields redirectUris 2>/dev/null || true)"
    if printf '%s' "${uris}" | grep -q 'localhost:5173' && printf '%s' "${uris}" | grep -q '127.0.0.1:5173'; then
      ok "portal redirectUris already include localhost + 127.0.0.1:5173"
    else
      do_run docker exec "${kc}" "${KCADM}" update "clients/${cid}" -r "${KC_REALM}" \
        -s 'redirectUris=["http://localhost:5173/*","http://127.0.0.1:5173/*"]' \
        -s 'webOrigins=["http://localhost:5173","http://127.0.0.1:5173"]'
    fi
  else
    note "[dry] would ensure ${KC_CLIENT} redirectUris include localhost + 127.0.0.1:5173"
  fi
  # BIC login theme (BIC-meta#178): set realm loginTheme=bic idempotently. The
  # realm file sets it on first import; this covers a realm imported before the
  # theme existed. Also ensures zh-CN so Keycloak's built-in Chinese login copy
  # renders (styling lives in the infra themes/bic theme; copy is not hardcoded).
  #
  # A container created BEFORE the compose theme mount has no /opt/keycloak/themes/bic
  # — pointing loginTheme at a missing theme breaks the login page. Inject it via
  # docker cp first (idempotent; dev-mode keycloak serves themes without restart).
  if [ "${DRY_RUN}" != "1" ]; then
    if ! docker exec "${kc}" test -d /opt/keycloak/themes/bic 2>/dev/null; then
      if [ -d "${INFRA_DIR}/themes/bic" ]; then
        do_run docker cp "${INFRA_DIR}/themes/bic" "${kc}":/opt/keycloak/themes/bic
        ok "bic theme injected into ${kc} (container predates compose mount)"
      else
        warn "bic theme missing in ${kc} and no ${INFRA_DIR}/themes/bic — pull BIC-infra (make pull); skipping loginTheme"
      fi
    fi
  else
    note "[dry] would docker-cp ${INFRA_DIR}/themes/bic into the keycloak container if absent"
  fi
  if [ "${DRY_RUN}" != "1" ] && ! docker exec "${kc}" test -d /opt/keycloak/themes/bic 2>/dev/null; then
    : # theme unavailable — loginTheme left untouched (guarded above)
  elif [ "${DRY_RUN}" != "1" ]; then
    theme="$(docker exec "${kc}" "${KCADM}" get "realms/${KC_REALM}" --fields loginTheme --format csv --noquotes 2>/dev/null | tr -d '\r' || true)"
    if [ "${theme}" = "bic" ]; then
      ok "realm ${KC_REALM} loginTheme already bic"
    else
      do_run docker exec "${kc}" "${KCADM}" update "realms/${KC_REALM}" \
        -s loginTheme=bic \
        -s internationalizationEnabled=true \
        -s defaultLocale=zh-CN \
        -s 'supportedLocales=["zh-CN"]'
      ok "realm ${KC_REALM} loginTheme set to bic (zh-CN login copy)"
    fi
  else
    note "[dry] would set realm ${KC_REALM} loginTheme=bic (+ zh-CN i18n) if not already bic"
  fi
  # bic-agent-service confidential client (create if missing, idempotent) —
  # realm import is first-boot-only (IGNORE_EXISTING), so already-imported
  # benches only get the client through this seed step.
  have=""
  if [ "${DRY_RUN}" != "1" ]; then
    have="$(docker exec "${kc}" "${KCADM}" get clients -r "${KC_REALM}" -q clientId="${KC_SERVICE_CLIENT}" --fields clientId 2>/dev/null | grep -c "\"${KC_SERVICE_CLIENT}\"" || true)"
  fi
  if [ "${have:-0}" != "0" ]; then
    ok "client ${KC_SERVICE_CLIENT} exists"
  else
    do_run docker exec "${kc}" "${KCADM}" create clients -r "${KC_REALM}" \
      -s clientId="${KC_SERVICE_CLIENT}" \
      -s name="BIC Agent Service" \
      -s protocol=openid-connect \
      -s enabled=true \
      -s publicClient=false \
      -s serviceAccountsEnabled=true \
      -s standardFlowEnabled=false \
      -s directAccessGrantsEnabled=false \
      -s clientAuthenticatorType=client-secret \
      -s secret="${KC_SERVICE_CLIENT_SECRET}"
  fi
else
  fail "keycloak realm ${KC_REALM} not live — cannot seed" "docker logs $(container_on_port 18080) --tail 50"
fi

# ===========================================================================
section "6. Dependency self-heal"
# Seed .env from .env.example on fresh clones — without it BE boots on wrong
# code defaults (template_db, empty Keycloak issuer). Never touches an existing .env.
for _repo in "${be}" "${lab}" "${portal}"; do
  if [ -d "${_repo}" ] && [ ! -f "${_repo}/.env" ] && [ -f "${_repo}/.env.example" ]; then
    do_sh "cp '${_repo}/.env.example' '${_repo}/.env'"
    ok "$(basename "${_repo}"): seeded .env from .env.example (review before real-Mind use)"
  fi
done

# Auth env self-heal (lab JWT enforcement wave): these keys are REQUIRED for a
# working bench. Append-only — an existing value is never overwritten, so LAN
# benches with a non-localhost issuer keep their override.
ensure_env_key() { # <env-file> <key> <value> <label>
  _f="$1"; _k="$2"; _v="$3"; _label="$4"
  [ -f "${_f}" ] || return 0
  if grep -q "^${_k}=" "${_f}"; then
    ok "${_label}: ${_k} present"
  else
    # heal a missing trailing newline first (append would glue onto the last line)
    [ -n "$(tail -c1 "${_f}")" ] && do_sh "printf '\n' >> '${_f}'"
    do_sh "printf '%s=%s\n' '${_k}' '${_v}' >> '${_f}'"
    ok "${_label}: ${_k} appended (dev default — override for non-standard benches)"
  fi
}
ensure_env_key "${be}/.env"  KEYCLOAK_CLIENT_ID     "${KC_SERVICE_CLIENT}"        "BE"
ensure_env_key "${be}/.env"  KEYCLOAK_CLIENT_SECRET "${KC_SERVICE_CLIENT_SECRET}" "BE"
ensure_env_key "${lab}/.env" KEYCLOAK_ISSUER_URL    "http://localhost:18080/realms/${KC_REALM}" "lab"
if [ -d "${portal}" ]; then
  if [ ! -d "${portal}/node_modules" ] || [ "${portal}/pnpm-lock.yaml" -nt "${portal}/node_modules" ]; then
    do_sh "cd '${portal}' && pnpm install"
  else
    ok "portal node_modules up to date"
  fi
fi
[ -d "${lab}" ] && do_sh "cd '${lab}' && uv sync --group mock"
[ -d "${be}" ] && do_sh "cd '${be}' && uv sync"

section "7. Migrations (alembic upgrade head)"
# Migrations mutate the SHARED database — only run them from a main checkout.
# (2026-07-10 incident: a wrong BIC_ROOT pointed at a stale feature-branch
# checkout and alembic ran against the live DB; it happened to fail safe.)
# Override consciously with BIC_ALLOW_BRANCH_MIGRATIONS=1.
migrate_repo() { # <dir> <label>
  local d="$1" label="$2" branch
  [ -d "${d}" ] || return 0
  branch="$(git -C "${d}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  if [ "${branch}" != "main" ] && [ "${BIC_ALLOW_BRANCH_MIGRATIONS:-0}" != "1" ]; then
    fail "${label}: refusing migrations from branch '${branch}' (not main)" \
         "cd ${d} && git checkout main   # or BIC_ALLOW_BRANCH_MIGRATIONS=1 if intentional"
    return 0
  fi
  do_sh "cd '${d}' && uv run alembic upgrade head"
}
migrate_repo "${lab}" BIC-lab-service
migrate_repo "${be}" BIC-agent-service

fi  # end full-bring-up sections (ONLY guard)

# ===========================================================================
section "8. App services (tmux ${BIC_TMUX}: lab -> BE -> portal -> mock -> chem)"

# start command for a service (BE carries the unset-proxy prefix).
start_cmd_for() {
  case "$1" in
    lab)    printf 'cd %q && make dev' "${lab}" ;;
    BE)     printf 'cd %q && %suv run uvicorn app.main:app --host 0.0.0.0 --port 8800' "${be}" "$(unset_proxy_prefix)" ;;
    portal) printf 'cd %q && pnpm dev' "${portal}" ;;
    # Mock uploads plate photos to S3; its coded defaults (localhost:9000 +
    # minioadmin/minioadmin) match neither infra MinIO's secret (bic_local_dev)
    # nor the full-real bench store (192.168.12.150, which real Mind must reach).
    # minimal profile -> local infra MinIO; anything else -> the 150 store.
    mock)   if [ "${BIC_PROFILE}" = "minimal" ]; then
              printf 'cd %q && TLC_FIXTURE_SEQUENCE="${TLC_FIXTURE_SEQUENCE:-tlc_plate_fixture.png,tlc_plate_med02.jpg}" S3_ENDPOINT=localhost:9000 S3_ACCESS_KEY=minioadmin S3_SECRET_KEY=bic_local_dev S3_BUCKET=tlc-mock uv run mars-interface-mock' "$(repo_dir mars_interface_mock)"
            else
              printf 'cd %q && TLC_FIXTURE_SEQUENCE="${TLC_FIXTURE_SEQUENCE:-tlc_plate_fixture.png,tlc_plate_med02.jpg}" S3_ENDPOINT=192.168.12.150:9000 S3_ACCESS_KEY=minioadmin S3_SECRET_KEY=bic_local_dev S3_BUCKET=tlc-images uv run mars-interface-mock' "$(repo_dir mars_interface_mock)"
            fi ;;
    chem)   printf 'cd %q && uv run uvicorn app.main:app --host 127.0.0.1 --port 8010' "${CHEM_DIR}" ;;
  esac
}
health_url_for() {
  case "$1" in
    lab) echo "http://localhost:8192/health" ;;
    BE)  echo "http://localhost:8800/health" ;;
    portal) echo "http://localhost:5173/src/main.tsx" ;;
    chem) echo "http://localhost:8010/health" ;;
    mock) echo "" ;;
  esac
}
service_healthy() { # <name>
  local n="$1" url; url="$(health_url_for "$n")"
  if [ "$n" = "mock" ]; then pgrep -f 'mars-interface-mock' >/dev/null 2>&1; return; fi
  [ "$(http_code "$url")" = "200" ]
}

ensure_session() {
  if tmux has-session -t "${BIC_TMUX}" 2>/dev/null; then
    note "tmux session ${BIC_TMUX} exists"
  else
    do_run tmux new-session -d -s "${BIC_TMUX}" -n bic
  fi
}
launch_window() { # <win> <cmd>
  local win="$1" cmd="$2"
  if tmux has-session -t "${BIC_TMUX}" 2>/dev/null && \
     tmux list-windows -t "${BIC_TMUX}" -F '#{window_name}' 2>/dev/null | grep -qx "${win}"; then
    note "window ${win} exists — sending start into it"
  else
    do_run tmux new-window -t "${BIC_TMUX}" -n "${win}"
  fi
  if [ "${DRY_RUN}" = "1" ]; then
    printf '  %s[dry]%s tmux send-keys -t %s:%s %q Enter\n' "${C_YEL}" "${C_RST}" "${BIC_TMUX}" "${win}" "${cmd}"
  else
    tmux send-keys -t "${BIC_TMUX}:${win}" "${cmd}" Enter
  fi
}

ensure_session
# window names: lab, agent, portal, mock, chem (chem optional in minimal profile)
for svc in lab BE portal mock chem; do
  [ -n "${ONLY}" ] && [ "${svc}" != "${ONLY}" ] && continue
  win="${svc}"; [ "${svc}" = "BE" ] && win="agent"
  if [ "${svc}" = "chem" ] && [ ! -d "${CHEM_DIR}" ]; then
    note "chem skipped (no ${CHEM_DIR}; optional — ELN naming lazy-skips)"
    continue
  fi
  if service_healthy "${svc}"; then
    ok "${svc} already healthy — skipped"
    continue
  fi
  launch_window "${win}" "$(start_cmd_for "${svc}")"
  # real health gate (mock has no HTTP surface)
  url="$(health_url_for "${svc}")"
  if [ -n "${url}" ]; then
    if wait_http "${url}" 90; then ok "${svc} healthy (${url})"; else fail "${svc} did not become healthy" "make restart-${svc} ; tmux attach -t ${BIC_TMUX}"; fi
  else
    if [ "${DRY_RUN}" != "1" ]; then sleep 2; fi
    if service_healthy mock; then ok "mock alive"; else warn "mock not detected yet (check tmux ${BIC_TMUX}:mock)"; fi
  fi
done

# ===========================================================================
printf '\n%s%s== Done ==%s  ' "${C_BLD}" "${C_BLU}" "${C_RST}"
printf 'run %smake status%s or %smake doctor%s to verify.\n' "${C_BLD}" "${C_RST}" "${C_BLD}" "${C_RST}"
[ "${DRY_RUN}" = "1" ] && printf '  %s(this was a DRY run — nothing changed)%s\n' "${C_DIM}" "${C_RST}"
exit 0
