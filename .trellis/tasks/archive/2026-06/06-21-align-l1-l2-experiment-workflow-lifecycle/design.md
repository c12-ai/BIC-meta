# Technical Design

## Scope Decision

This is a parent-level implementation task. It owns one lifecycle contract and may be executed as direct slices or split into child tasks before `task.py start`:

```text
Experiment Objective subagent -> Experiment.stage + Plan step ownership -> robot Job materialization -> snapshot/live contract -> portal hydration/rendering
```

Deliverables:

- backend Experiment Objective subagent boundary;
- backend `Experiment.stage`;
- Plan-owned robot/manual step ownership via `plans.params.steps`;
- robot-only backend Job materialization after plan confirmation;
- objective-confirm and plan-confirm stage transitions;
- snapshot DTO updates;
- portal snapshot/live stage projection.

This task does not own the full Objective form UI, reaction parsing, or Mind material/goal-confirm protocol. It owns the backend subagent and event boundary needed for the Level 1 objective stage.

## Updated DB Schema

After this task, the workflow lifecycle schema should be:

```sql
CREATE TABLE experiments (
    experiment_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    kind VARCHAR(32) NOT NULL,
    objective JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(32) NOT NULL DEFAULT 'recommended',
    stage VARCHAR(32) NOT NULL DEFAULT 'experiment_objective',
    started_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_experiments_session_id
    ON experiments (session_id);

CREATE TABLE plans (
    plan_id VARCHAR(64) PRIMARY KEY,
    experiment_id VARCHAR(64) NOT NULL REFERENCES experiments(experiment_id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'recommended',
    current_job_id VARCHAR(64),
    params JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX ix_plans_experiment_id
    ON plans (experiment_id);

CREATE INDEX ix_plans_experiment_created_at
    ON plans (experiment_id, created_at);

CREATE TABLE jobs (
    job_id VARCHAR(64) PRIMARY KEY,
    plan_id VARCHAR(64) NOT NULL REFERENCES plans(plan_id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    executor VARCHAR(32) NOT NULL,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT uq_jobs_plan_seq UNIQUE (plan_id, seq)
);

CREATE INDEX ix_jobs_plan_id
    ON jobs (plan_id);

ALTER TABLE plans
    ADD CONSTRAINT fk_plans_current_job_id
    FOREIGN KEY (current_job_id) REFERENCES jobs(job_id) ON DELETE SET NULL;

CREATE TABLE trials (
    trial_id VARCHAR(64) PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    attempt INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    phase VARCHAR(32) NOT NULL DEFAULT 'collecting_params',
    params JSONB,
    result JSONB,
    analysis JSONB,
    error_message TEXT,
    steps JSONB,
    analysis_completed BOOLEAN NOT NULL DEFAULT FALSE,
    lab_task_id VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    started_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE,
    announced_transitions JSONB NOT NULL DEFAULT '[]',
    CONSTRAINT uq_trials_job_attempt UNIQUE (job_id, attempt)
);

CREATE INDEX ix_trials_job_id
    ON trials (job_id);

CREATE INDEX ix_trials_job_created_at
    ON trials (job_id, created_at);
```

The effective hierarchy is:

```text
Session -> Experiment(stage) -> Plan(params.steps type) -> Job(robot execution) -> Trial(phase)
```

Allowed `experiments.stage` values:

- `experiment_objective`
- `workflow_design`
- `parameter_design`

Allowed `trials.phase` values:

- `collecting_params`
- `rts`
- `conducting`
- `done`

Allowed `plans.params.steps[].type` values:

- `robot`
- `manual`

The confirmed fixed workflow currently has 4 Plan steps: TLC, CC, FP, and RE. Robot/manual ownership is per Plan step.

Database columns may remain `VARCHAR` or `JSONB` to match the existing persistence style, but fixed value sets must be represented by enums or generated const enums at boundaries. Persist enum values, not enum member names.

`plans.params.steps` is the authority for plan-card display and robot/manual ownership. Backend `jobs` rows are created only for confirmed Plan steps whose `type` is `robot`; every created `jobs` row is robot-intended execution work by construction and does not need a separate `type` column.

`jobs.seq` must equal the original index of the matching entry in the confirmed `plans.params.steps` array. Because manual steps do not create backend `jobs`, `jobs.seq` can be sparse. Runtime cursor logic must scan to the next materialized job with `seq > current.seq` rather than assuming `seq + 1` exists.

## DB Schema Design Update

The migration should be additive and narrow:

```text
experiments.stage VARCHAR(32) NOT NULL DEFAULT 'experiment_objective'
```

The default is only for schema simplicity and local/dev rows. No historical data backfill is required for this task.

Update the ORM and persistence layer in the same slice:

- add shared/domain enums for `ExperimentStage`, `TrialPhase`, and Plan step `type` values;
- add `Experiment.stage` to the SQLAlchemy model and `ExperimentSnapshot`;
- type `Trial.phase` as `TrialPhase` in the SQLAlchemy model, repositories, runtime, and snapshot DTOs;
- allow controlled `stage` updates through `ExperimentsRepo.update_fields`;
- keep `Job` rows type-less; robot/manual ownership remains on `plans.params.steps`;
- ensure confirmed `plans.params.steps` is persisted before robot-only job materialization.
- keep `jobs.seq` aligned to the confirmed Plan step index so `plans.params.steps[job.seq]` is always the matching Plan card.

## Enum Contract

Level 1 stage and Level 2 phase are enum contracts:

```text
ExperimentStage.EXPERIMENT_OBJECTIVE = "experiment_objective"
ExperimentStage.WORKFLOW_DESIGN = "workflow_design"
ExperimentStage.PARAMETER_DESIGN = "parameter_design"

TrialPhase.COLLECTING_PARAMS = "collecting_params"
TrialPhase.RTS = "rts"
TrialPhase.CONDUCTING = "conducting"
TrialPhase.DONE = "done"
```

Use enum values as the durable DB/API/SSE payloads. Do not persist enum member names such as `EXPERIMENT_OBJECTIVE` or `COLLECTING_PARAMS`.

Backend implementation shape:

- define the enums in a layer-neutral/shared location that runtime, events, repositories, and API DTOs can import;
- keep physical DB columns as `VARCHAR(32)` unless a separate migration explicitly adopts native database enums;
- if using SQLAlchemy `Enum`, configure it to persist `.value` strings, not member names;
- replace phase transition maps and stage transition writes with enum-keyed logic;
- type repo snapshots as `ExperimentStage` and `TrialPhase`, not `str`.

Portal implementation shape:

- expose/generated enum or const-enum-equivalent types for `ExperimentStage` and `TrialPhase`;
- type snapshot and SSE consumers with those enums;
- avoid hard-coded string comparisons outside the enum/const definitions.

The wire/domain schema update is separate from the experiment/job DB schema but required for the same lifecycle contract:

- define `ConfirmKind` once as a shared/layer-neutral `StrEnum` with values `plan`, `params`, `result_review`, and `objective`;
- use that enum everywhere a confirm kind appears instead of maintaining a separate `ConfirmKindLiteral` mirror;
- add the minimal objective-confirm payload shape needed by the Experiment Objective subagent and portal;
- add `ExperimentObjectiveConfirmedEvent` as the event that advances `experiments.stage`;
- route `FORM_CONFIRM(objective)` to the Experiment Objective subagent instead of `plan_subgraph` or `form_confirm_gate`.

Do not expand `OriginalAction` / `TYPED_ORIGINAL_ACTIONS` just to add objective confirmation. Those are only needed if the implementation requires a new typed objective form action for portal rendering or stricter validation; otherwise, keep the objective-confirm payload minimal.

ConfirmKind reconciliation:

- canonical semantic values are the enum values: `plan`, `params`, `result_review`, `objective`;
- wire payloads serialize those enum values as lowercase strings;
- event payload models should type `confirm_kind` as `ConfirmKind`, not as scattered string literals;
- `pending_decisions.kind` should persist enum values, not enum member names, by configuring SQLAlchemy enum value storage;
- the target DB values are therefore lowercase (`plan`, `params`, `result_review`, `objective`), not uppercase (`PLAN`, `PARAMS`, `RESULT_REVIEW`, `OBJECTIVE`).

Because `app/events/**` cannot import from other `app/` packages, the enum should live in a layer-neutral place that both runtime and events may import. Use `BIC-shared-types` for this shared enum; `app.core.enums.ConfirmKind` can then re-export or be replaced by that shared enum.

No historical workflow or pending-decision backfill is required. The expected path is dev DB reset or empty `pending_decisions`; do not preserve old uppercase `pending_decisions.kind` rows unless Drake separately requests data preservation.

## Stage Machine

Allowed transitions:

| Current | Event | Next | Idempotency |
| --- | --- | --- | --- |
| none | experiment created | `experiment_objective` | insert only |
| `experiment_objective` | objective confirmed | `workflow_design` | no-op if already `workflow_design` or `parameter_design` |
| `workflow_design` | plan confirmed | `parameter_design` | no-op if already `parameter_design` |
| `parameter_design` | params/result/dispatch events | `parameter_design` | no stage write |

Backward transitions are not allowed in this task.

This task does not model terminal experiment completion. Completion remains represented through existing plan/job/trial status and result review state.

## Backend Contract

### Repositories

Update `ExperimentsRepo`:

- include `stage` in `ExperimentSnapshot`;
- include `stage` in `_row_to_snapshot`;
- allow controlled `stage` updates through `update_fields`;
- keep `kind` immutable.

Update `JobsRepo`:

- keep `seq`, `executor`, and `title` immutable from generic updates.

### Event application

`ExperimentCreatedEvent.apply()` should insert an experiment with `stage="experiment_objective"` via the model default or explicit insert.

Objective confirmation should use the existing form-confirm transport with a new confirm kind:

```text
ConfirmKind.OBJECTIVE = "objective"
FORM_CONFIRM(objective) -> ExperimentObjectiveConfirmedEvent
```

The Experiment Objective subagent should:

1. create or reuse the active experiment when the session has no confirmed objective;
2. keep the experiment in `experiment_objective`;
3. request objective confirmation through a pending form/decision with `confirm_kind="objective"`;
4. process `FORM_CONFIRM(objective)` after `ExperimentObjectiveConfirmedEvent` is emitted;
5. prevent normal routing into `plan_subgraph` before objective confirmation.

Objective confirmation should advance:

```text
experiment_objective -> workflow_design
```

`ExperimentObjectiveConfirmedEvent.apply()` should:

1. update `experiments.objective` when the confirmed payload contains objective text;
2. call `ExperimentsRepo.update_fields(..., {"stage": "workflow_design"})`;
3. no-op if the experiment is already `workflow_design` or `parameter_design`;
4. emit enough live state for the portal to advance to Workflow Design.

After objective confirmation is applied, the same graph turn should be allowed to enter `plan_subgraph` so Workflow Design can actually produce the plan. The durable stage remains `workflow_design` until plan confirmation.

`PlanConfirmedEvent.apply()` should:

1. keep its existing idempotent guard for already-confirmed plans;
2. set `plans.status="confirmed"`;
3. persist confirmed plan params, including the fixed plan steps and each step's `robot | manual` type;
4. treat the persisted confirmed `plans.params.steps` as the source of truth for job materialization;
5. insert backend jobs only for confirmed Plan steps whose `type` is `robot`;
6. ensure every inserted job is robot-intended execution work by construction;
7. set each inserted `jobs.seq` to the original confirmed Plan step index, not a dense robot-only ordinal;
8. keep fixed plan-card order and manual/robot ownership in `plans.params.steps`;
9. advance the owning experiment to `parameter_design` if the current stage is not already `parameter_design`;
10. emit/use the plan-confirm live signal so the portal advances to Parameter Design without refresh.

Do not hard-code TLC/FP as non-materializable placeholders. If the confirmed Plan marks TLC/FP as `robot`, they materialize like any other robot step. Until their real robot execution path exists, Test Kit/demo inputs should mark TLC/FP as `manual`.

Plan re-confirm replay must remain a no-op after the existing confirmed-plan guard.

Cursor update required by sparse `jobs.seq`:

- `plans.current_job_id` still points to the last completed materialized job.
- `SessionContext.next_job` should return the first materialized job whose `seq` is greater than the current job's `seq`.
- When `current_job_id` is null, `next_job` should return the lowest-seq materialized job.
- Runtime code must not assume materialized job seqs are contiguous.

## Agent Graph Execution

`route_entry` should distinguish objective confirmation from plan confirmation:

- `FORM_CONFIRM(objective)` -> Experiment Objective subagent;
- `FORM_CONFIRM(plan)` -> `plan_subgraph`;
- `FORM_CONFIRM(params)` and `FORM_CONFIRM(result_review)` -> `form_confirm_gate`;
- task terminal, decision response, and decision expiry events remain routed to `specialist_dispatcher`.

`route_after_admit` currently sends accepted execute turns with no in-flight task to `plan_subgraph`. After this task, routing must respect experiment stage:

- no experiment or `experiment_objective`: Experiment Objective subagent;
- `workflow_design`: plan path;
- `parameter_design`: specialist dispatcher or existing in-flight behavior.

This task should not route into `plan_subgraph` before objective confirmation in the normal path.

The graph factory should register the Experiment Objective subagent as a first-class node/subgraph alongside `plan_subgraph` and `specialist_dispatcher`.

The intended graph topology after this task:

```mermaid
flowchart TD
    START([START]) --> Reception["reception"]
    Reception --> RouteEntry{"route_entry"}

    RouteEntry -->|USER_MESSAGE| Intent["intent_detection"]
    RouteEntry -->|USER_MESSAGE| Admit["user_admittance"]
    Intent --> RouteAfterAdmit{"route_after_admit"}
    Admit --> RouteAfterAdmit

    RouteEntry -->|FORM_CONFIRM(objective)| Objective["experiment_objective_subagent"]
    RouteEntry -->|FORM_CONFIRM(plan)| Plan["plan_subgraph"]
    RouteEntry -->|FORM_CONFIRM(params/result_review)| FormGate["form_confirm_gate"]
    RouteEntry -->|TASK_TERMINAL / DECISION_RESPONSE / DECISION_EXPIRED| Dispatcher["specialist_dispatcher"]

    RouteAfterAdmit -->|rejected| Reject["emit_admit_reject"]
    RouteAfterAdmit -->|query and no in-flight| Query["query_agent"]
    RouteAfterAdmit -->|has in-flight| Dispatcher
    RouteAfterAdmit -->|no experiment or experiment_objective| Objective
    RouteAfterAdmit -->|workflow_design| Plan
    RouteAfterAdmit -->|parameter_design| Dispatcher

    Objective -->|request objective confirm| END([END])
    Objective -->|objective confirmed; stage=workflow_design| Plan
    Plan -->|plan proposed| END
    Plan -->|plan confirmed; stage=parameter_design| Dispatcher
    FormGate --> Dispatcher
    Dispatcher --> CC["cc_subgraph"]
    Dispatcher --> RE["re_subgraph"]
    Dispatcher --> END
    CC --> Dispatcher
    RE --> Dispatcher
```

Execution rules:

- A first execute turn with no experiment enters `experiment_objective`, creates/reuses the experiment, and requests objective confirmation through the Experiment Objective subagent.
- `FORM_CONFIRM(objective)` applies `ExperimentObjectiveConfirmedEvent`, moves durable stage to `workflow_design`, then allows `plan_subgraph` to propose the workflow plan in the same turn.
- `FORM_CONFIRM(plan)` applies `PlanConfirmedEvent`, persists the confirmed Plan steps, materializes robot-intended backend jobs for confirmed `robot` steps, moves durable stage to `parameter_design`, then allows the dispatcher to continue with parameter collection for robot jobs.
- Manual steps remain in the Plan hierarchy only; they are not backend Job/Trial records.

### Live SSE contract

Live portal stage progression is event-driven:

- objective-confirm event -> portal sets active Level 1 stage to `workflow_design`;
- plan-confirm event -> portal sets active Level 1 stage to `parameter_design`;
- dispatch/result/params events do not change Level 1 stage.

Snapshot remains recovery source of truth. If a live event is missed, refresh must restore the same stage from `SnapshotExperimentItem.stage`.

### Snapshot DTO

Update `GET /sessions/{session_id}/snapshot`:

`SnapshotExperimentItem` adds:

```text
stage: ExperimentStage
```

`SnapshotJobItem` remains type-less. A snapshot job means a materialized robot-intended backend job.

`SnapshotTrialItem.phase` changes from raw `string` typing to:

```text
phase: TrialPhase
```

`plans.params.steps` remains unchanged and authoritative. It is the proposal/plan-display payload for Workflow Design and the robot/manual ownership payload for Parameter Design, including after plan confirmation.

## Why Not `jobs.type`

`jobs.type` is not required because robot/manual ownership belongs to the Plan, not to the materialized backend Job row. The Plan Agent emits a fixed plan with every card and marks which cards are robot versus manual. The portal should use `plans.params.steps` to decide:

- which Plan cards are robot-executed;
- which Plan cards are manual/user-input;
- which Parameter Design surfaces are visible;
- which cards should expose robot execution controls.

Backend `jobs` rows are a narrower execution layer. They should be created only for confirmed Plan steps marked `robot`. Therefore every materialized `jobs` row is robot work by construction; adding `jobs.type` would duplicate the Plan payload and create a second source of truth.

## Portal Contract

Update `BIC-agent-portal/src/lib/agent-client.ts`:

- `SnapshotExperiment.stage`;
- `SnapshotTrial.phase`;
- keep `SnapshotJob` type-less.

Update `BIC-agent-portal/src/stores/workspaceStore.ts` hydration:

- set active Level 1 setup state from `snapshot.experiments[].stage`;
- use `plans.params.steps` as the source of truth for robot/manual plan-card display;
- use `snapshot.jobs` only as materialized robot execution state.

Update `TaskConfigPane` or its selectors:

- Objective step status comes from experiment stage/objective state, not just local `objective`, `jobs`, or `taskId` heuristics;
- Workflow step is active/completed based on stage plus `planConfirmed`;
- Parameter step unlocks when stage is `parameter_design`.

## Manual And TLC/FP Steps

Manual plan steps:

- stay visible in workflow;
- remain in `plans.params.steps`;
- do not materialize backend `jobs` rows;
- are excluded from robot dispatch;
- should not show robot dispatch controls in Parameter Design.

TLC/FP robot plan steps:

- must not be filtered out by special-case materialization logic;
- materialize when the confirmed Plan step has `type="robot"`;
- must not pretend to be CC/RE specialists;
- can be avoided in Test Kit/demo paths by marking TLC/FP as `manual` until their robot implementations are ready.

## Rollout And Rollback

Migration is additive:

- `experiments.stage` default `experiment_objective`.

No historical data backfill is required. Existing local/dev rows may read as defaults after migration; correctness for previously created sessions is out of scope.

Rollback shape:

- code can stop consuming `stage` and the new shared enum typing;
- columns can remain harmless if rollback does not include DB downgrade;
- if downgrade is required, drop `experiments.stage`.

No new external service, API key, or third-party account is required.

## Risks

### Stage/source-of-truth drift

Risk: portal still derives stage from local heuristics while backend exposes stage.

Mitigation: update hydration and stepper selectors in the same slice as snapshot DTO changes; add snapshot/live tests.

### Objective boundary expansion

Risk: implementing the Experiment Objective subagent expands into the full Objective form and Mind protocol.

Mitigation: keep this task limited to the subagent, durable objective-stage state, and objective-confirm event boundary. Full form/Mind behavior remains outside this task unless needed only for minimal compile/test wiring.

### Plan/job ownership drift

Risk: implementation accidentally treats backend `jobs` as the authority for robot/manual display.

Mitigation: keep robot/manual ownership exclusively in `plans.params.steps`; create backend `jobs` only for robot-executed steps. Add tests proving manual Plan steps do not create jobs/trials and portal hydration still uses Plan params for card display.

### Enum/string drift

Risk: `Experiment.stage` or `Trial.phase` is typed as an enum in one layer but compared or persisted as ad hoc strings in another layer.

Mitigation: define shared enum contracts for `ExperimentStage` and `TrialPhase`, persist enum values, and update repository snapshots, runtime transition tables, API DTOs, portal types, and tests in the same slice.

## Affected Areas

- `BIC-shared-types/bic_shared_types/*` shared enum location for `ConfirmKind`
- `BIC-shared-types` tests or TS export tooling if the enum is exported to the portal
- `BIC-agent-service/app/data/models.py`
- `BIC-agent-service/alembic/versions/*`
- `BIC-agent-service/app/core/enums.py`
- `BIC-agent-service/app/repositories/experiments_repo.py`
- `BIC-agent-service/app/repositories/trials_repo.py`
- `BIC-agent-service/app/repositories/jobs_repo.py`
- `BIC-agent-service/app/events/runtime_emitted.py`
- `BIC-agent-service/app/events/form_payloads.py`
- `BIC-agent-service/app/session/service.py`
- `BIC-agent-service/app/runtime/turn_schemas.py`
- `BIC-agent-service/app/runtime/service.py`
- `BIC-agent-service/app/runtime/types/specialist.py`
- `BIC-agent-service/app/runtime/graphs/nodes/route_entry.py`
- `BIC-agent-service/app/runtime/graphs/nodes/route_after_admit.py`
- `BIC-agent-service/app/runtime/graphs/nodes/reception_node.py`
- `BIC-agent-service/app/runtime/graphs/nodes/experiment_objective.py`
- `BIC-agent-service/app/runtime/graphs/factory.py`
- `BIC-agent-service/app/api/routers/sessions.py`
- `BIC-agent-service/tests/unit/test_persistence_repo_experiments.py`
- `BIC-agent-service/tests/unit/test_persistence_repo_trials.py`
- `BIC-agent-service/tests/unit/test_persistence_repo_jobs.py`
- `BIC-agent-service/tests/unit/test_runtime_emitted_apply.py`
- `BIC-agent-service/tests/unit/test_events_codec.py`
- `BIC-agent-service/tests/unit/test_import_hygiene.py`
- `BIC-agent-service/tests/unit/test_persistence_repo_snapshot.py`
- `BIC-agent-service/tests/integration/test_l1_l2_wireup.py`
- `BIC-agent-portal/src/lib/agent-client.ts`
- `BIC-agent-portal/src/types/events.ts`
- `BIC-agent-portal/src/lib/event-dispatcher.ts`
- `BIC-agent-portal/src/lib/sse-client.ts`
- `BIC-agent-portal/src/stores/workspaceStore.ts`
- `BIC-agent-portal/src/components/workspace/TaskConfigPane.tsx`
- `BIC-agent-portal/src/components/workspace/ExperimentObjectiveStep.tsx`
- `BIC-agent-portal/src/components/workspace/WorkflowDesignStep.tsx`
- `BIC-agent-portal/src/components/workspace/ParameterDesignPanel.tsx`
- `BIC-agent-portal/src/components/workspace/StepStrip.tsx`
- `BIC-agent-portal/src/components/workspace/SpecialistSubtabs.tsx`
- portal SSE/workspace event handler files that consume objective-confirm and plan-confirm events
- `BIC-agent-portal/src/stores/workspaceStore.routing.test.ts`
- `BIC-agent-portal/src/lib/session-loader.test.ts`
- `BIC-agent-portal/src/lib/event-dispatcher.test.ts`
