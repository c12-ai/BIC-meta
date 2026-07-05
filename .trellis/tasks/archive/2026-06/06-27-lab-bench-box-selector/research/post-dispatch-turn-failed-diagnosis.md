# Research: post-dispatch `turn_failed` (autonomous TASK_TERMINAL turn building `TLCParam` from `{}`)

- **Query**: Root-cause the autonomous `turn_failed` (turn `f11d7bcc`) that fired after a TLC task dispatched successfully in session `b24f9b5d-eecd-45ec-bf84-dd4f50dca675`, building `TLCParam` from an empty dict.
- **Scope**: internal (BIC-agent-service), READ-ONLY (logs + DB + code)
- **Date**: 2026-06-28

---

## ROOT CAUSE (one line)

The lab's terminal MQ message spawned an **autonomous `TASK_TERMINAL` turn** (`EventIngress._handle_terminal` → `orchestrator.submit_turn`, no user message); it routed to the TLC subgraph's deterministic Rf-eval node `_evaluate_tlc_result_node` (`tlc.py:722`), which crashed at `TLCParam.model_validate({})` because the trial's persisted `trials.params` had **no `recommended` section** — that section was written to disk by the API-time params-confirm apply (seq36) but then **overwritten ~25s later by a still-running LLM turn's whole-blob `task_params_set`** (seq37, turn `3d080e9e`) that carried only `{from_user}`. Dispatch still succeeded because it read `recommended` from the in-memory FORM_CONFIRM `form_values`, not from disk — so the on-disk strip went unnoticed until the terminal turn re-loaded params from disk.

It is the **TLC Rf-eval loop ENTRY misfiring on an under-persisted trial**, driven by a **persistence overwrite race**, not by the retry leg itself.

---

## Hard evidence (DB + log)

Stack trace (`app/logs/error.log:38529-38587`), terminal call site:

```
File ".../app/runtime/graphs/specialists/tlc.py", line 722, in _evaluate_tlc_result_node
    recommended = _trial_recommended_param(trial) or TLCParam.model_validate(
File ".../pydantic/main.py", line 732, in model_validate
pydantic_core._pydantic_core.ValidationError: 2 validation errors for TLCParam
solvents        Field required [type=missing, input_value={}, input_type=dict]
solvent_ratio   Field required [type=missing, input_value={}, input_type=dict]
During task with name 'evaluate_tlc_result' ...
During task with name 'tlc_subgraph' ...
```

Session event timeline (`session_events`, session `b24f9b5d…`):

| seq | kind | turn_id | emitted_at | note |
|---|---|---|---|---|
| 35 | task_created | 3d080e9e | 06:09:35 | trial `d5920849` minted for `…-job-0` (executor **tlc**) |
| 36 | **form_confirmed** | 2f382694 | 06:09:36 | params confirm, `form_values` has `recommended:{PE,EA}`, `target_window:[0.3,0.6]`. **API-time apply writes them to `trials.params`** |
| 37 | **task_params_set** | 3d080e9e | 06:10:01 | turn 3d080e9e STILL running; `update_tlc_params` emits `{from_user:{rxn, target_window:null}}` — **whole-blob replace strips `recommended`** |
| 41 | turn_completed | 3d080e9e | 06:10:06 | the overwriting turn finally finishes |
| 42–45 | dispatch | 2f382694 | 06:10:06 | params-confirm re-entry → `auto_submit` → `_submit_l4` (reads in-memory draft, **dispatch OK**, `lab_task_id=20f99a92`) |
| 46–47 | task_progress | (mq) | 06:10:06 | lab completes |
| 50 | turn_started | **f11d7bcc** | 06:10:13 | **autonomous TASK_TERMINAL turn** (no `user_message_submitted` precedes it) |
| 51 | **turn_failed** | f11d7bcc | 06:10:30 | `2 validation errors for TLCParam … input_value={}` |

Trial row after the run (`trials` table) — the persisted params confirm the strip:

```
trial_id  = d5920849-4f87-430a-a94a-88802d330b22
job_id    = 558d5b50-…-job-0   (executor tlc, seq 0)   ← TLC job, NOT CC
status    = completed
phase     = conducting          ← never advanced to done
analysis_completed = f          ← result-review never opened
params    = {"from_user": {"rxn": "...", "target_window": null}}   ← NO "recommended"
```

Jobs for the plan (`jobs` table): `job-0 tlc`, `job-1 cc`, `job-2 fp`, `job-3 re`. The seq34 narration "starting the Column Chromatography step with Specialist cc" is an **LLM hallucination** — the dispatched trial is the **TLC** job. The TLC specialist ran correctly.

---

## Q1 — What starts the autonomous turn after dispatch completes?

The MQ terminal-status pipeline, NOT a graph auto-continue or retry re-entry.

- `app/session/event_ingress.py:115-182` `EventIngress._handle_terminal`: when the lab publishes a terminal `TaskStatusMsgPayload`, it commits the terminal fields onto `trials` then **builds a `TurnInput(kind=TASK_TERMINAL, source=MQ)` with no user message** and calls `orchestrator.submit_turn(session_id, turn)` (line 172-182).
- `app/session/orchestrator.py:246-266` `submit_turn` enqueues it on the per-session worker; `_worker_loop` (line 295-323) dequeues and runs `_run_turn` (line 325-357), which emits `turn_started` then `runtime.invoke`. No user input is involved — this is the autonomous turn `f11d7bcc`.
- This is **intended** behavior: the TLC design routes a terminal trial in `conducting` into the deterministic Rf-eval loop (`tlc.py:50-54`, `382-385`, `698-712`). The terminal turn is how the async lab result re-enters the agent. It is neither a retry nor a spurious re-entry — it's the normal "advance to result-review" turn. It just crashed at its first node.

Routing of a TASK_TERMINAL turn to the right trial:
`reception_node._pick_terminal_task_specialist` (`reception_node.py:139-175`) looks up `turn.task_terminal.task_id` in `ctx.trials`, resolves the executor (tlc) via the parent job, sets `source="task_terminal"`, `current_phase="conducting"`. The dispatch bundle's `params_draft` is seeded from the persisted trial by `_extract_trial_flags_for_dispatch` (`reception_node.py:393-440`, line 437-438: `if trial.params: out["params_draft"] = dict(trial.params)`). → `specialist_dispatcher` routes to `tlc_subgraph` → `_post_react_route` (`tlc.py:382-385`) sees `conducting` + terminal status → `evaluate_tlc_result`.

## Q2 — Where `TLCParam` is built from `{}` (exact call site)

`app/runtime/graphs/specialists/tlc.py:722-724`, inside `_evaluate_tlc_result_node`:

```python
recommended = _trial_recommended_param(trial) or TLCParam.model_validate(
    (draft.get("recommended") if isinstance(draft, dict) else None) or {}
)
```

Two fallbacks, both empty here:
1. `_trial_recommended_param(trial)` (`tlc.py:230-243`) reads `trial.params["recommended"]`; returns `None` because the persisted blob is `{"from_user": …}` (no `recommended`).
2. `draft.get("recommended")` — `draft` is `state.params_draft`, seeded from the same persisted blob → `None`.

So the expression collapses to `TLCParam.model_validate({})`. `TLCParam` requires `solvents` and `solvent_ratio` (both missing) → `ValidationError`. The `or {}` "defensive default" is the bug: it converts a missing-recommendation into an invalid-construction crash instead of failing loud with an actionable message or skipping gracefully.

NOTE this is NOT the guarded `_submit_l4` TLC arm (`tools.py:542-566`). That arm explicitly raises `"submit_l4_execution: params not dispatchable"` when `tlc_form.recommended is None`. It did not fire because at dispatch time the in-memory draft (from FORM_CONFIRM `form_values`) still had `recommended` — only the on-disk copy was stripped.

## Q3 — Is this the TLC Rf-retry loop misfiring?

No — it crashed at the **ENTRY** of the eval loop, before any retry leg.

- Topology (`tlc.py:993-1009`): `evaluate_tlc_result → {auto_retry | emit_result_review}`. `_auto_retry_node` (`tlc.py:769-860`) and `_dispatch_retry_trial` (`tlc.py:665-696`) never ran — the crash is upstream at `_evaluate_tlc_result_node` (`tlc.py:698-767`).
- The loop is turn-driven, not an in-graph cycle: `auto_retry` re-dispatches then ends the turn (`tlc.py:1009 add_edge("auto_retry", END)`); the next attempt arrives as a fresh TASK_TERMINAL turn. So a retry would re-enter the SAME crashing node. But on this trace `attempt=1` and the crash is on the very first eval, so no retry was attempted (1 trial, 1 `task_dispatched` in the DB — no attempt-2 minted).
- `TLC_MAX_ATTEMPTS=3` (`tlc.py:155`) and `_evaluate_route` (`tlc.py:182-193`) are irrelevant here — they run only after a successful recognition, which never happened.

## Q4 — Why `recommended` is empty on that turn

A **persistence overwrite race** between the API-time params-confirm apply and a still-running LLM turn, with a whole-blob replace:

1. `service.submit_form_confirm` (`service.py:168-301`) runs `FormConfirmedEvent.apply` at **API time** in its own transaction via `persist_event_with_decision_cas` (line 275), THEN enqueues the FORM_CONFIRM turn. The apply (`runtime_emitted.py:545-613`) for a PARAMS confirm in `collecting_params` (`_FORM_CONFIRM_PHASE_ADVANCE[("collecting_params","params")]="rts"`, line 60-63) writes `update_fields["params"] = dict(self.form_values)` (line 604-605) — i.e. it DID persist `recommended` + `target_window` at **seq36 / 06:09:36**.
2. But turn `3d080e9e` (the trial's first specialist turn) was **still running** until 06:10:06. At **06:10:01 (seq37)** its `update_tlc_params` tool emitted `TaskParamsSetEvent` whose apply (`runtime_emitted.py:658-662`) is a **whole-blob replace**: `fields={"params": self.params}` with `params = {"from_user": {rxn, target_window:null}}`. This **clobbered the just-confirmed `recommended`** and re-nulled `target_window`.
3. The dispatch turn `2f382694` then read `recommended` from its in-memory `SpecialistState.params_draft` (projected from the FORM_CONFIRM `form_values` by `reception_node._validate_form_values_and_seed_drafts`, `reception_node.py:366-385`), so dispatch passed the `_submit_l4` guard and succeeded — masking the on-disk strip.
4. The autonomous terminal turn `f11d7bcc` has **no `form_values`** (it's a TASK_TERMINAL, `form_confirm_payload=None`), so `reception_node` could only seed `params_draft` from the **stripped on-disk `trials.params`** → no `recommended` → crash.

Contributing oddity (upstream, not the crash cause): turn `3d080e9e` ran `recommend_tlc_params` which FAILED (seq39: "missing/invalid fields: target_window") because `target_window` was null in its draft — so that turn never produced a `recommended` of its own; the only `recommended` that ever existed came from the chemist/E2E `form_values`, and it lived on disk for ~25s before being overwritten.

## Q5 — Harmful or cosmetic? (verdict)

**Harmful (session-wedging), but bounded — not a retry storm, no double-dispatch.**

- The E2E reported PASS because the lab task completed (seq46-47) before the crash. But the agent side is left **wedged**: trial `phase=conducting`, `status=completed`, `analysis_completed=false` (verified in DB). The result-review form (`_emit_result_review_node`, `tlc.py:862-910`) never opened, `TaskAnalysisCompletedEvent` (`tlc.py:892`) never fired, and the plan cursor never advanced — so CC/FP/RE never proceed. A real chemist would see a `turn_failed` after their TLC dispatched and the workflow would stall.
- **No double-dispatch / no state corruption**: the crash is at the first eval node, before `auto_retry`/`_dispatch_retry_trial`. DB shows exactly 1 trial and 1 `task_dispatched`. No attempt-2 minted.
- **No infinite retry loop**: `EventIngress.handle_task_status` returns successfully once the turn is *enqueued*, so the MQ consumer ACKs the message (`consumer.py:303-305`) BEFORE the turn runs and fails asynchronously on the worker. The orchestrator swallows the failure into one `TurnFailedEvent` (`orchestrator.py:356-357`). The terminal message is not redelivered, so the crash fires exactly once.
- **Latent re-crash risk**: TLC's `_post_react_route` (`tlc.py:382-385`) has **no `analysis_completed` gate**, unlike CC (`cc.py:248`) and RE (`re.py:220`) which both guard `and not trial.analysis_completed`. If the same terminal turn were ever re-driven (e.g. reconciler gap-1 recovery, or a manual re-enqueue), it would re-crash identically because `recommended` is still absent on disk and `analysis_completed` is still false.

### Recommended fix direction (do NOT implement)

Two independent defects; fixing either prevents this crash, but both should be addressed:

1. **Stop the overwrite race (the real cause)** — `TaskParamsSetEvent.apply` (`runtime_emitted.py:658-662`) does an unconditional whole-blob replace of `trials.params`. A late in-flight LLM `task_params_set` can clobber a freshly chemist-confirmed `recommended`. Options to surface with the owner: make the params write a section-merge instead of whole-blob replace; or have the confirm apply win (e.g. don't let a `collecting_params`-era write land after the trial advanced to `rts`); or serialize the confirm against the in-flight turn (the confirm applies at API time while turn `3d080e9e` is mid-flight). This is a contract-level change → Rule 10 (spec update) applies.

2. **Make `_evaluate_tlc_result_node` fail loud, not crash on `{}`** (`tlc.py:722-724`) — replace the `or {}` "default" with an explicit guard: if neither `trial.params["recommended"]` nor `draft["recommended"]` is present on a terminal TLC trial, raise an actionable `RuntimeError` (the dispatched condition is unrecoverable for recognition) per Rule 9, rather than a bare pydantic `ValidationError` from `TLCParam({})`. A dispatched trial should always carry its `recommended`; its absence here is the symptom of defect #1, so this is the defensive backstop, not the primary fix.

Optionally, add the missing `analysis_completed` gate to TLC's `_post_react_route` (`tlc.py:382-385`) to match CC/RE, so a re-driven terminal turn for an already-reviewed trial doesn't re-enter the eval loop.

---

## Files cited

| File:line | Role |
|---|---|
| `app/runtime/graphs/specialists/tlc.py:722-724` | **Crash site** — `TLCParam.model_validate({})` |
| `app/runtime/graphs/specialists/tlc.py:230-243` | `_trial_recommended_param` (returns None on missing) |
| `app/runtime/graphs/specialists/tlc.py:382-385` | `_post_react_route` terminal → `evaluate_tlc_result` (no analysis_completed gate) |
| `app/runtime/graphs/specialists/tlc.py:698-767` | `_evaluate_tlc_result_node` |
| `app/session/event_ingress.py:115-182` | spawns the autonomous TASK_TERMINAL turn |
| `app/session/orchestrator.py:325-357` | `_run_turn` (drives turn, emits turn_failed) |
| `app/runtime/graphs/nodes/reception_node.py:139-175` | `_pick_terminal_task_specialist` |
| `app/runtime/graphs/nodes/reception_node.py:393-440` | `_extract_trial_flags_for_dispatch` (seeds draft from disk) |
| `app/events/runtime_emitted.py:545-613` | `FormConfirmedEvent.apply` (API-time params write) |
| `app/events/runtime_emitted.py:658-662` | `TaskParamsSetEvent.apply` (**whole-blob replace — the clobber**) |
| `app/events/runtime_emitted.py:60-63` | `_FORM_CONFIRM_PHASE_ADVANCE` |
| `app/session/service.py:168-301` | `submit_form_confirm` (apply at API time, then enqueue) |
| `app/runtime/graphs/specialists/tools.py:542-566` | `_submit_l4` TLC arm (guards `recommended is None`; not the crash path) |
| `app/mq/consumer.py:303-348` | MQ ACK-on-enqueue (so crash does not redeliver/loop) |
| `app/runtime/graphs/specialists/cc.py:248`, `re.py:220` | CC/RE DO gate on `analysis_completed`; TLC does not |

## Caveats

- The earlier `12:12:51` error in `error.log` (`unrecognized TLC slot id: 'tlc_rack_box_2ml_l1_slot_1'`, a different session `3cb2419f`) is the **parent task's** slot-taxonomy bug (prd.md), unrelated to this `f11d7bcc` crash.
- `metric.phase_advance_mismatch_total` was checked and is NOT present for decision `5f7a7e91` — the form-confirm apply DID match `("collecting_params","params")` and DID write `recommended`; the loss is purely the later seq37 overwrite, confirmed by seq ordering (36 < 37) and emitted_at (06:09:36 → 06:10:01) with turn `3d080e9e` still open until 06:10:06.
