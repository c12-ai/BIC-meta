# Agent-owned TLC round loop + L4 adaptive stub + E2E

> Child 3 of parent **06-28-tlc-retry-loop-boundary**. THIRD/last in the chain (after child-1
> contracts + child-2 lab). Rebuilds the L3 TLC subgraph to drive the create→append→cleanup
> loop, makes the L4 stubs real-shaped, and proves the whole program with the E2E. Read parent
> `design.md` §2.1/§2.5/§3 + `research/agent-service-tlc-retry.md` first.

## Goal

Rebuild the agent-side TLC loop to own the round cycle over the new aggregator-Task contract:
create ONE lab task (tubes + window), append a round per attempt (new ratio), read each round's
photo URL off MQ, recognize + decide deterministically, append cleanup on in-window success.
L4 mind stubs become real-shaped (history-aware ratio; scripted per-round Rf). Rewrite the E2E.

## Confirmed facts / decisions (INHERITED — do not reopen)

- **1 Agent Trial = 1 Lab Task** (parent design.md:14,18; implement.md:46). The whole TLC run is
  ONE `Trial` whose `lab_task_id = T`; `Trial.lab_task_id` is strictly 1:1 with the lab Task.
  Rounds are NOT separate trials — they live on the single trial. (Settled; verified consistent
  across all task docs. The "1 trial = 1 attempt" phrasing meant lab-attempt, not agent-trial.)
- **"attempt" → round-index on the single trial.** Today `_evaluate_route` keys on `trial.attempt`
  and `_auto_retry_node` mints a new trial per attempt (`research/agent-service-tlc-retry.md:64,
  178`). Under the one-trial invariant this BECOMES a round counter + `params.rounds[]` on the
  single trial. This is required surgery to honor the invariant, NOT a new decision.
- **Loop = create → append round(ratio) → recognize → decide → (append round | append cleanup).**
  No per-round trial minting; no whole-task re-dispatch. (parent §2.1/§3)
- **`AWAITING_CONFIRMATION` (`"awaiting_confirm"`, ≤20 chars) is the round-done signal**, robot-free.
- **Mock-in-L4-only:** L3 loop is production-real; ALL fakery in `mind_client` L4 stubs, INDEPENDENT
  (recognition scripted by round index; mixcase adapts from observed-Rf history). (parent §2.3)
- **Deterministic decision stays agent-side:** keep `_evaluate_route` / `TLC_MAX_ATTEMPTS` / cap;
  out-of-window & under cap → append round; in-window → append cleanup + result_review(SUCCESS).

## Requirements

- **R1 — lab_client gains `append_round` + `cleanup`.** Add methods alongside `submit_task`
  (`lab_client.py`): `append_round(lab_task_id, AppendTLCRoundRequest)` → `POST /tasks/{id}/rounds`;
  `cleanup(lab_task_id)` → `POST /tasks/{id}/cleanup`. Typed via child-1 models.
- **R2 — Split `_submit_l4` TLC arm into create-vs-append** (`tools.py:544-582`). Create sends
  tubes + target_window once (CreateTLCTaskRequest, child-1 field); rounds call `append_round`
  with only the ratio (`AppendTLCRoundRequest{param}`). `sample_tubes` NOT re-sent per round →
  dissolves the clobber bug by construction (parent decision #2).
- **R3 — Rework the loop nodes** (`tlc.py`): replace `_auto_retry_node`'s "mint trial + full
  request" with "append round to the SAME trial/task"; re-point `_evaluate_route` /
  `_build_retry_mixcase_request` from `trial.attempt`/multi-trial to the single trial's
  `params.rounds[]` round history. Append cleanup on the in-window branch.
- **R4 — Ingress: route `AWAITING_CONFIRMATION`.** Add `"awaiting_confirm"` to
  `NON_TERMINAL_STATUSES` (`event_ingress.py:40`) AND make `handle_task_status_transition`
  (`fast_path_handlers.py:409`) treat a round-skill's `AWAITING_CONFIRMATION` + `image_url` as
  "round done → `recognize_tlc_plate(url)` → decide". **Without R4 the loop silently breaks**
  (status falls through → UnacceptableStatusError → NACK). (parent implement Phase 3, pinned.)
- **R5 — L4 stubs real-shaped, INDEPENDENT** (`mind_client.py`): `recommend_tlc_mixcase` reads
  `request.trials` observed-Rf history → adjusts ratio (below window → more polar; above → less);
  `recognize_tlc_plate` scripted by round index (1→0.25 OUT, 2→0.51 IN). No live HTTP.
- **R6 — Rewrite `tlc-retry-flow.spec.ts`** to the aggregator-Task shape (AC1–AC3 of parent);
  **migrate `tlc-e2e-final-chain.spec.ts`** to the new flow, preserving its tube chain-of-custody
  DB assertions.
- **R7 — Spec docs (Rule 10):** update the agent L3 graphs spec + L1 mq-consumer spec for the new
  loop topology + the `AWAITING_CONFIRMATION` routing.

## Acceptance criteria

- [ ] **AC1** E2E (round-based): one lab task, ≥2 round appends with a DIFFERENT ratio between
  round 1 and 2, recognition OUT→IN, one cleanup after success, one result_review(SUCCESS), accept,
  no `turn_failed`. ONE agent Trial (assert `lab_task_id` stable across rounds).
- [ ] **AC2** Ratio adapts: round-2 append carries a different `TLCParam.solvent_ratio` than round 1.
- [ ] **AC3** `AWAITING_CONFIRMATION` routes correctly (no `UnacceptableStatusError`; recognition
  fires per round).
- [ ] **AC4** `tlc-e2e-final-chain.spec.ts` migrated + green (tube chain-of-custody preserved).
- [ ] **AC5** agent `uv run pytest -q` green; spec docs updated.

## Out of scope

- shared-types defs (child 1); lab routes/engine (child 2); old-path deletion (parent Phase 3b).
- Live ChemEngine HTTP routes (L4 stays stubbed).

## Open questions

- Q1: where the single trial's `params.rounds[]` history is persisted/read so
  `_build_retry_mixcase_request` threads observed-Rf across rounds without separate trial rows —
  resolve the exact `tlc.py` state seam in design.

## Post-integration bug (found by live E2E, 2026-06-30)

The round loop runs end-to-end (rounds append, ratios adapt, recognition fires) but never
reaches the IN-window success → cleanup never appends → task wedged at `awaiting_confirm`.

ROOT CAUSE (confirmed, broker-trace + code): the eval node `_evaluate_tlc_result_node`
(tlc.py:709-711) reads `from_user.target_window` from `state.params_draft`, which holds the
LLM's STALE `(0.3,0.5)`. The chemist's confirmed `(0.40,0.60)` reached the lab create request
but was NOT written back to `from_user.target_window` in the draft the evaluator reads. Fixture
Rf 0.51 is IN (0.40,0.60) but OUT (0.3,0.5) → every round fails → cap-reached at 3 → no cleanup.
(Same draft-staleness class as the existing `recommended` D1-race guard at tlc.py:719-730, which
target_window lacks.)

FIX (Drake): write the chemist-confirmed `target_window` back into
`state.params_draft.from_user.target_window` at params-confirm, so the eval path and the lab
create request use the SAME authoritative window. Fix site: the TLC params-confirm flow
(FormConfirmedEvent.apply / the confirm handler that persists form_values into trials.params).

ALSO FIXED en route (lab-service, scripts/mock_robot_server.py): the robot mock had NO TLC skill
handler → START_TLC fell through to _handle_unknown (no captured image) → image_url=None → the
round-done trigger never fired. Added `_handle_start_tlc` (emits a contract-conforming
CapturedImage: work_station + camera=left_arm_rgb + url) + `_handle_end_tlc`.

## Post-integration bug #2 — ingress NACK-drop race (RC-A, found 2026-06-30)

INTERMITTENT (timing-dependent, reproduced run 1 of the final E2E). The lab's first round
status callback arrives ~31ms BEFORE the agent registers the trial→lab_task_id mapping →
`event_ingress.resolve_trial_id` returns None → `UnacceptableStatusError: unknown task_id` →
the consumer NACKs it. In this occurrence it was NOT redelivered (one nack, no recovery) → the
round-done signal lost → loop never started (rounds=0).

WHY the window exists: `lab_task_id` is persisted by `TaskDispatchedEvent.apply` which commits
at END of the dispatch turn — AFTER `lab.submit_task()` already told the lab to begin (tools.py
_submit_l4). So the lab can publish round-1 status before the agent's mapping commits.

FIX DIRECTION (Drake): close the race at the SOURCE — persist trials.lab_task_id IMMEDIATELY
when `lab.submit_task()` returns (before the rest of the dispatch turn), so the trial→lab_task
mapping exists before any lab status can arrive → resolve never misses → no NACK, no reliance on
requeue. (Alternative considered: make the ingress hold/queue a status for a not-yet-registered
task_id instead of NACK-dropping — heavier, and doesn't fix the root ordering.)

NOTE the earlier "the requeue self-heals this race" conclusion was INCOMPLETE — it self-heals
only when the dispatch-turn commit lands within the requeue budget; under a slow LLM turn or this
~31ms-then-no-redelivery occurrence it does not. The source fix removes the dependency entirely.

## RC-B (lab-team, NOT ours) — cleanup submitted before robot idle

The lab submits `end_thin_layer_chromatography` (cleanup) ~7s after round 2's plate finished,
before the robot flips back to idle → `No idle robots available` → step fails, no back-off/retry.
Lab-team owned (lab's mid-task step-submit timing). Out of scope for this agent-side task; flag
for the lab team.
