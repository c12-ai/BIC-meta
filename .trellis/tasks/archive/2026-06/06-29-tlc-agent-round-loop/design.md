# Design — Agent-owned TLC round loop (child 3, agent-service)

> THIRD/last in the chain. Consumes child-1 contracts + child-2 lab routes. Parent
> `design.md` §1/§2.1/§3 (CORRECTED model) is authority. Research:
> `research/agent-service-tlc-retry.md`.

## 1. The model (CORRECTED — grill Q9)

`1 TLC job = N attempts (= N agent Trials) = 1 Lab Task (lab_task_id=T) = N skills.`

- N agent `Trial` rows (one per attempt/round) — the existing `ctx.trials[job_id]`
  attempt-ordered history is REUSED UNCHANGED. `_evaluate_route(attempt)`,
  `_build_retry_mixcase_request(prior_trials)`, `recognize_tlc_plate(attempt=...)` all keep
  working off the trials list. **No rewrite of the retry-history machinery** (this is the win
  from the corrected model — Option B, not the feared Option A rewrite).
- All N trials SHARE `lab_task_id = T` (many-to-one). `_auto_retry_node` still mints a new trial
  per attempt, but the trial's `lab_task_id` is the EXISTING T (not a new task), and instead of
  dispatching a full `CreateTLCTaskRequest` it calls `lab.append_round(T, ratio)`.

## 2. The loop (rewired `tlc.py`)

```
create:   _auto_submit / first dispatch → lab.submit_task(CreateTLCTaskRequest{tubes, target_window})
          → trial#1.lab_task_id = T ; lab runs prep → parks AWAITING_CONFIRMATION
round:    append round skill → lab.append_round(T, AppendTLCRoundRequest{param=ratio_n})
          → lab runs round → parks AWAITING_CONFIRMATION + image_url
recognize:(MQ AWAITING_CONFIRMATION + image_url) → recognize_tlc_plate(url, attempt) → verdict
decide:   _evaluate_route(in_window, attempt):
            out & attempt<cap → _auto_retry_node: recommend_tlc_mixcase(prior_trials) →
              mint trial#(n+1) (lab_task_id=T) → lab.append_round(T, ratio_{n+1})   ← loop
            in-window        → lab.cleanup(T) + emit result_review(SUCCESS)
            out & attempt==cap → emit result_review(FAILED)
```

## 3. Key seams + the surgery (vs. today)

| Concern | Today | Child-3 change |
|---|---|---|
| Retry dispatch | `_auto_retry_node` → `_dispatch_retry_trial` → full `CreateTLCTaskRequest` (`tlc.py:665,840`) | mint trial (keep) BUT call `lab.append_round(T, ratio)` — no new task |
| First dispatch | `_submit_l4` TLC arm builds full request w/ `objects=sample_tubes` (`tools.py:562`) | create sends tubes+window ONCE; this is the ONLY place tubes go |
| Round history | `ctx.trials[job_id]` tuple (`context.py:221`) | UNCHANGED — reused |
| MQ→trial resolve | `WHERE lab_task_id==T` → 1 row (`trials_repo.py:385`) | → MAX(attempt) trial (N rows now share T) — grill Q9 |
| Status routing | `NON_TERMINAL_STATUSES` = {pending,in_progress,waiting} (`event_ingress.py:40`) | ADD `awaiting_confirm`; fast-path treats round `awaiting_confirm`+`image_url` as "round done → recognize" |
| lab_client | `submit_task`/`query`/`cancel` | ADD `append_round(T, req)`, `cleanup(T)` |

## 4. lab_client additions (R1)

- `append_round(self, lab_task_id, request: AppendTLCRoundRequest) -> TaskRead` →
  `POST /tasks/{lab_task_id}/rounds`.
- `cleanup(self, lab_task_id) -> TaskRead` → `POST /tasks/{lab_task_id}/cleanup`.
- Both follow the `submit_task` httpx pattern (`trust_env=False`, `_lab_error_from_status`).

## 5. L4 stubs (R5) — `mind_client.py`, INDEPENDENT, no live HTTP

- `recommend_tlc_mixcase(request)` — read `request.trials[-1].observed_rf` (the threaded history);
  if Rf below window → shift ratio more polar (e.g. 2:1→3:1); above → less polar; return new
  `TLCParam`. Real adaptation; still a stub (no `/api/tlc/tlc_mixcase_protocol` call).
- `recognize_tlc_plate(request, attempt)` — scripted by attempt index (already exists,
  `med005_fixture` script `forced_retry`): attempt 1→0.25 (OUT), attempt 2→0.51-ish (IN). KEEP.

## 6. Ingress routing (R4 — the silent-break guard)

`event_ingress.py`: add `TaskStatus.AWAITING_CONFIRMATION.value` to `NON_TERMINAL_STATUSES`
(`:40`). In `handle_task_status_transition` (`fast_path_handlers.py:409`): when the status is
`awaiting_confirm` AND `image_url` is present (a round skill just finished) → drive
"round done → `recognize_tlc_plate(url)` → `_evaluate_route` → append/cleanup". Without the
`NON_TERMINAL_STATUSES` add, the status falls through → `UnacceptableStatusError` → NACK → loop
silently dies (research-confirmed).

## 7. Tests (R6)

- Rewrite `tlc-retry-flow.spec.ts` to the aggregator shape (parent AC1–AC3): one lab task,
  ≥2 round appends w/ differing ratio, recognize OUT→IN, one cleanup, one result_review(SUCCESS),
  accept, no turn_failed; assert `lab_task_id` stable across the N trials.
- Migrate `tlc-e2e-final-chain.spec.ts` to the new flow; keep its tube chain-of-custody DB asserts.
- Agent pytest: the loop nodes (append vs. cleanup branch), the max-attempt resolution, the L4
  history-aware mixcase (round-2 ratio ≠ round-1).

## 8. Risks

- **The `resolve_trial_id` max-attempt change** is subtle: a late/duplicate status for an OLD
  round could mis-route. Mitigate: rounds are strictly sequential (only one trial live); assert
  the resolved trial is the live one (not analysis-complete). Test a regressive/duplicate status.
- **Ingress fast-path** must distinguish a round's `awaiting_confirm` (→ recognize) from prep's
  `awaiting_confirm` (→ nothing, wait for the agent's first append). Key off `image_url` presence
  (prep has none; a round has one).
- Self-contained to the TLC subgraph + `mind_client` + `lab_client` + `event_ingress`/`trials_repo`
  resolution. CC/RE untouched.
