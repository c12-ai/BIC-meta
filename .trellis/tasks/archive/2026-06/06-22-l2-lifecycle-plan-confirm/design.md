# Design: L2 Lifecycle — Plan Confirm (robot-only jobs + TrialPhase + stage advance)

- **Task**: `06-22-l2-lifecycle-plan-confirm`
- **Parent**: `06-21-align-l1-l2-experiment-workflow-lifecycle` (Stage Machine, robot-only materialization, sparse `jobs.seq` cursor, Enum Contract)
- **Date**: 2026-06-22
- **Layer**: L2/L4 (events apply + repos + snapshot DTO + cursor helper)

> ⚠️ **BLOCKER / PROVENANCE NOTE (Rule 1 + Rule 9).** When this design was
> drafted, neither the active task's `prd.md` nor the parent task dir
> (`06-21-align-l1-l2-experiment-workflow-lifecycle/`) existed on disk. The
> "requirements / code findings / acceptance criteria" the brief said to read
> from `prd.md` could not be loaded. Everything below is grounded in the LIVE
> source (exact `file:line` verified by reading each file) plus the brief's
> explicit instructions — NOT in a PRD. **Before implementing, confirm the
> requirements with Drake / the PRD author**, especially: (a) is the
> robot-only-materialization decision final, and (b) is `TrialPhase` meant to
> replace the existing `SpecialistPhase` `Literal` or sit alongside it. See
> "Open Questions" at the end.

---

## 1. Context — what the live code does today

The fixed workflow is **TLC → CC → FP → RE**, each step typed `robot | manual`
(`app/runtime/types/plan.py` `TaskDraft`, lines 47-66). A plan is **proposed**
(zero jobs) and **confirmed** (jobs materialized). Today's confirm path
materializes **ALL** steps:

`app/events/runtime_emitted.py` `PlanConfirmedEvent.apply` (lines 321-354):

```python
plan = await tx.plans.get(plan_id=self.plan_id)            # 328
if plan is not None and plan.status == "confirmed":         # 329 idempotent guard
    return                                                  # 330
await tx.plans.update_fields(... {"status": "confirmed"})   # 332-335
await tx.plans.set_params(plan_id=..., params={"steps": self.confirmed_jobs})  # 339-342
for seq, item in enumerate(self.confirmed_jobs):            # 347  ALL steps
    await tx.jobs.insert(
        job_id=f"{self.plan_id}-job-{seq}", plan_id=..., seq=seq,
        executor=item["executor"], title=item["title"],
    )
```

Two gaps vs. the parent's Stage Machine:

1. **Materializes manual steps too** (line 347 iterates `self.confirmed_jobs`
   unfiltered). The parent task says only `type == "robot"` steps become `jobs`
   rows. Manual steps live on `plans.params.steps` only.
2. **No L1 stage advance.** `ExperimentStage` (enums.py:96-107) already
   *documents* "plan confirmation (parent task 06-21) advances to
   `PARAMETER_DESIGN`" (lines 101-102) and `events.md:111` documents the
   objective→`workflow_design` write — but **`PlanConfirmedEvent.apply` does NOT
   write `experiments.stage` at all**. The `workflow_design → parameter_design`
   transition is unimplemented. (Surfaced per Rule 5: enum docstring and code
   disagree; the code is the gap to close.)

There is **no `TrialPhase` enum.** The trial lifecycle phase is the
`SpecialistPhase` `Literal` (`app/runtime/types/specialist.py:166-171`:
`collecting_params | rts | conducting | done`) and the DB column is plain
`String(32)` (`models.py:255`), the snapshot `str` (`trials_repo.py:146`,
`sessions.py:516`). The brief asks for a `TrialPhase` `StrEnum` mirroring
`ExperimentStage`, persisted by value via `values_callable`.

---

## 2. Goals / Non-goals

**Goals**
1. Add `TrialPhase` `StrEnum` next to `ExperimentStage`; persist the trial
   `phase` column by **value** (`values_callable`), mirroring the
   `Experiment.stage` column.
2. Rewrite `PlanConfirmedEvent.apply` to materialize **robot-only** jobs, keeping
   `seq = original step index` (NOT a re-packed 0..N), and advance the L1 stage
   `workflow_design → parameter_design` idempotently / no-backward.
3. Rewrite the `next_job` cursor to scan for `seq > current.seq` (sparse-seq
   safe) instead of `current.seq + 1`.
4. Re-type the snapshot `phase` field to `TrialPhase` (DTO authority).
5. Update every test that assumes all-steps materialization or contiguous seq.

**Non-goals**
- No change to `PlanProposedEvent` (propose stays "all steps to `plans.params`,
  zero jobs").
- No DB migration for the `phase` *type* (column stays VARCHAR — see §8).
- No change to the dispatch picker's *algorithm* (`reception_node._pick_next_planned_step`),
  but its correctness under sparse jobs MUST be verified (§6) — it already reads
  type from `plans.params.steps[seq]`, which is exactly why `seq` must stay the
  original index.

---

## 3. `TrialPhase` enum + value persistence

### 3.1 New enum (`app/core/enums.py`, append after `ExperimentStage` at line 108)

Mirror the `StrEnum` style. The member **values** must be byte-identical to
today's `SpecialistPhase` `Literal` strings so existing rows / wire payloads
decode unchanged (hard cutover is NOT acceptable here — there is live `phase`
data):

```python
class TrialPhase(StrEnum):
    """Per-trial specialist lifecycle phase (Level-2).

    Durable DB/API/SSE value (not the member name). Mirrors the
    ``SpecialistPhase`` literal in ``app/runtime/types/specialist.py`` — same
    string values so existing ``trials.phase`` rows decode unchanged. New
    trials start in ``COLLECTING_PARAMS`` (column server_default).
    """

    COLLECTING_PARAMS = "collecting_params"
    RTS = "rts"
    CONDUCTING = "conducting"
    DONE = "done"
```

> **DECISION (Drake, 2026-06-22): KEEP SEPARATE — distinct concepts, do NOT unify.**
> `TrialPhase` (L4, DB/DTO authority for `trials.phase`) and the L3
> `SpecialistPhase` `Literal` (the *agent-work* phase machine) are **intentionally
> independent**, even though they share the same 4 string values today.
>
> **Why not unify (the key reasoning):** they are *different concepts* —
> `SpecialistPhase` is "where the agent's work on a Job is" (which tools run, when
> to dispatch); `TrialPhase` is "where a single attempt is". **Same values today
> is a coincidence, not an identity.** They are free to diverge in the future —
> e.g. the deterministic retry loop (§11, out of scope here) may give a Trial
> states a Specialist doesn't have (a "retrying" / "superseded" attempt state).
> Aliasing them now (`SpecialistPhase = TrialPhase`) would assert sameness forever
> and force a painful tear-apart across 13 files the moment they need to differ.
> Coupling two coincidentally-equal-but-semantically-distinct things is the trap
> (Rule 5 — don't blend things that may contradict).
>
> **Therefore:**
> - Define `TrialPhase` as a fresh `StrEnum` in `app/core/enums.py`. NO alias, NO
>   shared base with `SpecialistPhase`.
> - Leave `SpecialistPhase` (specialist.py:166) and its 34 usages — including
>   `reception_node.py:78`'s `get_args(SpecialistPhase.__value__)` — **completely
>   untouched**. This task does not refactor the L3 phase machine.
> - Add a spec/code note that the two are **intentionally distinct** (NOT a fork
>   awaiting consolidation) so a future reader does not "helpfully" merge them.

### 3.2 Column value persistence (`app/data/models.py`, `Trial.phase`, line 255)

Today:
```python
phase: Mapped[str] = mapped_column(String(32), nullable=False, server_default="collecting_params")
```
Change to mirror `Experiment.stage` (models.py:117-126) — same
`values_callable` so the column persists the enum **value**:
```python
phase: Mapped[TrialPhase] = mapped_column(
    SQLEnum(
        TrialPhase,
        native_enum=False,
        length=32,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
    ),
    nullable=False,
    server_default="collecting_params",
)
```
Add `TrialPhase` to the import at `models.py:35`
(`from app.core.enums import ConfirmKind, ExperimentStage, ObjectiveKind`).

> `native_enum=False` means the DB column stays `VARCHAR(32)` — **no Postgres
> ENUM type is created, no Alembic type migration is needed** (this matches how
> `Experiment.stage` was added in 06-18 without a type DDL). The only thing the
> change does is teach SQLAlchemy to coerce `str ↔ TrialPhase`.

### 3.3 Snapshot typing (`app/repositories/trials_repo.py` + `app/api/routers/sessions.py`)

- `TrialSnapshot.phase: str` (trials_repo.py:146) → `phase: TrialPhase`.
  `_row_to_snapshot` (line 166: `phase=row.phase`) needs no change — SQLAlchemy
  hands back a `TrialPhase` once the column is enum-typed; pydantic accepts it.
  Add `from app.core.enums import TrialPhase` (trials_repo.py:33 already imports
  `TerminalStatus` from there).
- `SnapshotTrialItem.phase: str` (sessions.py:516) → `phase: TrialPhase`. The
  mapping at sessions.py:679 (`phase=t.phase`) needs no change. Import
  `TrialPhase` (sessions.py already imports `ExperimentStage` for
  `SnapshotExperimentItem.stage:465`).

> **Wire contract note (Rule 10):** because `TrialPhase` is a `StrEnum`, the JSON
> serialization is byte-identical to today's `str` (`"collecting_params"`, …).
> The FE contract does NOT change. This is the same property `ExperimentStage`
> relies on. Capture in `persistence.md` / `events.md` regardless (spec update is
> part of the change set per Rule 10).

---

## 4. `PlanConfirmedEvent.apply` rewrite (robot-only + stage advance)

File: `app/events/runtime_emitted.py`, `PlanConfirmedEvent` (class 284-354).
The event field shape is **unchanged** (`plan_id`, `confirmed_jobs:
list[dict[str, Any]]`, lines 318-319). The wire codec stays the same.

### 4.1 Idempotent guard — KEEP

Lines 328-330 stay verbatim (frozen-plan re-confirm is a no-op). Status flip
(332-335) and params overwrite (339-342) stay verbatim.

### 4.2 Materialize robot-only, `seq = original index`

Replace the loop (lines 343-354). Use `enumerate` so `seq` is the **original
step index** (the index into `plans.params.steps`), and skip non-robot steps:

```python
# Materialize ROBOT-only steps — insert-only (a proposed plan has zero jobs).
# ``seq`` is the ORIGINAL step index (the index into ``plans.params.steps``),
# NOT a re-packed 0..N counter: dispatch reads each step's robot/manual
# ``type`` from ``plans.params.steps[seq]`` (reception_node._step_type_from_params),
# so a job's ``seq`` MUST line up with its params index or the type lookup
# desyncs. Manual steps get NO job row — they live only on ``plans.params.steps``.
for seq, item in enumerate(self.confirmed_jobs):
    if item.get("type") != "robot":
        continue
    await tx.jobs.insert(  # type: ignore[attr-defined]
        job_id=f"{self.plan_id}-job-{seq}",
        plan_id=self.plan_id,
        seq=seq,
        executor=item["executor"],
        title=item["title"],
    )
```

Consequences:
- For a `[tlc:manual, cc:robot, fp:manual, re:robot]` plan, jobs are
  `{seq=1 cc, seq=3 re}` — **sparse seqs**. `UNIQUE(plan_id, seq)` still holds
  (no collisions).
- `job_id` format `f"{plan_id}-job-{seq}"` is unchanged; the PARENT-Command fast
  path mirror (`reception_node._pick_next_planned_step:307`,
  `f"{plan_id}-job-{selected_cursor}"`) stays compatible because
  `selected_cursor` is also the original step index there.

### 4.3 Advance L1 stage `workflow_design → parameter_design` (idempotent, no-backward)

`PlanConfirmedEvent` carries `plan_id` only — **not `experiment_id`** (verified:
fields 318-319; the L2 builder at `service.py:448-452` constructs it with
`plan_id` + `confirmed_jobs` only). So resolve the experiment via the plan:

```python
# Advance the L1 stage workflow_design -> parameter_design (parent 06-21 Stage
# Machine). Resolve the experiment via plan -> experiment_id (the event has no
# experiment_id field). Idempotent / no-backward: only advance FROM
# workflow_design, mirroring ExperimentObjectiveConfirmedEvent.apply
# (bypass_emitted.py:138-139). ``"parameter_design"`` is a layer-neutral
# literal (app/events/** cannot import app.core.enums.ExperimentStage) and MUST
# stay byte-identical to ExperimentStage.PARAMETER_DESIGN.value.
experiment = await tx.experiments.get_by_plan(plan_id=self.plan_id)  # see §4.4
if experiment is not None and experiment.stage == "workflow_design":
    await tx.experiments.update_fields(
        experiment.experiment_id, {"stage": "parameter_design"},
    )
```

Mirror of the **proven** idempotent pattern in
`bypass_emitted.py:128-140` (`ExperimentObjectiveConfirmedEvent.apply`):
guard on the source stage string so a raw replay never moves backward and never
re-fires.

> **Placement matters:** the stage advance MUST run AFTER the idempotent guard
> (so a frozen-plan re-confirm does not re-advance) but is otherwise independent
> of the job loop. Putting it inside the post-guard body is correct — the guard
> at 329-330 already short-circuits frozen replays.

### 4.4 Experiment resolution helper

`PlanConfirmedEvent.apply` needs experiment-by-plan. Two options — **pick the
one that needs no new repo method if it already exists**:

- **Option A (preferred if a getter exists):** `tx.plans.get(plan_id)` returns a
  `PlanSnapshot` carrying `experiment_id` (the plan row has `experiment_id` —
  models.py `Plan`, and `PlanProposedEvent.apply` inserts it). Then
  `tx.experiments.get(experiment_id)`. This uses only existing repo methods
  (`PlansRepo.get`, `ExperimentsRepo.get`) — **no new repo surface**, no `# type:
  ignore` beyond the existing pattern. The `apply` already calls
  `tx.plans.get(plan_id=self.plan_id)` at line 328 for the guard, so reuse that
  `plan` object: `plan.experiment_id`.
- **Option B:** add `ExperimentsRepo.get_by_plan(plan_id)` (one JOIN
  `experiments ← plans`). More code; only worth it if `PlanSnapshot` does not
  expose `experiment_id`.

> **Implementer: verify `PlanSnapshot.experiment_id` exists** (read
> `app/repositories/plans_repo.py`). If yes, Option A — reuse the `plan` already
> fetched at line 328: `if plan is not None: experiment = await
> tx.experiments.get(plan.experiment_id)`. This avoids an extra query and any new
> repo method. The design assumes Option A; fall back to B only if the snapshot
> lacks `experiment_id`.

### 4.5 Layer-neutral concern (the brief's explicit question)

> **Does `PlanConfirmedEvent` need a phase/stage literal field?** **No.** The
> destination stage `"parameter_design"` is a **hard-coded literal inside
> `apply`** (exactly as `ExperimentObjectiveConfirmedEvent.apply` hard-codes
> `"workflow_design"` at bypass_emitted.py:139, and `ExperimentCreatedEvent`
> hard-codes `kind="purification"` at runtime_emitted.py:225). `app/events/**` is
> layer-neutral (cannot import `app.core.enums` — enforced by
> `tests/unit/test_import_hygiene.py` Gate 2, lines 131-164). The literal is the
> agreed-upon trade-off; it must be kept byte-identical to the enum value, and a
> comment must say so. No new event field is required.

---

## 5. `next_job` sparse-seq cursor rewrite

File: `app/core/context.py`, `SessionContext.next_job` (property 178-204).

Today (line 200-203):
```python
next_seq = current.seq + 1
for job in self.jobs:
    if job.seq == next_seq:
        return job
return None
```

This assumes contiguous seqs. With robot-only materialization, a plan can have
jobs `{seq=1, seq=3}` — `current.seq + 1 == 2` matches nothing, so dispatch
stalls at the gap. Rewrite to "the job with the **smallest seq strictly greater
than** the current cursor":

```python
# Sparse-seq safe (parent 06-21): robot-only materialization leaves gaps in
# ``seq`` (manual steps get no job row), so "next" is the smallest seq strictly
# greater than the current cursor — NOT ``current.seq + 1``.
candidates = [job for job in self.jobs if job.seq > current.seq]
if not candidates:
    return None
return min(candidates, key=lambda job: job.seq)
```

The `current_job_id IS NULL` branch (line 195-196, returns `self.jobs[0]`) stays
correct as long as `self.jobs` is loaded ordered-by-seq-ASC (it is —
`JobsRepo.list_by_plan` orders `seq ASC`, test_persistence_repo_jobs.py:116). So
`self.jobs[0]` is the lowest-seq job, which is the right "first" even when that
seq is not 0 (e.g. seq=1 if TLC is manual). **Verify the loader orders `ctx.jobs`
by seq ASC** (it does via `list_by_plan`); if any loader path appends unordered,
`self.jobs[0]` would be wrong — add a `min(self.jobs, key=seq)` for safety if the
ordering is not guaranteed at the `ctx` boundary.

---

## 6. Downstream impact — does anything assume a job per plan step? (the brief's critical question)

**Yes, two consumers read `seq` — both verified SAFE under "seq = original
index", and one test must be updated.**

### 6.1 `reception_node._pick_next_planned_step` (lines 251-332) — SAFE, by design

Cross-turn dispatch (lines 318-332):
```python
next_job = state.ctx.next_job                              # 318 (now sparse-safe, §5)
candidate = choose_planned_dispatch_candidate(
    (job.seq, job.executor, _step_type_from_params(state, job.seq))   # 321-323
    for job in state.ctx.jobs
    if job.seq >= next_job.seq                             # 324
)
```
- `_step_type_from_params(state, job.seq)` (lines 228-248) indexes
  `plan.params.steps[seq]` **by the job's seq**. **This is exactly why robot-only
  materialization MUST keep `seq = original step index`** — if confirm re-packed
  seqs to 0..N, `job.seq` would index the wrong `params.steps` entry and the
  robot/manual classification would desync. With `seq = original index`, the
  lookup stays aligned. ✅
- `choose_planned_dispatch_candidate` (specialist.py:140-158) scans forward and
  returns the first `robot cc/re` specialist (or a stub). Manual steps are never
  dispatched anyway — and now they have no job row, so the scan only sees robot
  jobs, which is even cleaner. ✅
- The PARENT-Command fast path (lines 296-309) reads from
  `state.plan_draft.steps` (the in-flight draft, every step present) and derives
  `job_id = f"{plan_id}-job-{selected_cursor}"` where `selected_cursor` is the
  enumerate index over the full draft = original index. This still aligns with
  the sparse jobs' `job_id` format. ✅

### 6.2 `events.md`-documented "ALL jobs" — SPEC must be updated (Rule 10)

`.trellis/spec/backend/L4/events.md:147` literally says *"materialize ALL jobs
(robot AND manual)"*. That sentence becomes false. **Update events.md:147** to
"materialize ROBOT-only jobs (`type=='robot'`), `seq = original step index`
(sparse)" and **events.md:111** (the objective-stage row) to add the
`workflow_design → parameter_design` advance on `PlanConfirmedEvent`. Also update
`persistence.md` (TrialPhase value-persistence note) and the `ExperimentStage`
docstring expectation (enums.py:101-102 already claims the advance — now it
becomes true).

### 6.3 No other `seq`-arithmetic consumer

Grep (`seq + 1` / `next_seq`) shows only `context.py:200` (fixed in §5) and
`_emitter.py` (unrelated `TurnSeqAllocator.next_seq`). The `current_job`
property (162-176) is an identity match (`job.job_id == current_job_id`), not
seq arithmetic — SAFE.

---

## 7. Affected files

| File | Change |
|---|---|
| `app/core/enums.py` | **NEW** `TrialPhase(StrEnum)` after line 108 |
| `app/data/models.py` | `Trial.phase` → `SQLEnum(TrialPhase, …, values_callable=…)` (line 255); import `TrialPhase` (line 35) |
| `app/repositories/trials_repo.py` | `TrialSnapshot.phase: TrialPhase` (line 146); import `TrialPhase` (line 33) |
| `app/api/routers/sessions.py` | `SnapshotTrialItem.phase: TrialPhase` (line 516); import `TrialPhase` |
| `app/events/runtime_emitted.py` | `PlanConfirmedEvent.apply` (321-354): robot-only loop + `workflow_design→parameter_design` advance |
| `app/core/context.py` | `next_job` sparse-seq scan (200-204) |
| `.trellis/spec/backend/L4/events.md` | lines 111 + 147; new TrialPhase note |
| `.trellis/spec/backend/L4/persistence.md` | TrialPhase value-persistence; trials.phase column |
| **Tests** (see §9) | update all-steps + contiguous-seq assumptions |

---

## 8. Rollout — migration assessment

**No data migration required.**
- `trials.phase` is already `VARCHAR(32)` and `native_enum=False` keeps it
  `VARCHAR` (no Postgres ENUM type, exactly like `Experiment.stage` added in
  06-18 without DDL). The member **values** equal today's stored strings, so
  existing rows decode unchanged. Run `uv run alembic check` / autogenerate to
  **confirm no DDL diff is produced** (expected: empty). If autogenerate emits a
  type-altering op, set the column up to suppress it (it should not, given
  `native_enum=False` + same length).
- No `jobs` backfill: this is dev-DB-reset territory (the project resets via
  `POST /reset`); confirmed plans created before the change keep their
  all-steps jobs, but the **dispatch path tolerates that** (manual jobs are just
  skipped by `choose_planned_dispatch_candidate`). New confirms are robot-only.
  No backward-compat code is needed (Drake's "no backward-compat unless asked").

---

## 9. Risks & tests that WILL break (the brief's CRITICAL ask)

> **Biggest risk:** existing tests assert all-steps materialization and
> contiguous seq. The robot-only change makes those assertions false; an
> implementer who only edits production code gets red tests and may "fix" them by
> reverting the behavior. The implementer MUST update these tests to the new
> intent (Rule 7 — tests verify intent).

### MUST-UPDATE tests (grep-confirmed)

1. **`tests/unit/test_runtime_emitted_apply.py:343`**
   `test_plan_confirmed_apply_materializes_all_jobs_and_overwrites_params` —
   asserts `len(jobs) == 4`, `[j.seq] == [0,1,2,3]`,
   `[j.executor] == ["tlc","cc","fp","re"]` (lines 390-395) over
   `_FIXED_STEPS` (lines 290-293: `tlc:manual, cc:robot, fp:manual, re:robot`).
   Under robot-only: only `cc(seq=1)` + `re(seq=3)` materialize. **Rewrite** the
   assertions to `len == 2`, `[j.seq] == [1,3]`, `[j.executor] == ["cc","re"]`,
   `job_id == ["plan-1-job-1","plan-1-job-3"]`. Note the Stage-2 edit at line 374
   flips `fp manual→robot`, so for the EDITED payload the expected set becomes
   `cc(1), fp(2), re(3)` — split into two cases or assert against the edited
   payload's robot subset. Also **add an assertion** that the stage advanced to
   `parameter_design` (needs the seed plan's experiment at `workflow_design` — see
   the module's `_seed_plan`; may need to set `stage="workflow_design"`).

2. **`tests/unit/test_runtime_emitted_apply.py:398`**
   `test_plan_confirmed_apply_reconfirm_is_idempotent_noop` — asserts
   `len(jobs_after) == 4` (line 450). **Rewrite** to the robot-only count
   (2 for `_FIXED_STEPS`). The idempotent-guard logic is unchanged, only the
   count.

3. **`tests/unit/test_reception_node.py:363`**
   `test_reception_ctx_jobs_skip_tlc_prefix_to_robot_cc` — seeds `job0 seq=0
   tlc(manual)` + `job1 seq=1 cc(robot)` and asserts dispatch picks `cc`
   (lines 367-395). Under robot-only the manual TLC `job-0` would **not exist** —
   the test's premise (a manual job row in `ctx.jobs`) no longer reflects
   production. **Update** to seed only the robot job `job1 seq=1 cc` (sparse:
   no seq=0 row) while `plans.params.steps` still carries both steps. This
   directly exercises the sparse-seq path and the `next_job` rewrite: `next_job`
   must return `job1` even though no seq=0 job exists. Assertions
   `active_job_id == "job-1"`, `plan_cursor == 1` should still hold.

4. **`tests/unit/test_persistence_repo_snapshot.py`** — `_seed_full_hierarchy`
   and the "proposed plan / no jobs" test (line ~132) likely seed jobs for both
   manual and robot steps. **Audit** any seeded job whose matching
   `params.steps[seq].type == "manual"` — if a test seeds a manual job to mimic
   confirm output, update it to robot-only. The "proposed → zero jobs" test
   (line 132+) is UNAFFECTED (propose still materializes nothing).

5. **`tests/unit/test_events_codec.py:156`** — round-trips `confirmed_jobs`
   (line 162 `[{"title": "CC step", "executor": "cc"}]`). The **codec is
   unchanged** (no field change), so this should still pass; only verify the
   item shape note. The objective-stage codec block (line 389) is also unchanged.

6. **`tests/unit/test_persistence_repo_trials.py:97`** — asserts
   `snap.phase == "collecting_params"`. With `phase: TrialPhase`, the snapshot
   value is `TrialPhase.COLLECTING_PARAMS`, which **`==` compares equal to the
   string `"collecting_params"`** (StrEnum). So this assertion still passes — but
   **add** a stronger `assert snap.phase is TrialPhase.COLLECTING_PARAMS` if the
   implementer wants identity-level coverage (Rule 7).

7. **`tests/unit/test_persistence_repo_jobs.py`** — uses explicit seq values in
   inserts (lines 110-112, sometimes non-contiguous already: 110 inserts seq=2
   first). These test the **repo** directly, not the confirm path, so they are
   **UNAFFECTED** by robot-only confirm. No change expected; listed for
   completeness so the implementer does not over-edit.

8. **`tests/unit/test_import_hygiene.py`** (Gate 2, 131-164) — guards that
   `app/events/**` does not import `app.core`. The stage advance uses a **literal
   string**, not an enum import, so this gate STAYS GREEN. If the implementer is
   tempted to `from app.core.enums import ExperimentStage` inside
   `runtime_emitted.py`, this test will (correctly) fail — do NOT; use the
   literal.

### Other risks

- **`SpecialistPhase` vs `TrialPhase` — NOT a dual-source-of-truth bug** (§3.1).
  They are intentionally distinct concepts (per-attempt vs agent-work phase), kept
  separate by decision; same values today is coincidental and may diverge. The
  risk is the opposite of consolidation: a future reader merging them. Mitigation:
  a spec/code note marking them intentionally distinct. Surfaced, not blended (Rule 5).
- **`PlanSnapshot.experiment_id` assumption** (§4.4). If absent, Option A breaks
  → use Option B (new `get_by_plan`). Verify before coding.
- **`ctx.jobs` ordering** (§5). `next_job`'s `self.jobs[0]` first-step branch
  assumes seq-ASC ordering. Verified via `list_by_plan`, but confirm the loader
  preserves it; the `min(..., key=seq)` rewrite of the main branch is
  order-independent regardless.

---

## 10. Open Questions — RESOLVED (Drake, 2026-06-22)

1. **Robot-only finality.** ✅ CONFIRMED — manual steps get NO job row (live only
   on `plans.params.steps`). This task inverts the old "ALL jobs" behavior;
   `events.md:147` is corrected.
2. **`TrialPhase` vs `SpecialistPhase`.** ✅ KEEP SEPARATE — they are distinct
   concepts (per-attempt trial state vs agent-work phase) that share values only
   by coincidence today and may diverge (the retry loop). Define `TrialPhase` as a
   fresh enum; leave `SpecialistPhase` + its 34 usages untouched; flag them as
   intentionally distinct. See §3.1.
3. **Stage source.** ✅ CONFIRMED — `workflow_design → parameter_design` is the
   ONLY transition `PlanConfirmedEvent` drives; grep shows no other writer of
   `parameter_design`.

## 11. Out of Scope — the deterministic retry loop (Drake, 2026-06-22)

Drake's Job/Trial model: a **Job ≈ Specialist** (TLC/CC/RE); a **Job has many
Trials**; **1 Trial = 1 attempt**. The per-attempt lifecycle is exactly the
`TrialPhase` ladder (`collecting_params → rts → conducting → done`). On an
**unsatisfactory** result, a **deterministic (NOT agent) auto-retry** loop
re-recommends params via Mind/ChemEngine (seeded from the prior trial's analysis),
auto-dispatches, and creates Trial #2/#3 until satisfactory.

**That retry loop is OUT OF SCOPE for this task.** This task ships only the
lifecycle *plumbing* the loop will later stand on: the `TrialPhase` enum,
plan-confirm → `parameter_design`, robot-only job materialization, and the
sparse-seq cursor. The retry loop (Mind re-recommend wiring, trial seeding from
prior analysis, attempt increment, auto-dispatch) is a separate, larger task with
its own design — and the natural place to also consolidate any remaining phase-
machine logic.
