#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
META_ROOT="$(cd "$KIT_DIR/../.." && pwd)"
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      EXECUTE=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$EXECUTE" -ne 1 ]]; then
  echo "This command installs project test dependencies and Playwright Chromium." >&2
  echo "Re-run with --execute after explicit user approval." >&2
  exit 2
fi

SERVICE_DIR="$META_ROOT/BIC-agent-service"
PORTAL_DIR="$META_ROOT/BIC-agent-portal"
[[ -d "$SERVICE_DIR" ]] || { echo "Missing repository: $SERVICE_DIR" >&2; exit 1; }
[[ -d "$PORTAL_DIR" ]] || { echo "Missing repository: $PORTAL_DIR" >&2; exit 1; }
command -v uv >/dev/null || {
  echo "Missing required tool: uv. Install uv, then re-run this command." >&2
  exit 1
}
command -v python3 >/dev/null || {
  echo "Missing required tool: python3. Install Python 3, then re-run this command." >&2
  exit 1
}
command -v node >/dev/null || {
  echo "Missing required tool: node. Install Node.js, then re-run this command." >&2
  exit 1
}
command -v npm >/dev/null || {
  echo "Missing required tool: npm. Install Node.js with npm, then re-run this command." >&2
  exit 1
}

if command -v pnpm >/dev/null; then
  PNPM=(pnpm)
elif command -v corepack >/dev/null; then
  PNPM=(corepack pnpm)
else
  echo "Missing pnpm/Corepack. Install Node.js with Corepack support." >&2
  exit 1
fi

echo "Preparing BIC-agent-service test environment..."
(cd "$SERVICE_DIR" && uv sync --frozen)

echo "Preparing BIC-agent-portal test environment..."
(cd "$PORTAL_DIR" && "${PNPM[@]}" install --frozen-lockfile)

PLAYWRIGHT_CLI="$PORTAL_DIR/node_modules/@playwright/test/cli.js"
[[ -f "$PLAYWRIGHT_CLI" ]] || {
  echo "Playwright CLI is missing after portal dependency installation." >&2
  exit 1
}
echo "Installing Playwright Chromium for the current OS..."
(cd "$PORTAL_DIR" && node "$PLAYWRIGHT_CLI" install chromium)

echo "Runtime setup finished. Running the read-only doctor..."
exec "$KIT_DIR/doctor-test-runtime.sh"
