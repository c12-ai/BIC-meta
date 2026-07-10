#!/usr/bin/env bash
# restart.sh <svc> — restart a single app service with the same self-heal and
# health gate as `up`. svc in: lab | BE | portal | mock | chem
#
# Only ever kills OUR own process on the port (foreign owners get a red card,
# never a kill).
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

svc="${1:-}"
case "${svc}" in
  lab|BE|portal|mock|chem) ;;
  *) printf 'usage: restart.sh <lab|BE|portal|mock|chem>\n' >&2; exit 2 ;;
esac

printf '%s%sBIC restart %s%s   ' "${C_BLD}" "${C_BLU}" "${svc}" "${C_RST}"
print_context

port_for() {
  case "$1" in lab) echo 8192 ;; BE) echo 8800 ;; portal) echo 5173 ;; chem) echo 8010 ;; mock) echo "" ;; esac
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

# --- stop ours on the port (if any) ---
section "Stop ${svc}"
port="$(port_for "${svc}")"
if [ -n "${port}" ]; then
  owner="$(port_owner "${port}")"
  pid="$(printf '%s' "${owner}" | awk '{print $2}')"
  cmd="$(printf '%s' "${owner}" | awk '{print $1}')"
  if [ -z "${pid}" ]; then
    note "${port} free"
  elif is_our_process "${pid}"; then
    do_run kill "${pid}"
    # port may not free instantly; escalate to KILL if still bound (per CLAUDE.md)
    if [ "${DRY_RUN}" != "1" ]; then
      i=0; while [ "${i}" -lt 5 ] && [ -n "$(port_owner "${port}")" ]; do i=$((i + 1)); sleep 1; done
      [ -n "$(port_owner "${port}")" ] && do_run kill -KILL "${pid}"
    fi
    ok "stopped our ${cmd} (pid ${pid}) on ${port}"
  else
    fail "${port} held by FOREIGN '${cmd}' (pid ${pid}) — refusing to kill someone else's process" \
         "inspect: lsof -nP -iTCP:${port} -sTCP:LISTEN"
    exit 1
  fi
else
  # mock: stop by name
  if pgrep -f 'mars-interface-mock' >/dev/null 2>&1; then do_sh "pkill -f 'mars-interface-mock' || true"; ok "stopped mock"; else note "mock not running"; fi
fi

# --- start via up.sh's per-service path (reuse by delegating to a scoped up) ---
section "Start ${svc}"
UP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/up.sh"
# up.sh is idempotent per service: it will skip healthy ones and (re)start this one.
BIC_ONLY="${svc}" do_run bash "${UP}"

# up.sh restarts everything not-healthy; that's acceptable (idempotent). For a
# tight single-service loop we still verify THIS service's health here.
section "Verify ${svc}"
url="$(health_url_for "${svc}")"
if [ -z "${url}" ]; then
  if pgrep -f 'mars-interface-mock' >/dev/null 2>&1 || [ "${DRY_RUN}" = "1" ]; then ok "mock alive"; else fail "mock not alive" "tmux attach -t ${BIC_TMUX}"; fi
elif [ "${DRY_RUN}" = "1" ]; then
  note "[dry] would verify ${url} == 200"
else
  i=0; while [ "${i}" -lt 90 ] && [ "$(http_code "${url}")" != "200" ]; do i=$((i + 1)); sleep 1; done
  if [ "$(http_code "${url}")" = "200" ]; then ok "${svc} healthy"; else fail "${svc} unhealthy" "tmux attach -t ${BIC_TMUX}"; fi
fi
