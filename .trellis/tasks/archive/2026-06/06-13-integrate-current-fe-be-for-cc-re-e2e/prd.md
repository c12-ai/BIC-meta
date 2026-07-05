# Integrate Current FE + BE for CC → RE E2E

## Goal

Make the **current** state of BIC-agent-portal (`feat/unified-params-form`) and
BIC-agent-service (`feat/experiments-plans-jobs-trials-overhaul`) work together
end-to-end, so that a single chained prompt drives **CC → RE execution** all the
way through to the lab service (Nexus) and passes when run via `/bic-e2e-runner`.

**Pass criteria:** `/bic-e2e-runner` runs `cc-re-chained-flow.spec.ts` and it goes
green — plan propose → confirm → CC params → CC dispatch → CC result accept →
RE auto-dispatch → RE params → RE dispatch → RE result accept.

## What I already know (from codebase exploration)

### FE (BIC-agent-portal, `feat/unified-params-form`)
* 26 uncommitted changes are **purely presentational** — no wire/contract changes:
  * Modified: `ParameterDesignPanel.tsx`, `ParameterDesignLayout.tsx`,
    `CcParamsForm.tsx` (896 lines churn), `ReParamsForm.tsx`, stage forms
    (Analyze/Fp/Tlc/sample-stage-chrome), `SpecialistSubtabs.tsx`,
    `TaskConfigPane.tsx`, `RecommendationBasis.tsx`, `Message.tsx`, `index.css`,
    `main.tsx`, `package.json` + lockfile.
  * Added (staged): 8 mockup/portal PNG screenshots + 2 `workspace-task-tree*.md`
    notes. These are artifacts, not code.
* FE does **not** import `bic_shared_types` — it hand-ports mirrors in
  `src/types/specialist-forms.ts` + `src/types/events.ts` with citation comments.
* Primary spec: `tests/cc-re-chained-flow.spec.ts` already covers the full chain.
* Wire contract (FE↔BE) appears stable across the redesign.

### BE (BIC-agent-service, `feat/experiments-plans-jobs-trials-overhaul`, clean)
* Planner emits only `cc`/`re` executors (`TaskDraft.executor: Literal["cc","re"]`,
  `app/runtime/types/plan.py:53`); single terminal tool `request_plan_confirmation`.
* `specialist_dispatcher` forks: `cc` → `cc_subgraph`, `re` → `re_subgraph`
  (`specialist_dispatcher.py:119`).
* `submit_l4_execution` (`specialists/tools.py:384`) builds `CreateCCTaskRequest` /
  `CreateRETaskRequest` and calls `lab.submit_task(...)`.
* `LabClient.submit_task` → `POST /tasks/` on lab-service (`lab_client.py:74`).
* **CC param recommendation is STUBBED** in MindClient
  (`mind_client.py:134-139`) — returns hard-coded `_CC_PARAM_STUB_RESPONSE`
  (`ColumnType.SILICA_12G`, fixed gradient). Endpoint placeholder:
  `/api/cc/cc_column_choice_protocol`. RE param recommendation is a **real**
  HTTP call to `/api/rotavap/re_get_params_protocol_standalone`.
* FORM_CONFIRM→decision-trial binding hardened (`reception_node.py:91-127`,
  `service.py:317-350`) — late params confirm won't mint a duplicate trial.
* `POST /reset` (port 8800) truncates agent PG + purges MQ.

### Shared types (BIC-shared-types, local `v1.1.2a1`)
* **Version-pin divergence — VERIFIED BENIGN on `POST /tasks/`** (2026-06-13):
  agent pins `v1.1.2a1`, lab pins `v1.0.5`, BUT:
  * `task_protocol/{cc,re,_base,responses}.py` are **byte-identical** between the
    two tags; `CreateCCTaskRequest`/`CreateRETaskRequest`/`CCParam`/`REParam`/
    `CCSampleCartridgeLocation`/`FlaskVolume`/`TaskType` are **field- and
    enum-identical**.
  * Lab parses with `extra='ignore'` (`task_protocol/_base.py:13`, no `forbid`
    anywhere) → the extra `agent_side_task_id` key (`lab_client.py:71`) is
    silently dropped, never rejected.
  * The only real v1.0.5→v1.1.2a1 diffs live in `mcp_protocol/*` + descriptions +
    sender-side `gt=0` tightening — all off the `POST /tasks/` path.
  * ⇒ **D2 does not fire as a baseline.** No shared-types or lab-pin change needed
    unless a *different* boundary (mcp_protocol, TaskSubmissionResponse round-trip)
    surfaces a break at runtime.
* Canonical Req/Resp bodies for the Agent→Lab boundary:
  `task_protocol/{cc,re}.py` (`CreateCCTaskRequest` / `CreateRETaskRequest`),
  `task_protocol/responses.py` (`TaskSubmissionResponse`, `TaskRead`).
* MindClient bodies: `mcp_protocol/{cc,re}.py`.

### Lab-service (Nexus, port 8192)
* `POST /admin/reset-to-test-data {robot_id: "talos.001"}` truncates + re-seeds
  (silica_12g + sample_40g cartridges, talos.001 idle, evaporator, etc.).
* Does NOT purge the agent↔lab MQ queue (that's the agent-side reset's job).

## Assumptions — all resolved (see Decisions + Verified facts)

* ~~A1~~ → resolved as **D1** (integrate-as-is, no merge).
* ~~A2~~ → resolved: CC stub is OK for plumbing (D-stub below); stub↔seed
  alignment **verified** (see Verified facts §4).
* ~~A3~~ → **FALSIFIED**: pin divergence verified BENIGN on `POST /tasks/`
  (2026-06-13). It is NOT the likely breaker; D2 does not fire as a baseline.

## Decisions (resolved with Drake 2026-06-13)

* **D1 (scope):** Integrate-and-fix-to-green. Run both current branches as-is,
  fix only what breaks CC→RE E2E. No branch merge, no feature build.
* **D2 (shared-types divergence):** If a v1.1.2a1 field breaks the `POST /tasks/`
  body at the Agent→Lab boundary, **bump lab-service pin up to v1.1.2a1** (forward-
  aligned, single source of truth). Lab-service code may need to handle new fields.
* **D3 (FE working tree):** Test the working tree **as-is** — the uncommitted
  redesign IS the "most current FE" to integrate. Do not stash.
* **D4 (port):** `:5173` — resolved by inspecting `playwright.cc-re-chained.config.ts`,
  not by asking. CLAUDE.md `:5174` is stale for this spec.
* **D5 (services):** Always up in tmux `service` (Drake). Runner verifies health +
  owns reset/idle-gate; does not need to cold-start them.
* **D6 (fix autonomy):** Auto-fix bench-state / test-bug / config; re-run
  LLM-non-determinism; **STOP and ask before ANY graph/flow or shared-types
  change.** (Drake)
* **D7 (re-run cap):** LLM-non-determinism failures (`admittance_rejected`,
  `volume_ml ≤ 2`) → auto-re-run the leg **at most 2×**; if still red, STOP and
  surface to Drake with evidence. No infinite re-roll.
* **D8 (commit policy):** On green, **stop at green + spec-doc update. Do NOT
  commit.** Honors Drake's global "never commit unless asked." Portal CLAUDE.md's
  Phase-3.4 auto-commit is overridden for this task (Rule 5: user instruction wins).
* **D9 (stub↔seed):** VERIFIED 2026-06-13 — CC stub `ColumnType.SILICA_12G`
  ("silica_12g") is fulfillable: lab `command_validator.validate_setup_cartridges`
  calls `get_available_by_spec("silica_12g")`; seed inserts `silica_12g_001
  spec=silica_12g unused`. No column mismatch.
* **D10 (dirty-DB handling):** OWNED BY `bic-e2e-runner`. Drake has already
  written the dirty-DB recovery into the runner playbook; the PRD does NOT
  duplicate it. The runner detects + recovers (reset / SQL re-assert / idle-gate)
  as part of Phase 0. (Live DB was observed dirty — `sample_40g_001 state=using`
  — confirming the runner's reset must run before the spec.)
* **D11 (static gates — conditional):** Static checks run ONLY if Phase 2 forces
  a code fix. FE change → `pnpm typecheck` + `pnpm check` (biome) on the portal;
  BE change → `uv run pytest -q` on agent-service. Run the relevant gate on the
  changed side BEFORE re-running the 35-min E2E. Zero code changes → skip; pure
  E2E green is the criterion (diagnostic-first ideal).

## Acceptance Criteria (evolving — mirrors the spec's real assertions)

* [ ] Bench precondition met: `/robots/idle` non-empty, cartridges seeded, devices idle.
* [ ] `cc-re-chained-flow.spec.ts` passes via `/bic-e2e-runner` (`:5173`, `--workers=1`).
* [ ] plan_proposed has exactly 2 steps {cc, re}; Confirm Plan accepted.
* [ ] CC leg: form_requested(params) #1 → params-confirm → form_confirmed #1 →
      dispatch → `task_progress.status === 'completed'` → Accept result.
* [ ] RE auto-dispatches (`_pick_next_planned_step` cursor advances) — 2nd
      task_created arrives without re-routing to CC.
* [ ] RE leg: form_requested(params) #2 (volume_ml > 2) → params-confirm →
      form_confirmed #2 → idle-gated dispatch → terminal `completed` → Accept.
* [ ] Final BE assertions: 2 task_created (executors cc + re via execByJobId),
      ≥2 form_requested(params), "Confirmed result review." ×2.
* [ ] No duplicate trials minted (decision-trial binding holds, no 4ms confirm race).
* [ ] If any contract changed: spec doc under `.trellis/spec/` updated (Rule 10).
* [ ] Every red leg classified (bench/test/LLM/external/product) before any fix.

## Out of Scope (explicit)

* Merging the two feature branches into each other or into main.
* Building a real Mind CC param endpoint (stub stays unless it blocks the flow).
* New Req/Resp bodies — types must come from shared-types (Drake's instruction).
* UI redesign work (the FE redesign is already done; we run it, not change it).

## Definition of Done

* `/bic-e2e-runner` green on the CC→RE chained spec.
* Any contract touched → spec updated in the same change set (Rule 10).
* Fail-loud: if a step is skipped or a leg is flaky, surface it, don't paper over.
* **No commit** — stop at green + spec update (D8); Drake commits when he chooses.
* LLM-non-determinism re-run cap respected (≤2, then surface — D7).

## Technical Approach

This is **diagnostic-first**, not build-first. The flow is already wired; we run
it and fix only what actually breaks. Biggest pre-supposed risk (shared-types pin
divergence) is verified benign on `POST /tasks/`, so there is **no baseline code
change** — we observe reality first.

### Verified facts (resolved by inspection, not assumption)
* **Port = :5173.** The cc-re spec runs under `playwright.cc-re-chained.config.ts`
  (`baseURL: http://localhost:5173`, line 15) + spec line 79. CLAUDE.md's `:5174`
  is the *default-config manual-demo* path — STALE for this spec (Rule 5 cleanup
  note: flag that CLAUDE.md line).
* **Services always up** in tmux session `service` (Drake): pane 0 lab(:8192),
  1 agent(:8800), 2 portal(:5173), 3 BIC_UI. All HTTP 200 as of 2026-06-13.
* **`resetLabState()` (tests/helpers.ts)** is the real per-test reset: HTTP lab
  reset + `docker exec bic-postgres psql` wipes on `labrun_db` (consume/devices/
  events/tasks) AND `talos_agent_db.sessions`, then **blocks on `/robots/idle`**.
* **§5 — Phase / event-emit / API-field alignment VERIFIED (2026-06-13).**
  Field-by-field trace, all three axes ALIGNED:
  * **Phase control:** one shared `SpecialistPhase` enum (`specialist.py:103`,
    `collecting_params→rts→conducting→done`); transitions are L2 `apply()`
    reductions keyed on `(phase, confirm_kind)` — no cc/re branch, identical for
    both. Routers symmetric (`re._post_react_route` mirrors cc). FE step-state is
    slaved to BE events (no parallel phase mirror; `autoSwitchEnabled` guard).
    Chained cursor `_pick_next_planned_step` is pointer-based (`current_job_id`+
    `seq`), single writer on result-accept — no off-by-one, can't route back to CC.
  * **Event emit (7/7):** `task_id→trial_id` / `plan_id→job_id` rename consistent
    across BE emit → FE `events.ts`/dispatcher/store → spec asserts. `plan_proposed`
    keeps `plan_id` by design. No stale emit sites.
  * **API fields (3/3 boundaries):** FE→BE confirm (`form_values` nested fields
    match, BE `extra="forbid"`); BE→Lab `POST /tasks/` (`_submit_l4` populates every
    required field, lab imports identical shared-types models); BE→Mind (CC no-HTTP
    stub; RE `REStandaloneParamRequest` all-required + reads `REParamResponse.param`
    by name). Safeguard: every boundary fails loud at Pydantic construction.
  * **2 doc-drifts (non-defect, later cleanup):** spec header says cursor "derives
    from ctx.tasks count" but code is pointer-based (more robust); inner
    `original_action` JSONB keeps `task_id` key intentionally (off the wire path).
* **§4 — CC stub↔seed alignment VERIFIED.** Stub `ColumnType.SILICA_12G`
  (mind_client.py:60) = `"silica_12g"`; lab validator (command_validator.py:191)
  `get_available_by_spec("silica_12g")`; seed (seed.py:142) `silica_12g_001
  spec=silica_12g unused`. CC dispatch will NOT fail on a column mismatch.
  ⚠️ Live DB observed dirty (`sample_40g_001 state=using`) — prior-run residue;
  **dirty-DB recovery is owned by the `bic-e2e-runner` playbook (D10), not the PRD.**

### Phase 0 — Bench precondition (runner-owned, full protocol)
The `bic-e2e-runner` agent owns this — it carries the battle-tested playbook.
NOT just two HTTP resets:
* **Proxy trap:** `unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY`
  (or `curl --noproxy '*'`) — the 127.0.0.1:7890 proxy 502s localhost.
* Lab reset `POST /admin/reset-to-test-data {robot_id:"talos.001"}` (8192) +
  agent `POST /reset` (8800, purges MQ) — but the spec's `beforeEach` also does
  the docker psql wipes itself, so the runner's job is to ensure a clean *start*.
* **Robot-idle gate is a HARD precondition**, not a candidate fix: block until
  `GET /robots/idle` is non-empty — the reset kicks a robot routine; dispatching
  inside its window fails `"No idle robots available"`. Fail loud on timeout.
* Seed reality: only `sample_40g_001` + `silica_12g_001` exist; old SQL breaks the
  new seed. After an executed CC the cartridge sits consumed → never rerun w/o reset.
* Infra failure modes the runner handles: **uvicorn --reload wedge** (force-restart
  pane 1 on open-SSE hang), **Vite HMR dual-module** (restart pane 2), zombie
  delayed-submit timer (restart lab pane).

### Phase 1 — Run + observe (backend-truth-first)
* Dispatch `/bic-e2e-runner` on `cc-re-chained-flow.spec.ts`, `--workers=1`.
* **Timing budget:** RE mock has a real ~14-min start→end evaporation sleep;
  spec outer cap 35 min, RE-terminal cap 18 min. A "hang" at ~5 min is NORMAL.
* Green ⇒ done; write spec-doc note, finish.
* Red ⇒ **backend truth first** (playbook §1): compare BE-emitted vs page-saw via
  `GET /api/sessions/:id/events` (or psql `talos_agent_db.session_events`) BEFORE
  touching test code. Capture exact failing leg + which event never arrived.

### Phase 2 — Fix only the real break (with a FAILURE TAXONOMY)
Every red leg must be classified — different classes have different owners and
different allowed actions (Drake: fix non-graph, GATE graph changes):

| Class | Examples | Allowed action |
|---|---|---|
| **bench-state bug** | "No idle robots", "No sample cartridge", consumed cartridge, zombie task | Auto-fix: re-reset / idle-gate / SQL re-assert per playbook |
| **test bug** | wrong selector, stale wait, missing fallback | Auto-fix surgically (Rule 3) |
| **LLM non-determinism** | `admittance_rejected` (safety verdict), RE `volume_ml ≤ 2` 422, shape-6 prose abandon | **Re-run** (it's non-deterministic) — do NOT "fix"; shape-6 nudge is test-side, graph nudge REJECTED by Drake |
| **external dependency** | ChemEngine `52.83.119.132:8002` down / `VISION_SERVICE_URL 未配置` 502 (RE recommend is a LIVE call) | Surface to Drake/ChemEngine team — NOT our code, do not skip silently |
| **product bug (non-graph)** | CC stub shape wrong, FE wiring, decision-trial dup | Auto-fix. If a new/different MindClient param is needed → **stub fn in BIC-shared-types**, types from shared-types, NO new Req/Resp bodies |
| **product bug (graph/flow)** | cursor advance (`_pick_next_planned_step`), router phase-gates, dispatcher routing | **STOP — propose to Drake BEFORE implementing** (his hard rule) |

### Phase 3 — Verify green + close loops
* Re-run `/bic-e2e-runner` to green (full chain, no skipped leg — Rule 9).
* Any contract touched → update spec under `.trellis/spec/` same change set (Rule 10).
* Clean up test-created rows. Report per-leg verdict with BE-vs-page evidence and
  the failure class. "Tests pass" is wrong if any leg was skipped.

## Decision (ADR-lite)

**Context:** "Integrate most current FE+BE" with a hard pass criterion
(CC→RE green via `/bic-e2e-runner`). Both branches carry recent overhaul work.
**Decision:** Treat as integrate-and-fix-to-green (D1). Start diagnostic-first —
the flow is wired and the top risk (pin divergence) is verified benign, so no
speculative baseline change. Fix strictly what Phase 1 proves broken.
**Consequences:** Minimal blast radius; every change traces to an observed
failure, not a guess. Risk: if multiple legs are flaky we iterate per-leg via the
runner playbook rather than batch-fixing — slower but fail-loud and surgical.

## Technical Notes

* Reset order matters: lab-service reset re-seeds cartridges + sets robot idle;
  agent reset purges MQ. The runner playbook (CLAUDE.local.md → `bic-e2e-runner`)
  carries reset preconditions + SSE-stall/LLM-abandon recovery.
* RE override in spec: 1 min / 1 mbar pressure step (bench memory).
* Run LLM specs `--workers=1` (FE E2E memory).

## Run 1 Findings (2026-06-13) — RED, 3 blockers

1. **CC `#cc-cartridge` stale locator** — test-bug — FIXED by runner (one-line
   `count() > 0` guard; `.textContent()` on a zero-match locator auto-waited the
   full 35-min timeout). CC leg now fully works: confirm→dispatch→completed→
   result_review.
2. **Post-CC re-plan regression** — product-bug (GRAPH/FLOW), GATED — after CC
   hits `completed` (session 79f98935 seq 37), the agent calls
   `request_plan_confirmation` AGAIN (seq 41) re-proposing the same 2-step plan
   instead of advancing the cursor to RE. Stray pending plan decision (48a065cc)
   then jams the CC result_review accept (67c4036e stays pending). Contradicts the
   spec contract (post-CC → advance to RE, not re-enter planning).
   → DECISION: investigate root cause (read-only) AND return a concrete diff for
   Drake's one-step approval. Do NOT apply a graph change without sign-off (D6).
3. **RE multi-step pressure editor** — test-bug — spec drives `Remove step 2` /
   `Step 1 duration/pressure` controls that exist only in CcParamsForm (gradient).
   Current ReParamsForm uses single `re-volume-ml` / `re-temperature` /
   `re-pressure` / `re-rotation-speed`.
   → DECISION: minimal rewrite — just satisfy the gate against the current form.
   Moot until #2 fixed (run can't reach RE leg).

## Blocker #2 — Root cause + fix decision (2026-06-14)

**Root cause:** `route_after_admit.py:59-65` has only a 2-state routing matrix
(in-flight → dispatcher; else → plan_subgraph). Missing a 3rd state: "confirmed
plan active, step done, next not yet dispatched." In that window (CC terminal,
before result_review accept), an `execute` USER_MESSAGE falls into "no in-flight
→ plan_subgraph" and the context-free plan prompt re-proposes the same plan →
stray pending plan decision wedges the result_review accept. The cursor logic
(`_pick_next_planned_step`) is sound but never reached — the turn is diverted one
node earlier. (Confirms earlier static trace was right but incomplete.)

**Decision (Drake): Option B-stub — route the stray turn to `query_agent`.**
* `route_after_admit`: during an active confirmed plan with no in-flight trial,
  route `execute` USER_MESSAGE → `query_agent`, NEVER → `plan_subgraph`.
* KNOWN: `query_agent` is a ticket-30 STUB (`query_agent.py:29-36`) — emits a
  fixed `TextDoneEvent` "Query support is not yet implemented; please rephrase as
  an execution request or try again later." Drake accepts this stub message for
  now (keeps route topology honest; contextual reply is a separate ticket).
  Do NOT implement a real query reply (out of D1 scope).
* Safety belt (REQUIRED): `_pick_next_planned_step` must never re-pick a terminal
  job → prevents the duplicate-trial regression (class fought by commit 752d855).
* Rule 10: update `.trellis/spec/backend/L3/graphs.md` route matrix (lines 62-66,
  114-116) with the 3rd state — same change set.

**⚠️ Spec-timing implication:** routing the stray turn to `query_agent` only
catches messages that arrive AFTER CC goes terminal. In the normal flow the CC
go-ahead lands while CC is still non-terminal → still dispatches. Implementer must
confirm the go-ahead doesn't race CC completion; if it does, that's a separate
spec adjustment (#3 territory).

**Implementer:** `trellis-implement` sub-agent.
**Tests:** new `tests/unit/test_route_after_admit.py` (assert active-plan + no
in-flight + execute → query_agent, NOT plan_subgraph); extend chained integration
test. Gate before re-run: `uv run pytest -q` (D11, BE change).

## Blocker #2 — REFRAMED by Drake's hard rule (2026-06-14)

**Drake's hard rule:** task dispatch/advance/cancel CANNOT be fired by a typed
message — it MUST be an explicit button click on the portal.

**The real bug (confirmed read-only):** dispatch today is gated on a TYPED
"go ahead" message → the rts-loop LLM calls `submit_l4_execution` → lab dispatch.
- params-confirm button only advances `collecting_params → rts` and STOPS (rts
  prompt: "DO NOT call submit_l4_execution — wait for an explicit USER_MESSAGE
  go-ahead", `dynamic_prompts.py:67-81`).
- NO dispatch button in FE; NO `dispatch` confirm_kind in BE (`ConfirmKind` =
  PLAN/PARAMS/RESULT_REVIEW only). The LLM is the dispatch gatekeeper, triggered
  by free text → violates the hard rule AND the duo-panel principle.
- The earlier "post-CC re-plan" was just ONE symptom of typed messages driving
  execution.

**DECISION (Drake) — Option A: deterministic auto-dispatch on params-confirm.**
* The params-confirm button BECOMES the explicit dispatch action. On a params
  FORM_CONFIRM advancing to `rts`, the BE deterministically runs `_submit_l4`
  (same body, same guardrail) — NO separate typed go-ahead, NO LLM tool-call
  gating. Mirror the existing deterministic backstop nodes (`auto_recommend`/
  `auto_analyze` in cc.py:434-463).
* Remove the rts prompt's FORM_CONFIRM "DO NOT submit / wait for go-ahead" branch.
* FE: ~none (button already POSTs `params`); optionally relabel "Confirm
  parameters" → "Confirm & dispatch".
* Spec test: DROP the typed go-ahead messages (CC ~line 396, RE ~559) — dispatch
  now follows the confirm click.
* SCOPE: integration-fix (all pieces exist), stays in D1. NOT Option B (new
  ConfirmKind.DISPATCH = build, rejected). Aligns with duo-panel principle
  (removes LLM from dispatch critical path).

**Re-plan symptom (Drake):** re-evaluate AFTER Option A lands — removing typed
messages from the dispatch path likely starves the re-plan trigger. Only fix
separately if it still appears in the re-run.

**Rule 10 spec docs to update (same change set):**
graphs.md (§2.2 rts/dispatch), specialist_tools.md (submit_l4 gate), events.md
(FormConfirmedEvent phase-advance), form.md (FE confirm→dispatch contract),
ParameterDesignPanel.tsx header contract.

## Test-side changes required by Option A (deterministic dispatch)

The spec assumed typed-go-ahead dispatch. With deterministic dispatch-on-confirm,
`cc-re-chained-flow.spec.ts` needs (verified against current code 2026-06-14):

1. **CC leg — drop the typed go-ahead** (lines 397-405): params-confirm now
   auto-dispatches. Remove step 5 (the "Please submit..." message + the rts
   "acknowledges and STOPS" comment). Dispatch wait (step 6) follows the confirm.
2. **RE leg — drop the typed go-ahead** (step 12, ~line 564+).
3. **RE leg — move the robot-idle gate BEFORE the RE confirm click** (currently
   lines 546-562, between confirm and go-ahead). With auto-dispatch, the confirm
   IS the submit, so the robot must be idle BEFORE clicking params-confirm — else
   the auto-dispatch hits "Robot is busy". Gate moves above step 11's click.
4. **#3 RE pressure rewrite** (lines 524-536): current `ReParamsForm` has NO
   multi-step editor. Replace `Remove step 2` / `Step 1 duration in minutes` /
   `Step 1 pressure in mbar` with the single `#re-pressure` input (UnitInput,
   mbar, step 1): `await page.locator('#re-pressure').fill('1')`. Keeps the
   minimize-sim-time intent (1 mbar). Note: form has no per-step duration field;
   duration is not chemist-editable in the current single-pressure model — drop
   the duration override (the BE collapses to a 1-element air_pressure list).
   Minimal rewrite — just satisfy the gate (Drake).

## RUN #3 — GREEN (2026-06-15)

`cc-re-chained-flow.spec.ts` PASSED (1 passed, 12.1m). All 7 final assertions held
(session 09977812): 2 task_created cc+re, 2 form_requested(params), both legs
terminal=completed, "Confirmed result review." ×2, no dup trial. BOTH dispatches
button-driven (form_confirmed→submit_l4→task_dispatched, zero typed go-aheads).
Took an auto-re-run: run-#1 RE leg hit LLM-abandon (skipped update_re_lab_logistics
→ disabled button); re-run passed (within D7 2× budget).

Fixes that proved out: deterministic dispatch (Option A), re-plan symptom gone,
CSS shrink-0 unblocking Accept, RE single-pressure edit, moved idle-gate.

### Two symptoms flagged (neither blocks the test)
1. **Trailing `turn_failed` (seq 81)** AFTER final RE result_review confirm:
   `specialist_dispatcher: no dispatch target on form_confirm turn,
   dispatch_source='no_plan'`. Spurious follow-on turn once plan fully consumed.
   Does NOT affect flow/test. → DECISION (Drake): FIX FIRST — investigate +
   propose diff (graph/dispatcher should no-op when plan exhausted on final
   result_review, not emit turn_failed). Gated; diff for approval before applying.
2. **RE LLM-abandon flake** — non-deterministic, presence-gate caught it, re-run
   passed. Known flake, not a defect.

### Closeout plan (Drake)
1. Fix the trailing turn_failed (gated graph fix, diff → approve → apply → re-verify).
2. Run trellis-check over full change set (BE dispatch + FE test + CSS) + finalize
   Rule 10 specs. Stay no-commit (D8).

## Dispatcher no-op fix — IMPLEMENTED + unit-proven (2026-06-15)

specialist_dispatcher.py: RESULT_REVIEW carve-out — no-op (goto=__end__) when the
final result_review confirm has a terminal trial + consumed plan; missing/non-terminal
trial still raises. + graphs.md §1.6 (Rule 10). Tests split (Rule 7): (a) missing/
non-terminal trial → raises; (b) terminal trial + plan consumed → __end__.
- BE: 655 pytest pass, pyright (venv) clean. IDE pyright errors = env noise
  (enum mistyped as Literal outside venv) — verified not real.

### Run #4 — RED on EXTERNAL bench flake (NOT our code), fix UNVERIFIED live
- CC leg GREEN again (dispatch→run→analyze→result_review accept).
- RE leg stalled mid-evaporation: robot sim `talos.001` dropped heartbeat 17× over
  ~41min (~every 2.5min vs 5s staleness threshold). Agent correctly timed out (16min
  turn_timeout). CLASS: bench-state / external dependency.
- The targeted post-final-result_review turn_failed was NEVER REACHED (RE didn't
  complete → no RE result_review → plan not consumed). Fix path not exercised E2E.
- Runner correctly did NOT auto-re-run (deterministic infra failure, not LLM flake).
- Dispatcher fix code IS loaded (worker restarted after edit, carve-out present).
- DECISION (Drake): Drake stabilizes the robot sim, then re-run #4 to confirm
  no turn_failed + full green.

### Recurring infra (for runner playbook awareness)
- uvicorn --reload wedges on open SSE → serves STALE code; force-restart pane
  service:1.1 after ANY BE edit before running.
- Robot sim heartbeat flapping stalls long RE evaporation runs — needs a stable
  sim connection before an RE-completing run.

## Run #4 (retry) — spec GREEN but turn_failed NOT gone (my fix was dead code)

Sim held (Drake re-stabilized). Full chain ran clean: CC→RE both completed, both
result_reviews accepted, all 7 spec assertions passed. BUT the trailing turn_failed
PERSISTS (session da8777fa, seq 83 after final form_confirmed seq 81). Runner
correctly refused to call it done (Rule 9 — spec is blind to turn_failed).

**My dispatcher carve-out was DEAD CODE on its target path:** it guarded on
`form_confirm.task_id`, which is ALWAYS None for RESULT_REVIEW confirms (FE never
sends task_id for result_review — only params; agent-client.ts:114-118). So the
terminal-trial check never ran; the RuntimeError fired as before. The needed data
IS available: the pending decision's `original_action.task_id` = the terminal RE
trial. service.py:243 only resolves resolved_task_id from original_action for
PARAMS (224-229), not RESULT_REVIEW. (Also a Rule 7 miss: my unit test (b) seeded
task_id directly, so it passed while the real None-path was never covered.)

**DECISION (Drake) — two fixes, one change set:**
1. **service.py:** resolve `resolved_task_id` for RESULT_REVIEW from the decision's
   `original_action.task_id`, same as PARAMS (224-229). Contract-preserving; makes
   turn_schemas.py:37-38 docstring honest; my existing dispatcher carve-out then
   works unchanged (sees a non-None terminal trial → __end__).
2. **Fix the unit test:** test (b) must use `form_confirm.task_id=None` + the
   decision-resolved id, so it covers the REAL result_review path (Rule 7).
3. **Spec assertion:** after the final form_confirmed, cc-re-chained-flow.spec.ts
   asserts NO turn_failed in session_events — fail loud on this regression class
   (was blind before; that's why it went green with the bug live).

## Run #5 — GREEN, dispatcher fix VERIFIED E2E (2026-06-15)

`cc-re-chained-flow.spec.ts` PASSED (17.6m), all 8 assertions (original 7 +
turn_failed===0). Backend truth (session 0c6a2e68): turn_failed_count=0 across 94
events; clean tail seq 92 form_confirmed(result_review) → 93 turn_started → 94
turn_completed. The service.py original_action.task_id resolution fed the dispatcher
carve-out → __end__ instead of raise. Both dispatches button-driven, symmetric.
One auto-re-run (attempt-1 CC LLM-abandon: skipped update_cc_lab_logistics; D7 budget).

### TASK GOAL MET: CC→RE green via runner, turn_failed eliminated.

### Latent gap flagged (NOT blocking — gated to Drake, separate from this task)
CC cartridge-null recovery: when the agent skips update_cc_lab_logistics,
sample_cartridge_location stays null → CcParamsForm has NO control to set it +
passesPresenceGate (CcParamsForm.tsx:163-173) omits it → Confirm enables into a
guaranteed BE 422 (cc_params_form_problems, form_payloads.py:256-272) a chemist
can't recover from (duo-panel violation). The spec's chemist-edit fallback
(cc-re-chained-flow.spec.ts:365-373) targets #cc-cartridge / "Select a cartridge
slot" — orphaned by the redesign (a0063da/c0b5314), now dead code. This is the
known CC LLM-abandon flake source. Separate follow-up — not part of CC→RE goal.

### Full change set this task (all uncommitted, no-commit per D8):
BE (BIC-agent-service):
- app/runtime/graphs/specialists/cc.py, re.py (auto_submit deterministic dispatch)
- app/runtime/middleware/dynamic_prompts.py (removed rts wait-for-go-ahead)
- app/runtime/graphs/nodes/specialist_dispatcher.py (result_review terminal no-op carve-out)
- app/session/service.py (result_review task_id resolution from original_action)
- .trellis/spec/backend/L3/{graphs,specialist_tools,events}.md + contracts.md (Rule 10)
- tests: test_specialists_{cc,re}.py, test_specialist_dispatcher.py,
  test_session_service_submit_form_confirm_persist.py, test_l3_reception_node_split_e2e.py
FE (BIC-agent-portal):
- tests/cc-re-chained-flow.spec.ts (drop typed go-aheads, move idle-gate, RE single-pressure,
  cartridge count() guard, turn_failed===0 assertion)
- src/components/workspace/ResultConfirmationPane.tsx (shrink-0 CSS fix)

## FOLLOW-UP #1 — CC cartridge-null gap: INVESTIGATED, fix DEFERRED (Drake 2026-06-15)

### Drake's ruling on the correct behavior
A missing required param is NOT a bug to default away. It's legitimate (agent
lacked intelligence, or user gave insufficient context — both OK; first-shot
success is never required). The CORRECT logic: when a required param is missing,
the AGENT tells the user which field is missing and asks for clarification — it
must NOT silently confirm, must NOT auto-default, must NOT dead-end.
→ NOT a hard-coded default, NOT a stub. The real fix is wiring cartridge into the
required-params clarification loop. Deferred to a dedicated task.

### Root cause (full trace)
- The value is 100% LLM-filled via the `update_cc_lab_logistics` tool
  (tools.py:617) during collecting_params. No deterministic backstop.
- Why the LLM skips it: same flake class as RE. The prompt says set cartridge
  "when known" (dynamic_prompts.py:149) — SOFT, optional-feeling. The LLM fills
  update_cc_from_user then jumps to request_params_confirmation, skipping logistics.
- The clarification MECHANISM ALREADY EXISTS and matches Drake's intent:
  request_clarification tool (tools.py:825) + HARD RULE that every collecting_params
  turn ends in request_params_confirmation OR request_clarification
  (dynamic_prompts.py:182) + "if validate reports missing fields, ask the chemist
  via request_clarification for exactly those fields" (dynamic_prompts.py:157-158).
- THE GAP: `sample_cartridge_location` is NOT in the required-fields-that-trigger-
  clarification set. The required-field list at dynamic_prompts.py:188 covers only
  from_user fields (sample_quantity, solvents, ...), NOT the lab_logistics cartridge.
  So a null cartridge doesn't route to "ask the chemist" — the agent confirms with
  null → FE presence-gate omits it (CcParamsForm.tsx:163-173, the c0b5314 redesign
  deleted both the #cc-cartridge selector AND the gate line) → BE 422
  (form_payloads.py:271-272) → dead end, no clarification.

### The deferred fix (dedicated task — comprehensive)
Wire `sample_cartridge_location` into the required-params clarification gate:
- Prompt: make cartridge a REQUIRED field (not "when known") that triggers
  request_clarification when null (dynamic_prompts.py:149,188).
- Validate gate: include sample_cartridge_location in the missing-required-fields
  check that routes to request_clarification.
- (Separately, the FE redesign that orphaned the #cc-cartridge selector +
  presence-gate line — c0b5314 — also needs the chemist-edit control restored so
  the chemist can answer the clarification. This is the "lil diff logic" lab_logistics
  layer Drake wants handled comprehensively.)
- Same gap exists for RE lab_logistics (flasks/collect_config) — handle both.
- The spec's chemist-edit fallback (cc-re-chained-flow.spec.ts:365-373) targets the
  orphaned #cc-cartridge — revive it when the FE control is restored.

### Status for THIS task
NOT fixed here (deferred per Drake). The CC→RE green run handles it via the D7
auto-re-run (LLM eventually fills it). Flagged as a known LLM-abandon flake source.
