# Implement Experiment Objective

> **Planning status (2026-06-21):** Re-scoped after research. Decisions locked with Drake.
> Full cross-repo objective vertical, structured as **one task, commits split by phase**.
> The 5-status FE header projection and the Level-2 `Trial.phase` enum refactor are **out of scope** (separate tasks Drake will create).

## Goal

Turn the current frontend-only Experiment Objective draft into a backend-backed, Mind-protocol-aware objective flow that:

* persists the objective through BIC-agent-service (no portal-to-Mind calls);
* names the experiment via a real `experiments.name` column;
* owns the Level-1 `Experiment.stage` machine and advances `experiment_objective -> workflow_design` on confirm;
* calls the Mind material-parse / goal-confirm contract (typed now, deterministic stub data until Mind routes are confirmed live);
* hydrates identically across live SSE and snapshot reload.

## Locked Decisions (2026-06-21)

| # | Decision | Choice |
| --- | --- | --- |
| D1 | Task Name storage | **Add `experiments.name` column** (additive Alembic migration). |
| D2 | Portal-facing API | **New objective draft + confirm endpoint pair.** Not the `/forms/confirm` decision path. |
| D3 | Reaction input scope | **Text SMILES only.** No OCR/image recognition. Edit opens the existing molecule editor. |
| D4 | Mind protocol | **Typed contract, stubbed data.** Wire the real shared-types `MindClient` request/response shape; back it with a deterministic stub behind a toggle until Mind confirms live routes. |
| D5 | Stage/event/subagent ownership | **06-18 builds them.** `Experiment.stage`, `ConfirmKind.OBJECTIVE`, the objective-confirm event, and the objective subagent node are built here. Parent `06-21`'s objective slice is superseded — flag for cleanup, update its `implement.md` to consume not rebuild. |
| D6 | Confirm flow | **Direct API confirm + objective-confirm event.** Portal Confirm calls `POST objective/confirm`; backend validates, persists, emits `ExperimentObjectiveConfirmedEvent` that advances the stage. No agent-minted HITL gate (duo-panel principle). |
| D7 | Task structure | **One task; commits split by phase.** Not a parent/child split. |
| D8 | 5-status FE header | **Out of scope.** Drake creates a separate FE task. Backend exposes `stage`; FE derives header later. |

## Research Ground Truth (verified against live `feat/shared-types-v1-1-6a1-cc-re-migration`)

Persisted in:
* `research/backend-touchpoints-current.md`
* `research/sharedtypes-portal-current.md`

Key facts the design relies on:

1. **Shared-types contract is ready.** Pin = `v1.1.6a1` (commit `51c70c4`). Live path: `bic_shared_types.model_service.http.experiment`. The deprecated `mcp_protocol.experiment` path is NOT used. A `MindClient` already exists with `parse_experiment_materials` / `confirm_experiment_goal`. **No shared-types code change is required for the contract itself.**
2. **`experiment_object_stub` is a dead protocol method** on `MindClientProtocol` (`mind_client.py:89`), returns `None`, called nowhere. There is nothing to "replace"; we wire the real shared-types client instead.
3. **`experiments` has `objective JSONB` + `status` but no `name` and no `stage` column.** `experiments.objective` is always written `{}` at creation and never updated; snapshot reads it read-only.
4. **Events are strictly layer-neutral** (test-enforced at `test_import_hygiene.py:131`). `app/events/**` must not import `ConfirmKind` or any stage enum. So `ConfirmKind.OBJECTIVE` is added in **two byte-identical places**: `app/core/enums.py` (the enum) and the `ConfirmKindLiteral` mirror at `app/events/form_payloads.py:59`. The objective-confirm event uses string literals.
5. **Dual-path persistence (D6/D41) is mandatory.** Every state change is both appended to `session_events` and projected to entity tables through `post_processor.apply` inside the three-piece transaction. The objective-confirm flow must emit a real `RuntimeEmittedEvent` / `OrchEmittedEvent`, not a bare repo write.
6. **Portal objective never survives refresh.** No `persist` middleware; `hydrateFromSnapshot` deliberately skips `snapshot.experiments[].objective`. The snapshot already carries `objective`, so the hydration source exists — we just wire it. Target weight is local `refAmount * yield / 100` and must become Mind's `target_weight_mg`.
7. **`Trial.phase` is raw `String(32)`**, not an enum. The enum refactor is the parent's job — **do not** touch it here.

## Repo Ownership

| Repo | Responsibility |
| --- | --- |
| `BIC-shared-types` | **No change.** Consume the existing `v1.1.6a1` Mind experiment contract + `MindClient`. |
| `BIC-agent-service` | Add `experiments.name` + `experiments.stage`; objective draft/confirm endpoints; objective persistence; `ConfirmKind.OBJECTIVE`; `ExperimentObjectiveConfirmedEvent`; objective subagent node + routing; Mind wiring (real client behind a stub toggle); snapshot DTO `name` + `stage`. |
| `BIC-agent-portal` | Rework the objective form around backend DTOs; add typed client methods; replace local-only draft/confirm with backend calls; hydrate from snapshot; remove local target-weight math. |
| `BIC-lab-service` | **No change.** |

## End-to-End Data Flow

```text
Chemist objective draft (Portal form)
  -> POST /sessions/{sid}/objective/draft        (BIC-agent-service)
  -> persist draft to experiments.objective (+ name)
  -> [reaction SMILES] -> MindClient.parse_experiment_materials  (typed; stub data)
  -> [targets]         -> MindClient.confirm_experiment_goal     (typed; stub data) -> target_weight_mg
  -> POST /sessions/{sid}/objective/confirm
  -> validate + persist + emit ExperimentObjectiveConfirmedEvent
  -> experiments.stage: experiment_objective -> workflow_design
  -> snapshot + SSE
  -> Portal hydrated objective + advance to Workflow Design (live, no refresh)
```

Validation ownership:

* Portal does presence/range checks for fast UX and renders errors.
* BIC-agent-service is authoritative: validates before persistence and before stage advancement; returns 422 mapped to field/form errors.

## Requirements

### R1. `experiments.name` and Task Name

* Add `experiments.name VARCHAR` (additive migration, nullable or defaulted — see design).
* Task Name is required at Confirm; lenient at Draft.
* Default generated name follows Feishu's rule: short summary + `yymmdd` + sequence suffix when duplicated in the current session.
* User can edit Task Name.
* Duplicate names within the current session are rejected at Confirm with a suggested alternative.

### R2. `experiments.stage` (Level-1) and objective-confirm transition

* Add `experiments.stage VARCHAR(32) NOT NULL DEFAULT 'experiment_objective'`.
* Define `ExperimentStage` enum: `experiment_objective | workflow_design | parameter_design`. Persist enum **values**, not member names.
* New experiments start in `experiment_objective`.
* Objective confirmation advances `experiment_objective -> workflow_design`.
* Transition is idempotent and never moves backward (no-op if already `workflow_design` or `parameter_design`).
* **Out of scope here:** the `workflow_design -> parameter_design` (plan-confirm) transition and `Trial.phase` enum — those belong to parent `06-21`. This task only needs the enum defined and the objective transition wired.

### R3. Objective draft/confirm endpoints (D2, D6)

* `POST /sessions/{session_id}/objective/draft` — lenient persist of the partial objective payload to `experiments.objective` (+ `name`).
* `POST /sessions/{session_id}/objective/confirm` — full validation, persist, emit `ExperimentObjectiveConfirmedEvent`, advance stage.
* Confirm goes through the dual-path persistence transaction (event appended + projected). Not the `/forms/confirm` decision transport.
* Endpoints live in L1 and call the L2 `service` Facade (layering rule).

### R4. Reaction Card (D3)

* Reaction is required at Confirm.
* Input is **text SMILES only**. No OCR/image route.
* Backend parses via `MindClient.parse_experiment_materials` (typed; stub data per D4) -> `rendered_rxn_url` + `materials[]`.
* Card shows rendered reaction structure when available.
* Edit action opens the **existing** portal molecule editor (research identifies the integration point; if none exists, document the gap and degrade to a SMILES text edit).
* Copy action copies reaction SMILES.

### R5. Reactant Table

* At least one substrate/reagent row required.
* Exactly one baseline/reference row enforced.
* Single row -> delete disabled, that row is baseline.
* Baseline row: `amount_mg` required; `equivalents` fixed `1.00`, not editable.
* Non-baseline rows: deletable; amount/equivalents may be empty until Mind recalculation fills them.
* Each row carries structure, compound name, molecular weight (if available), `amount_mg`, `equivalents`, baseline flag.
* Compound name length: pick **one** exact validated character budget (default: 50 chars) and test it.
* Switching baseline or changing target inputs triggers backend/Mind recalculation, not local arithmetic.

### R6. Target Purity, Yield, Weight

* Target purity and target yield required at Confirm; positive percent in `(0, 100]`; rendered with `%`, normalized to 2 decimals.
* Target weight is backend/Mind-calculated, read-only, rendered in `mg`, normalized to 3 decimals, sourced from `MindClient.confirm_experiment_goal -> target_weight_mg`.
* The portal's local `refAmount * yield / 100` math is removed (or isolated behind an unmistakable loading/unavailable state that cannot be mistaken for final chemistry output).

### R7. Persistence and Hydration

* Save Draft persists through BIC-agent-service.
* Confirm persists + advances to Workflow Design only after backend acceptance.
* Snapshot hydration restores the objective form from `snapshot.experiments[].objective` (+ `name`, `stage`), not stale local store state.
* `hydrateFromSnapshot` must stop skipping `objective`.
* Live SSE and hard refresh must agree on: task name, reaction render, reactant rows, baseline row, target purity/yield/weight, objective confirmation state, and Level-1 stage.

### R8. Validation and Error UX

* Required fields show `This field is required.`
* Length/range errors show the configured max/range.
* Backend 422 maps to field-level errors when possible, form-level otherwise.
* Draft lenient; Confirm strict.
* All visible portal copy is English.

## Out of Scope

* Direct portal-to-Mind calls.
* Reimplementing a molecule drawing/rendering library.
* OCR/image-based reaction extraction.
* The 5-status FE header projection (separate FE task — D8).
* `Trial.phase` enum refactor and the `workflow_design -> parameter_design` plan-confirm transition (parent `06-21`).
* Changing Workflow Design / Parameter Design behavior except for receiving the confirmed objective handoff.
* Any shared-types code change.
* Backfilling historical experiment rows.

## Acceptance Criteria

* [ ] Migration adds `experiments.name` and `experiments.stage` (additive; downgrade drops both).
* [ ] `ExperimentStage` enum exists; new experiments are `experiment_objective`; persisted values are lowercase strings.
* [ ] `ConfirmKind.OBJECTIVE` added in both `app/core/enums.py` and the `ConfirmKindLiteral` mirror, byte-identical.
* [ ] `POST objective/draft` persists a lenient draft to `experiments.objective` (+ `name`).
* [ ] `POST objective/confirm` validates, persists, and emits `ExperimentObjectiveConfirmedEvent` via the dual-path transaction.
* [ ] Objective confirm advances `experiment_objective -> workflow_design`; replay/idempotent; never backward.
* [ ] Objective subagent node registered; accepted execute with no confirmed objective routes there, not directly to `plan_subgraph`; after confirm the same turn may continue into `plan_subgraph`.
* [ ] Snapshot `SnapshotExperimentItem` exposes `name` and `stage`.
* [ ] Reaction parse populates `rendered_rxn_url` + material rows via `MindClient.parse_experiment_materials` (stub data acceptable).
* [ ] Target weight comes from `MindClient.confirm_experiment_goal -> target_weight_mg`; local FE math removed/isolated.
* [ ] Exactly one baseline row enforced; baseline equivalents fixed `1.00`; only baseline amount required pre-goal-confirm.
* [ ] Target purity/yield enforce `(0, 100]` and 2-decimal presentation; target weight 3 decimals.
* [ ] Task Name required, editable, default-generated, duplicate-guarded within a session.
* [ ] Portal `hydrateFromSnapshot` restores objective from backend data; live SSE and hard refresh agree.
* [ ] No portal code calls Mind directly.
* [ ] Mind wiring is behind a stub toggle; flipping to live requires no contract change.

## Definition of Done

* Backend tests cover: name + stage migration/repo, objective draft/confirm persistence, objective-confirm event apply (idempotent, no-backward), ConfirmKind.OBJECTIVE codec, objective routing, Mind wrapper (stub), snapshot DTO shape.
* Portal tests cover: objective form validation, baseline switching, backend error mapping, draft/confirm flow, snapshot hydration, live objective-confirm stage advance.
* Verification commands pass:
  * Backend: `uv run ruff check app tests`, `uv run ruff format --check app`, `uv run pyright app`, `alembic check`, targeted `uv run pytest`.
  * Portal: `pnpm typecheck`, `pnpm exec biome check <touched>`, `pnpm build`, targeted Vitest/Playwright.
* Parent `06-21` `implement.md` updated to consume (not rebuild) the stage/event/subagent built here (D5 cleanup flag).
* Implementation notes record that Mind material-parse/goal-confirm runs on stub data pending live Mind routes (D4).

## Open Questions (must be resolved before / during design, none block start)

* Exact FE↔contract field mapping between the portal form rows and `ExperimentMaterialParseResponse.materials[]` (shapes are not 1:1 — design resolves the adapter).
* Which existing portal component is the molecule-editor integration point for the reaction edit action (research to confirm; degrade to SMILES text edit if none).
* `experiments.name` nullability: nullable with app-level required-at-confirm, vs. `NOT NULL DEFAULT ''` (design picks one).

## Research References

* `research/backend-touchpoints-current.md` — live backend touch-points + 7 deltas.
* `research/sharedtypes-portal-current.md` — shared-types `v1.1.6a1` contract + portal form gaps.
* `research/feishu-objective-spec.md` — Feishu page + status sheet (status sheet now FE-only, D8).
