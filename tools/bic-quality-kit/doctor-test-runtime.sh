#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCTOR="$KIT_DIR/skill/bic-quality-guan-ping-ce/scripts/runtime_readiness.py"

command -v python3 >/dev/null || {
  echo "Missing required tool: python3. Install Python 3, then re-run this command." >&2
  exit 1
}

exec python3 "$DOCTOR" "$@"
