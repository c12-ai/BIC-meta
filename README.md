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
  scripts/bootstrap.sh
  BIC-agent-portal/      # child repo
  BIC-agent-service/     # child repo
  BIC-lab-service/       # child repo
  BIC-shared-types/      # cross-team child repo, referenced only
```

Do not use Git submodules for this workspace. The root repo ignores child repo directories and provides bootstrap commands to clone missing repos.

## Clone Order

New developers clone this root meta repo first:

```bash
git clone git@github.com:c12-ai/BIC.git
cd BIC
```

Then clone child repos:

```bash
make bootstrap
```

Targeted clone commands:

```bash
make bootstrap-backend   # BIC-agent-service
make bootstrap-portal    # BIC-agent-portal
make bootstrap-lab       # BIC-lab-service
make bootstrap-shared    # BIC-shared-types, clone only
```

Bootstrap is safe to re-run. Existing directories are skipped. It does not run `git pull`, `git checkout`, `git reset`, or mutate an existing child repo.

Dry-run mode:

```bash
make bootstrap DRY_RUN=1
make bootstrap-backend DRY_RUN=1
```

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

Start shared infra first:

```bash
docker start bic-postgres bic-redis bic-rabbitmq bic-minio
```

Then start services in order:

```bash
cd BIC-lab-service && make dev
cd BIC-agent-service && make dev
cd BIC-agent-portal && pnpm dev
```

Open <http://localhost:5173>.

## PRD Update Flow

When a change affects product behavior:

1. Update `Production-PRD.md` in this root meta repo.
2. Update child Project PRDs only when they refine repo-owned behavior.
3. Implement code changes in child repo PRs.
4. Link implementation PRs back to the PRD PR or commit.

Documentation-only PRD changes can be root-only.

## Trellis Tracking

Track shared Trellis artifacts:

- `.trellis/workflow.md`
- `.trellis/spec/`
- `.trellis/tasks/`
- `.trellis/workspace/`
- `.trellis/scripts/`

Do not track Trellis runtime/pointer/temp files such as `.trellis/.developer`, `.trellis/.current-task`, `.trellis/.runtime/`, `.trellis/.agents/`, `.trellis/.agent-log`, `.trellis/.session-id`, `.trellis/.plan-log`, `.trellis/.backup-*`, caches, and temp files.
