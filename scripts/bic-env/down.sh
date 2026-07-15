#!/usr/bin/env bash
# down.sh — stop the app services cleanly.
#
# By default leaves the docker infra UP: bic-* containers are shared with other
# local stacks, and stopping them would break others' in-flight work (same
# port-governance rule as up: don't touch things that aren't ours).
# Use `make down INFRA=1` to also stop this bench's infra containers.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

STOP_INFRA="${INFRA:-0}"

printf '%s%sBIC down%s   ' "${C_BLD}" "${C_BLU}" "${C_RST}"
print_context

section "App services"
# Kill the tmux session (host processes: lab/BE/portal/mock/chem).
if tmux has-session -t "${BIC_TMUX}" 2>/dev/null; then
  do_run tmux kill-session -t "${BIC_TMUX}"
  ok "tmux session ${BIC_TMUX} killed"
else
  note "no tmux session ${BIC_TMUX}"
fi

# Reap any of OUR app processes still holding app ports (never foreign ones).
for port in 8192 8800 5173 8010; do
  owner="$(port_owner "${port}")"
  pid="$(printf '%s' "${owner}" | awk '{print $2}')"
  cmd="$(printf '%s' "${owner}" | awk '{print $1}')"
  [ -n "${pid}" ] || { note "${port} already free"; continue; }
  if is_our_process "${pid}"; then
    do_run kill "${pid}"
    ok "freed ${port} (our ${cmd} pid ${pid})"
  else
    warn "${port} held by FOREIGN '${cmd}' (pid ${pid}) — leaving it (not ours)"
  fi
done
# mock has no port; kill by name if it lingers outside tmux.
if pgrep -f 'mars-interface-mock' >/dev/null 2>&1; then
  do_sh "pkill -f 'mars-interface-mock' || true"
  ok "stopped mars-interface-mock"
fi

section "Infra containers"
if [ "${STOP_INFRA}" = "1" ]; then
  warn "INFRA=1 — stopping shared infra (may disrupt other local stacks)"
  while IFS='|' read -r name _ _; do
    [ -n "${name}" ] || continue
    container_running "${name}" && do_run docker stop "${name}"
  done <<EOF
$(infra_containers)
EOF
  kc="$(container_on_port 18080)"; [ -n "${kc}" ] && do_run docker stop "${kc}"
else
  note "left running (shared). Use 'make down INFRA=1' to stop them too."
fi

printf '\n%s%s== Down ==%s\n' "${C_BLD}" "${C_BLU}" "${C_RST}"
