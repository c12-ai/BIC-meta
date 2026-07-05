# Design — Migrate 5 plan-first specs to objective-first flow

Decision date: 2026-07-03. Research basis: `research/migration-recipe.md` (per-spec recipes).

## Approach
Extract ONE shared helper `driveObjectiveFirstSession()` as a new export in `tests/helpers.ts`
(session create → objective prompt with SMILES/baseline/feed/purity+yield → poll
`experiments[0].stage == 'experiment_objective'` → `POST /objective/confirm` → wait for
auto-proposed plan / Workflow Design heading), lifted from the merged reference
`tests/form-edit-sync-on-send.spec.ts`. Keep `__paramsFormEvents` (specialist-filtered)
instrumentation per-spec (closes over `addInitScript`/`page` — matches existing convention).

Plan-review annotation (code-review gate, 2026-07-03): tests/helpers.ts currently has FIVE
exports (`gotoApp`, `PNG_1x1`, `resetLabState`, `waitForParamsForm`,
`confirmParamsThroughMaterialDialog`) — add `driveObjectiveFirstSession` as the sixth; don't
duplicate `gotoApp`'s viewport/goto work inside it or call `gotoApp` redundantly in migrated
specs.

## Per-spec migration (scope = exactly these 5)
1. `cc-re-chained-flow.spec.ts` — replace plan-first opening (:282-329 area) with helper;
   drive the FULL TLC robot leg before the CC leg (CC locked until TLC Accept — fixed
   TLC→CC→FP→RE workflow); replace unfiltered `__paramsFormCount` (:256) with
   specialist-filtered events; replace `test.setTimeout(35min)` (:213) with 40min (real robot
   leg added) — config cap stays 12min per test? NO: spec-level setTimeout overrides config;
   set deliberately and document why in-spec.
2. `honest-chain-guard.spec.ts` (:95) — objective opening via API is allowed for setup, but
   inside the guarded flow keep DOM-only waits (no reload, no /events fallback, no window.__ —
   that is the spec's whole point; preserve it).
3. `manual-live-demo.spec.ts` (:265) — helper opening; REMOVE the obsolete rts-phase
   go-ahead gate (:491-523, dispatch is deterministic now); specialist-filter the count
   (:179-207); G3 PMC/SMC toggle lives in TlcUploadControl (CC-scoped) — verify reachable
   after TLC Accept, else drop G3 with an in-spec comment explaining why.
4. `task-progress-stream.spec.ts` (:223) — helper opening; TLC leg first; scope ALL
   task_progress assertions to the CC trial_id (second task_created) or they mix TLC+CC
   events; specialist-filter (:141,171).
5. `tlc-upload-chain.spec.ts` (:169,:311) — T1 untouched; T2/T3 get objective opening +
   delete `test.skip(!planProposed)` (skip-forever is the bug); plate upload happens in CC
   context after TLC Accept.

If a spec's original intent cannot survive migration, STOP and flag it for Drake as a
deletion candidate — do not force a hollow test (Rule 7: tests encode intent).

## Acceptance / verification split
- This change set: helper + 5 migrated specs; gates = tsc/eslint (repo convention) +
  Playwright `--list` parses.
- Live-bench green run (PRD acceptance) happens AFTER implementation via the bic-e2e-runner
  playbook; COMMIT ONLY AFTER the bench run passes (Rule 9 — don't commit specs that were
  never executed).

## Contracts
Test-only change; no FE/BE contract touched. No spec-doc contract edit required.

## Rollback
Revert the single test-only commit; product code untouched.
