#!/usr/bin/env bash
#
# Unit-test-like self-check for deploy.sh pre-flight port logic. Exercises BOTH
# branches deterministically (a known-free port and a port we occupy on purpose)
# so a regression in port_in_use / port_occupant fails loudly.
#
#     ./scripts/preflight-selftest.sh
#
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source deploy.sh for its functions only (main is guarded on direct execution).
# shellcheck source=../deploy.sh disable=SC1091
source "$HERE/../deploy.sh"

fails=0
FREE_PORT=39997
BUSY_PORT=39998

# --- branch 1: a free port must read as NOT in use ---
if port_in_use "$FREE_PORT"; then
  echo "FAIL: free port $FREE_PORT reported in-use"; fails=$((fails+1))
else
  echo "PASS: free-port branch — $FREE_PORT not in use"
fi

# --- branch 2: an occupied port must read as in use, with an occupant ---
ready="$(mktemp)"
python3 - "$BUSY_PORT" "$ready" <<'PY' &
import socket, sys, time
port = int(sys.argv[1]); ready = sys.argv[2]
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", port)); s.listen(1)
open(ready, "w").close()
time.sleep(30)
PY
lpid=$!
trap 'kill "$lpid" 2>/dev/null || true; rm -f "$ready"' EXIT
for _ in $(seq 1 50); do [ -s "$ready" ] && break; sleep 0.1; done

if port_in_use "$BUSY_PORT"; then
  echo "PASS: occupied-port branch — $BUSY_PORT in use; occupant: $(port_occupant "$BUSY_PORT")"
else
  echo "FAIL: occupied port $BUSY_PORT not detected"; fails=$((fails+1))
fi

if [ "$fails" -eq 0 ]; then
  echo "SELFTEST PASS (both branches)"
else
  echo "SELFTEST FAIL ($fails)"; exit 1
fi
