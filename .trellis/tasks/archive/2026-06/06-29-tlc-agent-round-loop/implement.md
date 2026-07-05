# Implement — Agent-owned TLC round loop (child 3, agent-service)

> LAST in the chain (after child-1 contracts pinned + child-2 lab routes live).
> Validate: `uv run pytest -q` + the bench E2E. Design: `design.md`. Model: N trials share
> one `lab_task_id=T` (grill Q9); reuse the existing attempt/history machinery.

## Pre-flight

- [ ] Child-1 version pinned (`AppendTLCRoundRequest`, `TaskStatus.AWAITING_CONFIRMATION=
  "awaiting_confirm"`, `TaskStatusMsgPayload.image_url`).
- [ ] Child-2 lab routes live (`POST /tasks/{id}/rounds`, `/cleanup`; `awaiting_confirm` parking).

## Ordered checklist

1. [ ] **lab_client** (R1) — add `append_round(lab_task_id, AppendTLCRoundRequest) -> TaskRead`
   (`POST /tasks/{id}/rounds`) and `cleanup(lab_task_id) -> TaskRead` (`POST /tasks/{id}/cleanup`),
   mirroring `submit_task`'s httpx pattern.
2. [ ] **Create vs. append split** (R2, `tools.py` `_submit_l4` TLC arm) — first dispatch sends
   `CreateTLCTaskRequest{param, objects=sample_tubes, target_window}` ONCE; rounds DON'T go through
   here. `sample_tubes` sent only at create.
3. [ ] **Loop rewire** (R3, `tlc.py`) — `_auto_retry_node`: keep minting a trial per attempt + the
   `recommend_tlc_mixcase(prior_trials)` history call, BUT set the new trial's `lab_task_id = T`
   (existing) and call `lab.append_round(T, AppendTLCRoundRequest{param=ratio})` instead of
   `_dispatch_retry_trial`'s full-task submit. In-window branch → `lab.cleanup(T)` + result_review.
4. [ ] **resolve_trial_id** (Q9, `trials_repo.py:385`) — resolve `lab_task_id=T` → MAX(attempt)
   trial (order by attempt desc, limit 1); the N trials of a job share T.
5. [ ] **Ingress routing** (R4) — add `"awaiting_confirm"` to `NON_TERMINAL_STATUSES`
   (`event_ingress.py:40`). In `handle_task_status_transition` (`fast_path_handlers.py:409`):
   `awaiting_confirm` + `image_url` present (a round finished) → "round done →
   `recognize_tlc_plate(url)` → `_evaluate_route` → append/cleanup". `awaiting_confirm` WITHOUT
   `image_url` (prep finished) → no-op (wait for the agent's first round append).
6. [ ] **L4 stubs** (R5, `mind_client.py`) — `recommend_tlc_mixcase` history-aware ratio adjust
   from `request.trials[-1].observed_rf`; `recognize_tlc_plate(attempt)` scripted per attempt
   (keep `forced_retry`). INDEPENDENT, no HTTP.
7. [ ] **Spec docs** (R7) — agent L3 graphs spec (loop topology) + L1 mq-consumer spec
   (`awaiting_confirm` routing).

## Tests (R6 / AC1–AC4)

- [ ] Rewrite `tests/tlc-retry-flow.spec.ts` → aggregator shape: one lab task, ≥2 round appends w/
  differing ratio, recognize OUT→IN, one cleanup after success, one result_review(SUCCESS), accept,
  no turn_failed; assert `lab_task_id` stable across the N trials.
- [ ] Migrate `tests/tlc-e2e-final-chain.spec.ts` → new flow; preserve tube chain-of-custody asserts.
- [ ] Unit: append-branch vs. cleanup-branch in `_evaluate_route`; max-attempt resolution; L4
  history-aware mixcase (round-2 ratio ≠ round-1); prep-vs-round `awaiting_confirm` discrimination.
- [ ] Regression: a duplicate/late `awaiting_confirm` for an old round must not mis-route (design §8).

## Validation

- [ ] `uv run pytest -q` (agent) green.
- [ ] Bench E2E green (the round-based `tlc-retry-flow.spec.ts`) — the parent's AC1.

## Risky points / rollback

- `_auto_retry_node` rewire (step 3) + `resolve_trial_id` max-attempt (step 4) are the load-bearing
  edits; focused unit tests first.
- Ingress prep-vs-round discrimination (step 5) keys off `image_url` presence — a prep status with a
  stray image, or a round status missing the image, mis-routes. Assert child-2 only sets `image_url`
  on round skills.
- All changes self-contained to TLC subgraph + mind_client + lab_client + ingress/trials_repo.
  CC/RE untouched; revert as a unit.

## Parent acceptance this child closes

- AC1 (round-based E2E), AC2 (prep-once/cleanup-once — proven jointly w/ child 2), AC3 (ratio
  adapts), AC5 (agent suite green). AC4 (specs) shared across all three children.
