# Implement: L2 Lifecycle — Plan Confirm

- **Task**: `06-22-l2-lifecycle-plan-confirm`
- **Design**: `./design.md` (read it first — exact `file:line` and the BLOCKER note)
- **Branch**: current is `feat/shared-types-v1-1-6a1-cc-re-migration`. Confirm
  with Drake whether this work lands here or on a new branch before committing.

> **PRE-FLIGHT (Rule 1 / Rule 9).** The PRD for this task does not exist on disk.
> Resolve the three Open Questions in `design.md §10` with Drake BEFORE writing
> code. Do NOT proceed on assumption if any answer is uncertain.

> **Run `trellis-before-dev` for the L4 + L2 layers** (`app/events/`,
> `app/repositories/`, `app/core/`) before editing — load
> `.trellis/spec/backend/L4/` and `/L2/` conventions.

Validation commands used throughout (run from `BIC-agent-service/`):
```bash
uv run ruff check app/ tests/ && uv run ruff format --check app/ tests/
uv run pyright app/core/enums.py app/data/models.py app/repositories/trials_repo.py \
  app/api/routers/sessions.py app/events/runtime_emitted.py app/core/context.py
uv run alembic check                       # expect NO new DDL diff (§ Phase 1)
uv run pytest tests/unit/test_runtime_emitted_apply.py tests/unit/test_reception_node.py \
  tests/unit/test_persistence_repo_trials.py tests/unit/test_persistence_repo_snapshot.py \
  tests/unit/test_persistence_repo_jobs.py tests/unit/test_events_codec.py \
  tests/unit/test_import_hygiene.py -q
```

---

## Phase 1 — `TrialPhase` enum + model/repo/snapshot typing (no behavior change)

**Goal:** introduce the enum and re-type the column/DTO. Pure typing; the
persisted strings are identical, so all existing tests must still pass
unchanged (except the optional identity assertion in step 1.5).

### Steps
1. `app/core/enums.py` — append `TrialPhase(StrEnum)` after line 108
   (`ExperimentStage`). Values: `collecting_params / rts / conducting / done`
   (byte-identical to `SpecialistPhase` *by coincidence*). Copy the design `§3.1`
   block verbatim. **Do NOT alias or merge with L3 `SpecialistPhase`** — they are
   intentionally distinct concepts that may diverge (design §3.1 decision). Leave
   `specialist.py` `SpecialistPhase` and `reception_node.py:78`
   `get_args(SpecialistPhase.__value__)` **untouched**. Add a 1-line comment on
   `TrialPhase` noting `SpecialistPhase` is the separate L3 agent-work sibling.
2. `app/data/models.py` — line 35 import: add `TrialPhase`. Line 255: change
   `Trial.phase` to the `SQLEnum(TrialPhase, native_enum=False, length=32,
   values_callable=…)` form (design `§3.2`, mirroring `Experiment.stage`
   117-126). Keep `server_default="collecting_params"`.
3. `app/repositories/trials_repo.py` — line 33 import: add `TrialPhase`. Line
   146: `TrialSnapshot.phase: str` → `phase: TrialPhase`. `_row_to_snapshot`
   (166) needs no change.
4. `app/api/routers/sessions.py` — import `TrialPhase`; line 516:
   `SnapshotTrialItem.phase: str` → `phase: TrialPhase`. Mapping at 679 unchanged.
5. (Optional, Rule 7) `tests/unit/test_persistence_repo_trials.py:97` — keep the
   `== "collecting_params"` assertion (StrEnum compares equal) and ADD
   `assert snap.phase is TrialPhase.COLLECTING_PARAMS` for identity coverage.

### Validation
```bash
uv run ruff check app/ tests/
uv run pyright app/core/enums.py app/data/models.py app/repositories/trials_repo.py app/api/routers/sessions.py
uv run alembic check          # CRITICAL: must report NO new migration / no DDL diff
uv run pytest tests/unit/test_persistence_repo_trials.py tests/unit/test_persistence_repo_snapshot.py -q
```
**If `alembic check` produces a diff** → the `native_enum=False` setting is not
suppressing the type DDL; STOP and reconcile (do not auto-generate a migration
without Drake). Expected: empty diff (matches how `Experiment.stage` landed in
06-18).

### Rollback point / commit
Commit: `feat(l4): TrialPhase enum + value-persisted trials.phase column`.
This phase is independently revertable and ships no behavior change.

---

## Phase 2 — `PlanConfirmedEvent` robot-only materialization + stage advance

**Goal:** confirm materializes ROBOT-only jobs (sparse `seq = original index`)
and advances `workflow_design → parameter_design` idempotently.

### Steps
1. **Verify `PlanSnapshot.experiment_id` exists** — read
   `app/repositories/plans_repo.py`. If present → design `§4.4` Option A (reuse
   the `plan` already fetched at runtime_emitted.py:328:
   `experiment = await tx.experiments.get(plan.experiment_id)`). If absent → add
   `ExperimentsRepo.get_by_plan(plan_id)` (one JOIN) and use it.
2. `app/events/runtime_emitted.py` `PlanConfirmedEvent.apply` (321-354):
   - KEEP guard (328-330), status flip (332-335), params overwrite (339-342).
   - Replace the job loop (343-354) with the robot-only loop (design `§4.2`):
     `if item.get("type") != "robot": continue` before `tx.jobs.insert`,
     `enumerate` index as `seq`.
   - After the loop, add the stage advance (design `§4.3`): resolve experiment
     (step 1), `if experiment is not None and experiment.stage ==
     "workflow_design": await tx.experiments.update_fields(experiment.experiment_id,
     {"stage": "parameter_design"})`. Use the **literal** `"parameter_design"`
     (NO `app.core.enums` import — `test_import_hygiene` Gate 2 enforces this).
     Add a comment: literal must equal `ExperimentStage.PARAMETER_DESIGN.value`.
   - Update the class docstring (284-314): change "materialize ALL jobs (robot
     AND manual)" to robot-only + note the stage advance.
3. Update the module-level comment block if it references all-steps confirm.

### Tests to update (Rule 7 — encode the new intent)
- `tests/unit/test_runtime_emitted_apply.py:343`
  (`..._materializes_all_jobs_and_overwrites_params`): rewrite job assertions to
  robot-only (`_FIXED_STEPS` → `cc(seq=1)`, `re(seq=3)`); for the Stage-2 edited
  payload (line 374 flips fp→robot) expect `cc(1), fp(2), re(3)`. Seed the plan's
  experiment at `stage="workflow_design"` and ADD an assertion that confirm
  advanced it to `parameter_design`. Rename the test to reflect robot-only.
- `tests/unit/test_runtime_emitted_apply.py:398`
  (`..._reconfirm_is_idempotent_noop`): change `len == 4` (line 450) to the
  robot-only count (2). Guard behavior unchanged.
- Add a NEW test: confirm against an experiment already at `parameter_design`
  (or `workflow_design` re-confirm) does NOT move the stage backward / does not
  re-advance (mirror `test_objective_confirmed_apply_is_idempotent_no_backward`
  at line 223).

### Validation
```bash
uv run ruff check app/ tests/
uv run pyright app/events/runtime_emitted.py
uv run pytest tests/unit/test_runtime_emitted_apply.py tests/unit/test_events_codec.py tests/unit/test_import_hygiene.py -q
```

### Rollback point / commit
Commit: `feat(events): robot-only job materialization + parameter_design stage advance on plan confirm`.

---

## Phase 3 — `next_job` sparse-seq cursor

**Goal:** dispatch tolerates seq gaps (manual steps have no job row).

### Steps
1. `app/core/context.py` `next_job` (200-204): replace `next_seq = current.seq +
   1` + exact-match loop with the "smallest seq strictly greater than current"
   scan (design `§5`): `candidates = [j for j in self.jobs if j.seq >
   current.seq]; return min(candidates, key=...) if candidates else None`.
   Update the property docstring (182-192) bullet "the job whose `seq =
   seq(current) + 1`" → "the job with the smallest seq strictly greater than the
   cursor (sparse-seq safe)".
2. Verify the `current_job_id IS NULL` branch (195-196) `self.jobs[0]` — confirm
   `ctx.jobs` is loaded seq-ASC (via `JobsRepo.list_by_plan`). If the loader does
   not guarantee ordering at the ctx boundary, change to `min(self.jobs,
   key=lambda j: j.seq)`.

### Tests to update
- `tests/unit/test_reception_node.py:363`
  (`..._skip_tlc_prefix_to_robot_cc`): drop the manual `job0 seq=0 tlc` from
  `ctx.jobs` (it would not exist under robot-only); keep only `job1 seq=1 cc`,
  keep both steps in `plans.params.steps`. Assert dispatch still returns
  `job-1` / `cursor=1` — this now exercises the sparse `next_job` (no seq=0 job).
- Add/confirm a test where `ctx.jobs == (cc seq=1, re seq=3)` and the cursor sits
  on the cc job (`current_job_id = cc`): `next_job` must return the `re seq=3`
  job (proves `seq > current.seq` skips the absent seq=2 gap). Search
  `test_*context*` / `test_reception_node` for an existing cursor test to extend.

### Validation
```bash
uv run ruff check app/ tests/
uv run pyright app/core/context.py
uv run pytest tests/unit/test_reception_node.py tests/unit/test_specialist_dispatcher.py -q
# plus any cursor/context test:
uv run pytest tests/unit -k "next_job or cursor or context" -q
```

### Rollback point / commit
Commit: `fix(context): sparse-seq next_job cursor for robot-only plans`.

---

## Phase 4 — Snapshot verification + spec update + full sweep

**Goal:** confirm end-to-end snapshot typing, update specs (Rule 10), run the
whole unit suite.

### Steps
1. Re-run snapshot tests; audit `tests/unit/test_persistence_repo_snapshot.py`
   seeds for any **manual** job row that mimics confirm output — update to
   robot-only if found. The "proposed → zero jobs" test is unaffected.
2. **Spec updates (Rule 10 — same change set):**
   - `.trellis/spec/backend/L4/events.md:147` — replace "materialize ALL jobs
     (robot AND manual)" with "materialize ROBOT-only jobs (`type=='robot'`),
     `seq = original step index` (sparse, gaps where manual steps sit)".
   - `.trellis/spec/backend/L4/events.md:111` — add the
     `workflow_design → parameter_design` stage advance to the `PlanConfirmedEvent`
     row (mirror the objective→workflow_design wording).
   - `.trellis/spec/backend/L4/persistence.md` — note `trials.phase` is now a
     value-persisted `TrialPhase` enum column (`native_enum=False`,
     `values_callable`); wire bytes unchanged (StrEnum). Flag the
     `SpecialistPhase` literal for follow-up consolidation (design `§3.1`).
   - Use the `BIC-agent-service:trellis-update-spec` skill for these edits.
3. Full unit sweep:
   ```bash
   uv run ruff check app/ tests/ && uv run ruff format --check app/ tests/
   uv run pyright app/
   uv run pytest tests/unit -q
   ```
4. (If time / Drake asks) targeted integration: a confirm-turn E2E that asserts
   stage → `parameter_design` and robot-only jobs in the snapshot.

### Rollback point / commit
Commit: `docs(spec): robot-only confirm + TrialPhase contract (events.md/persistence.md)`.

---

## Review gate

Before declaring done, invoke `BIC-agent-service:trellis-check` and confirm:
- [ ] `alembic check` clean (no unexpected DDL).
- [ ] No `app/events/**` import of `app.core` (test_import_hygiene Gate 2 green).
- [ ] Every updated test asserts the NEW intent (robot-only count, sparse seq,
      stage advance) — not a reverted old behavior.
- [ ] `parameter_design` literal == `ExperimentStage.PARAMETER_DESIGN.value`
      (byte-identical), commented.
- [ ] Spec (events.md 111+147, persistence.md) updated in the SAME change set.

## Completion checklist

- [ ] Phase 1: `TrialPhase` enum, value-persisted column, DTO typing — committed.
- [ ] Phase 2: robot-only materialization + stage advance + idempotent-no-backward
      test — committed.
- [ ] Phase 3: sparse-seq `next_job` + reception/cursor tests — committed.
- [ ] Phase 4: snapshot audit + spec updates + full unit sweep green — committed.
- [ ] Open Questions (design §10) resolved with Drake and reflected in code.
- [ ] No backward-compat scaffolding added (Drake's standing rule).
