#!/usr/bin/env bash
# mind.sh <status|real|mock> — switch the bench between MOCK and REAL Mind/MinIO,
# and always SAY which one is active (the bench must never be ambiguous about it).
#
# The two modes (intent lives in BE .env MIND_MOCK_MODE; this script converges
# reality to intent and verifies each leg before flipping the BE):
#
#   MOCK  (default)  Mind answers come from BE fixtures; local bic-minio serves :9000.
#   REAL             BE -> real Mind on the lab LAN (192.168.12.104:8002), reached
#                    off-lab via the orin-tail tailscale node (c12-workstation),
#                    which advertises 192.168.12.0/24. MinIO = orin's instance,
#                    fronted locally by minio-forward.py on :9000/:9001 so that
#                    presigned URLs signed for host 192.168.12.150:9000 work from
#                    BOTH sides (bench -> forwarder -> orin; Mind -> orin directly).
#
# One-time sudo per boot (real mode, off-lab only): the /32 host route to the
# Mind box (the local LAN is also 192.168.12.x, so the connected /24 otherwise
# wins). The route and the forwarder do NOT survive a reboot — `make up` /
# `make mind-real` re-establish them.
#
# `make up` calls `mind.sh converge` (no sudo): full-real profile auto-switches
# to REAL when every leg is already reachable, else stays MOCK and says why.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FWD_SCRIPT="${_here}/minio-forward.py"
FWD_LOG="/tmp/bic-minio-forward.log"
BE_ENV="$(repo_dir BIC-agent-service)/.env"
# Canned real-Mind probe (captured from a live 2026-07-11 run): parse must be 200.
MIND_PROBE_PATH="/api/protocol/experiment/rxn-parse"
MIND_PROBE_BODY='{"rxn":"C#CC(C)(O)C.BrC1=CC=C(I)C(COC)=C1>>BrC2=CC=C(C(COC)=C2)C#CC(C)(O)C"}'

# ----------------------------------------------------------------------------
# probes (read-only)
# ----------------------------------------------------------------------------
orin_minio_up()   { [ "$(http_code "http://${ORIN_TS_IP}:9000/minio/health/live" 5)" = "200" ]; }
local_9000_up()   { [ "$(http_code "http://127.0.0.1:9000/minio/health/live" 5)" = "200" ]; }
mind_tcp_up()     { tcp_open "${MIND_LAB_IP}" "${MIND_PORT}" 3; }
mind_probe_200() {
  local code
  code="$(curl -s --noproxy '*' --max-time 20 -o /dev/null -w '%{http_code}' \
    -X POST "http://${MIND_LAB_IP}:${MIND_PORT}${MIND_PROBE_PATH}" \
    -H 'Content-Type: application/json' -d "${MIND_PROBE_BODY}" 2>/dev/null || true)"
  [ "${code}" = "200" ]
}
# aws profile: same rxn-parse probe, but against the public cloud Mind.
aws_mind_probe_200() {
  local code
  code="$(curl -s --noproxy '*' --max-time 20 -o /dev/null -w '%{http_code}' \
    -X POST "http://${AWS_MIND_HOST}:${AWS_MIND_PORT}${MIND_PROBE_PATH}" \
    -H 'Content-Type: application/json' -d "${MIND_PROBE_BODY}" 2>/dev/null || true)"
  [ "${code}" = "200" ]
}

# mode_banner <MOCK|REAL|BROKEN> <detail>
mode_banner() {
  local col="${C_GRN}"
  [ "$1" = "BROKEN" ] && col="${C_RED}"
  [ "$1" = "MOCK" ] && col="${C_YEL}"
  printf '\n  %s%s>>> MIND MODE: %s <<<%s  %s\n' "${C_BLD}" "${col}" "$1" "${C_RST}" "$2"
}

# ----------------------------------------------------------------------------
# BE .env edit — set_env_kv <key> <value> (idempotent; appends if missing)
# ----------------------------------------------------------------------------
set_env_kv() {
  local key="$1" val="$2" cur
  [ -f "${BE_ENV}" ] || { fail "BE .env missing at ${BE_ENV}" "make up  # seeds it"; return 1; }
  cur="$(sed -n "s/^${key}=//p" "${BE_ENV}" | head -1 | sed 's/#.*//' | tr -d '[:space:]')"
  if [ "${cur}" = "${val}" ]; then return 0; fi
  ENV_CHANGED=1
  if grep -q "^${key}=" "${BE_ENV}"; then
    do_sh "sed -i '' 's|^${key}=.*|${key}=${val}|' '${BE_ENV}'"
  else
    do_sh "printf '%s\n' '${key}=${val}' >> '${BE_ENV}'"
  fi
}

restart_be() {
  local pid
  if [ "${NO_RESTART:-0}" = "1" ]; then
    # converge mode: up.sh launches the BE right after — just make sure a
    # running BE cannot keep serving with the stale flags.
    pid="$(port_pid 8800)"
    if [ -n "${pid}" ] && is_our_process "${pid}"; then
      do_run kill "${pid}"
      if [ "${DRY_RUN}" != "1" ]; then
        i=0; while [ "${i}" -lt 5 ] && [ -n "$(port_owner 8800)" ]; do i=$((i + 1)); sleep 1; done
        [ -n "$(port_owner 8800)" ] && do_run kill -KILL "${pid}"
      fi
      note "stopped BE (pid ${pid}) — up.sh relaunches it with the new flags"
    fi
    return 0
  fi
  note "restarting BE so the new MIND_* flags load"
  do_run bash "${_here}/restart.sh" BE
}

# ----------------------------------------------------------------------------
# status — read-only report of intent + every leg of the real path
# ----------------------------------------------------------------------------
cmd_status() {
  local intent owner9000 fwd cloud_up
  intent="$(be_mind_mock)"

  # aws profile: cloud Mind + AWS S3 — no orin route/forwarder legs to report.
  if [ "${BIC_PROFILE}" = "aws" ]; then
    section "Mind mode (aws profile — intent: BE .env MIND_MOCK_MODE)"
    case "${intent}" in
      true)  warn "intent MOCK (MIND_MOCK_MODE=true) — unexpected on aws profile (make mind-real for cloud)" ;;
      false) ok "intent REAL (MIND_MOCK_MODE=false)" ;;
      unset) warn "MIND_MOCK_MODE not set in ${BE_ENV} (BE code default: mock)" ;;
    esac
    section "Cloud Mind leg (aws profile)"
    if [ "$(http_code "http://${AWS_MIND_HOST}:${AWS_MIND_PORT}/openapi.json" 8)" = "200" ]; then
      ok "cloud Mind reachable (${AWS_MIND_HOST}:${AWS_MIND_PORT} openapi 200)"; cloud_up=1
    else
      warn "cloud Mind not reachable (${AWS_MIND_HOST}:${AWS_MIND_PORT}) — check network / VPN"; cloud_up=0
    fi
    if [ "${intent}" = "false" ] && [ "${cloud_up}" = "1" ]; then
      mode_banner REAL "REAL (aws cloud) — Mind ${AWS_MIND_HOST}:${AWS_MIND_PORT} + AWS S3 (no route/forwarder)"
    elif [ "${intent}" = "false" ]; then
      mode_banner BROKEN "intent REAL but cloud Mind unreachable — check network, then: make mind-real"
      return 1
    else
      mode_banner MOCK "intent MOCK on aws profile — run: make mind-real to use cloud Mind"
    fi
    return 0
  fi

  section "Mind mode (intent: BE .env MIND_MOCK_MODE)"
  case "${intent}" in
    true)  ok "intent MOCK (MIND_MOCK_MODE=true)" ;;
    false) ok "intent REAL (MIND_MOCK_MODE=false)" ;;
    unset) warn "MIND_MOCK_MODE not set in ${BE_ENV} (BE code default: mock)" ;;
  esac

  section "Real-path legs (needed only for REAL)"
  if tcp_open "${ORIN_TS_IP}" 9000 3; then ok "orin-tail reachable (${ORIN_TS_IP})"; else warn "orin-tail unreachable (tailscale down / peer offline)"; fi
  if orin_minio_up; then ok "orin MinIO healthy (:9000)"; else warn "orin MinIO not healthy"; fi
  if mind_route_ok; then ok "/32 route to Mind box via utun present"; else warn "no /32 route to ${MIND_LAB_IP} via tailscale (make mind-real adds it, sudo)"; fi
  if mind_tcp_up; then ok "real Mind TCP up (${MIND_LAB_IP}:${MIND_PORT})"; else warn "real Mind not reachable"; fi
  fwd="$(minio_fwd_pid)"
  owner9000="$(port_owner 9000)"
  if [ -n "${fwd}" ]; then
    ok ":9000 = forwarder -> orin (pid ${fwd})"
  elif container_running bic-minio; then
    ok ":9000 = local bic-minio container"
  else
    warn ":9000 owner: ${owner9000:-none} (neither forwarder nor bic-minio)"
  fi

  # verdict
  if [ "${intent}" = "false" ]; then
    if mind_tcp_up && [ -n "${fwd}" ] && orin_minio_up; then
      mode_banner REAL "real Mind ${MIND_LAB_IP}:${MIND_PORT} + orin MinIO via forwarder"
    else
      mode_banner BROKEN "intent is REAL but a leg is down — run: make mind-real  (or fall back: make mind-mock)"
      return 1
    fi
  else
    if container_running bic-minio || local_9000_up; then
      mode_banner MOCK "Mind fixtures + local MinIO (enable real: make mind-real)"
    else
      mode_banner BROKEN "intent is MOCK but no MinIO on :9000 — run: make mind-mock"
      return 1
    fi
  fi
}

# ----------------------------------------------------------------------------
# real — converge every leg to REAL, verify, flip BE, restart BE
#   ALLOW_SUDO=0 (converge mode) skips sudo steps and bails if they are needed.
# ----------------------------------------------------------------------------
cmd_real() {
  local allow_sudo="${1:-1}"
  ENV_CHANGED=0
  section "Switch to REAL Mind/MinIO (via orin-tail)"

  # 1. orin reachable at all?
  if ! tcp_open "${ORIN_TS_IP}" 9000 3; then
    fail "orin-tail (${ORIN_TS_IP}) unreachable — tailscale down or peer offline" \
         "tailscale status   # peer c12-workstation must be online"
    mode_banner MOCK "staying MOCK (real path unavailable)"
    return 1
  fi
  ok "orin-tail reachable"

  # 2. /32 route to the Mind box (sudo, once per boot)
  if mind_route_ok; then
    ok "/32 route to ${MIND_LAB_IP} already present"
  elif [ "${allow_sudo}" = "1" ]; then
    note "adding host route (sudo will prompt once)"
    utun="$(ifconfig 2>/dev/null | awk -v ip="$(tailscale ip -4 2>/dev/null | head -1)" '/^utun[0-9]+:/{u=substr($1,1,length($1)-1)} $0 ~ "inet " ip {print u; exit}')"
    utun="${utun:-utun6}"
    do_run sudo route add -host "${MIND_LAB_IP}" -interface "${utun}"
  else
    fail "no /32 route to ${MIND_LAB_IP} (needs one sudo command)" "make mind-real"
    mode_banner MOCK "staying MOCK (route missing)"
    return 1
  fi

  # 3. presign host must resolve locally (off-lab boxes that are not .150 need
  #    a loopback alias so BE can reach the host it signs URLs for)
  if orin_lab_ip_is_local; then
    ok "presign host ${ORIN_LAB_IP} answers locally"
  elif [ "${allow_sudo}" = "1" ]; then
    do_run sudo ifconfig lo0 alias "${ORIN_LAB_IP}/32"
  else
    fail "presign host ${ORIN_LAB_IP} not local (needs one sudo command)" "make mind-real"
    mode_banner MOCK "staying MOCK (presign host unresolved)"
    return 1
  fi

  # 4. :9000 = forwarder -> orin (replaces local bic-minio)
  if [ -n "$(minio_fwd_pid)" ]; then
    ok "minio forwarder already running (pid $(minio_fwd_pid))"
  else
    if container_running bic-minio; then do_run docker stop bic-minio; fi
    do_sh "ORIN_TS_IP='${ORIN_TS_IP}' nohup python3 '${FWD_SCRIPT}' >> '${FWD_LOG}' 2>&1 &"
    if [ "${DRY_RUN}" != "1" ]; then
      i=0; while [ "${i}" -lt 10 ] && ! local_9000_up; do i=$((i + 1)); sleep 1; done
    fi
  fi
  if [ "${DRY_RUN}" = "1" ] || local_9000_up; then
    ok ":9000 serves orin MinIO through the forwarder"
  else
    fail ":9000 not healthy after starting forwarder" "cat ${FWD_LOG}"
    return 1
  fi

  # 5. real Mind must actually answer (hard gate — never flip BE onto a dead engine)
  if [ "${DRY_RUN}" = "1" ]; then
    note "[dry] would POST ${MIND_PROBE_PATH} to ${MIND_LAB_IP}:${MIND_PORT} and require 200"
  elif mind_probe_200; then
    ok "real Mind answered the rxn-parse probe (200)"
  else
    fail "real Mind did not answer 200 on ${MIND_PROBE_PATH}" \
         "curl -s --noproxy '*' http://${MIND_LAB_IP}:${MIND_PORT}${MIND_PROBE_PATH} ; # Mind box down?"
    mode_banner MOCK "staying MOCK (Mind probe failed) — BE flags untouched"
    return 1
  fi

  # 6. flip BE intent + restart
  set_env_kv MCP_HOST "${MIND_LAB_IP}"
  set_env_kv MCP_PORT "${MIND_PORT}"
  set_env_kv MIND_MOCK_MODE false
  set_env_kv MIND_RECOGNITION_MOCK_MODE false
  if [ "${ENV_CHANGED}" = "1" ]; then restart_be; else ok "BE .env already REAL — no restart needed"; fi

  mode_banner REAL "real Mind ${MIND_LAB_IP}:${MIND_PORT} + orin MinIO (presign host ${ORIN_LAB_IP}:9000)"
  note "reboot loses the route + forwarder — make up / make mind-real restores them"
}

# ----------------------------------------------------------------------------
# mock — converge back to MOCK (fixtures + local bic-minio)
# ----------------------------------------------------------------------------
cmd_mock() {
  ENV_CHANGED=0
  section "Switch to MOCK Mind + local MinIO"

  fwd="$(minio_fwd_pid)"
  if [ -n "${fwd}" ]; then
    do_run kill "${fwd}"
    ok "stopped minio forwarder (pid ${fwd})"
  else
    note "no forwarder running"
  fi
  if container_running bic-minio; then
    ok "bic-minio already running"
  else
    do_run docker start bic-minio
    if [ "${DRY_RUN}" != "1" ]; then
      i=0; while [ "${i}" -lt 15 ] && ! local_9000_up; do i=$((i + 1)); sleep 1; done
      if local_9000_up; then ok "local bic-minio healthy on :9000"; else fail "bic-minio not healthy" "docker logs bic-minio --tail 20"; fi
    fi
  fi

  set_env_kv MIND_MOCK_MODE true
  set_env_kv MIND_RECOGNITION_MOCK_MODE true
  if [ "${ENV_CHANGED}" = "1" ]; then restart_be; else ok "BE .env already MOCK — no restart needed"; fi

  mode_banner MOCK "Mind fixtures + local MinIO (enable real: make mind-real)"
  note "the /32 route to ${MIND_LAB_IP} is left in place (harmless); remove: sudo route delete -host ${MIND_LAB_IP}"
}

# ----------------------------------------------------------------------------
# aws — cloud Mind (aws profile). No route / forwarder / orin leg: Mind and S3
# are public-internet direct. Probe the cloud Mind, then flip BE to REAL.
# ----------------------------------------------------------------------------
cmd_aws() {
  ENV_CHANGED=0
  section "Cloud Mind (aws profile) — ${AWS_MIND_HOST}:${AWS_MIND_PORT}"

  # Hard gate: never flip BE onto a dead engine.
  if [ "${DRY_RUN}" = "1" ]; then
    note "[dry] would POST ${MIND_PROBE_PATH} to ${AWS_MIND_HOST}:${AWS_MIND_PORT} and require 200"
  elif aws_mind_probe_200; then
    ok "cloud Mind answered the rxn-parse probe (200)"
  else
    fail "cloud Mind did not answer 200 on ${MIND_PROBE_PATH} (${AWS_MIND_HOST}:${AWS_MIND_PORT})" \
         "curl -s --noproxy '*' -X POST http://${AWS_MIND_HOST}:${AWS_MIND_PORT}${MIND_PROBE_PATH} -H 'Content-Type: application/json' -d '${MIND_PROBE_BODY}'   # cloud Mind down / no network?"
    mode_banner BROKEN "cloud Mind ${AWS_MIND_HOST}:${AWS_MIND_PORT} unreachable — check network, then: make mind-real"
    return 1
  fi

  # flip BE intent to REAL (cloud). S3 keys are converged by up.sh section 6.
  set_env_kv MCP_HOST "${AWS_MIND_HOST}"
  set_env_kv MCP_PORT "${AWS_MIND_PORT}"
  set_env_kv MIND_MOCK_MODE false
  set_env_kv MIND_RECOGNITION_MOCK_MODE false
  if [ "${ENV_CHANGED}" = "1" ]; then restart_be; else ok "BE .env already REAL (aws cloud) — no restart needed"; fi

  mode_banner REAL "REAL (aws cloud) — Mind ${AWS_MIND_HOST}:${AWS_MIND_PORT} + AWS S3 (no route/forwarder)"
}

# ----------------------------------------------------------------------------
# converge — called by `make up` BEFORE the BE launches. No sudo, no BE restart
# (up.sh starts/heals the BE right after, so flags load on that launch).
# Policy: full-real profile auto-goes REAL when every leg is reachable without
# sudo; anything else stays/goes MOCK. Always prints the mode banner.
# ----------------------------------------------------------------------------
cmd_converge() {
  NO_RESTART=1
  ENV_CHANGED=0
  # aws profile: cloud Mind only. On probe failure, fail loud and leave BE flags
  # as-is — never silently fall back to mock (no local Mind/MinIO on this bench).
  if [ "${BIC_PROFILE}" = "aws" ]; then
    if ! cmd_aws; then
      note "aws profile: cloud Mind unreachable — BE flags left as-is (fix network, then: make mind-real)"
    fi
    return 0
  fi
  if [ "${BIC_PROFILE}" = "full-real" ] && mind_route_ok && orin_lab_ip_is_local && tcp_open "${ORIN_TS_IP}" 9000 3; then
    if ! cmd_real 0; then
      note "real path failed mid-switch — falling back to MOCK"
      cmd_mock
    fi
  else
    # default: mock. Explain what is missing when the profile wanted real.
    if [ "${BIC_PROFILE}" = "full-real" ]; then
      mind_route_ok || note "real path off: no /32 route to ${MIND_LAB_IP} (make mind-real, one sudo)"
      tcp_open "${ORIN_TS_IP}" 9000 3 || note "real path off: orin-tail unreachable"
    fi
    cmd_mock
  fi
}

case "${1:-status}" in
  status)   cmd_status ;;
  real)     if [ "${BIC_PROFILE}" = "aws" ]; then cmd_aws; else cmd_real 1; fi ;;
  mock)     cmd_mock ;;
  converge) cmd_converge ;;
  *) printf 'usage: mind.sh <status|real|mock|converge>\n' >&2; exit 2 ;;
esac
