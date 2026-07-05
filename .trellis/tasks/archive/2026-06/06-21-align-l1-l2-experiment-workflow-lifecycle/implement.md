# Implementation Plan

## Review Gate Before Start

Before running `task.py start`, confirm:

- `prd.md` requirements are accepted.
- `design.md` technical contract is accepted.
- This task is allowed to include the backend Experiment Objective subagent.
- Historical data backfill is not required.
- Manual Plan steps remain plan-level only and non-dispatchable for this task.
- TLC/FP must not be hard-coded as non-materializable placeholders; Test Kit/demo inputs should keep them manual until their robot implementations are ready.

## ⚠️ Cleanup flag (2026-06-22) — consume, do NOT rebuild (06-18 D5)

Child task `06-18-implement-experiment-objective` has **already delivered** the Level-1
objective slice this parent originally scoped. CONSUME these; do not re-implement them:

- ✅ `ExperimentStage` enum + `experiments.stage` column + migration `b3d9f1c47a82` (Phase 1 of 06-18).
  NOTE: 06-18 kept `ExperimentStage` in `app/core/enums.py` (NOT moved to shared-types). If the parent
  still wants the shared-types move + TS export, that is net-new — reconcile, don't duplicate.
- ✅ `ConfirmKind.OBJECTIVE` + the `ConfirmKindLiteral` mirror (06-18 Phase 1).
- ✅ `ExperimentObjectiveConfirmedEvent` advancing `experiment_objective → workflow_design` (06-18 Phase 2).
- ✅ Objective draft/confirm endpoints + L2 service + Mind stubs (06-18 Phase 3).
- ✅ Snapshot `name` + `stage` (06-18 Phase 5).

The **full Experiment Objective ReAct subagent + routing** (`route_after_admit` stage gate, the
objective subgraph, `FORM_CONFIRM(objective)`, and **removing `plan_subgraph`'s `ExperimentCreatedEvent`
fallback**) is owned by the new child task **`06-22-experiment-objective-subagent`** — NOT this parent and
NOT 06-18. Confirm-model reconciliation (06-18 direct-API confirm vs 06-22 agent-emitted form-confirm)
happens in 06-22's design.

✅ **DONE (child `06-22-l2-lifecycle-plan-confirm`, 2026-06-22):** the `TrialPhase` enum (Level-2,
value-persisted, intentionally distinct from L3 `SpecialistPhase`), the `workflow_design →
parameter_design` plan-confirm transition (idempotent/no-backward), robot-only Job materialization
(sparse `jobs.seq` = original step index; manual steps = plan cards only), and the sparse-seq
`next_job` cursor. Backend lifecycle is now complete.

✅ **DONE (child `06-22-objective-draft-live-sync`, 2026-06-22):** `ExperimentObjectiveDrafted`
runtime event — the 3 objective tools emit it after mutating the draft so agent chat-driven edits
persist to `experiments.objective` + broadcast live (FE consumption of `experiment_objective_drafted`
is the portal task's job).

✅ **DONE (child `06-22-portal-lifecycle-objective-form`, 2026-06-22):** the portal lifecycle
projection — stage-driven Task Config stepper (derives from backend `Experiment.stage`, drops the
`Boolean(taskId)` heuristics; past steps lock), backend-backed objective form (reaction/material
`<img>` from Mind, `target_weight_mg` from backend not local math, async draft/confirm, 422 field
mapping), snapshot hydration of objective + stage, and live SSE stepper advance on both
`experiment_objective_confirmed` → Workflow and `plan_confirmed` → Parameter (+ `experiment_objective_drafted`
live form sync). 5 phases, 46 unit tests. The live Playwright objective→workflow smoke is deferred
to a follow-up (services managed via tmux `bic-services`).

**The Level-1/Level-2 lifecycle alignment (this whole parent) is now backend + frontend complete.**
The only remaining objective-area work is the deterministic retry loop (unsatisfactory result →
auto-recommend → Trial #2/#3) — a SEPARATE future task, NOT this parent. The Phase 1–5 steps below predate the split — the
backend lifecycle items are DONE; only the portal slice remains.

## Phase 0: Parent Task Execution Shape

This is a parent-level task. Execute in these independently reviewable slices:

0. Child prerequisite: `.trellis/tasks/06-18-implement-experiment-objective/` must provide the backend Experiment Objective subagent and objective-confirm boundary needed for the parent workflow to run end to end.
1. Integrate the child Objective boundary into the parent Level 1 stage machine.
2. Backend schema/repository/snapshot lifecycle contract.
3. Plan-confirm stage transition and robot-only Job materialization.
4. Portal snapshot/live projection.

The existing `06-18-implement-experiment-objective` task is now the first child task. Complete its backend subagent/objective-confirm slice before starting the parent integration work that depends on objective-confirm stage advancement. Additional slices can be implemented as child tasks if the implementation turn is too large. If they remain in one task, keep commits split by slice.

## Phase 1: Shared Enums, Schema, And Repositories

1. Add shared enum contracts.
   - Move/define `ConfirmKind` in `BIC-shared-types` as the shared layer-neutral enum.
   - Add `ConfirmKind.OBJECTIVE = "objective"`.
   - Replace `ConfirmKindLiteral` as the authoritative source with the shared enum.
   - Add/import enum for `ExperimentStage`.
   - Add/import enum for `TrialPhase`.
   - Keep Plan step `type` as the Plan payload enum/const, not as a Job column.
   - Generate/export TypeScript enum or const-enum-equivalent types if the portal consumes shared-types TS output.
   - Configure `pending_decisions.kind` to persist enum values (`plan`, `params`, `result_review`, `objective`) instead of enum member names.

2. Add an Alembic migration under `BIC-agent-service/alembic/versions/`.
   - Add `experiments.stage VARCHAR(32) NOT NULL DEFAULT 'experiment_objective'`.
   - Do not add pending-decision data normalization/backfill; rely on the dev DB reset/no-backfill policy.
   - Include downgrade steps that drop `experiments.stage`.
   - Do not add historical data backfill.

3. Update `BIC-agent-service/app/data/models.py`.
   - Add `Experiment.stage`.
   - Change `Trial.phase` model typing from raw string to `TrialPhase`, while persisting enum values.
   - Preserve `jobs` as type-less.

4. Update `BIC-agent-service/app/repositories/experiments_repo.py`.
   - Add `stage` to `ExperimentSnapshot`.
   - Include `stage` in `_row_to_snapshot`.
   - Add `stage` to `_UPDATABLE_FIELDS`.
   - Keep default insert behavior at `experiment_objective`.

5. Update `BIC-agent-service/app/repositories/trials_repo.py`.
   - Change `TrialSnapshot.phase` from raw `str` to `TrialPhase`.
   - Ensure `_row_to_snapshot` returns a `TrialPhase`.
   - Ensure writes to `phase` use enum values.

6. Update `BIC-agent-service/app/repositories/jobs_repo.py`.
   - Keep `JobSnapshot` type-less.
   - Keep `JobsRepo.insert` type-less.
   - Preserve `seq` as the confirmed Plan step index.

7. Add/update repository tests.
   - `tests/unit/test_persistence_repo_experiments.py`
   - `tests/unit/test_persistence_repo_trials.py`
   - `tests/unit/test_persistence_repo_jobs.py`

Rollback point: migration and repository changes are isolated. If tests fail here, revert this phase before touching runtime or portal code.

## Phase 2: Experiment Objective Subagent

1. Add objective confirmation wire handling.
   - Use `ConfirmKind.OBJECTIVE = "objective"` from the shared enum.
   - Add the minimal objective-confirm payload shape needed by the Experiment Objective subagent and portal.
   - Do not expand `OriginalAction` / `TYPED_ORIGINAL_ACTIONS` unless the implementation needs typed objective form rendering or stricter validation.
   - Add `ExperimentObjectiveConfirmedEvent`.
   - Export/register the event anywhere runtime event exhaustiveness requires it.
   - Ensure the confirmed event updates objective text when present and advances stage to `workflow_design`.

2. Add a first-class backend Experiment Objective subagent.
   - Suggested file: `BIC-agent-service/app/runtime/graphs/nodes/experiment_objective.py`.
   - Create or reuse the active experiment.
   - Keep stage at `experiment_objective`.
   - Own the normal no-objective entry path before `plan_subgraph`.
   - On `FORM_CONFIRM(objective)`, allow the graph to continue into `plan_subgraph` after the objective-confirm event has advanced stage to `workflow_design`.

3. Wire the subagent into graph construction.
   - Update `BIC-agent-service/app/runtime/graphs/factory.py`.
   - Update `BIC-agent-service/app/runtime/graphs/nodes/route_entry.py`.
   - Update `BIC-agent-service/app/runtime/graphs/nodes/route_after_admit.py`.
   - Route `FORM_CONFIRM(objective)` to the Objective subagent.
   - Route no experiment / `experiment_objective` to the Objective subagent.
   - Route `workflow_design` to `plan_subgraph`.

4. Add objective-confirm event handling.
   - The objective-confirm event advances `experiment_objective -> workflow_design`.
   - The event must be idempotent and never move stage backward.
   - The live event must be consumable by the portal to advance to Workflow Design.

5. Add/update tests.
   - Accepted execute with no objective routes to Objective subagent.
   - `FORM_CONFIRM(objective)` routes to Objective subagent, not plan or parameter form gate.
   - Objective confirm advances durable stage to `workflow_design`.
   - Objective confirm can continue into plan proposal once stage is `workflow_design`.
   - Replayed objective confirm is a no-op when already at `workflow_design` or later.
   - Objective event is covered by event codec/exhaustiveness tests.

Rollback point: if the Objective subagent causes route instability, revert graph routing and objective event wiring while keeping schema/repository changes.

## Phase 3: Backend Runtime Transitions

1. Update experiment creation.
   - Ensure `ExperimentCreatedEvent.apply()` writes or defaults `stage="experiment_objective"`.

2. Update plan confirmation.
   - In `PlanConfirmedEvent.apply()`, keep the existing confirmed-plan idempotent guard.
   - Persist confirmed `plans.params.steps` with all fixed plan cards and their `robot | manual` type.
   - Insert backend jobs only for confirmed Plan steps whose `type` is `robot`.
   - Do not special-case TLC/FP out of materialization; Test Kit/demo inputs should mark them manual until their robot implementations are ready.
   - Set `jobs.seq` to the original confirmed Plan step index, not a dense robot-only ordinal.
   - Update cursor logic so `ctx.next_job` scans to the next materialized job with `seq > current.seq` and does not require contiguous seqs.
   - Do not create jobs or trials for manual plan steps.
   - Advance the owning experiment to `parameter_design` after successful plan confirmation.
   - Ensure the plan-confirm live event advances the portal to Parameter Design.

3. Update phase transition code.
   - Replace raw-string `Trial.phase` transition keys with `TrialPhase` enum keys.
   - Replace runtime phase comparisons with `TrialPhase` wherever practical.
   - Keep wire/SSE payload values as lowercase enum values.

4. Add/update runtime tests.
   - `tests/unit/test_runtime_emitted_apply.py`
   - `tests/unit/test_reception_node.py` or route-specific tests if present
   - `tests/unit/test_events_codec.py`
   - `tests/unit/test_import_hygiene.py`
   - `tests/integration/test_l1_l2_wireup.py`

Rollback point: if plan-confirm stage movement destabilizes existing turn flow, keep schema/repo changes and revert only runtime event modifications.

## Phase 4: Backend Snapshot Contract

1. Update `BIC-agent-service/app/api/routers/sessions.py`.
   - Add `stage` to `SnapshotExperimentItem`.
   - Type `SnapshotExperimentItem.stage` as `ExperimentStage`.
   - Type `SnapshotTrialItem.phase` as `TrialPhase`.
   - Keep `SnapshotJobItem` type-less.
   - Keep `plans.params.steps` as the snapshot source for robot/manual plan-card ownership.

2. Update snapshot repository tests.
   - `tests/unit/test_persistence_repo_snapshot.py`
   - session route snapshot tests if present.

3. Confirm no `BIC-lab-service` changes are required.
   - Existing CC/RE dispatch gate must keep validating lab logistics/material readiness.

Rollback point: snapshot DTO changes should be reverted together with portal consumer changes if contract shape changes during implementation.

## Phase 5: Portal Contract, Live Events, And Hydration

1. Update `BIC-agent-portal/src/lib/agent-client.ts`.
   - Add `ExperimentStage` enum/const type.
   - Add `TrialPhase` enum/const type.
   - Type `SnapshotExperiment.stage` as `ExperimentStage`.
   - Type `SnapshotTrial.phase` as `TrialPhase`.
   - Keep `SnapshotJob` type-less.
   - Keep `plans.params.steps` unchanged.

2. Update `BIC-agent-portal/src/stores/workspaceStore.ts`.
   - Hydrate active setup stage from backend experiment stage.
   - Use `plans.params.steps` for robot/manual Plan-card ownership before and after confirmation.
   - Use `snapshot.jobs` only for robot execution state.
   - Remove any plan that treats `jobs.type` as an authority.

3. Update portal live event handling.
   - objective-confirm event sets active Level 1 stage to `workflow_design`.
   - plan-confirm event sets active Level 1 stage to `parameter_design`.
   - params/dispatch/result events do not change Level 1 stage.
   - Update `src/types/events.ts`, `src/lib/event-dispatcher.ts`, and `src/lib/sse-client.ts` exhaustiveness.

4. Update portal workspace surfaces.
   - `BIC-agent-portal/src/components/workspace/TaskConfigPane.tsx`
   - `BIC-agent-portal/src/components/workspace/ExperimentObjectiveStep.tsx`
   - `BIC-agent-portal/src/components/workspace/WorkflowDesignStep.tsx`
   - `BIC-agent-portal/src/components/workspace/ParameterDesignPanel.tsx`
   - `BIC-agent-portal/src/components/workspace/StepStrip.tsx`
   - `BIC-agent-portal/src/components/workspace/SpecialistSubtabs.tsx`
   - Use backend stage/confirmed state for Objective, Workflow, and Parameter step status.
   - Keep Parameter locked until `parameter_design`.

5. Update portal tests.
   - `src/stores/workspaceStore.routing.test.ts`
   - `src/lib/session-loader.test.ts`
   - `src/lib/event-dispatcher.test.ts`
   - Add focused tests for enum-typed stage hydration, enum-typed trial phase hydration, live objective-confirm, live plan-confirm, Plan-owned robot/manual display, sparse job-seq hydration, and robot-only job hydration.

Rollback point: if portal hydration becomes inconsistent, revert portal changes while keeping backend contract hidden until consumer tests pass.

## Phase 6: Verification

Run targeted backend checks from `BIC-agent-service`:

```bash
uv run pytest tests/unit/test_persistence_repo_experiments.py tests/unit/test_persistence_repo_trials.py tests/unit/test_persistence_repo_jobs.py tests/unit/test_runtime_emitted_apply.py tests/unit/test_events_codec.py tests/unit/test_import_hygiene.py tests/unit/test_persistence_repo_snapshot.py tests/integration/test_l1_l2_wireup.py
uv run ruff check app tests
uv run pyright app
```

Run shared-types checks if `ConfirmKind` is moved there:

```bash
uv run pytest
uv run python scripts/export_ts_enums.py --check
```

Run targeted portal checks from `BIC-agent-portal`:

```bash
pnpm test -- src/stores/workspaceStore.routing.test.ts src/lib/session-loader.test.ts src/lib/event-dispatcher.test.ts
pnpm typecheck
pnpm exec biome check src/lib/agent-client.ts src/types/events.ts src/lib/event-dispatcher.ts src/lib/sse-client.ts src/stores/workspaceStore.ts src/components/workspace/TaskConfigPane.tsx src/components/workspace/ExperimentObjectiveStep.tsx src/components/workspace/WorkflowDesignStep.tsx src/components/workspace/ParameterDesignPanel.tsx src/components/workspace/StepStrip.tsx src/components/workspace/SpecialistSubtabs.tsx src/stores/workspaceStore.routing.test.ts src/lib/session-loader.test.ts src/lib/event-dispatcher.test.ts
pnpm build
```

Run lab-service tests only if dispatch request shape or material-readiness behavior changes. The expected path is no `BIC-lab-service` code change.

## Phase 7: Final Review

1. Compare implementation against `prd.md` acceptance criteria.
2. Re-read `design.md` risks and confirm mitigations landed.
3. Run Trellis final check flow for all affected packages.
4. Decide whether lifecycle conventions should be added to `.trellis/spec/`.
5. Commit work after presenting the commit plan.

## Completion Checklist

- [ ] Migration adds `experiments.stage`.
- [ ] Level 1 stage uses `ExperimentStage` enum across backend and portal contracts.
- [ ] Level 2 trial phase uses `TrialPhase` enum across backend and portal contracts.
- [ ] Experiment Objective subagent is registered and reachable from normal no-objective routing.
- [ ] Repositories expose experiment stage snapshots.
- [ ] Objective confirm advances to `workflow_design`.
- [ ] Plan confirm advances to `parameter_design`.
- [ ] Plan confirm persists confirmed `plans.params.steps`.
- [ ] Plan confirm materializes backend jobs only for confirmed Plan steps with `type="robot"`.
- [ ] Materialized `jobs.seq` equals the original confirmed Plan step index; cursor logic handles sparse seqs.
- [ ] Snapshot route exposes experiment stage.
- [ ] Portal hydrates Level 1 stage from backend snapshot.
- [ ] Portal live objective-confirm advances to Workflow Design.
- [ ] Portal live plan-confirm advances to Parameter Design.
- [ ] Portal reads Plan params for robot/manual ownership.
- [ ] Manual plan steps remain visible but non-dispatchable and do not create backend trials.
- [ ] TLC/FP are not hard-coded as non-materializable placeholders; Test Kit/demo inputs keep them manual until real robot execution is implemented.
- [ ] Backend targeted tests pass.
- [ ] Portal targeted tests pass.
- [ ] Typecheck/lint/build checks pass for affected packages.
