# Current Backend Lifecycle Audit

## Question

Does the current backend already match the intended product model?

- Level 1 forward flow: Experiment Objective -> Workflow Design -> Parameter Design.
- Level 1 / Level 2 hierarchy: Experiment -> Plan -> Job -> Trial.
- Per-job Level 2 flow: collecting parameters -> confirmed/ready parameters -> dispatch gate -> robot execution or manual handling.

## Summary

The backend is structurally close but not complete. The vertical hierarchy mostly exists. The Level 1 forward stage machine does not exist as a first-class backend state. Parameter work exists, but it is modeled as `Trial.phase`, not as a visible Level 1 `Parameter Design` stage. Robot/manual choices exist in the plan payload and should remain Plan-owned. Backend `jobs` should represent robot execution work only. Current runtime support is strongest for CC/RE today, but this lifecycle task should not hard-code TLC/FP as non-materializable placeholders.

## Evidence

### Durable hierarchy exists

`BIC-agent-service/app/data/models.py` defines the intended four-level hierarchy:

- `Experiment` is the top level with `experiment_id`, `session_id`, `kind`, `objective`, `status`, and `started_at` at lines 81-109.
- `Plan` is a child of experiment with `plan_id`, `experiment_id`, `status`, `current_job_id`, and `params` at lines 112-166.
- `Job` is a child of plan with `seq`, `executor`, `title`, and `status` at lines 169-206.
- `Trial` is a child of job with `attempt`, `status`, `phase`, `params`, `result`, `analysis`, `steps`, and `lab_task_id` at lines 209-270.

This means the vertical "Experiment / Plan / Job / Trial" structure is mostly already implemented.

### Level 1 stage is not first-class

`Experiment` has `objective` and `status`, but no explicit `stage` column. `ExperimentsRepo._UPDATABLE_FIELDS` only allows `status`, `objective`, and `started_at`. `SnapshotExperimentItem` exposes `objective`, `status`, and `started_at`, but no stage.

Current consequence: the backend cannot directly say "this experiment is in Experiment Objective / Workflow Design / Parameter Design." The portal or runtime must infer it from objective presence, plan status, jobs, trials, and pending decisions.

### Plan creation currently bypasses a real objective stage

In `BIC-agent-service/app/runtime/graphs/nodes/route_after_admit.py`, accepted execute turns with no in-flight task route directly to `plan_subgraph` lines 56-65.

In `BIC-agent-service/app/runtime/graphs/nodes/plan_subgraph.py`, if no experiment exists, the plan path emits `ExperimentCreatedEvent` with `objective={}` at lines 286-300, then immediately emits `PlanProposedEvent` at lines 302-312.

Current consequence: Experiment Objective is not a required backend-owned first stage before Workflow Design.

### Workflow Design is mostly implemented

`TaskDraft` in `BIC-agent-service/app/runtime/types/plan.py` has:

- `title`
- `executor: "tlc" | "cc" | "fp" | "re"`
- `type: "robot" | "manual"`

`PlanProposedEvent.apply()` inserts the plan as `proposed` and persists the step payload under `plans.params.steps`, including `type`. `PlanConfirmedEvent.apply()` flips the plan to `confirmed`, overwrites `plans.params`, and currently materializes all jobs. The desired shape is narrower: after plan confirmation, persist the user-confirmed `plans.params.steps`, then materialize backend `jobs` only for confirmed steps with `type="robot"`.

### Robot/manual type is Plan-owned

`Job` has no `type` column. `PlanConfirmedEvent.apply()` intentionally does not persist `type` onto jobs; it stays in `plans.params.steps[seq]`. `SnapshotJobItem` also omits type and documents that robot/manual `type` lives on the matching `plans.params.steps[seq]` entry.

Current consequence: this is correct for the product model as clarified by Drake. Plan cards and Parameter Design visibility are driven by `plans.params.steps`; backend `jobs` rows should exist only for robot execution work and therefore do not need their own `type`. When manual steps are skipped, `jobs.seq` must still point back to the original confirmed Plan step index so `plans.params.steps[job.seq]` remains the matching card.

### Parameter Design exists, but as Trial phase

`Trial.phase` defaults to `collecting_params`. `runtime_emitted.py` has `_FORM_CONFIRM_PHASE_ADVANCE`:

- `("collecting_params", "params") -> "rts"`
- `("conducting", "result_review") -> "done"`

`TaskDispatchedEvent.apply()` sets `trials.status="dispatched"`, `phase="conducting"`, and `lab_task_id`.

Current consequence: per-job parameter collection and confirmation exist, but Level 1 Parameter Design is not explicitly represented on `experiments.stage`.

### Parameter confirmation and lab-logistics dispatch gate are correctly separated

`BIC-agent-service/app/events/form_payloads.py` deliberately treats lab logistics as dispatch-gated, not params-confirm-gated:

- CC `sample_cartridge_location` is not required by `cc_params_form_problems`.
- RE `flasks` / `collect_config` are not required by `re_params_form_problems`.

`BIC-agent-service/app/runtime/graphs/specialists/tools.py::_submit_l4` enforces the dispatch gate:

- CC requires `lab_logistics.sample_cartridge_location`.
- RE requires `lab_logistics.flasks` and `lab_logistics.collect_config`.

`BIC-lab-service` then validates material readiness before task creation:

- `TaskService.create_task()` runs `CommandValidator.validate_task_materials`.
- `POST /preparations/validate` dry-runs the same material readiness logic.

This matches the desired rule: confirmed parameters can exist before dispatch, but dispatch must verify lab logistics and material readiness.

### Manual steps and incomplete robot implementations

`classify_step_dispatch()` in `BIC-agent-service/app/runtime/types/specialist.py` says:

- manual steps -> `skip`
- robot CC/RE -> real specialist
- robot TLC/FP -> `stub`

Current consequence: manual plan steps are not executable backend work and should not materialize jobs/trials. TLC/FP robot support is incomplete today, but Drake clarified that this task should not add code restrictions that prevent TLC/FP robot steps from materializing; Test Kit/demo inputs should mark TLC/FP manual until their implementations land.

## Main Gaps

1. Add first-class Level 1 stage state.
2. Add a real objective save/confirm path or integrate with the existing objective task.
3. Advance Level 1 stage on objective confirm and plan confirm.
4. Keep robot/manual ownership on `plans.params.steps`; do not add `jobs.type`.
5. Change plan confirmation so manual Plan steps do not materialize backend jobs/trials.
6. Preserve the original Plan step index in `jobs.seq` and update cursor logic for sparse materialized jobs.
7. Avoid hard-coded TLC/FP placeholder restrictions; Test Kit/demo data should keep TLC/FP manual until real robot implementations land.

## Related Tasks

- `.trellis/tasks/06-18-implement-experiment-objective/` is related and narrower. It covers backend-backed Experiment Objective and Mind/shared-types integration.
- This task is broader. It should own lifecycle alignment and stage projection, and it may depend on or coordinate with the Objective implementation.

## Decision Update 2026-06-21

Drake clarified that the backend Experiment Objective subagent is included in this parent task. The parent task still does not own full Objective form UI or Mind material/goal-confirm behavior, but it does own the subagent boundary, the objective-confirm event boundary, and the `experiment_objective -> workflow_design` stage transition.

Drake also clarified that `jobs.type` should not be added. The Plan Agent emits the fixed plan and marks each Plan step as robot or manual. The portal uses `plans.params.steps` to decide which cards are shown as robot or manual. Before plan confirmation there are no backend Job rows. After plan confirmation, every created backend Job should represent robot execution work; manual Plan steps remain Plan-level only.

Drake clarified that both Level 1 `Experiment.stage` and Level 2 `Trial.phase` should use enum contracts. The current `SpecialistPhase` literal/type-alias shape and raw `TrialSnapshot.phase: str` should be replaced by an enum-backed contract whose durable values remain `collecting_params`, `rts`, `conducting`, and `done`.

Drake clarified that the fixed Plan has 4 steps, not 5. The current fixed sequence remains TLC, CC, FP, RE.

Drake clarified that TLC/FP should not be forcibly treated as Plan-level placeholders in code. Even before the backend implementations are complete, the lifecycle logic should remain real: a confirmed `robot` TLC/FP step is eligible for backend Job materialization. Test Kit/demo setup is responsible for marking TLC/FP manual until robot support is ready.
