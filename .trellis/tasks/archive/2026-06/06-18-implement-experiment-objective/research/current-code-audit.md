# Current Code Audit

## Portal

### Current Experiment Objective

File: `src/components/workspace/ExperimentObjectiveStep.tsx`

Current behavior:

* React Hook Form + Zod form.
* Save Draft stores local state with `saveObjectiveDraft(values)`.
* Confirm stores local state with `confirmObjective(values)` and advances to Workflow Design.
* No backend POST.
* Numeric draft fields are strings.
* Reaction card is a SMILES text input plus placeholder preview.
* Reactant structure is a placeholder icon, not the molecule renderer.
* Target weight is computed locally as `reference amount * target yield / 100`.
* Validation already covers required task name, required reactants, one reference row, positive numbers, and max 100 for purity/yield.

Main gaps:

* Objective is not persisted to backend.
* Objective is not hydrated from backend snapshot.
* Reaction is not required in validation.
* Reaction edit/copy actions are not implemented.
* No Mind material parse call.
* No Mind goal confirm call.
* No molecular weight field.
* Non-baseline amount/equivalents are currently required, contrary to Feishu.
* Target weight is local arithmetic, not Mind-calculated.
* Decimal normalization does not match Feishu exactly.

### Task Config Pane

File: `src/components/workspace/TaskConfigPane.tsx`

Current behavior:

* Keeps the setup rail fixed above a scrollable step body.
* Step definitions match Experiment Objective, Workflow Design, Parameter Design.
* Objective is marked saved if local objective exists, objective confirmed, jobs exist, or active trial exists.
* Dirty-form discard guard is already present.
* Footer behavior only partially matches Feishu. Objective and workflow actions are sticky inside the step body; Parameter Design owns its own step-local footer. There is not yet one fixed right-panel footer shared by the whole Task Configuration pane.

Main gaps:

* Objective saved/confirmed state is not backend-backed.
* Step state does not express the five Feishu execution statuses.
* Objective locking after backend execution starts needs alignment with backend state.

### Workspace Header and Status

Files:

* `src/components/workspace/WorkspaceHeader.tsx`
* `src/stores/workspaceStore.selectors.ts`

Current status badges:

* `idle`
* `configuring`
* `dispatched`
* `failed`
* `analyzed`
* `completed`

Main gaps:

* Product statuses are `configuring`, `dispatching`, `executing`, `awaiting_confirm`, `all_completed`.
* Current status is derived from active trial local state, not directly from `jobs.status`.

### Snapshot DTO

File: `src/lib/agent-client.ts`

Current snapshot includes:

* `experiments[].objective`
* `experiments[].status`
* `jobs[].status`
* `trials[]`
* `pending_decisions[]`

Main gaps:

* Snapshot experiment has no `name`.
* Portal currently preserves local objective across hydrate instead of replacing it from snapshot.
* Snapshot `jobs[].status` exists, but the frontend `Job` type and hydration path currently drop it for proposed/rendered jobs. Header/status code therefore cannot consume `jobs.status` yet.

## Backend

Repository: `/Users/drakezhou/Development/BIC/BIC-agent-service`

### Experiment Persistence

Files:

* `app/data/models.py`
* `app/repositories/experiments_repo.py`
* `.trellis/spec/backend/L4/persistence.md`

Current shape:

* `experiments.experiment_id`
* `experiments.session_id`
* `experiments.kind`
* `experiments.objective JSONB`
* `experiments.status`
* `experiments.started_at`

Main gaps:

* No `experiments.name`, despite Feishu calling for a backend experiment table `name` field.
* `ExperimentsRepo.update_fields` allows only `status`, `objective`, and `started_at`.

### Mind Client

File: `app/infrastructure/mind_client.py`

Current shape:

* `MindClientProtocol` includes `experiment_object_stub() -> None`.
* CC param/result and RE result paths still include stubs.
* BIC-agent-service `pyproject.toml` pins `bic-shared-types` at `v1.1.2a1`.

Main gaps:

* No typed `parse_experiment_materials` method.
* No typed `confirm_experiment_goal` method.
* No backend route/service facade for portal Objective draft or confirm.

## Tests to Add or Update

Portal:

* Unit tests for Objective validation rules.
* Store/client tests for backend-backed save/confirm.
* Snapshot hydration test for objective fields.
* Header status projection tests for the five Feishu statuses.
* Component or Playwright smoke for Objective -> Workflow transition.

Backend:

* Repository/service tests for objective draft and confirmed objective persistence.
* Duplicate task-name handling within session.
* MindClient wrapper tests with `httpx.MockTransport`.
* Session snapshot shape tests.
* Route tests for any new objective endpoint.
