# BIC Dev Container

One container for the whole workspace (agent-service, lab-service, portal,
shared-types) plus its own Postgres / Redis / RabbitMQ / MinIO sidecars.

The sidecars share the dev container's network namespace, so every service is
on `localhost` with the same ports and `bic_local_dev` credentials as the host
stack — the repos' existing `.env` files, `check_services.py`, reset curls,
and the tmux workflow all work unchanged. The sidecar stack is fully separate
from the `bic-*` containers on the host (own volumes, no published ports).

## First run

1. VS Code → "Reopen in Container". `post-create.sh` runs `uv sync` in both
   Python services, `pnpm install` + Playwright chromium in the portal.
   The uv git deps need access to the private `github.com/c12-ai` repos —
   VS Code forwards your local git credentials automatically; if a sync fails,
   fix auth and rerun `bash .devcontainer/post-create.sh`.
2. The sidecar Postgres starts empty (only `template_db` / `labrun_db` are
   created). Seed it the usual way:
   - lab-service: `uv run alembic upgrade head`, then the
     `/admin/reset-to-test-data` curl from the root `CLAUDE.md`
   - agent-service: `curl -X POST http://localhost:8800/reset`

## Notes

- `.venv` and `node_modules` are named-volume overlays — the container's Linux
  envs never touch your macOS ones on the host.
- Ports (8800 / 8192 / 5173 / infra) are forwarded by VS Code on demand; if the
  host stack is running, VS Code picks a free host port instead of colliding.
- Launch services the same way as on the host, e.g. in tmux:
  `uv run python -m app.main` (agent BE / lab), `pnpm dev` (portal).
