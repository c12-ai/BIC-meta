#!/usr/bin/env bash
set -uo pipefail

WORKSPACE=/workspaces/BIC
fail=0

# Named volumes mount root-owned; hand them to the dev user.
sudo chown vscode:vscode \
  "$WORKSPACE/BIC-agent-service/.venv" \
  "$WORKSPACE/BIC-lab-service/.venv" \
  "$WORKSPACE/BIC-agent-portal/node_modules"

# pnpm 9 matches BIC-agent-portal/pnpm-lock.yaml (lockfileVersion 9.0)
sudo npm install -g pnpm@9

# uv git deps pull private github.com/c12-ai repos — relies on the git
# credentials VS Code forwards into the container (ssh-agent or helper).
for svc in BIC-agent-service BIC-lab-service; do
  echo "==> uv sync: $svc"
  (cd "$WORKSPACE/$svc" && uv sync) \
    || { echo "!! uv sync failed for $svc — check git auth for github.com/c12-ai"; fail=1; }
done

echo "==> pnpm install: BIC-agent-portal"
(cd "$WORKSPACE/BIC-agent-portal" && pnpm install) || fail=1

echo "==> playwright browsers (chromium)"
(cd "$WORKSPACE/BIC-agent-portal" && pnpm exec playwright install --with-deps chromium) \
  || { echo "!! playwright install failed — E2E only, dev servers unaffected"; fail=1; }

if [ "$fail" -ne 0 ]; then
  echo "post-create finished WITH ERRORS — see !! lines above"
else
  echo "post-create finished cleanly"
fi
exit "$fail"
