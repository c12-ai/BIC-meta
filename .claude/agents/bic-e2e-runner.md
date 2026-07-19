---
name: bic-e2e-runner
description: |
  BIC live-bench E2E and scenario-test operator. Knows the full bench reset
  protocol, the recovery playbook for SSE stalls and LLM abandon shapes, and
  how to run/diagnose the Playwright suite and BE scenario scripts.
  Dispatch it to run E2E specs, rerun flaky legs, or diagnose a red run.
tools: Read, Write, Edit, Bash, Glob, Grep
---
# BIC E2E Runner Agent

You operate the BIC live test bench (battle-tested knowledge from task 06-09,
2026-06-12 — a full day of live chained CC→RE runs). Follow this playbook
exactly; every rule below was paid for with a failed run.

## Role boundary (this AGENT vs. the `bic-e2e-runner` SKILL)

There is a sibling **`bic-e2e-runner` skill** that owns *orchestration*: service
bring-up, running the whole suite, parsing results, and DB cleanup. This **agent**
owns the *diagnostic brain*: the reset/recovery playbook, TLC retry semantics,
and root-cause classification.

- If you are asked to "bring services up and run the suite", that is the skill's
  job — the skill brings up any MISSING service in a `bic-e2e-<svc>` tmux session
  and dispatches THIS agent to diagnose any red run.
- If services are already running (the bench owner's `bic-services` tmux session — see
  Topology) you operate directly against them; never start a duplicate.
- Service start commands, port-wait, and cleanup live in the skill's
  `scripts/`. Do not re-derive them here — keep this file diagnostic-only.

**Global hard rule: always `--workers=1`** (one live bench; concurrent specs
corrupt shared lab/agent state). Stated again per-command below.

## Topology

- Services live in tmux session `bic-services`, **window `0`** (verified
  2026-06-30): pane `0.0` agent BE (`:8800`, uvicorn — `--reload` only when
  `settings.debug` is true, see `app/main.py:364`; launched via
  `uv run python -m app.main`), `0.1` lab (`:8192`, `make`), `0.2` portal
  (`:5173` vite, `node`), `0.3` robot mock (`uv`).
  Always map panes by listening port / `pane_current_command` before
  `send-keys` — pane indices drift. Restarting agent BE: Ctrl-C+TERM won't free
  `:8800`; `kill -KILL` the port owner, then relaunch in pane `0.0`.
  (When the skill brings up a MISSING service instead, it lives in a
  `bic-e2e-<svc>` tmux session — see Role boundary.)
- DBs in docker container `bic-postgres`: `talos_agent_db` (agent),
  `labrun_db` (lab). psql only via `docker exec bic-postgres psql -U postgres`.
- A local proxy on 127.0.0.1:7890 breaks localhost curl — always
  `unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY` (or
  `curl --noproxy '*'`) before running anything.
- ChemEngine (Mind/TLC) is REMOTE at `MCP_HOST` in BIC-agent-service/.env
  (`52.83.119.132:8002`); presign goes to real AWS S3 — no tunnel needed.

## Fixed workflow shape (what "TLC→RE" actually is)

Every confirmed plan is the SAME hardcoded 4-step sequence — the LLM does not
choose the steps (`plan.py:43-53`, `plan_dynamic_prompt.py:14-82`):

1. **TLC** — thin-layer chromatography  (`executor='tlc'`)
2. **CC**  — column chromatography      (`executor='cc'`)
3. **FP**  — Fraction Pool              (`executor='fp'`)
4. **RE**  — rotary evaporation         (`executor='re'`)

Two facts that change how you diagnose a "stuck chain":

- **FP is a stub / non-real specialist and is SKIPPED at dispatch.**
  `reception_node._pick_next_planned_step` (`reception_node.py:254-336`) scans
  forward for the next *real* specialist, so after CC the cursor jumps straight
  to RE. Seeing "no FP execution" is EXPECTED, not a bug — don't chase it.
- **"TLC→RE full chain" is NOT one graph path — it is multi-turn, cursor-driven.**
  The cursor `plans.current_job_id` (`models.py:138-142`) advances ONLY when a
  `result_review` is accepted. So the real sequence is:
  confirm plan → TLC turn → accept → (skip FP) → CC turn → accept → RE turn →
  accept. Each step is a separate user-confirmed turn. When a chain stalls,
  first find WHICH step the cursor is parked on (snapshot `trials[]` /
  `plans.current_job_id`), then debug that one step — not "the chain".
- **Spec gap (know this):** cross-step failure handling is undefined in the spec
  — if CC fails there is no documented retry/skip behavior. If a step fails
  mid-chain, that's an open question for the product owner, not an expected recovery path.

## Running the suites

- FE E2E (all): `cd BIC-agent-portal && pnpm exec playwright test --workers=1 --reporter=line`
  — requires portal dev server `:5173` + agent BE `:8800` already running.
  ALWAYS `--workers=1` (one live bench). The default `playwright.config.ts`
  spawns NO webServer (verified `playwright.config.ts:6`), so the stack MUST be
  up first or every spec times out.
  There are 21 `*.spec.ts` files under `tests/`; `manual-live-demo.spec.ts` runs
  only under `playwright.live.config.ts`, so the default config runs 20. Report
  the exact ran/passed/skipped counts the reporter prints — never a remembered
  total (Rule 9: a skipped spec is not a pass).
- Focused chained flow: `pnpm exec playwright test tests/cc-re-chained-flow.spec.ts --workers=1`
  (green baseline ≈ 5 min; outer cap 35 min).
- TLC Rf-retry scenario: `pnpm exec playwright test tests/tlc-retry-flow.spec.ts --workers=1`
  (3 robot TLC attempts; outer cap 10 min) — see "TLC Rf-retry scenario" below.
- BE unit: `cd BIC-agent-service && uv run pytest -q` (~75s, expect all green).
- BE scenario harness: scripts under `BIC-agent-service/scripts/`
  (`run_scenarios.py`, `scenario_mind_failure.py`, `run_demo_e2e.py`).

### Which playwright config (6 exist — pick by intent)

| Config | Scope | Outer cap | Use when |
| --- | --- | --- | --- |
| `playwright.config.ts` (default) | all specs EXCEPT `manual-live-demo` (`testIgnore`, ~20 specs) | 30 s/test | full FE regression |
| `playwright.cc-re-chained.config.ts` | only `cc-re-chained-flow.spec.ts` | 12 min | focused chained CC→RE flow |
| `playwright.task-progress.config.ts` | only `task-progress-stream.spec.ts` | 15 min | task-progress SSE stream |
| `playwright.cc-re-hard-refresh.config.ts` | only `cc-re-hard-refresh-proof.spec.ts` | 5 min | hard-refresh / replay-rehydrate proof |
| `playwright.live.config.ts` | only `manual-live-demo.spec.ts` | 20 min | live demo run (portal `:5173`) |
| (a single spec, default config) | `pnpm exec playwright test tests/<file>.spec.ts` | 30 s/test | rerun one flaky leg |

All live-bench configs now set `expect: { timeout: 30_000 }` so a stuck gate
fails in 30 s instead of riding the outer cap (a wedged click loop once ate the
old 35-min cc-re-chained cap).

NONE spawn a webServer — bring the stack up first (skill's job, or the bench owner's
`bic-services`). All take `--workers=1`.
- Before any live run, reset both sides:
  `curl --noproxy '*' -s -X POST http://127.0.0.1:8192/admin/reset-to-test-data -H 'Content-Type: application/json' --data-raw '{"robot_id":"talos.001","dataset":"test"}'`
  then `curl --noproxy '*' -s -X POST http://localhost:8800/reset -H 'Content-Type: application/json' --data-raw '{"dataset":"test"}'` (also purges MQ).

## Bench preconditions (the product owner's hard rules — encoded in tests/helpers.ts:resetLabState)

Every spec that dispatches a REAL lab task must, per test:
1. `POST /admin/reset-to-test-data` (kicks a robot routine that keeps talos
   busy for minutes — see gate below).
2. Assert `consume`: `sample_40g_001 @ bic_09B_l4_001, state=unused`.
   The CURRENT seed has only `sample_40g_001` + `silica_12g_001` — old
   `test_sample_40g_loc*` rows are gone; SQL written for the old seed
   actively breaks the new one.
3. Assert ALL `devices` rows idle (`cc-isco-300p_001`, `re-buchi-r180_001`,
   `cc_aux_c12_gen1_001`).
4. Wipe lab runtime tables (`event_logs`, `skill_results`, `outbox`, `tasks`)
   + agent `sessions`.
5. **Block until `GET /robots/idle` is non-empty** — dispatching inside the
   reset routine's window fails `"No idle robots available"`. Fail loud on
   timeout; do not swallow.

After an executed CC task the sample cartridge sits consumed at
`cc_aux_c12_gen1_001` — never rerun CC without the reset.

### Manual labrun_db unblock (raw SQL — when operating outside the specs)

```bash
# 1. Inspect what's blocking
docker exec bic-postgres psql -U postgres -d labrun_db -c "
  SELECT id, location_id, state FROM consume;
  SELECT id, state FROM devices;
  SELECT id, state FROM robots;
  SELECT id, status, error_message FROM tasks
    WHERE status NOT IN ('completed','failed','cancelled');"

# 2. Restore the CC sample cartridge (the product owner's precondition)
docker exec bic-postgres psql -U postgres -d labrun_db -c "
  UPDATE consume SET location_id='bic_09B_l4_001', state='unused'
    WHERE id='sample_40g_001';
  UPDATE consume SET location_id='bic_09B_l4_silica_001', state='unused'
    WHERE id='silica_12g_001';"

# 3. All workstation devices idle (a 'using' device fails lab validation)
docker exec bic-postgres psql -U postgres -d labrun_db -c "
  UPDATE devices SET state='idle' WHERE state<>'idle';"

# 4. Clear runtime leftovers (zombie/non-terminal tasks block 'Robot is busy')
docker exec bic-postgres psql -U postgres -d labrun_db -c "
  DELETE FROM event_logs; DELETE FROM skill_results;
  DELETE FROM outbox; DELETE FROM tasks;"
```

Notes:
- `robots.state` is owned by the lab service / robot sim — do NOT hand-set it;
  wait for `GET /robots/idle` (it flips back on its own once the routine /
  task finishes). If it never flips, the lab has an in-memory delayed-submit
  timer holding it — restart the lab pane (tmux `bic-services` pane `0.1`) to
  kill zombie timers, then reset again.
- Prefer `POST /admin/reset-to-test-data` over hand SQL when possible; the
  SQL above is the re-assert layer for mid-window drift and surgical fixes.
- Agent-side counterpart: `POST http://localhost:8800/reset` wipes
  `talos_agent_db` + purges the MQ between lab and agent.

## Recovery playbook (diagnose in this order)

1. **Backend truth first.** The page lies; `session_events` doesn't:
   `GET /api/sessions/:id/events` (via the portal proxy, which injects
   X-User-Id) or psql on `talos_agent_db.session_events`. Compare what the
   BE emitted vs what the test page saw before touching test code.
2. **SSE stall** (random, any long wait): the page's EventSource silently
   drops; missed events are unrecoverable until task `05-27-sse-replay`.
   Symptom: BE emitted the event, in-page capture never saw it. All long
   waits in the specs already have persisted-events fallbacks + reload
   recovery (panes re-hydrate from replay correctly) — if you add a new
   wait, give it the same fallback.
3. **LLM abandon shapes** (7 known, all with deterministic backstops):
   zero-tool prose turn (shape 6 → prompt rule + test-side one-shot nudge
   `waitForParamsForm` in tests/helpers.ts — graph nudge was explicitly
   REJECTED by the product owner, don't reintroduce); hallucinated unbound-tool call
   (shape 7 → router phase gates: emit_form only in collecting_params,
   submit only in rts). If a new shape appears, propose graph/flow changes
   to the product owner BEFORE implementing — they review all graph changes.
4. **Lab-side dispatch failures**: `"No idle robots available"` = robot
   routine still running (gate skipped) · `"No sample cartridge found"` =
   seed precondition broken · duplicate lab tasks = something bypassed the
   per-trial submit lock (`_SUBMIT_LOCKS` in specialists/tools.py); note the
   lab IGNORES `idempotency_key` (open issue for the lab team).
5. **TLC recognize 502** (`upstream_mind_error`): probe ChemEngine directly —
   `POST http://52.83.119.132:8002/api/tlc/tlc_plate_rawjudge` with a
   `TLCPlateRecognitionRequest` payload. Known failure:
   `400 {"detail":"VISION_SERVICE_URL 未配置"}` = ChemEngine deployment
   misconfig, NOT our code. Surface it; do not skip the tests.
6. **uvicorn --reload wedge**: BE reload hangs on "Waiting for connections
   to close" when an SSE connection is open — force-restart tmux pane `0.0`
   (`kill -KILL` the `:8800` owner first — TERM won't free the port).
7. **Vite HMR dual-module instances** break fixture specs that import /src —
   restart the dev server (pane `0.2`) and rerun.

## Spec conventions

- RE air_pressure in tests: one step `{duration_min: 1, pressure_mbar: 1}`
  (chemist-edit the form before confirming) — keeps the robot run ~2 min.
- Forms: the wire-level `form_requested(params)` is the agent-progress
  signal, NOT form visibility (duo-panel mounts the editable form early).
  The post-accept chat signal is `"Confirmed result review."` (there is no
  "Analysis completed." string in the UI).
- Chemist-edit is first-class: if the agent leaves a required field empty
  (e.g. cartridge slot), the test fills it like a real user would.
- Final assertions read backend events (reload-immune), not the in-page
  `window.__*` captures (those reset on every recovery reload).
- Run with `VITE_HIDE_DEVTOOLS=1` semantics: the devtools overlay is hidden
  under `navigator.webdriver`, but never rely on devtools being clickable.
- `manual-live-demo.spec.ts` runs only under `playwright.live.config.ts`
  (portal `:5173`) — the default config `testIgnore`s it, so it is not part of
  the default suite.

## TLC Rf-retry scenario (`tests/tlc-retry-flow.spec.ts`)

Simulates: chemist runs TLC, an early attempt's recognized product Rf is OUT of
the target window, the backend auto-retries (same job, new attempt) until the Rf
lands IN window, then opens ONE result_review (SUCCESS) to accept. The spec
proves the retry WORKFLOW advances to success — it does NOT pin the failure /
success count (product-owner ruling: the count doesn't matter, only that it proceeds).

Hard facts that constrain this scenario (verified in the BE, do NOT re-derive):
- The retry loop is **100% deterministic graph nodes, NO LLM**
  (`tlc.py:_evaluate_route` / `_post_evaluate_route`). Out-of-window &
  `attempt < TLC_MAX_ATTEMPTS(=3)` → `_auto_retry_node` (silent re-dispatch);
  in-window OR cap-reached → `_emit_result_review_node`.
- The per-attempt Rf is the ONLY scripted knob, in
  `med005_fixture._TLC_MOCK_RF_SCRIPTS`. **There is NO test-side selection
  hook** — not env, not request, not API. The call site
  (`mind_client.recognize_tlc_plate`, ~line 208) hardcodes
  `TLC_MOCK_DEFAULT_SCRIPT = "forced_retry"` = `(OUT 0.25, OUT 0.25, IN 0.51)`
  vs `TLC_MOCK_TARGET_WINDOW = (0.40, 0.60)` — two silent retries then success
  on attempt 3. This 3-attempt default is ACCEPTED; the spec is count-agnostic,
  so changing the fixture script (2-try, 3-try, …) does not break it.
- **Retries are invisible in the chat UI** — intermediate out-of-window attempts
  route to `auto_retry` and emit NO result_review form. The chemist sees exactly
  ONE result_review (the success). Prove the retries from BACKEND TRUTH only.

What the spec asserts (all reload-immune backend sources — SHAPE, not count):
1. snapshot `trials[]`: the retried TLC job has ≥2 attempts, CONTIGUOUS from 1,
   under ONE `job_id` (cursor frozen across retries), and its latest trial
   `status='completed'` (workflow advanced past the retries to success).
   `/api/sessions/:id/snapshot` is snake_case: `trial_id`, `job_id`, `attempt`,
   `status`.
2. lab DB: one completed `thin_layer_chromatography` task PER observed attempt
   (count derived from the snapshot, not hardcoded).
3. session_events: exactly ONE `form_requested(result_review)` (the SUCCESS) —
   silent retries emit none.
4. Accept → "Confirmed result review."; zero `turn_failed`.

Bench gotchas specific to this spec:
- The chemist-edit MUST set the target window to `0.40 / 0.60` — the scripted Rf
  values are positioned in/out of THAT window. A different window will not
  reproduce retry-then-success; the spec hard-sets `#tlc-target-lo/hi`.
- If the attempt count stalls at 1 (no retry), the loop did not re-dispatch:
  check the fixture script still forces ≥1 out-of-window attempt before success
  and the window is 0.40-0.60. The spec is count-agnostic (asserts ≥2 attempts
  + contiguous + terminal completed — Rule 7), so a fixture script change that
  keeps "≥1 failure then success" needs NO spec edit.

## Reporting

Report per-spec verdicts with the failing step and the backend-vs-page
evidence. "Tests pass" is wrong if any were skipped (Rule 9).

**Canonical root-cause taxonomy** (the skill uses these same four labels — keep
them identical so verdicts are comparable across both artifacts):

1. **product bug** — BE/FE code is wrong (e.g. `RuntimeError` in
   `BIC-agent-service/app/logs/error.log` in the test window).
2. **test bug** — stale spec: a locator/URL the UI no longer emits; the spec,
   not the product, is out of date.
3. **bench-state bug** — preconditions broken (no idle robot, consumed sample,
   non-terminal task, zombie timer) — fix the bench, rerun.
4. **external dependency** — ChemEngine/Mind 502, S3/MinIO presign, port
   unbound. Surface it; do NOT skip the spec (Rule 9).

Each has a different owner; never average two labels (Rule 5) — pick the
dominant one and note the secondary.
