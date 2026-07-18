# BIC Workspace

This is the root meta repo for the BIC workspace. It owns shared documentation, workspace-level AI instructions, Trellis planning artifacts, and onboarding scripts.

Child repos remain independent Git repositories cloned under this directory.

## Workspace Model

```text
BIC/
  Production-PRD.md
  README.md
  CLAUDE.md
  AGENTS.md -> CLAUDE.md
  Makefile
  scripts/bic-env/        # orchestrator scripts (see "Scripts" below)
  BIC-agent-portal/      # child repo
  BIC-agent-service/     # child repo
  BIC-lab-service/       # child repo
  mars_interface_mock/   # robot mock (MQ)
  BIC-shared-types/      # cross-team child repo, referenced only
```

Do not use Git submodules for this workspace. The root repo ignores child repo directories.

## Clone Order

New developers clone this root meta repo first, then clone each child repo next to it:

```bash
git clone git@github.com:c12-ai/BIC-meta.git BIC
cd BIC
git clone git@github.com:c12-ai/BIC-agent-service.git
git clone git@github.com:c12-ai/BIC-agent-portal.git
git clone git@github.com:c12-ai/BIC-lab-service.git
git clone git@github.com:c12-ai/BIC-shared-types.git
git clone git@github.com:c12-ai/mars_interface_mock.git
```

`make up` red-cards any missing repo with the fix command.

## PRD Ownership

Root Production PRD:

```text
Production-PRD.md
```

Use it for cross-end, cross-service, or overall business logic.

Agent Service Project PRD:

```text
BIC-agent-service/docs/project-prd.md
```

Use it for Agent behavior and Agent Copilot self-behavior owned by the backend agent service.

Use the `prd` skill when creating, updating, splitting, moving, or reviewing PRD content.

## Repos

| Repo | Role | Local port |
| --- | --- | --- |
| `BIC-lab-service` | Nexus / LIMS, lab state, robot orchestration over MQ | `8192` |
| `BIC-agent-service` | Agent backend, LangGraph/FastAPI, talks to Nexus | `8800` |
| `BIC-agent-portal` | Frontend portal, no BFF | `5173` |
| `BIC-shared-types` | Cross-team shared object/protocol types | n/a |

## Local Startup

Two lines. Everything else is encoded in the scripts and printed by `make doctor`.

```bash
make up STAGE=local     # idempotent: infra, DBs, keycloak seed, deps, tmux bic-services
make doctor STAGE=local # read-only checkup; every red card prints its own fix command
```

Open <http://localhost:5173>.

### The stage: `STAGE=local | dev | prod`

Every service reads its own `.env.<stage>` file and REQUIRES a stage to start — there is no
default `.env`. The orchestrator selects a stage and launches; **it never writes config**. Each
repo's `.env.<stage>` is the single source of truth, owned by you.

- `STAGE=local` (default) — your bench. Copy `.env.local.example` → `.env.local` per repo and
  fill it once. (Portal's local file is `.env.localdev`, a Vite convention.)
- `STAGE=dev` / `STAGE=prod` — load `.env.dev` / `.env.prod`. Fill those before use.

Missing a stage file? `make up` fails loud and tells you which `.env.<stage>.example` to copy.

To switch what a stage points at (mock vs real Mind, local MinIO vs AWS S3), edit that repo's
`.env.<stage>` — e.g. set `MIND_MOCK_MODE=false` / `MCP_HOST=...` for real Mind. No script
toggles it anymore.

### Make targets

| Command | What it does |
| --- | --- |
| `make up STAGE=local` | Idempotent bring-up + self-heal. `DRY=1` previews without changing anything. Bad `STAGE` fails. |
| `make doctor STAGE=local` | Read-only full checkup (docker, containers, ports, DBs, keycloak, service health, auth cards reading `.env.<stage>`). GREEN = bench is up. |
| `make down` | Stop app services. `make down INFRA=1` also stops the shared docker infra. |
| `make restart-<svc> STAGE=local` | Restart one of `lab \| BE \| portal \| mock \| chem` with the same health gate. |
| `make pull` | Fast-forward all repos (meta/services/infra) to `origin/main`. |
| `make update` | `pull` + full restart on the new code (pull + up alone does NOT redeploy running services). |

Knob: `BIC_ROOT=/path` (where the sibling repos live — defaults to this repo's parent, autodetected).

When a red card isn't enough, the troubleshooting appendix is
[`ops/run-latest-2026-07-10.md`](ops/run-latest-2026-07-10.md) — `make doctor` points there.

## Scripts

The orchestrator lives in `scripts/bic-env/`. It only ever affects the **current machine's
network** — to deploy to a server, SSH into that server and run there.

| Script | Responsibility | Run it via |
| --- | --- | --- |
| `common.sh` | Shared library (paths, `BIC_STAGE`/`APP_ENV`, `env_file()`, health probes, colors). Sourced by all; not run directly. | — |
| `up.sh` | Bring up: docker → infra → keycloak seed → DBs → migrations → launch 4 services (staged), each health-gated. Idempotent. Never writes config. | `make up STAGE=local` |
| `down.sh` | Stop all app services (kill tmux session + reap PIDs). `INFRA=1` also stops shared docker infra. | `make down` |
| `restart.sh` | Stop one service and relaunch it via `up.sh` (scoped), same health gate. | `make restart-<svc> STAGE=local` |
| `doctor.sh` | Read-only deep health check: tools, containers, ports, DBs, keycloak, service health, auth (reads `.env.<stage>`). | `make doctor STAGE=local` |
| `pull.sh` | `git pull --ff-only` across meta/services/infra. | `make pull` |
| `get-token.sh` | Mint a Keycloak service-account token (300 s) for manual authed calls. | `scripts/bic-env/get-token.sh` |

### Which command for which scenario

| Scenario | Command |
| --- | --- |
| First time / cold start the whole bench | `make up STAGE=local` |
| Check the bench is healthy | `make doctor STAGE=local` |
| One service is misbehaving — restart just it | `make restart-BE STAGE=local` (or `lab`/`portal`/`mock`/`chem`) |
| Preview what `up` would do, change nothing | `make up STAGE=local DRY=1` |
| Pulled new code — redeploy running services | `make update` (or `make pull` then `make restart-<svc> STAGE=local`) |
| Stop the app services | `make down` |
| Stop app services + shared infra | `make down INFRA=1` |
| Switch a service to real Mind / AWS S3 | edit that repo's `.env.<stage>`, then `make restart-<svc> STAGE=local` |
| Run a service by hand from its own repo | `make dev ENV=local` (agent/lab) · `pnpm dev:local` (portal) · `APP_ENV=local uv run mars-interface-mock` (mock) |
| Reset agent DB + MQ | `curl -X POST http://localhost:8800/reset \| jq` |
| Reset lab DB to seed | `curl -X POST http://127.0.0.1:8192/admin/reset-to-test-data -H "Authorization: Bearer $(scripts/bic-env/get-token.sh)" -H 'Content-Type: application/json' -d '{"robot_id":"talos.001"}'` |
| Get a token for manual authed calls | `scripts/bic-env/get-token.sh` |

## PRD Update Flow

When a change affects product behavior:

1. Update `Production-PRD.md` in this root meta repo.
2. Update child Project PRDs only when they refine repo-owned behavior.
3. Implement code changes in child repo PRs.
4. Link implementation PRs back to the PRD PR or commit.

Documentation-only PRD changes can be root-only.

## Wiki

Wiki-source pages are tracked in this repo under:

```text
docs/wiki/
```

Start from `docs/wiki/Home.md`.

GitHub Wiki is enabled for `BIC-meta`, but GitHub only creates the backing
`BIC-meta.wiki.git` repository after the first page is saved through the web UI.
After that one-time initialization, these pages can be pushed to the GitHub Wiki
remote directly.

## Trellis Tracking

Track shared Trellis artifacts:

- `.trellis/workflow.md`
- `.trellis/spec/`
- `.trellis/tasks/`
- `.trellis/workspace/`
- `.trellis/scripts/`

Do not track Trellis runtime/pointer/temp files such as `.trellis/.developer`, `.trellis/.current-task`, `.trellis/.runtime/`, `.trellis/.agents/`, `.trellis/.agent-log`, `.trellis/.session-id`, `.trellis/.plan-log`, `.trellis/.backup-*`, caches, and temp files.
