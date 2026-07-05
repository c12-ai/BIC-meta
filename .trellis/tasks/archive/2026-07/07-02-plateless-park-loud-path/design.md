# Design — Loud path for plateless TLC park + lab-task failure (R2 decided)

Decision date: 2026-07-03. Decider: main session (Fable5) per Drake's /loop delegation.
Research basis: `research/fix-seams.md` (verified seams, exact refs).

## R2 decision: Option 2 — fail-loud, chat-visible

A plateless `awaiting_confirmation` park is a contract violation (R7 contract: parked rounds
carry a plate image; mock fixed in mars_interface_mock `61d29c9`). Without an image the round
can never be evaluated, so the trial cannot proceed → treat it as a lab-side failure and tell
the chemist in chat. Rejected: Option 1 (progress-event-only) — chemist still uninformed in
chat, which is the original complaint; Option 3 (HITL retry-photo) — needs new graph nodes +
robot retry support that doesn't exist (YAGNI; can layer on later without rework).

## Changes (BIC-agent-service, branch off main @ 7d2b1ba)

### 1. event_ingress.py — plateless-park branch
New guard BEFORE the non-terminal fast-path routing (currently `event_ingress.py:119`):

- Condition: `status == AWAITING_CONFIRMATION and payload.image_url is None`
- Actions: warn log (`event_ingress.plateless_park`, include trial_id/session_id) →
  synthesize a terminal failure through the SAME machinery `_handle_terminal` uses:
  `apply_terminal_from_lab(status=failed, error_message="TLC round parked awaiting
  confirmation without a plate image")` + `emit_terminal_progress` + `submit_turn(TASK_TERMINAL)`.
- REUSE `_handle_terminal` (delegate with a synthesized failed payload) if its signature
  allows; only inline the three calls if delegation contorts the payload. Do not copy-paste
  the terminal flow.
- Key property: `TASK_TERMINAL` on a `failed` trial routes to `narrate` in the TLC subgraph
  (does NOT enter the Rf-eval loop — verified `tlc.py:407`); `TASK_TERMINAL(None)` would
  wrongly enter `evaluate_tlc_result` — do not use it.

### 2. tlc.py — specific failed-lab-task narration (covers second silent shape)
- New constant `_NARRATE_PROMPT_LAB_TASK_FAILED`: instruct the LLM to tell the chemist
  plainly the lab task failed and the workflow leg stopped; no fabricated error details;
  suggest checking the lab panel / retrying from there (duo-panel: user can act without agent).
- Selection branch in `_build_narrate_prompt` (tlc.py:552-561): when `last_tool_name is None`
  AND `current_phase == "conducting"` AND `ctx.find_trial(task_id).status == "failed"` →
  return the new prompt. Existing `_NARRATE_PROMPT_SUBMIT_FAILED` (submit-time) untouched.

### 3. Tests (R3)
- UPDATE `test_round_awaiting_confirm_without_image_is_progress_only`
  (`tests/.../test_event_ingress.py:236`): plateless push now routes to the loud branch, not
  the fast path — rename + re-pin (docstring states WHY: silent stall bench-proven 07-02).
- ADD non-mocked regression test wiring a REAL `FastPathHandlers` (pattern:
  `test_fast_path_handlers_system.py`): plateless park → asserts warn log (caplog), a
  terminal task_progress event appended to session events, and a TASK_TERMINAL turn
  submitted. Must FAIL on current main (silent return), PASS after fix.
- ADD pure unit test for `_build_narrate_prompt` failed-branch selection (minimal fake state).

## Plan-review amendments (python-expert gate, 2026-07-03)
- Idempotency: plateless parks can be MQ-redelivered or arrive after the trial is already
  terminal — the branch MUST inherit `_handle_terminal`'s duplicate-terminal semantics
  (delegate, don't inline; verify what it does on an already-terminal trial and add that case
  to the system test).
- Null-safety: `ctx.find_trial(task_id)` may return None — narrate-branch condition checks
  trial is not None before `.status`.
- Log assertion: if logging is structlog-based, caplog may not capture — the system test's
  primary assertion is the appended session event; assert the warn only via a pattern the
  test suite already uses.

## Contracts
No FE contract / BIC-shared-types change: only existing event kinds (task_progress) and the
existing turn-submission path are used. Rule 10: no spec contract edit required; add a
loud-path convention note to the backend spec during step 3.3.

## Rollback
Single revert of one commit; no migration, no data shape change.
