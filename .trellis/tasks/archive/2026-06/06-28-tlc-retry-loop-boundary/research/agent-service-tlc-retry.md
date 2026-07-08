# Research: Agent-service TLC Rf-retry loop & loop-boundary

- **Query**: TLC Rf-retry redesign — confirm the `sample_tubes`-drop bug in `_auto_retry_node`, trace retry dispatch / re-recommend / decision path, and assess prep-once/cleanup-on-success loop-boundary model.
- **Scope**: internal (BIC-agent-service + BIC-shared-types) + live log forensics
- **Date**: 2026-06-28

---

## TL;DR (decision-grade)

- **The bug is REAL and reproduced in the live log** (error.log:38588-38634). On the FIRST retry (attempt 1 out-of-window → mint attempt 2), `_dispatch_retry_trial` → `_submit_l4` raises `params not dispatchable: lab_logistics.sample_tubes: select 2–4 sample tubes (got 0)`.
- **Root cause is NOT a literal "drop" inside `_auto_retry_node`'s draft spread.** `_auto_retry_node` builds `retry_draft = {**draft, "recommended": ...}` (tlc.py:834-837) — that DOES carry `lab_logistics` *if `draft` has it*. The real failure is upstream: by the time the retry runs, the just-scored trial's persisted `trials.params` **no longer contains `lab_logistics.sample_tubes`**, so `draft` (re-seeded from it) is already missing them. See "Root Cause Chain" below.
- **Minimal fix**: in `_auto_retry_node`, re-attach `lab_logistics` from the AUTHORITATIVE source (the FE-confirmed first-attempt trial / `last_form_snapshot`), not from the LLM-clobbered live draft, before building `retry_draft`. `sample_tubes` + `target_window` are FIXED across rounds — only `recommended.solvent_ratio` changes.
- **Deeper loop-boundary (prep-once / cleanup-on-success): the agent has NO such notion today.** Every retry re-dispatches a COMPLETE `CreateTLCTaskRequest` (full task) via the same `lab.submit_task` path — so the lab re-runs the whole TLC program (incl. prep + cleanup) each attempt. The contract has no "round" / "prep-once" / "cleanup-on-success" concept. This is the crux of the redesign and it would change the minimal fix's surface (see §5/§6).

---

## Findings

### Files Found

| File Path | Role |
|---|---|
| `BIC-agent-service/app/runtime/graphs/specialists/tlc.py` | TLC specialist subgraph: eval + retry loop. **All bug-relevant nodes live here.** |
| `BIC-agent-service/app/runtime/graphs/specialists/tools.py` | `_submit_l4` (tlc arm at 542-566) — the validator that raises "got 0". |
| `BIC-agent-service/app/events/form_payloads.py` | `TLCParamsForm` / `TLCLabLogistics` / `TLCFromUserFields` / `tlc_params_form_problems` (where `sample_tubes` lives, 295-354). |
| `BIC-agent-service/app/runtime/graphs/nodes/reception_node.py` | Re-seeds `params_draft` from persisted `trials.params` on cross-turn re-entry (437-438, 688). |
| `BIC-agent-service/app/events/runtime_emitted.py` | `TaskParamsSetEvent.apply` (whole-blob `params` overwrite, 658-662); `TaskCreatedEvent.apply` (mint attempt, 834-840); `TaskDispatchedEvent.apply` (861-868); `FormConfirmedEvent.apply` (persists confirmed form_values, 604-605). |
| `BIC-agent-service/app/runtime/middleware/dynamic_prompts.py` | `_TLC_HEADER` line 256: **"lab_logistics: empty for TLC (no cartridge/flasks)"** — the LLM is told NOT to manage `sample_tubes`. Inconsistent with `_submit_l4`'s 2–4 requirement. |
| `BIC-agent-service/app/infrastructure/mind_client.py` | `recommend_tlc_mixcase` (215-231, **STUBBED — ignores `trials` history**); `recognize_tlc_plate` (186-213, R9 per-attempt scripted Rf). |
| `BIC-shared-types/.../experiment_task/http/tlc.py` | `CreateTLCTaskRequest` (`param: TLCParam`, `objects: list[ObjectLocation]` min=2/max=4). |
| `BIC-shared-types/.../model_service/http/tlc.py` | `TLCMixcaseRequest` / `TLCMixcaseResponse` / `TLCMixcaseRecommendation` / `TLCMixcaseTrial` / `TLCPlateRecognition`. |
| `BIC-shared-types/.../experiment_task/mq/task_status.py` | `TaskStatusMsgPayload` — the terminal MQ message (carries NO Rf). |

---

### Q1 — `_auto_retry_node`: which params carry forward, which drop, what `submit_l4` needs

`_auto_retry_node` (tlc.py:769-860) builds the new attempt's draft as:
```python
draft = state.params_draft or {}                         # tlc.py:794
...
retry_draft = {
    **(draft if isinstance(draft, dict) else {}),        # tlc.py:834-835  (carries from_user + lab_logistics IF present in draft)
    "recommended": recommended_param.model_dump(mode="json"),  # tlc.py:836  (overwrites recommended ONLY)
}
emit_event(TaskParamsSetEvent, trial_id=new_trial_id, params=retry_draft)  # tlc.py:838
lab_task_id = await _dispatch_retry_trial(state, runtime, new_trial_id=new_trial_id, retry_draft=retry_draft)  # tlc.py:840
```
- **Carried forward**: whatever `draft` (= `state.params_draft`) holds — i.e. `from_user` and `lab_logistics` ARE spread; `recommended` is replaced with the new Mind param.
- **Literally dropped in the spread: nothing** — the spread is non-destructive. The drop happens UPSTREAM (`draft` already lacks `lab_logistics`, see Root Cause Chain).

**Full set `_submit_l4` requires for TLC dispatch** (tools.py:542-566):
- `state.params_draft["recommended"]` → `TLCParam` (NOT None) → `CreateTLCTaskRequest.param`.
- `state.params_draft["lab_logistics"]["sample_tubes"]` → `list[ObjectLocation]`, **2 ≤ len ≤ 4** → `CreateTLCTaskRequest.objects`. **This is the field that fails "got 0".**
- `from_user` is NOT used for dispatch (it drives recommendation only — tools.py:462-464 docstring; `from_user` is fine to keep but irrelevant to the wire request).

So a fix must guarantee `retry_draft["lab_logistics"]["sample_tubes"]` has the chemist's 2–4 tubes. Those tubes are FIXED across rounds.

---

### Q2 — How a retry dispatches today (`_dispatch_retry_trial` / `_submit_l4`)

`_dispatch_retry_trial` (tlc.py:665-696) submits a **COMPLETE fresh TLC task** per attempt — it is NOT finer-grained:
```python
dispatch_state = state.model_copy(update={"task_id": new_trial_id, "params_draft": retry_draft})  # tlc.py:684
result = await _submit_l4(dispatch_state, runtime, tool_call_id, lab)                              # tlc.py:686
```
`_submit_l4`'s tlc arm (tools.py:562-566) builds the entire request:
```python
task_request = CreateTLCTaskRequest(
    task_id=task_uuid,            # the new trial's UUID
    param=tlc_form.recommended,   # new solvent system
    objects=sample_tubes,         # the 2–4 tubes (REQUIRED, the failing field)
)
```
POSTed via `lab.submit_task(task_request, idempotency_key=agent_task_id)` (tools.py:582). **This is the same machinery the FIRST dispatch uses** (`_auto_submit_node` at confirm). The lab receives a brand-new full TLC task each attempt → it re-runs the whole program (prep → spot → develop → photo → … and cleanup), with NO notion of "this is round 2 of the same prepared plate". A terminal-failed re-dispatch raises loud (tlc.py:687-688).

---

### Q3 — Where the new recommended param comes from on retry

`_auto_retry_node` re-recommends via `mind.recommend_tlc_mixcase(retry_request)` (tlc.py:818-819), where `retry_request` is built by `_build_retry_mixcase_request` (tlc.py:264-298):
- It threads PRIOR TRIALS as `TLCMixcaseTrial` history: `{step=attempt, param=recommended, observed_rf={smiles: rf}}` (tlc.py:280-291).
- The just-scored attempt's observed Rf is taken from the verdict (not yet on ctx) and merged/overwritten into the history (tlc.py:809-816).
- Returns `response.recommendation.param` → a NEW `TLCParam` (solvent system + ratio). Confirmed the request type carries observed-Rf history correctly.

**Caveat (load-bearing for the redesign's realism)**: `MindClient.recommend_tlc_mixcase` is **STUBBED** (mind_client.py:215-231) — it returns a hard-coded `med005_tlc_mixcase_response()` and **ignores the `trials` history entirely**. So today every "new recommended param" is the SAME canned value; the "2:1 → 3:1 ratio adapts to observed Rf" behavior is wiring-only, not yet real. The shared-type request DOES carry history, so switching to live Mind is localized to that method.

Also note `recognize_tlc_plate` is stubbed with **per-attempt scripted Rf** (mind_client.py:202-211 + `med005_tlc_recognition_response_for_attempt`) — in the failing run attempt=1 scripted `product_rf=0.25` vs `target_window=(0.3,0.5)` → out-of-window (app.log.1:31000).

---

### Q4 — The deterministic decision path (NO LLM)

Confirmed: out-of-window & attempt<cap → `auto_retry` (NO result_review form); in-window OR cap → `result_review`.

- `_rf_in_window` (tlc.py:167-179): null `product_rf` or null window → out-of-range.
- `_evaluate_route` (tlc.py:182-193): `in_window → _EVAL_SUCCESS`; `attempt < TLC_MAX_ATTEMPTS → _EVAL_RETRY`; else `_EVAL_FAIL`. `TLC_MAX_ATTEMPTS = 3` (tlc.py:155).
- `_evaluate_tlc_result_node` (tlc.py:698-767): calls recognition for the current attempt, persists recognition onto the trial draft (`merged_draft`, tlc.py:745-751), computes `in_window`, stores `TLCEvalVerdict` on `state.tlc_eval`.
- `_post_evaluate_route` (tlc.py:389-408): `_EVAL_RETRY → "auto_retry"`; `_EVAL_SUCCESS`/`_EVAL_FAIL → "emit_result_review"`.
- `_post_react_route` (tlc.py:382-385): a terminal trial in `conducting` → `evaluate_tlc_result` (the entry to the loop). No result-review form is opened on the retry branch — `auto_retry` ends the turn (edge to END, tlc.py:1009); the loop is driven by successive MQ-terminal turns, not an in-graph cycle (tlc.py:1003-1008).

The decision logic is correct. The defect is purely in param ASSEMBLY on the retry leg.

---

### Q5 — PREP-once / CLEANUP-on-success: does the agent express it today?

**No.** Evidence:
- Every dispatch (initial AND retry) builds a full `CreateTLCTaskRequest` and POSTs it (tools.py:562-566; tlc.py:684-686). There is no "round" / "step within a prepared plate" granularity, no "prep-once" flag, no "cleanup-on-success" command.
- The retry mints a NEW trial (`TaskCreatedEvent` → `next_attempt` → new `trials` row, tlc.py:824-831 / runtime_emitted.py:834-840) and dispatches it as an independent task. The lab sees N independent TLC tasks for N attempts.
- The loop boundary today is "one full TLC task == one attempt"; the comment at tlc.py:1003-1008 explicitly models the loop as "successive TASK_TERMINAL turns", each a complete task.
- There is no CLEANUP command anywhere on the agent side; cleanup (if any) is implicit inside the lab's single-task program.

This confirms the redesign premise: the corrected real-world model (PREP once → per-round aspirate+tank with NEW ratio → spot → develop → photo → S3 → recognize → Rf check → cleanup-on-success / new-ratio-on-fail) is **not representable** in the current Agent↔Lab contract. Expressing it requires either (a) a finer-grained Agent↔Lab command surface (start-session / run-round(ratio) / cleanup), or (b) keeping the "full task per attempt" model but making the lab idempotent about prep/cleanup. That is a contract change → spec updates required (Rule 10, see §6).

---

### Q6 — Contracts & spec surfaces a redesign would touch

**Agent↔Lab (L4) request — `CreateTLCTaskRequest`** (`BIC-shared-types/bic_shared_types/experiment_task/http/tlc.py`):
```python
class CreateTLCTaskRequest(CreateTaskRequestBase):
    task_type: Literal[TaskType.THIN_LAYER_CHROMATOGRAPHY] = ...
    param: TLCParam                                   # solvent system + ratio (changes per round)
    objects: list[ObjectLocation] = Field(min_length=2, max_length=4)  # the FIXED 2–4 sample tubes
```
Discriminated union `CreateTaskRequest` (CC|RE|TLC, on `task_type`); POSTed via `lab.submit_task`. A round-based redesign would add a new request shape OR a "round"/"session" field here.

**Agent↔Lab (L1) terminal MQ — `TaskStatusMsgPayload`** (`BIC-shared-types/.../experiment_task/mq/task_status.py`): `task_id`, `agent_side_task_id`, `status: TaskStatus`, `steps[]`, `error_message`. **Carries NO Rf** — recognition is a separate Mind call after the terminal turn (tlc.py:726 comment). A redesign that emits per-round results would change this payload (e.g. round index, per-round photo S3 key).

**Agent↔Mind (L4) — `TLCMixcaseRequest`/`Response`** (`BIC-shared-types/.../model_service/http/tlc.py`): already round-aware (`trials` history with `observed_rf`, `predicted_rf`). No shape change needed for the round model, but the stub must be replaced with a live route for ratio-adaptation to actually work.

**Spec docs (Rule 10 — update in the same change set):**
- `BIC-agent-service/.trellis/spec/backend/L3/graphs.md` — TLC subgraph topology / Rf-retry loop (the eval→retry→dispatch wiring).
- `BIC-agent-service/.trellis/spec/backend/L3/specialist_tools.md` — `_submit_l4` dispatch gate (the `sample_tubes` 2–4 requirement) and the TLC tool surface.
- `BIC-agent-service/.trellis/spec/backend/contracts.md` — cross-layer + Agent↔Lab TLC contract.
- `BIC-agent-service/.trellis/spec/backend/L1/mq-consumer.md` — terminal-status ingress (if MQ shape changes).
- `BIC-shared-types/.trellis/spec/**` + the contract artifacts (`schemas/`, `contracts/experiment_task/create-task.openapi.yaml`, `CHANGELOG.md`) — regenerate via export scripts if `CreateTLCTaskRequest`/`TaskStatusMsgPayload` change (per BIC-shared-types AGENTS.md).
- BIC-lab-service spec (the robot mock that runs the full TLC program) — owns prep/cleanup; a round model changes its task decomposition.

---

## Root Cause Chain (the "got 0" bug, with file:line + live log)

Live failure: `error.log:38588` →
`RuntimeError('submit_l4_execution: params not dispatchable: lab_logistics.sample_tubes: select 2–4 sample tubes (got 0)')`
traceback: `_auto_retry_node` (tlc.py:840) → `_dispatch_retry_trial` (tlc.py:686) → `_submit_l4` (tools.py:559).
Decision was correct: `app.log.1:31000` → `tlc.evaluate: attempt=1 product_rf=0.25 target_window=(0.3, 0.5) in_window=False` → out-of-window → auto_retry. Failure is on the FIRST retry (attempt 1 → 2).

Why `retry_draft["lab_logistics"]["sample_tubes"]` is empty even though attempt-1 was confirmed WITH tubes:

1. **FE confirm persists tubes.** At confirm, `FormConfirmedEvent.apply` whole-writes `form_values` (incl. `lab_logistics.sample_tubes`) to attempt-1's `trials.params` (runtime_emitted.py:604-605). The E2E confirm POST carried 2 bench tubes (`tlc-e2e-final-chain.spec.ts:10`, log seq 28). Attempt-1 dispatch succeeds.
2. **A post-confirm LLM turn re-runs `collecting_params` and CLOBBERS the persisted params.** After `form_confirmed` (seq 28, 15:20:25), the agent makes another LLM call still in `collecting_params` whose message thread shows `update_tlc_params(fields={from_user:{rxn}})` only (app.log.1:23475 message array), then emits `task_params_set` **seq 29** (app.log.1:23486, 15:20:37).
3. **`TaskParamsSetEvent.apply` is a WHOLE-BLOB overwrite** (runtime_emitted.py:658-662): `update_fields(fields={"params": self.params})`. The emitted `params` is the agent-side `state.params_draft`, which after the confirm re-entry contains only `from_user` (the LLM never manages `lab_logistics` — the dynamic prompt explicitly says "lab_logistics: empty for TLC", dynamic_prompts.py:256). So seq-29 **overwrites attempt-1's `trials.params` and drops `lab_logistics.sample_tubes`.**
4. **The retry reads the clobbered draft.** When attempt-1 finishes, the TASK_TERMINAL turn re-seeds `state.params_draft = dict(trial.params)` from the (now tube-less) attempt-1 row (reception_node.py:437-438 via :688). `_evaluate_tlc_result_node` preserves it (`merged_draft = {**draft, "from_user": ...}`, tlc.py:750). `_auto_retry_node`'s `draft` therefore has NO `lab_logistics`, so `retry_draft = {**draft, "recommended": ...}` has empty `sample_tubes` → `_submit_l4` "got 0".

**Two independent defects feed this:**
- (a) `TaskParamsSetEvent` whole-blob overwrite + LLM draft that never carries `lab_logistics` ⇒ confirmed lab-logistics is destroyable by any later params-set. (CC has the same shape risk for `sample_cartridge_location` but its flow apparently doesn't re-run collecting after confirm in this scenario.)
- (b) `_auto_retry_node` trusts the live (clobberable) draft for `lab_logistics` instead of the authoritative confirmed source.

---

## Minimal fix (for the bug, independent of the deeper redesign)

Goal: guarantee `retry_draft["lab_logistics"]["sample_tubes"]` = the chemist's FIXED 2–4 tubes. Only `recommended` (solvent ratio) should change per round; `sample_tubes` and `from_user.target_window` are fixed.

Most surgical, in `_auto_retry_node` (tlc.py, before building `retry_draft` at 834): pull `lab_logistics` from the AUTHORITATIVE confirmed source rather than the live `draft`, e.g.
- read the FIRST attempt's persisted `trials.params["lab_logistics"]` (attempt 1 is the confirmed row) off `state.ctx.trials[job_id]`, OR
- read `trial.last_form_snapshot` if present (the confirmed form payload),
then build `retry_draft = {**draft, "lab_logistics": confirmed_lab_logistics, "recommended": recommended_param...}`.

Caveat: the truly authoritative copy is attempt-1's confirmed `form_values`. But per defect (a), attempt-1's `trials.params` may ALSO have been clobbered by the seq-29 overwrite — so reading "attempt 1's params" is only safe if it was NOT re-clobbered. The robust minimal fix is to source `lab_logistics` from the data that the WHOLE-BLOB overwrite cannot touch: either (i) stop the post-confirm `collecting_params` re-run from overwriting `lab_logistics` (make `TaskParamsSetEvent`/the LLM draft preserve `lab_logistics`), or (ii) carry `sample_tubes` on a field the LLM never writes. **Recommend pairing both**: (b) in `_auto_retry_node` read tubes from `last_form_snapshot`/the confirmed action, AND (a) make `TaskParamsSetEvent.apply` a section-merge for `lab_logistics` (or have the LLM draft never null it). Decision on (a) vs (b) scope should go to Drake — both are contract-adjacent.

### Does the deeper loop-boundary redesign change the minimal fix?
**Yes, materially.** If the redesign moves to a round-based Agent↔Lab contract (prep-once → run-round(ratio) → cleanup-on-success), then:
- A retry is no longer "mint a new full trial + full `CreateTLCTaskRequest`" — it becomes "send the next round's ratio to an already-prepared plate". `sample_tubes` would be sent ONCE at prep, not per round, so the per-retry `_submit_l4` would not re-validate `objects` at all → the "got 0" failure mode disappears by construction.
- The minimal fix (re-attach tubes per retry) becomes unnecessary/obsolete under the round model, but is still the correct stop-gap for the CURRENT full-task-per-attempt contract.
- Either way, defect (a) (whole-blob `TaskParamsSetEvent` clobbering confirmed lab-logistics) is worth fixing on its own — it is a latent data-integrity bug for any confirmed lab-logistics field.

---

## Caveats / Not Found

- **DB ground truth unavailable**: `talos_agent_db.trials` was reset to 0 rows at research time, so the persisted attempt-1 params could not be inspected directly. The root cause is established from the live log message-thread + event seq + the whole-blob `apply` code path, not from a DB dump.
- **`recommend_tlc_mixcase` is stubbed and ignores `trials`** — the "ratio adapts to observed Rf" behavior is not yet real; the redesign should not assume live ratio adaptation until that Mind route lands.
- **Did not fully trace** whether CC's confirmed `sample_cartridge_location` suffers the same post-confirm-clobber (the same `TaskParamsSetEvent` whole-blob shape applies); flagged as a parallel risk, not verified.
- **Did not read** BIC-lab-service's TLC task decomposition (where prep/cleanup actually live) — only confirmed the agent has no round/prep/cleanup concept. A round-based redesign needs a lab-service research pass for the robot program boundaries.
