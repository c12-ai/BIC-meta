Project-level Production PRD: @Production-PRD.md

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

1. BIC-agent-service: agent backend. Written in Langgraph. Communicate with Nexus. @/Users/drakezhou/Development/BIC/BIC-agent-service
2. BIC-agent-portal: agent frontend. (No BFF anymore) @/Users/drakezhou/Development/BIC/BIC-agent-portal
3. BIC-lab-service: (Nexus) manage lab status (LIMS), orch and report exp task, communicate with robot and backend using MQ. @/Users/drakezhou/Development/BIC/BIC-lab-service
4. BIC-shared-types: Defined cross team shared object type @/Users/drakezhou/Development/BIC/BIC-shared-types

## Local Dev Infra:

> **端口口径（定档 2026-07-10）**：全平台端口分配以 `ops/port-allocation-2026-07-10.md`（权威源 `BIC-infra` README）为准。已在位不迁：lab `:8192` · BE `:8800` · portal `:5173`（`5174` 废止）· chem `:8010` · Mind 代理 `:8011` · Phoenix `:6006`/`:4317`。易撞默认口 `+10000`：**Keycloak `:18080`**（新增硬依赖，8080+10000）· Grafana 未来 `:13000`。禁用清单 `3000/5000/7000/8000/8080`。基建：pg-bic `:5432`/pg-talos `:5433` · redis `:6379` · rabbitmq `:5672`(+`15672`) · minio `:9000`(+`9001`)。

1. PostgreSQL: Deployed through docker. Container ID: fe20b9a21cbfe1117b5da64ecf88396bb3aa7ceabe01e12e016e7302aa6de3b6
2. RabbitMQ: Used by LabService to get update from Robot and then push to Agent Side. Container ID: 2431d43650888a896824cfdffa7d29df9e424b6ff3016031279c87e4a360fb0f
3. MinIO: Docker Container ID: 2a801bee136c178407ee7d1e2b606fed7dcca941a681e91053e1779d32973aa2
4. tmux session `bic-services` (window `0`, verified 2026-07-03; DRIFTS — never trust a cached roster): current mapping `0.0` lab (`:8192`), `0.1` agent BE (`:8800`, `make dev`), `0.2` portal (`:5173`, node), `0.3` robot mock (uv). Always map panes by listening port / `pane_current_command` before `send-keys`. Restarting agent BE: Ctrl-C+TERM won't free `:8800` — `kill -KILL` the port owner, then relaunch in its pane.
5. Cold start (after reboot / all down), in order:
   1. `open -a Docker`, wait for daemon, then `docker start bic-postgres bic-rabbitmq bic-minio bic-keycloak` (bic-redis auto-starts). Keycloak `:18080` is a hard dep now (BE only accepts Bearer JWT); its issuer must match BE `KEYCLOAK_ISSUER_URL` + portal `VITE_OIDC_AUTHORITY` — all three `http://localhost:18080/realms/bic` (see `ops/run-latest-2026-07-10.md` §5).
   2. each repo after `git checkout main`: sync deps first — portal `pnpm install`, BE/lab `uv sync` (the Keycloak batch added `react-oidc-context`; skipping `pnpm install` white-screens the portal with an import error).
   3. pane `0.0` lab: `cd BIC-lab-service && make dev` — wait for `:8192/health` 200 (agent BE's dep-check needs it)
   4. pane `0.1` agent BE: `cd BIC-agent-service && make dev`
   5. pane `0.2` portal: `cd BIC-agent-portal && pnpm dev`
   6. pane `0.3` robot mock: `cd mars_interface_mock && uv run mars-interface-mock`
   `curl` health checks need `--noproxy '*'` (local 127.0.0.1:7890 proxy masks localhost). Portal health ≠ `:5173` HTTP 200 alone (dev server up ≠ page compiles) — also confirm a real load: `curl --noproxy '*' http://localhost:5173/src/main.tsx` returns JS (not an error), or open the page.

## Test Scenarios.
1. E2E (FE <-> BE <-> LabService) test case: @/Users/drakezhou/Development/BIC/BIC-agent-portal/tests. Run with playwright.test
2. BE Scenarios test: All cases and scenarios under: @/Users/drakezhou/Development/BIC/BIC-agent-service/scripts
3. Live-bench E2E / scenario testing: dispatch the `bic-e2e-runner` agent (`@.claude/agents/bic-e2e-runner.md`) — it carries the full bench playbook (reset preconditions, SSE-stall + LLM-abandon recovery, ChemEngine probe). Don't re-derive the protocol in the main session.



## Command

#### BIC-Agent-Service

Reset API: `curl -X POST http://localhost:8800/reset | jq`

This API will reset AgentService PostgresDB and purge MQ between LabService and AgentService

#### BIC-Lab-Service

Reset API: 

```bash
curl --location --request POST 'http://127.0.0.1:8192/admin/reset-to-test-data' \
--header 'User-Agent: Apifox/1.0.0 (https://apifox.com)' \
--header 'Content-Type: application/json' \
--header 'Accept: */*' \
--header 'Host: 127.0.0.1:8192' \
--header 'Connection: keep-alive' \
--data-raw '{
    "robot_id": "talos.001"
}'
```

This will reset LabService DB.

## Working Practices

- Gate chains short-circuit — re-run the WHOLE chain after any fix: a `a && b && c` gate that fails at `b` never ran `c`. After fixing `b`, re-run the full chain from the top, and only report per-gate results the chain actually printed.

## SOP Index

Load only the SOP that matches the current work.

| SOP / Skill | Use when | Link |
|---|---|---|
| `prd` | Updating, creating, relocating, splitting, merging, or reviewing Production PRD / Project PRD content; deciding whether requirements belong at root or child-repo level | `@.claude/skills/prd/SKILL.md` |
| `bump-version` | Drake asks to bump, release, or cut a package version | `@.claude/skills/bump-version/SKILL.md` |
