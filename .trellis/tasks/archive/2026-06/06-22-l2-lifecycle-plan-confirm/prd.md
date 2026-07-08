# L2 Lifecycle: trial phase + plan-confirm stage + robot job materialization

> Child of `06-21-align-l1-l2-experiment-workflow-lifecycle`. This is the **remaining
> backend lifecycle slice** the parent still owns after `06-18` / `06-22` delivered the
> Level-1 objective stage + subagent. Sibling: `06-22-portal-lifecycle-objective-form`
> consumes this contract — land this first.

## Goal

Complete the backend lifecycle so plan confirmation advances the experiment to
`parameter_design`, materializes **robot-only** backend jobs (sparse `jobs.seq`), and
types `Trial.phase` as a real enum across model/repo/runtime/snapshot. After this, the
snapshot fully describes the Level-1/Level-2 state the portal stepper renders.

## What's already done (do NOT redo)

- Level-1 `Experiment.stage` enum + `experiment_objective → workflow_design` (06-18/06-22).
- Objective subagent + stage-gated routing; experiment creation in the objective subagent.
- `PlanConfirmedEvent.apply` currently flips `plans.status="confirmed"`, persists
  `plans.params.steps`, and materializes **ALL** steps (robot + manual) with contiguous seq.

## Code findings (ground truth, verified 2026-06-22)

- `PlanConfirmedEvent.apply` (`app/events/runtime_emitted.py:321-354`): materializes every
  step `for seq, item in enumerate(self.confirmed_jobs)` — robot AND manual; does **NOT**
  advance `Experiment.stage`.
- `SessionContext.next_job` (`app/core/context.py:200`): `next_seq = current.seq + 1` —
  **assumes contiguous seqs**. Robot-only sparse materialization breaks this; the cursor must
  scan to the next materialized job with `seq > current.seq`.
- `Trial.phase` is raw `String(32)` (`trials_repo.py:146`, `models.py:247`), server default
  `collecting_params`; no enum.
- `_FORM_CONFIRM_PHASE_ADVANCE` (`runtime_emitted.py:60`) keys phase transitions by raw strings.

## Requirements

### R1. `TrialPhase` enum (Level-2)

* Define `TrialPhase` in `app/core/enums.py`: `collecting_params | rts | conducting | done`.
* Persist enum **values** (not member names) — follow the `ExperimentStage` `values_callable`
  pattern established in 06-18 (`models.py` stage column).
* Type `Trial.phase` as `TrialPhase` in the model, `TrialSnapshot`, repo writes, runtime
  transition table (`_FORM_CONFIRM_PHASE_ADVANCE`), and the snapshot DTO.
* No scattered raw-string phase comparisons.
* Additive migration only if the column type changes; the existing `VARCHAR(32)` + value
  storage is fine, so likely **no migration** (verify with `alembic check`).

### R2. Plan-confirm advances `Experiment.stage`

* `PlanConfirmedEvent.apply` advances the owning experiment `workflow_design → parameter_design`.
* Idempotent / no-backward: no-op the stage write if already `parameter_design` (mirror the
  `ExperimentObjectiveConfirmedEvent` idempotent pattern).
* The existing confirmed-plan idempotent guard stays first.
* Must read the experiment via the plan (`plan → experiment_id`) inside the same tx.

### R3. Robot-only job materialization (sparse `jobs.seq`)

* `PlanConfirmedEvent.apply` materializes backend `jobs` **only** for confirmed steps whose
  `type == "robot"`.
* `jobs.seq` = the **original confirmed plan step index** (NOT a dense robot-only ordinal), so
  `plans.params.steps[job.seq]` always joins back to the matching plan card. Seqs are **sparse**
  when manual steps are skipped.
* Manual steps remain plan-cards only: persisted in `plans.params.steps`, NO `jobs` row, NO
  `trials`, NO Nexus dispatch.
* `plans.params.steps` stays the authority for robot/manual ownership (no `jobs.type` column).
* TLC/FP are not special-cased out of materialization — if a confirmed step is `type="robot"` it
  materializes like any other; Test Kit/demo inputs keep TLC/FP `manual` until their robot
  implementations land.

### R4. Cursor handles sparse seqs

* `SessionContext.next_job` returns the first materialized job whose `seq > current.seq`
  (scan, not `seq + 1`). When `current_job_id` is null → the lowest-seq materialized job.
* Runtime code must not assume contiguous seqs.
* `plans.current_job_id` still points at the last completed materialized job.

### R5. Snapshot exposes the typed lifecycle

* `SnapshotTrialItem.phase` typed as `TrialPhase` (lowercase value on the wire).
* `SnapshotExperimentItem.stage` already present (06-18); plan-confirm now moves it to
  `parameter_design` so the snapshot reflects it.
* Snapshot/live parity: a hard refresh and the plan-confirm SSE event agree on stage + the
  materialized robot jobs + trial phases.

## Out of Scope

* The Level-1 objective stage/subagent (done — 06-18/06-22).
* The portal (sibling task `06-22-portal-lifecycle-objective-form`).
* Real TLC/FP robot specialist execution.
* Manual "mark done" workflow.
* Changing Nexus material-readiness / dispatch-gate semantics (the existing CC/RE dispatch
  validation stays intact — params confirmation is separate from lab-logistics gating).
* Backfilling historical data.

## Acceptance Criteria

* [ ] `TrialPhase` enum defined; `Trial.phase` typed as `TrialPhase` across model/repo/runtime/snapshot; persists values not names.
* [ ] Plan confirmation advances `workflow_design → parameter_design`; idempotent; no-backward.
* [ ] Plan confirmation materializes `jobs` ONLY for confirmed `type="robot"` steps.
* [ ] `jobs.seq` equals the original plan step index; sparse when manual steps are skipped; `plans.params.steps[job.seq]` joins back.
* [ ] Manual steps create NO jobs and NO trials; remain visible plan cards.
* [ ] `SessionContext.next_job` scans `seq > current.seq` (handles sparse seqs); null cursor → lowest-seq job.
* [ ] Existing CC/RE dispatch validation intact (params confirm separate from lab-logistics gate).
* [ ] `SnapshotTrialItem.phase` typed `TrialPhase`; snapshot/live parity on stage + jobs + phase.
* [ ] ruff / format / pyright / alembic / full pytest green; spec docs updated (Rule 10).

## Definition of Done

* Backend lifecycle changes implemented + tested (repo, event-apply, cursor, snapshot, codec).
* Verification commands pass.
* `.trellis/spec/` updated (L4/persistence trials.phase enum, L4/events PlanConfirmedEvent
  robot-only + stage advance, L1/http-routes snapshot phase typing).
* Parent `06-21` implement.md cleanup banner updated to mark this slice done.
* Committed (per Drake's go-ahead).

## Research References

* Parent `06-21` `design.md` — the authoritative lifecycle/cursor/sparse-seq design.
* `06-18` shipped the `ExperimentStage` `values_callable` value-persistence pattern to mirror for `TrialPhase`.
