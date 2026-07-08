# Readiness dry-run must run full create-side precondition chain

## Goal

The FE "validate readiness" preview (`POST /preparations/validate`) must return the same
verdict as the real dispatch gate (`POST /tasks/`), so a chemist never sees "ready" and then
a TurnFailed 400 at dispatch.

## Background (observed 2026-07-03)

TLC dispatch failed with a 400 → TurnFailed popup while the readiness preview passed.
Root cause: the dry-run endpoint runs ONLY `CommandValidator.validate_task_materials`,
while `TaskService.create_task` additionally runs, before materials:

- per-type param-shape checks (`validate_re_task_params` / `validate_fp_task_params` /
  `validate_tlc_task_params`)
- inside the TLC check: tube-placement rules (`_validate_tlc_objects`) and the durable-occupancy
  gate (`validate_tlc_prep`) — the one that fired (all silica plates / 50ml boxes `using`).

None of these run in the dry-run, so the preview and the gate have drifted.

## Requirements

1. The dry-run and `create_task` must execute the SAME precondition chain via one shared
   `CommandValidator` entry point — no duplicated ordering that can drift again.
2. `create_task` behavior is unchanged: same check order, same 400 messages, still no
   partial persist on failure.
3. The dry-run stays strictly write-free (no task/reservation/binding rows).
4. Blocking reasons must reach the FE: additive `errors: string[]` on
   `ValidatePreparationResponse` (existing fields `valid` / `missing_materials` / `warnings`
   unchanged — backward compatible).
5. FE renders the new `errors` in the MaterialPreparationPanel; dispatch stays gated on
   `valid === true`.
6. FE tube gate parity: `tubeSelectionProblem` must also reject selections not starting at
   column 1 (lab requires cols exactly `1..n`; FE currently only checks one-box / one-row /
   contiguous).
7. Spec update (Rule 10): document the `/preparations/validate` contract (currently in no
   spec doc) including the new `errors` field and the "same chain as create" guarantee.

## Acceptance Criteria

- [ ] With all silica plates occupied (`using`), TLC `POST /preparations/validate` returns
  `valid=false` with the occupancy message in `errors` — same message `POST /tasks/` 400s with.
- [ ] A TLC tube selection violating one-box / one-row / start-at-col-1 returns `valid=false`
  with the placement message in `errors` (dry-run, nothing persisted).
- [ ] RE/FP malformed params fail the dry-run the same way they fail create.
- [ ] Happy path: dry-run response identical to today plus `errors: []`.
- [ ] Unit test proves dry-run and create share the same chain (single entry point called by both).
- [ ] FE: `errors` rendered; a col-2-start tube selection is rejected client-side by
  `tubeSelectionProblem` (unit test in `tlc-params-draft.test.ts`).
- [ ] Lab + portal quality gates green (full chains re-run after any fix).

## Constraints / Non-goals

- No change to the robot-busy retry semantics (`ValidationResult.robot_busy`).
- No new endpoint; no versioning — additive response field only.
- Not addressing cross-step failure recovery or other TurnFailed sources.
