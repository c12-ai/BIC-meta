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

> **端口口径（定档 2026-07-10）**：全平台端口分配以 `ops/port-allocation-2026-07-10.md`（权威源 `BIC-infra` README）为准。已在位不迁：lab `:8192` · BE `:8800` · portal `:5173`（`5174` 废止）· chem `:8010` · Mind 代理 `:8011` · Phoenix `:6006`/`:4317`。易撞默认口 `+10000`：**Keycloak `:18080`**（新增硬依赖，8080+10000）· Grafana 未来 `:13000`。禁用清单 `3000/5000/7000/8000/8080`。基建：postgres 单实例 `bic-postgres:5432`（`5433` 退役，#153 收敛，全库归 infra `postgres-databases.txt` 管）· redis `:6379` · rabbitmq `:5672`(+`15672`) · minio `:9000`(+`9001`)。

1. PostgreSQL: Deployed through docker. Container ID: fe20b9a21cbfe1117b5da64ecf88396bb3aa7ceabe01e12e016e7302aa6de3b6
2. RabbitMQ: Used by LabService to get update from Robot and then push to Agent Side. Container ID: 2431d43650888a896824cfdffa7d29df9e424b6ff3016031279c87e4a360fb0f
3. MinIO: Docker Container ID: 2a801bee136c178407ee7d1e2b606fed7dcca941a681e91053e1779d32973aa2
4. tmux session `bic-services` (window `0`, verified 2026-07-03; DRIFTS — never trust a cached roster): current mapping `0.0` lab (`:8192`), `0.1` agent BE (`:8800`, `make dev`), `0.2` portal (`:5173`, node), `0.3` robot mock (uv). Always map panes by listening port / `pane_current_command` before `send-keys`. Restarting agent BE: Ctrl-C+TERM won't free `:8800` — `kill -KILL` the port owner, then relaunch in its pane.
5. **Cold start — use the make entry (from the meta repo root):**
   ```bash
   make up        # idempotent: docker+infra, wait-for-pg, DB create, keycloak seed, dep sync, tmux bic-services (lab→BE→portal→mock→chem), each health-gated
   make doctor    # read-only checkup; GREEN = bench up. Every red card prints its own fix command.
   ```
   `make up` is safe to re-run (skips anything already healthy) and `make up DRY=1` previews the plan without touching a live bench. `BIC_ROOT` is autodetected for both known layouts — service repos nested inside this repo, or this repo cloned next to them — so no override is needed on a standard checkout. The scripts encode every trap below (retired-5433 listener check, proxy unset for BE, portal white-screen check, DB existence); `ops/run-latest-2026-07-10.md` is now the troubleshooting appendix that `doctor` points to — no need to read it end-to-end.

   > **Auth 口径(定档 2026-07-13)**:lab-service 对除 `GET /`、`/health*` 外的所有 HTTP 路由强制校验 Keycloak JWT;portal 带用户 token,agent BE 带 `bic-agent-service` 服务账号 token。`make up` 会自愈必需的 dev 键(BE `KEYCLOAK_CLIENT_ID/SECRET`、lab `KEYCLOAK_ISSUER_URL`,只增不改——LAN bench 的 issuer 覆盖值不会被动);`make doctor` 有三张 Auth 卡(BE secret / 401 探针 / 服务 token 往返)。**拉了 auth 相关合并后必须显式重启 lab+BE+mock**(`bash scripts/bic-env/restart.sh <svc>`)——`make up` 跳过健康服务,老进程继续跑老代码;lab 若杀不干净会有孤儿 worker 攥着 socket 诈尸,`pkill -KILL -f BIC-lab-service` 清场(doctor 红卡会指出)。手动 curl lab 一律带 `-H "Authorization: Bearer $(scripts/bic-env/get-token.sh)"`(300s 有效)。逃生阀:lab `.env` 加 `LAB_AUTH_MODE=off`+重启(启动 WARN,查完撤)。完整清单:`ops/auth-bench-2026-07-13.md`。

   BIC-chem-service is **optional** and only affects ELN enrichment (FW / moles / compound-name fill-ins). The main workflow still runs without it; missing enrichment fields are omitted from the report. Current port authority is `:8010` (the old infra `:8810` was retired). Host-mode Agent Service config is `CHEM_SERVICE_HOST=127.0.0.1`, `CHEM_SERVICE_PORT=8010`; an infra/docker network deployment should point `CHEM_SERVICE_HOST` at the service DNS name but still keep port `8010`.

   <details><summary>Manual fallback (if <code>make</code> is unavailable / debugging a single step)</summary>

   1. `open -a Docker`, wait for daemon, then `docker start bic-postgres bic-rabbitmq bic-minio bic-keycloak` (bic-redis auto-starts). Keycloak `:18080` is a hard dep now (BE only accepts Bearer JWT); its issuer must match BE `KEYCLOAK_ISSUER_URL` + portal `VITE_OIDC_AUTHORITY` — all three `http://localhost:18080/realms/bic` (see `ops/run-latest-2026-07-10.md` §5).
   2. each repo after `git checkout main`: sync deps first — portal `pnpm install`, BE/lab `uv sync` (the Keycloak batch added `react-oidc-context`; skipping `pnpm install` white-screens the portal with an import error).
   3. Optional for ELN enrichment only: start chem-service on `:8010`. `make up` / `make restart-chem` use the local `BIC-chem-service` checkout when present; the infra image path is `cd BIC-infra && make chem-up && make chem-smoke`, and `make chem-smoke` verifies `/health/readiness` plus `POST /molecular-weight`.
   4. pane `0.0` lab: `cd BIC-lab-service && make dev` — wait for `:8192/health` 200 (agent BE's dep-check needs it)
   5. pane `0.1` agent BE: `cd BIC-agent-service && make dev`
   6. pane `0.2` portal: `cd BIC-agent-portal && pnpm dev`
   7. pane `0.3` robot mock: `cd mars_interface_mock && uv run mars-interface-mock`
   `curl` health checks need `--noproxy '*'` (local 127.0.0.1:7890 proxy masks localhost). Portal health ≠ `:5173` HTTP 200 alone (dev server up ≠ page compiles) — also confirm a real load: `curl --noproxy '*' http://localhost:5173/src/main.tsx` returns JS (not an error), or open the page.
   </details>

## Test Scenarios.
1. E2E (FE <-> BE <-> LabService) test case: @$BIC_ROOT/BIC-agent-portal/tests. Run with playwright.test
2. BE Scenarios test: All cases and scenarios under: @$BIC_ROOT/BIC-agent-service/scripts
3. Live-bench E2E / scenario testing: dispatch the `bic-e2e-runner` agent (`@.claude/agents/bic-e2e-runner.md`) — it carries the full bench playbook (reset preconditions, SSE-stall + LLM-abandon recovery, ChemEngine probe). Don't re-derive the protocol in the main session.



## Command

#### BIC-Agent-Service

Reset API: `curl -X POST http://localhost:8800/reset | jq`

This API will reset AgentService PostgresDB and purge MQ between LabService and AgentService

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
    "robot_id": "talos.001"
}'
```

This will reset LabService DB. Lab-service requires a Keycloak Bearer JWT on all
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

### Triage labels

两根轴（定档 2026-07-16）：**分诊轴** `needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`（engineering skills 读它）；**生命周期轴** `stage:已析根因` → `stage:已实现待复测` → `stage:已验证`（S1/S2/S3 用）。`stage:待调查` / `stage:待裁定` / `stage:待修复` 已退役删除。See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` + `docs/adr/` at the repo root, created lazily by `/domain-modeling`. See `docs/agents/domain.md`.
