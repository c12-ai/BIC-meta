Project-level Production PRD: `Production-PRD.md` — read it before any product/business-rule work (cross-service behavior, workflow rules, acceptance criteria). The `prd` skill governs edits to it.

This is BIC Project folder which contains multiple repo.

<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->

## Folder Structure

1. BIC-agent-service: agent backend. Written in Langgraph. Communicate with Nexus. @$BIC_ROOT/BIC-agent-service
2. BIC-agent-portal: agent frontend. (No BFF anymore) @$BIC_ROOT/BIC-agent-portal
3. BIC-lab-service: (Nexus) manage lab status (LIMS), orch and report exp task, communicate with robot and backend using MQ. @$BIC_ROOT/BIC-lab-service
4. BIC-shared-types: Defined cross team shared object type @$BIC_ROOT/BIC-shared-types
5. BIC-chem-service: stateless RDKit molecular-weight calculator used by Agent Service ELN report enrichment. Optional for the main workflow; if absent, ELN downloads still work but FW/mole fields are omitted.

## Local Dev Infra:

> **Ports**: platform-wide allocation follows `ops/port-allocation-2026-07-10.md` (authoritative source: `BIC-infra` README). App services: lab `:8192` · BE `:8800` · portal `:5173` (`5174` is dead) · chem `:8010` · Mind proxy `:8011` · Phoenix `:6006`/`:4317`. Collision-prone defaults shift `+10000`: **Keycloak `:18080`** (hard dependency) · Grafana (future) `:13000`. Never bind `3000/5000/7000/8000/8080`. Infra: single postgres instance `bic-postgres:5432` (`5433` is dead; every database is registered in `BIC-infra` `postgres-databases.txt`) · redis `:6379` · rabbitmq `:5672` (+`15672` mgmt) · minio `:9000` (+`9001` console).

1. PostgreSQL: docker container `bic-postgres`.
2. RabbitMQ: docker container `bic-rabbitmq`. Used by LabService to get updates from the Robot and push them to the Agent side.
3. MinIO: docker container `bic-minio`.
4. tmux session `bic-services` (window `0`). The pane layout DRIFTS — never trust a cached roster; always identify panes by listening port / `pane_current_command` before `send-keys`. Typical layout: `0.0` lab (`:8192`), `0.1` agent BE (`:8800`, `make dev`), `0.2` portal (`:5173`, node), `0.3` robot mock (uv). Restarting agent BE: Ctrl-C+TERM won't free `:8800` — `kill -KILL` the port owner, then relaunch in its pane.
5. **Cold start — use the make entry (from the meta repo root). Every service now REQUIRES a stage:**
   ```bash
   make up STAGE=local        # idempotent: docker+infra, wait-for-pg, DB create, keycloak seed, dep sync, migrations, tmux bic-services (lab→BE→portal→mock→chem), each health-gated
   make doctor STAGE=local    # read-only checkup; GREEN = bench up. Every red card prints its own fix command.
   ```
   **Stage model:** each service reads its own `.env.<stage>` file (`STAGE=local|dev|prod`, default `local`) and hard-exits if the stage/file is missing — there is no plain `.env`. The orchestrator only launches; it NEVER writes config. Each repo's `.env.<stage>` is the single source of truth, owned by the developer (copy `.env.<stage>.example` → `.env.<stage>` once; portal's local file is `.env.localdev`, a Vite convention). To switch mock↔real Mind / local MinIO↔AWS S3, edit that repo's `.env.<stage>` (e.g. `MIND_MOCK_MODE=false`, `MCP_HOST=...`) and `make restart-<svc> STAGE=local`. The orchestrator is current-network-only; to deploy to a server, SSH in and run there. All orchestrator logic lives in `scripts/bic-env/` (`up.sh`, `down.sh`, `restart.sh`, `doctor.sh`, `pull.sh`, `get-token.sh`, `common.sh`). `make up STAGE=local DRY=1` previews without touching a live bench. **`BIC_ROOT` resolution**: explicit env/make-arg > the gitignored `.bic-env` machine pin > autodetect — on a machine with multiple checkouts, read `.bic-env` before assuming which tree the bench actually runs. `ops/run-latest-2026-07-10.md` is the troubleshooting appendix `doctor` points to.

   Per-repo manual start (from each repo, stage required — no default): `make dev ENV=local` (agent BE, lab) · `pnpm dev:local` (portal) · `APP_ENV=local uv run mars-interface-mock` (mock). A bare `make dev` / `pnpm dev` FAILS with a "pick a stage" message. Use `export`-style / make-arg so uvicorn `--reload` subprocesses inherit the stage.

   > **Auth**: lab-service enforces Keycloak JWT on every HTTP route except `GET /` and `/health*`; the portal sends a user token, agent BE sends the `bic-agent-service` service-account token. Auth keys (BE `KEYCLOAK_CLIENT_ID/SECRET`, lab `KEYCLOAK_ISSUER_URL`) come from each repo's `.env.<stage>` — `make up` never heals/rewrites any `.env` (stage files are developer-owned; on a missing file `up.sh` fails loud and prints the `cp .env.<stage>.example` fix); `make doctor` has Auth cards (reads `.env.<stage>`: BE secret / 401 probe / service-token round trip). **After pulling auth-related merges, explicitly restart lab+BE+mock** (`make restart-<svc> STAGE=local`) — `make up` skips healthy services, so old processes keep running old code; if lab won't die cleanly an orphan worker can hold the socket, `pkill -KILL -f BIC-lab-service` clears it (a doctor red card points this out). Manual curls against lab always carry `-H "Authorization: Bearer $(scripts/bic-env/get-token.sh)"` (valid 300 s). Escape hatch: add `LAB_AUTH_MODE=off` to lab's `.env.local` + restart (startup WARN; revert after debugging). Full checklist: `ops/auth-bench-2026-07-13.md`.

   BIC-chem-service is **optional** and only affects ELN enrichment (FW / moles / compound-name fill-ins). The main workflow still runs without it; missing enrichment fields are omitted from the report. Current port authority is `:8010` (the old infra `:8810` was retired). Host-mode Agent Service config is `CHEM_SERVICE_HOST=127.0.0.1`, `CHEM_SERVICE_PORT=8010`; an infra/docker network deployment should point `CHEM_SERVICE_HOST` at the service DNS name but still keep port `8010`.

   <details><summary>Manual fallback (if <code>make</code> is unavailable / debugging a single step)</summary>

   1. `open -a Docker`, wait for daemon, then `docker start bic-postgres bic-rabbitmq bic-minio bic-keycloak` (bic-redis auto-starts). Keycloak `:18080` is a hard dep now (BE only accepts Bearer JWT); its issuer must match BE `KEYCLOAK_ISSUER_URL` + portal `VITE_OIDC_AUTHORITY` — all three `http://localhost:18080/realms/bic` (see `ops/run-latest-2026-07-10.md` §5).
   2. each repo after `git checkout main`: sync deps first — portal `pnpm install`, BE/lab `uv sync` (the Keycloak batch added `react-oidc-context`; skipping `pnpm install` white-screens the portal with an import error).
   3. Optional for ELN enrichment only: start chem-service on `:8010`. `make up` / `make restart-chem` use the local `BIC-chem-service` checkout when present; the infra image path is `cd BIC-infra && make chem-up && make chem-smoke`, and `make chem-smoke` verifies `/health/readiness` plus `POST /molecular-weight`.
   4. pane `0.0` lab: `cd BIC-lab-service && make dev ENV=local` — wait for `:8192/health` 200 (agent BE's dep-check needs it)
   5. pane `0.1` agent BE: `cd BIC-agent-service && make dev ENV=local`
   6. pane `0.2` portal: `cd BIC-agent-portal && pnpm dev:local`
   7. pane `0.3` robot mock: `cd mars_interface_mock && APP_ENV=local uv run mars-interface-mock`
   > Every service REQUIRES a stage (no default `.env`): `make dev ENV=local` / `pnpm dev:local` / `APP_ENV=local ...`. A bare `make dev` or `pnpm dev` fails with a "pick a stage" message.
   `curl` health checks need `--noproxy '*'` (local 127.0.0.1:7890 proxy masks localhost). Portal health ≠ `:5173` HTTP 200 alone (dev server up ≠ page compiles) — also confirm a real load: `curl --noproxy '*' http://localhost:5173/src/main.tsx` returns JS (not an error), or open the page.
   </details>

## Test Scenarios.
1. E2E (FE <-> BE <-> LabService) test case: @$BIC_ROOT/BIC-agent-portal/tests. Run with playwright.test
2. BE Scenarios test: All cases and scenarios under: @$BIC_ROOT/BIC-agent-service/scripts
3. Live-bench E2E / scenario testing: dispatch the `bic-e2e-runner` agent (`@.claude/agents/bic-e2e-runner.md`) — it carries the full bench playbook (reset preconditions, SSE-stall + LLM-abandon recovery, ChemEngine probe). Don't re-derive the protocol in the main session.



## Command

#### BIC-Agent-Service

Reset API: `curl -X POST http://localhost:8800/reset -H 'Content-Type: application/json' --data-raw '{"dataset":"test"}' | jq`

This API will reset AgentService PostgresDB and purge MQ between LabService and AgentService. `dataset` is REQUIRED (`"test"` = schema-only empty; `"demo"` = re-insert the captured demo snapshot — see BIC-agent-service `scripts/capture_demo_snapshot.py`).

#### BIC-Lab-Service

Reset API: 

```bash
curl --location --request POST 'http://127.0.0.1:8192/admin/reset-to-test-data' \
--header "Authorization: Bearer $(scripts/bic-env/get-token.sh)" \
--header 'User-Agent: Apifox/1.0.0 (https://apifox.com)' \
--header 'Content-Type: application/json' \
--header 'Accept: */*' \
--header 'Host: 127.0.0.1:8192' \
--header 'Connection: keep-alive' \
--data-raw '{
    "robot_id": "talos.001",
    "dataset": "test"
}'
```

This will reset LabService DB. `dataset` is REQUIRED (`"test"` = canonical seed; `"demo"` = captured post-run bench snapshot, frozen at the same moment as the agent-side snapshot — see BIC-lab-service `scripts/capture_demo_snapshot.py`). Lab-service requires a Keycloak Bearer JWT on all
non-health routes; `scripts/bic-env/get-token.sh` prints a service-account token
(valid 300 s) for manual calls like this.

## Working Practices

- Gate chains short-circuit — re-run the WHOLE chain after any fix: a `a && b && c` gate that fails at `b` never ran `c`. After fixing `b`, re-run the full chain from the top, and only report per-gate results the chain actually printed.

## SOP Index

Load only the SOP that matches the current work.

| SOP / Skill | Use when | Link |
|---|---|---|
| `prd` | Updating, creating, relocating, splitting, merging, or reviewing Production PRD / Project PRD content; deciding whether requirements belong at root or child-repo level | `@.claude/skills/prd/SKILL.md` |
| `bump-version` | The product owner asks to bump, release, or cut a package version | `@.claude/skills/bump-version/SKILL.md` |
| `pr-stack` | One topic/issue produces ≥2 PRs — same repo: stacked PRs (`gh stack`) are the default; cross-repo: per-repo stacks + BIC-meta tracking issue | `@.claude/skills/pr-stack/SKILL.md` |

## Agent skills

### Issue tracker

GitHub issues in `c12-ai/BIC-meta`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### GitHub bot identity

Identity follows who drives the session (ruling): **interactive sessions** (a developer directing the agent, including having it write code or open PRs) use the developer's own `gh` identity — switch nothing; **fully autonomous sessions** (cron jobs, batch pipelines, unattended dispatch) switch to the bot before GitHub writes: `export GH_TOKEN=$(scripts/gh-app/gh-app-token.sh)` — authored as `c12-apex-dev[bot]`, 1 h token auto-cached. Reads work under either identity. Setup and details: `docs/agents/github-bot.md`.

### Triage labels

Labels run on two axes: the **triage axis** `needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix` (read by the engineering skills), and the **lifecycle axis** `stage:已析根因` → `stage:已实现待复测` → `stage:已验证` (used by S1/S2/S3; the label strings are literal identifiers — do not translate them). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` + `docs/adr/` at the repo root, created lazily by `/domain-modeling`. See `docs/agents/domain.md`.
