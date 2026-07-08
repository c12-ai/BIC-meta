# Fix: late task_params_set clobbers confirmed `recommended` → TLC eval crash

> Standalone bug (NOT a child of the TLC-ObjectLocation parent). Found by the
> final TLC E2E (session `b24f9b5d…`). Full root-cause:
> `.trellis/tasks/06-27-lab-bench-box-selector/research/post-dispatch-turn-failed-diagnosis.md`.
> **Plan-only for now** — owner wants PRD + design reviewed before implementation.

## Problem

A TLC experiment dispatches and runs, but the agent-side workflow then **silently
wedges**: after the lab reports the task terminal, an autonomous TASK_TERMINAL turn
enters the TLC Rf-eval node and crashes with `2 validation errors for TLCParam:
solvents/solvent_ratio Field required [input_value={}]` (`turn_failed`). The trial
is left `phase=conducting`, `analysis_completed=false`; the result-review form never
opens and the plan cursor never advances → CC/FP/RE never proceed.

## Root cause (a persistence overwrite race)

1. Params-confirm persists the trial's `recommended` (PE/EA) at API time
   (`FormConfirmedEvent.apply`, `runtime_emitted.py:604-605`, seq36).
2. ~25s later, a **still-running** LLM turn (`3d080e9e`) emits a whole-blob
   `task_params_set` whose apply does an **unconditional whole-blob replace** of
   `trials.params` (`TaskParamsSetEvent.apply`, `runtime_emitted.py:658-662`,
   seq37) carrying only `{from_user:{rxn, target_window:null}}` — **clobbering the
   just-confirmed `recommended`** on disk.
3. Dispatch still succeeds because `_submit_l4` reads `recommended` from the
   in-memory FORM_CONFIRM `form_values`, not from disk — **masking** the strip.
4. The autonomous TASK_TERMINAL turn (`f11d7bcc`) has no `form_values`; it seeds
   `params_draft` from the **stripped on-disk `trials.params`** → no `recommended`
   → `_evaluate_tlc_result_node` (`tlc.py:722-724`) falls through to
   `TLCParam.model_validate({})` → crash.

## Two defects to fix

- **D1 (real cause)** — `TaskParamsSetEvent.apply` whole-blob replace
  (`runtime_emitted.py:658-662`) can overwrite a confirmed `recommended`. This is a
  **contract-level event-apply change → Rule 10** (the event's persisted effect is
  a contract between the runtime emitter and the trial store).
- **D2 (defensive backstop)** — `_evaluate_tlc_result_node` (`tlc.py:722-724`) uses
  `... or TLCParam.model_validate(... or {})`, converting a missing recommendation
  into a bare pydantic crash. Should fail loud with an actionable error (Rule 9),
  not `TLCParam({})`.
- **D3 (optional hardening)** — TLC's `_post_react_route` (`tlc.py:382-385`) lacks
  the `analysis_completed` gate that CC (`cc.py:248`) / RE (`re.py:220`) have, so a
  re-driven terminal turn would re-enter the eval loop and re-crash. Add the gate
  for parity.

## Open design questions (to resolve in design.md)

- D1 approach — pick one (design.md will recommend): (a) section-MERGE in
  `TaskParamsSetEvent.apply` instead of whole-blob replace (preserve sections the
  event doesn't carry, e.g. `recommended`); (b) confirm-wins / phase-guard (don't
  let a `collecting_params`-era `task_params_set` land after the trial advanced to
  `rts`); (c) serialize the API-time confirm against the in-flight turn. Each has
  different blast radius across CC/RE (they share `TaskParamsSetEvent`).
- Whether D1 alone is sufficient or D2+D3 are also required (defense in depth).
- Rule 10: which spec doc(s) describe the `task_params_set` persisted-effect
  contract; update in the same change set.

## Acceptance Criteria (provisional — finalize in design)

- [ ] A late/in-flight `task_params_set` carrying only `from_user` does NOT strip a
      previously-confirmed `recommended` (or `lab_logistics`) from `trials.params`.
- [ ] After a TLC dispatch + terminal, the Rf-eval turn finds `recommended` and
      proceeds to recognition/result-review — no `turn_failed`, no wedge.
- [ ] If `recommended` is genuinely absent on a terminal TLC trial, the eval node
      fails loud with an actionable message (not `TLCParam({})`).
- [ ] CC/RE `task_params_set` behavior is unaffected (regression-checked).
- [ ] Spec updated (Rule 10); agent gate green (ruff, pyright, pytest).
- [ ] Re-run TLC E2E through to result-review (the leg the wedge blocked).

## Out of scope

- The TLC-ObjectLocation program (children 1–5, done).
- The LLM-abandon / nudge flakiness (separate).
- The `recommend_tlc_params` "target_window null" failure (contributing oddity,
  noted in research; investigate separately if it recurs).

## Notes

- Plan-only: write `design.md` (D1 approach decision + blast radius across CC/RE)
  before `task.py start`. Do not implement until reviewed.
