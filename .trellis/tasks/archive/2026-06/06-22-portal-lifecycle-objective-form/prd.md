# Portal lifecycle stepper + objective form

> Child of `06-21-align-l1-l2-experiment-workflow-lifecycle`. The **frontend half** of the
> shared lifecycle target. Consumes the backend contract from `06-18` (objective API/event/
> snapshot), `06-22` (objective subagent + `FORM_CONFIRM(objective)`), and the sibling
> `06-22-l2-lifecycle-plan-confirm` (TrialPhase + plan-confirm→parameter_design + robot jobs).
> **Depends on the sibling BE task — land that first.**

## Goal

Make the portal render the Level-1 lifecycle from **backend `Experiment.stage`** instead of
local heuristics, and turn the frontend-only Experiment Objective form into a backend-backed,
Mind-aware, snapshot-hydrating form. After this, the Task Configuration stepper
(Objective → Workflow → Parameter) and the objective form agree across live SSE and hard refresh.

## Code findings (ground truth, verified 2026-06-22)

- **Stepper is local-heuristic driven**, not stage-driven: `TaskConfigPane.tsx:61-78` computes
  `objectiveLocked = Boolean(taskId)`, `workflowLocked = planConfirmed || Boolean(taskId)`, and
  completed-state from `objectiveConfirmed || Boolean(objective) || Boolean(jobs || taskId)`.
- `SnapshotExperiment` (`agent-client.ts:344`) does **not** carry `stage` / `name` yet (BE now
  sends them — 06-18 Phase 5).
- Objective form is frontend-only: `saveObjectiveDraft` / `confirmObjective` only mutate
  `workspaceStore`, never POST (`workspaceStore.ts:636-637`); target weight is local
  `refAmount * yield / 100` (`ExperimentObjectiveStep.tsx:127-136`); `hydrateFromSnapshot`
  deliberately skips `snapshot.experiments[].objective` (`workspaceStore.ts:752-755`); no
  `persist` middleware → the draft is lost on refresh.
- Step components exist: `ExperimentObjectiveStep`, `WorkflowDesignStep`, `ParameterDesignPanel`,
  `StepStrip`, `TaskConfigPane`. Portal already has a `TrialPhase` TS type (`workspaceStore.ts`).

## Requirements

### R1. Stage-driven stepper

* Type `SnapshotExperiment.stage` (`ExperimentStage`: `experiment_objective | workflow_design |
  parameter_design`) and `SnapshotExperiment.name` in `agent-client.ts`.
* `TaskConfigPane` derives Objective/Workflow/Parameter step active/locked/complete state from
  backend `stage` (+ `planConfirmed` for the workflow→parameter handoff), NOT from
  `Boolean(taskId)` heuristics.
* Parameter step unlocks only at `stage == parameter_design`.
* On live SSE: the objective-confirm event moves the stepper to Workflow Design; the plan-confirm
  event moves it to Parameter Design — without refresh.
* Snapshot hydration restores the active stage from `snapshot.experiments[].stage`.

### R2. Backend-backed objective form

* Add typed `agent-client.ts` methods for the objective draft/confirm endpoints (06-18).
* Replace local-only `saveObjectiveDraft` / `confirmObjective` with async backend-backed actions.
* `hydrateFromSnapshot` restores the objective form from `snapshot.experiments[].objective`
  (+ `name`, `stage`) — stop skipping it.
* Live SSE and hard refresh agree on: task name, reaction render, reactant rows, baseline row,
  target purity/yield/weight, objective confirmation state, active stage.

### R3. Reaction + materials from Mind (not local)

* Render reaction structure from the backend `rendered_rxn_url` (`<img>`; server-rendered — no
  client molecule lib).
* Render reactant rows from the Mind material-parse / goal-confirm materials in the objective
  payload (role, smiles, name, amount_mg, equivalents, is_baseline).
* Copy action copies reaction SMILES; edit opens the existing molecule editor if one exists,
  else degrade to SMILES text edit (research: portal has no molecule renderer — document the gap).
* **Remove** the local `refAmount * yield / 100` target-weight math; render `target_weight_mg`
  from the backend (3 decimals), with a clear loading/unavailable state when absent.

### R4. Objective confirm via the agent form path

* Objective confirm uses the `FORM_CONFIRM(objective)` decision flow that `06-22` added
  (the agent emits `FormRequestedEvent(confirm_kind="objective")`; the portal confirms it like a
  plan/params confirm), AND/OR the direct `POST objective/confirm` (both apply the same
  `ExperimentObjectiveConfirmedEvent`). Reconcile which the form uses — prefer the decision flow
  for agent-proposed objectives, direct API for pure form-driven confirm (duo-panel).
* On confirm success the stepper advances to Workflow Design.

### R5. Robot/manual plan cards + parameter visibility (from the sibling BE contract)

* Workflow Design reads `plans.params.steps[].type` for robot/manual card display (NOT `jobs.type`).
* Parameter Design surfaces only robot-materialized jobs/trials; manual steps show as plan cards
  with no dispatch controls.
* Per-trial Parameter state reads `SnapshotTrial.phase` (`TrialPhase`).

### R6. Validation + error UX

* Required fields: `This field is required.`; length/range errors show configured max/range.
* Backend 422 (`form_validation_failed`) maps to field-level errors when possible, form-level otherwise.
* Save Draft lenient; Confirm strict. All copy English.

## Out of Scope

* Backend lifecycle changes (sibling `06-22-l2-lifecycle-plan-confirm`).
* The 5-status FE header projection (separate FE task Drake owns).
* OCR/image reaction recognition.
* A new client-side molecule drawing library.
* Live-sync of agent chat-driven draft edits to the form mid-react-loop (needs the flagged
  backend `ExperimentObjectiveDraftedEvent` — out of scope here).

## Acceptance Criteria

* [ ] `SnapshotExperiment` typed with `stage` + `name`; `SnapshotTrial.phase` typed `TrialPhase`.
* [ ] Stepper active/locked/complete derives from backend `stage`, not `Boolean(taskId)` heuristics.
* [ ] Objective form POSTs draft/confirm to the backend; no local-only persistence.
* [ ] `hydrateFromSnapshot` restores the objective form from backend data; survives hard refresh.
* [ ] Reaction renders from `rendered_rxn_url`; reactant rows from Mind materials; copy SMILES works.
* [ ] Local target-weight math removed; `target_weight_mg` comes from the backend (3 decimals).
* [ ] Live objective-confirm → Workflow Design; live plan-confirm → Parameter Design; no refresh.
* [ ] Robot/manual cards read `plans.params.steps[].type`; manual steps non-dispatchable.
* [ ] No portal code calls Mind directly.
* [ ] `pnpm typecheck`, `pnpm exec biome check <touched>`, `pnpm build`, targeted Vitest/Playwright green.

## Definition of Done

* Portal client + store + stepper + objective form + step components updated and tested.
* Vitest covers stage-driven stepper, snapshot hydration, draft/confirm flow, error mapping,
  baseline switching; Playwright smoke for Objective → Workflow transition.
* Verification commands pass; FE↔BE contract spec updated if any contract shifts (Rule 10).
* Parent `06-21` implement.md cleanup banner updated.
* Committed (per Drake's go-ahead).

## Research References

* `.trellis/tasks/06-18-implement-experiment-objective/research/sharedtypes-portal-current.md` —
  the live portal objective-form gaps (no POST, local math, snapshot skip).
* Parent `06-21` `design.md` — Portal Contract section (stepper from stage, plan params for robot/manual).
