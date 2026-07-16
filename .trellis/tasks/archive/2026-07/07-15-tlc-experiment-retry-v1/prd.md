# TLC user-initiated experiment retry V1

## Goal

Make the existing TLC retry/rework control start a real fresh trial with fresh
material preparation, while preserving the source trial and leaving robot-level
material reuse for a later release.

## Requirements

- Scope is TLC only. CC/FP/RE rework behavior must not change.
- A TLC result-review retry and a TLC terminal execution-failure retry create the
  next attempt under the same job; the source trial remains historical.
- Copy stable TLC inputs and recommendation into the new trial, but clear
  `lab_logistics.sample_tubes` and TLC result/evidence fields.
- Never reuse, delete, return, dispose, or otherwise rewrite source-trial tubes.
- The new trial starts in `collecting_params`, opens Material Preparation, and
  never auto-dispatches.
- The normal staged-placement, readiness, params-confirm, and dispatch gates apply.
- The existing automatic TLC Rf round retry remains unchanged.
- Retry is idempotent: one source trial cannot mint multiple manual retry trials.
- Keep changes narrow; no schema migration and no robot/shared-types protocol change.

## Acceptance Criteria

- [ ] Clicking TLC “Retry experiment” on a pending result review creates exactly
      one next-attempt trial and foregrounds fresh Material Preparation.
- [ ] Clicking TLC “Retry experiment” after terminal execution failure does the
      same through an execute-authorized backend endpoint.
- [ ] The new trial keeps `from_user.rxn`, `target_window`, `recognition_mode`,
      and `recommended`, while clearing tube assignments and TLC evidence/result fields.
- [ ] The retry attempt has no Lab Task id, progress, analysis, result, or readiness state.
- [ ] A duplicate result-review confirm or duplicate failure retry request does not
      create another trial.
- [ ] Source-trial history and its material state remain unchanged.
- [ ] TLC automatic Rf round retry and non-TLC rework tests remain green.
- [ ] Focused Agent Service and Portal tests, lint/type checks for touched code,
      and `git diff --check` pass.

## Notes

- Parent product contract: `../../../Production-PRD.md` § User-Initiated Experiment Retry.
- V1 deliberately defaults to fresh materials because item-level Mars/Lab usage
  facts are not yet authoritative enough for safe reuse.
