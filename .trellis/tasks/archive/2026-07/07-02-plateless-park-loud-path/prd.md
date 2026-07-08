# Loud path for plateless TLC round park (silent stall)

## Goal

A TLC round that parks `AWAITING_CONFIRMATION` WITHOUT a plate image must fail loud, not
stall silently forever.

## Finding (bench-proven 2026-07-02, task 07-02 run 3)

When the robot's round result carries no `captured_images`, the lab publishes the parked
status with `image_url=None`. The agent's round-done gate
(`BIC-agent-service/app/session/event_ingress.py:115` — `if status == AWAITING_CONFIRMATION
and payload.image_url is not None`) falls through to the fast path, where
`_derive_transition_key` has no key for `awaiting_confirm` → silent return, MQ message ACKed.
Result: ZERO session events, no warn log, no task_progress, no timeout — trial frozen at
`status=dispatched, phase=conducting`; chemist and FE see "in progress" forever. The code
comment calls this park "defensive — does not occur"; the stale mock proved it occurs.

Full evidence chain: task 07-02 run-3 report (bench runner, 2026-07-02), run log
`/tmp/bic-e2e-form-edit-sync/run3.log`.

## Second instance of the same gap (2026-07-02, task 07-02 run 4b)

When a dispatched lab task FAILS (lab `tasks.status=failed` — e.g. the round-2 IndexError,
session `40235a4a…`), the agent-side trial sits `conducting`/`failed` and follow-up agent turns
tell the chemist "The TLC experiment is currently running… standing by". Zero `turn_failed`,
nothing in chat. Scope of this task should cover BOTH silent shapes: plateless park AND
lab-task-failure — same seam (loud path for lab-side anomalies reaching the agent).

## Requirements (draft)

- R1: A plateless `awaiting_confirm` park emits, at minimum, a warn log + a task_progress
  (or equivalent) event so the stall is visible in session events and the FE.
- R2: Decide the recovery semantics (retry-photo request? fail the round? HITL decision?) —
  business call for Drake during planning.
- R3: Regression test pinning the loud path.

## Acceptance Criteria (R2 decided 2026-07-03: Option 2 — fail-loud, chat-visible; see design.md)

- [x] Plateless park emits warn log + terminal TaskProgressEvent (R1) — event_ingress guard.
- [x] Recovery semantics (R2): trial → failed via _handle_terminal delegation; chemist told in
      chat via TASK_TERMINAL(failed) → narrate; no silent wait, no auto-retry promise.
- [x] Second shape: post-dispatch lab failure narrates via _NARRATE_PROMPT_LAB_TASK_FAILED,
      not generic "standing by".
- [x] Regression tests pin the loud path (R3): non-mocked system test red→green proven,
      idempotency + conjunctive-guard tests. Full suite 1125 passed; pre-commit clean.
- Committed: 4db3eb6 (+ spec note d464ab2) on fix/plateless-park-loud-path. Not pushed.

## Re-validated STILL_VALID (2026-07-03, sonnet research-agent pass)

Core bug confirmed present on agent-service main (`7d2b1ba`): plateless park still falls
through `event_ingress.py:115` → `_derive_transition_key` (`trials_repo.py:52-88`) has no
`awaiting_confirmation` key → silent return at `fast_path_handlers.py:450-451`; no warn, no
task_progress. R2 (recovery semantics) still Drake's open call; R3 absent — the existing
`test_round_awaiting_confirm_without_image_is_progress_only` (`test_event_ingress.py:236`)
tests routing only and its docstring wrongly claims a progress event is emitted (fix it here).
Second instance (lab-task-failure) PARTIALLY mitigated: PR #32 routing keeps a `failed` trial
out of the Rf-eval loop, but narration is still the generic `_NARRATE_PROMPT_TEXT_REPLY`
(`tlc.py:403-410`) — whether that is "loud enough" rides the R2 decision.

## Second verification pass (2026-07-03 19:23, sonnet) — VERDICT unchanged: STILL_VALID

Confirmed on agent-service main `7d2b1ba`, clean tree. Two corrections to the section above:

- Test docstring at `test_event_ingress.py:236` is NOT wrongly claiming emission — it says
  "emitted as plain progress" describing routing. The real R3 gap: the test mocks the fast
  path (`assert_awaited_once_with`), so it can never catch the silent return at
  `fast_path_handlers.py:450-451`. Don't "fix the docstring" — write a non-mocked loud-path
  regression test.
- `tlc.py:403-410` conflates two spots: the route gate `_post_react_route` is at
  `tlc.py:403-411` (a `failed` trial fails the `awaiting_confirmation` check → `narrate`);
  the generic prompt is selected in `_build_narrate_prompt` (`tlc.py:552-561`,
  `_NARRATE_PROMPT_TEXT_REPLY` at 542). `_NARRATE_PROMPT_SUBMIT_FAILED` only covers
  submit-time failure — the silent shape is specifically post-dispatch MQ `failed` on a
  `conducting` trial.
- Warn-log nuance: `try_record_transition_announcement` (`trials_repo.py:668-674`) warns only
  when `derived_key is None` AND status is terminal; non-terminal `awaiting_confirmation`
  stays fully silent. Bug intact, no fixing commits after `7d2b1ba`.
