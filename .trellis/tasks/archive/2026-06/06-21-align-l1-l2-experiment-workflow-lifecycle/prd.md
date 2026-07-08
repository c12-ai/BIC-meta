# Align L1/L2 Experiment Workflow Lifecycle

## Goal

Make the agent backend and portal represent the intended workflow explicitly:

```text
Level 1 forward flow:
Experiment Objective -> Workflow Design -> Parameter Design

Level 1 / Level 2 hierarchy:
Experiment -> Plan -> Job -> Trial

Per-job Level 2 flow:
Collecting parameters -> confirmed/ready parameters -> dispatch gate -> execution/result review
```

The backend should own the durable lifecycle state. The portal should hydrate and render that state from snapshot/SSE instead of reconstructing the Level 1 flow from local heuristics.

## Current Gaps

- The backend already has the vertical `experiments -> plans -> jobs -> trials` tables.
- The backend does not have a first-class Level 1 stage for `experiment_objective`, `workflow_design`, and `parameter_design`.
- The first execute path can still create an experiment with `objective={}` and go straight to plan proposal.
- Workflow Design is mostly implemented, but plan confirmation does not advance an experiment-level stage.
- Parameter Design exists as `Trial.phase`, not as a Level 1 stage surfaced on `Experiment`.
- Plan robot/manual ownership is already carried by `plans.params.steps[].type`; this must remain the authority for Workflow Design cards and Parameter Design visibility.
- Plan confirmation currently risks treating manual plan steps as materialized backend jobs. In the intended model, backend `jobs` rows exist only for confirmed Plan steps whose `type` is `robot`.
- The current runtime has real CC/RE specialist paths today. This task must not hard-code TLC/FP as non-materializable placeholders; Test Kit/demo inputs can mark TLC/FP as manual until their robot implementations land.

Research evidence is persisted in `research/current-backend-lifecycle-audit.md`.

## Scope

This task owns lifecycle alignment:

- add backend-owned Level 1 experiment stage;
- implement the backend Experiment Objective subagent boundary that owns entry into the first Level 1 stage;
- make objective confirmation the only normal path into Workflow Design;
- make plan confirmation advance into Parameter Design;
- keep `plans.params.steps[].type` as the Plan-owned robot/manual authority;
- materialize backend `jobs` only for confirmed Plan steps whose `type` is `robot`;
- expose experiment stage through snapshot and portal state;
- preserve the existing CC/RE per-job parameter and dispatch flow.

This task includes the backend subagent/event boundary for Experiment Objective. It does not rebuild the full Objective form UI, reaction parsing, or Mind material/goal-confirm protocol unless those are required only to make the subagent boundary compile.

## Requirements

### R1. Experiment stage enum

Add a backend-owned `Experiment.stage` using an enum contract with these values:

- `experiment_objective`
- `workflow_design`
- `parameter_design`

New experiments start in `experiment_objective`.

The enum values are the durable DB/API/SSE values. Code should not use scattered raw strings for Level 1 stage comparisons or writes.

### R2. Stage transition rules

Allowed stage transitions:

| From | Trigger | To |
| --- | --- | --- |
| no experiment | create experiment | `experiment_objective` |
| `experiment_objective` | objective confirmed | `workflow_design` |
| `workflow_design` | plan confirmed | `parameter_design` |
| `parameter_design` | result review / dispatch / trial updates | no Level 1 stage change |

Repeated confirm/replay must be idempotent. A stale event must not move an experiment backward.

### R3. Objective boundary

The normal execute path for a new experiment must not jump straight to plan proposal.

When there is no confirmed objective:

- create or reuse an experiment in `experiment_objective`;
- route into the Experiment Objective subagent;
- keep Workflow Design unavailable;
- emit/use an objective-confirm event when the objective is confirmed;
- advance to `workflow_design` only after backend objective confirmation succeeds.

The objective-confirm event must update durable state and provide enough live signal for the portal to move from Experiment Objective to Workflow Design without waiting for refresh.

### R4. Workflow Design boundary

Workflow Design remains plan proposal plus chemist plan confirmation.

When a plan is confirmed:

- `plans.status` becomes `confirmed`;
- `plans.params.steps` persists the user-confirmed fixed plan, including each step's `robot | manual` type;
- the persisted `confirmed` plan params are the source of truth for job materialization;
- backend `jobs` rows materialize only for confirmed steps with `type="robot"`;
- every materialized backend `jobs` row represents robot-intended execution work by construction;
- `jobs.seq` matches the original confirmed Plan step index so each job can be joined back to `plans.params.steps[job.seq]`; sequences may be sparse when manual steps are skipped;
- experiment stage advances to `parameter_design`.

The plan-confirm event must update durable state and provide enough live signal for the portal to move from Workflow Design to Parameter Design without waiting for refresh.

### R5. Trial phase enum and Parameter Design boundary

Parameter Design remains per job/trial. `Trial.phase` must use an enum contract with these values:

- `collecting_params` while gathering inputs;
- `rts` after params confirmation;
- `conducting` after dispatch;
- `done` after result review confirmation.

The phase transitions are:

- `Trial.phase = collecting_params` while gathering inputs;
- `Trial.phase = rts` after params confirmation;
- dispatch validates lab logistics and material readiness before calling Nexus;
- `Trial.phase = conducting` after dispatch;
- `Trial.phase = done` after result review confirmation.

The Level 1 `parameter_design` stage means the confirmed workflow is ready for per-job parameter work. It does not duplicate trial-level phase.

The enum values are the durable DB/API/SSE values. Code should not use scattered raw strings for Level 2 phase comparisons or writes.

### R6. Plan-owned robot/manual type

Persist robot/manual ownership on the plan step payload:

- `robot`
- `manual`

The Plan Agent proposes the fixed workflow as `plans.params.steps`. The confirmed fixed workflow has 4 steps: TLC, CC, FP, and RE. Each step carries its `type`. The portal uses this Plan payload to decide:

- which Plan cards are robot-executed versus manual;
- which Parameter Design surfaces are visible;
- which cards should show robot execution controls or manual-input behavior.

Do not add `jobs.type` for this task.

### R7. Manual plan-step MVP behavior

Manual steps remain Plan-level cards. They do not become backend `jobs` rows in this task.

Required behavior:

- persist them in `plans.params.steps`;
- do not call Nexus for them;
- do not show robot dispatch controls for them;
- do not create `trials` for them.

Manual "mark done" is out of scope for this task.

### R8. TLC/FP robot behavior

TLC/FP must not be filtered out by special-case placeholder logic in this task. If the confirmed Plan marks TLC/FP as `robot`, they follow the same Plan-confirm materialization rule as other robot steps.

Required behavior:

- do not add code that prevents TLC/FP robot Plan steps from becoming backend `jobs`;
- do not pretend TLC/FP are CC/RE specialists;
- rely on Test Kit/demo configuration to mark TLC/FP as `manual` until their robot implementations are ready;
- when TLC/FP robot support lands, this lifecycle design should not need another materialization-rule rewrite.

Real TLC/FP robot execution is out of scope.

### R9. Snapshot and live parity

`GET /sessions/{session_id}/snapshot` must expose:

- experiment stage;
- unchanged plan params for plan proposal/workflow display and robot/manual ownership;
- robot-executed backend jobs and trial phase/status for Parameter Design;

Snapshot hydration and live SSE updates must agree on:

- active Level 1 stage;
- Workflow Design confirmed/proposed state;
- per-plan-step robot/manual ownership;
- per-trial parameter/dispatch phase.

Live stage progression is driven by objective-confirm and plan-confirm events. Snapshot is the recovery source of truth after refresh.

## Acceptance Criteria

- [ ] New experiments are created with `stage="experiment_objective"`.
- [ ] Level 1 stage uses an enum contract across model, repo, runtime, snapshot, and portal types.
- [ ] Accepted execute turns with no confirmed objective route to the Experiment Objective subagent, not directly to `plan_subgraph`.
- [ ] Snapshot experiment items include `stage`.
- [ ] Objective confirmation advances the experiment to `workflow_design`.
- [ ] Objective-confirm live handling moves the portal to Workflow Design without refresh.
- [ ] The plan path does not create `ExperimentCreatedEvent(objective={})` as the first normal objective path.
- [ ] Plan confirmation advances the experiment to `parameter_design`.
- [ ] Plan-confirm live handling moves the portal to Parameter Design without refresh.
- [ ] Confirmed `plans.params.steps` remains the source of truth for robot/manual plan-card ownership.
- [ ] Plan confirmation materializes backend jobs only for confirmed Plan steps with `type="robot"`.
- [ ] Materialized `jobs.seq` remains the original confirmed Plan step index and joins back to `plans.params.steps[job.seq]`.
- [ ] Portal snapshot hydration reads experiment stage from backend data.
- [ ] Portal uses Plan params, not `jobs.type`, to decide robot/manual card display.
- [ ] Manual plan steps are visible but non-dispatchable and do not create backend trials.
- [ ] TLC/FP are not hard-coded as non-materializable placeholders; Test Kit/demo inputs keep them manual until real robot execution is implemented.
- [ ] Level 2 `Trial.phase` uses an enum contract across model, repo, runtime, snapshot, and portal types.
- [ ] Existing CC/RE dispatch validation remains intact: params confirmation is separate from lab-logistics/material-readiness dispatch gating.
- [ ] Refresh snapshot and live SSE produce the same visible Level 1 stage and job ownership state.

## Out of Scope

- Rebuilding the Experiment Objective form or Mind parse/goal-confirm flow.
- Backfilling historical data. Existing data correctness is not part of this task.
- Real TLC/FP robot specialist implementation.
- Manual job "mark done" workflow.
- Changing Nexus material readiness semantics.
- Backward-compatibility shims for old frontend-only objective state unless Drake explicitly asks for migration.

## Definition of Done

- `prd.md`, `design.md`, and `implement.md` are reviewed before `task.py start`.
- Backend lifecycle/schema/snapshot changes are implemented and tested.
- Portal snapshot/live state projection is implemented and tested.
- Verification commands in `implement.md` pass.
- Trellis specs are updated if this task establishes a new lifecycle convention.
- Code changes are committed before task archive.
