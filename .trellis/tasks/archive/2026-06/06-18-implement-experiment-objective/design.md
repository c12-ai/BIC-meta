# Technical Design — Implement Experiment Objective

> Grounds the locked decisions (PRD D1–D8) against live code (`feat/shared-types-v1-1-6a1-cc-re-migration`).
> Contract field names below are quoted verbatim from `bic_shared_types.model_service.http.experiment` @ `v1.1.6a1` (`51c70c4`).

## 1 · Scope & Boundaries

This task owns the **objective vertical**: backend schema (`name`, `stage`), objective draft/confirm endpoints, objective persistence + Mind wiring, the `ExperimentObjectiveConfirmedEvent`, the objective subagent node + routing, snapshot DTO, and the portal objective form rework.

It deliberately stops at the `experiment_objective -> workflow_design` transition. The `workflow_design -> parameter_design` plan-confirm transition, `Trial.phase` enum, and the FE 5-status header are **other tasks** (PRD D5/D8).

Layer map (per `backend/contracts.md`): L1 routes → L2 `service` Facade → L3 runtime (objective subagent) → L4 (repos, `MindClient`, events). Events stay layer-neutral.

## 2 · Shared-Types Contract (consume, no change)

Import path: `bic_shared_types.model_service.http.experiment` (the `mcp_protocol.experiment` re-export is deprecated and emits a warning — do **not** import it).

```python
# requests (Agent -> Mind)
ExperimentMaterialParseRequest: rxn: RxnSmiles
ExperimentGoalConfirmRequest:   rxn: RxnSmiles
                                feed_amount_mg: float = Field(gt=0)
                                target_purity_pct: float = Field(gt=0, le=100)
                                target_yield_pct: float = Field(gt=0, le=100)
                                basis_material_hint: str | None = None
# responses (Mind -> Agent)
ExperimentMaterialParseResponse: rendered_rxn_url: FileUrl
                                 materials: list[ExperimentParsedMaterial]  # min_length=1
  ExperimentParsedMaterial:      role: substrate|reagent|product, smiles, name?, structure_url?
ExperimentGoalConfirmResponse:   target_weight_mg: float = Field(ge=0)
                                 rendered_rxn_url: FileUrl
                                 materials: list[ExperimentMaterial]        # min_length=1
  ExperimentMaterial:            role: substrate|reagent, smiles, amount_mg(ge=0),
                                 equivalents(gt=0), is_baseline
```

The shared-types `MindClient` exposes `parse_experiment_materials(req) -> ...Response` / `confirm_experiment_goal(req) -> ...Response`, but the **agent-service** `MindClient` (`app/infrastructure/mind_client.py`) does NOT — it only has the dead `experiment_object_stub` placeholder. We add the two methods to the agent-service client (see §2a), not by instantiating the shared-types client.

**`RxnSmiles` validator gotcha:** requires exactly two `>` (`reactants>agents>products`, agents may be empty) and non-empty reactants+products. The backend MUST normalize/validate the user's SMILES before constructing the request, mapping validator `ValueError` to a 422 field error rather than a 500.

**Contract asymmetry the adapter must handle:** parse returns substrate+reagent+**product** rows; goal-confirm returns substrate+reagent only (+ `target_weight_mg`, per-material `amount_mg`/`equivalents`/`is_baseline`). The objective form's reactant table maps to goal-confirm `materials[]`; the product row from parse is display-only for the reaction card.

### 2a · Mind stub — in-method, matching the codebase (D4, RECONCILED)

**Conflict resolved (Rule 5/8):** the original design proposed an `ObjectiveMaterialPort` + config toggle. Research found the codebase has **zero precedent** for a config-driven Mind stub — `recommend_param` / `analyze_result` / `recognize_tlc_plate` are all stubbed *unconditionally inside the agent-service `MindClient` methods*, returning `med005_*` contract-typed fixtures, with a TODO to swap the body for HTTP when Mind lands. We match that pattern; the port + toggle is dropped (simpler, consistent, no new config/lifespan/spec surface).

* Add two methods to the agent-service `MindClient`, replacing the `experiment_object_stub` placeholder:
  * `async def parse_experiment_materials(self, request: ExperimentMaterialParseRequest) -> ExperimentMaterialParseResponse`
  * `async def confirm_experiment_goal(self, request: ExperimentGoalConfirmRequest) -> ExperimentGoalConfirmResponse`
* Both are **stubbed in-method** (like `recognize_tlc_plate`): `logger.warning("... is stubbed ...")` + return a deterministic, contract-valid response. Add `med005_experiment_material_parse_response()` / `med005_experiment_goal_confirm_response()` factories to `app/data/med005_fixture.py` (fixed `rendered_rxn_url`, echoed materials, computed `target_weight_mg`).
* Update `MindClientProtocol` to declare the two methods (drop `experiment_object_stub`).
* When Mind confirms the live routes, swap the method body for the real HTTP call (identical to the existing CC/RE TODO) — callers are unchanged. Record in task notes that objective material-parse / goal-confirm run on stub data.

## 3 · DB Schema (additive migration)

```sql
ALTER TABLE experiments ADD COLUMN name VARCHAR(255);                              -- D1
ALTER TABLE experiments ADD COLUMN stage VARCHAR(32) NOT NULL DEFAULT 'experiment_objective';  -- D2/R2
```

* `name` nullability: **nullable** column; required-at-confirm enforced in the app layer (lenient draft can have null name). This avoids an empty-string sentinel and keeps duplicate-guard queries clean. (Resolves PRD open question.)
* `stage` default exists for schema simplicity / dev rows only; no historical backfill (PRD out-of-scope).
* Downgrade drops both columns.
* `alembic check` must be clean after the model change.

Models (`app/data/models.py`): add `Experiment.name: Mapped[str | None]` and `Experiment.stage: Mapped[str]` (persist `ExperimentStage` **value**; column stays `String(32)` per existing persistence style). Do **not** touch `Trial.phase` (parent's job).

## 4 · Enums

```python
# app/core/enums.py
class ExperimentStage(StrEnum):
    EXPERIMENT_OBJECTIVE = "experiment_objective"
    WORKFLOW_DESIGN = "workflow_design"
    PARAMETER_DESIGN = "parameter_design"

class ConfirmKind(StrEnum):
    PLAN = "plan"; PARAMS = "params"; RESULT_REVIEW = "result_review"
    OBJECTIVE = "objective"   # NEW
```

**Layer-neutral mirror (test-enforced):** `app/events/**` cannot import `app.core.enums`. Add `"objective"` to the `ConfirmKindLiteral` mirror at `app/events/form_payloads.py:59`, byte-identical to the enum value. `test_import_hygiene.py` and `test_events_codec.py` guard this.

`ExperimentStage` is consumed by repos/runtime/snapshot (upper layers) — it may import from `app.core.enums` freely. Only the events package needs the literal mirror.

## 5 · Objective Persistence & Repos

`ExperimentsRepo` (`app/repositories/experiments_repo.py`):

* Add `name` and `stage` to `ExperimentSnapshot` and `_row_to_snapshot`.
* Add `name`, `stage` to the updatable-fields set so `update_fields` can write them.
* Add a method to persist the objective payload to `experiments.objective` (JSONB) — or reuse `update_fields({"objective": ..., "name": ...})`. Keep `kind` immutable.

Objective payload shape persisted in `experiments.objective` (JSONB) — the backend's canonical objective DTO (a pydantic model in L2/L4, not the wire form):

```text
objective = {
  "reaction_smiles": str,
  "rendered_rxn_url": str | null,
  "reactants": [ { smiles, name, molecular_weight?, amount_mg?, equivalents?, is_baseline } ],
  "target_purity_pct": float,
  "target_yield_pct": float,
  "target_weight_mg": float | null,     # Mind-calculated
  "confirmed": bool
}
```

`name` is stored in the new column, not inside `objective`.

## 6 · L1 Endpoints (D2, D3)

Add to `app/api/routers/sessions.py` (L1, calls L2 `service` Facade only):

```text
POST /sessions/{session_id}/objective/draft
  body: ObjectiveDraftRequest (lenient — partial fields allowed)
  -> service.save_objective_draft(...)
  -> persist to experiments.objective (+ name); NO event/stage change
  -> 200 ObjectiveDraftResponse (echo persisted draft + any Mind-parsed materials)

POST /sessions/{session_id}/objective/confirm
  body: ObjectiveConfirmRequest (full — validated)
  -> service.confirm_objective(...)
  -> validate (name present + session-unique; reaction valid; targets in range; baseline rules)
  -> Mind goal-confirm -> target_weight_mg
  -> emit ExperimentObjectiveConfirmedEvent through the three-piece tx (§7)
  -> 200 ObjectiveConfirmResponse (stage=workflow_design, confirmed objective)
  -> 422 on validation failure (field-mapped)
```

Draft may optionally trigger `parse_experiment_materials` to populate the rendered reaction + material rows (so the form fills as the chemist types the SMILES); confirm triggers `confirm_experiment_goal` for the authoritative `target_weight_mg`. Both go through the stub port (§2a).

Request/response DTOs are L1 pydantic schemas; they adapt to/from the backend objective DTO (§5) and the Mind contract (§2). Keep the adapter in one place (L2 or a dedicated objective module) to resolve the parse/goal-confirm asymmetry.

## 7 · Objective-Confirm Event (D6, dual-path D6/D41)

New event `ExperimentObjectiveConfirmedEvent` in `app/events/` (layer-neutral; string literals only):

```text
ExperimentObjectiveConfirmedEvent(
    experiment_id: str,
    objective: dict,          # the persisted objective payload (wire JSONB)
    name: str,
    confirm_kind: "objective" # literal
)
```

`apply(...)` (projection, runs in `post_processor.apply` inside the three-piece tx):

1. update `experiments.objective` (+ `name`) with the confirmed payload;
2. `ExperimentsRepo.update_fields(experiment_id, {"stage": "workflow_design"})`;
3. **idempotent / no-backward:** no-op the stage write if current stage is already `workflow_design` or `parameter_design`;
4. nothing else — no job materialization here (that's plan-confirm, parent's task).

The L2 orchestrator emits this through the standard transaction:

```text
async with persistence.transaction():
    await post_processor.apply(event)                 # stage projection
    seq = await persistence.session_events.append(event)
await broadcaster.emit(session_id, event, session_seq=seq)   # live SSE -> portal advances stage
```

This satisfies I1 (append-before-emit) and gives the portal a live signal to move to Workflow Design without refresh; snapshot remains the recovery source.

Codec/exhaustiveness: register the event wherever `test_events_codec.py` / runtime event unions require it.

## 8 · Objective Subagent & Routing (D5)

New node `app/runtime/graphs/nodes/experiment_objective.py`, registered in `factory.py` alongside `plan_subgraph` / `specialist_dispatcher`.

Routing changes:

* `route_entry.py`: `FORM_CONFIRM(objective)` — there is **no** agent-minted objective form in this design (D6 = direct API confirm). So the objective confirm does **not** flow through `route_entry`'s `FORM_CONFIRM` branch; it is an L1 endpoint that emits the event directly. `route_entry` only needs to keep its existing `plan/params/result_review` branches intact. **(Simplification vs. parent's sketch — the direct-API decision removes the FORM_CONFIRM(objective) routing entirely.)**
* `route_after_admit.py`: an accepted execute turn with no confirmed objective must route to the **objective subagent**, not `plan_subgraph`. Gate on `experiment.stage`:
  * no experiment / `experiment_objective` → objective subagent;
  * `workflow_design` → `plan_subgraph`;
  * `parameter_design` → specialist dispatcher / existing in-flight behavior.
  * Update the `Literal[...]` goto union that currently allows only `plan_subgraph` to include the objective node target (research flagged this union).

Objective subagent behavior (minimal — the rich form is the portal + endpoints; the subagent owns the *conversational* entry):

1. create or reuse the active experiment in `experiment_objective`;
2. surface/acknowledge that the chemist should fill the Objective form (the portal renders it);
3. do **not** route into `plan_subgraph` before objective confirmation;
4. after `ExperimentObjectiveConfirmedEvent` has advanced stage to `workflow_design`, a subsequent turn proceeds to `plan_subgraph` normally.

> Design note: because confirm is a direct API call (not an in-graph FORM_CONFIRM), the subagent's job is narrow — guard the entry and keep the experiment in `experiment_objective`. The stage advance happens via the endpoint's event, then normal routing picks up `workflow_design`.

## 9 · Snapshot DTO

`app/api/routers/sessions.py` — `SnapshotExperimentItem` adds:

```text
name: str | None
stage: ExperimentStage      # serialized as the lowercase value
```

`objective` already exists on the snapshot item (currently read-only `{}`); it now carries the real persisted objective. `SnapshotJobItem` / `SnapshotTrialItem` unchanged (no `Trial.phase` enum here).

## 10 · Portal Changes

`src/lib/agent-client.ts`:

* Add `ExperimentStage` const-union type + `SnapshotExperiment.name` / `.stage`.
* Add typed client methods `saveObjectiveDraft(sessionId, body)` / `confirmObjective(sessionId, body)` hitting the new endpoints.
* Hand-mirror the objective request/response shapes (established pattern — shared-types does not export these to TS; the `export_ts_enums.py` script only emits Solvent/ColumnType/FlaskVolume).

`src/stores/workspaceStore.ts`:

* Replace local-only `saveObjectiveDraft` / `confirmObjective` (`:636-637`) with async actions calling the client; keep dirty-form ergonomics.
* `hydrateFromSnapshot` (`:752-755`) must **stop skipping** `snapshot.experiments[].objective` — populate the form from it, plus `name` and `stage`.
* On live `ExperimentObjectiveConfirmedEvent`, set Level-1 stage to `workflow_design` (advance the stepper without refresh).

`src/components/workspace/ExperimentObjectiveStep.tsx`:

* Remove local `targetWeightMg = refAmount * yield / 100` (`:127-136`); render `target_weight_mg` from the confirm response / hydrated objective, 3 decimals; show a loading/unavailable state when absent.
* Reaction card: render `rendered_rxn_url` / `structure_url` as `<img>` (server-rendered; no client molecule lib). Edit → existing molecule editor **if one exists** (research found none — degrade to SMILES text edit and document the gap). Copy → reaction SMILES.
* Reactant table maps to goal-confirm `materials[]`; enforce exactly-one-baseline (already in zod), baseline `equivalents` fixed `1.00`, only-baseline-amount-required-pre-confirm.
* Map backend 422 → field/form errors.

## 11 · Affected Files

Backend (`BIC-agent-service`):
* `alembic/versions/<new>_experiments_name_stage.py`
* `app/data/models.py`
* `app/core/enums.py`
* `app/events/form_payloads.py` (ConfirmKindLiteral mirror)
* `app/events/<objective_confirmed_event>.py` (+ registration/codec)
* `app/repositories/experiments_repo.py`
* `app/infrastructure/mind_client.py` (objective material port / stub adapter wiring)
* `app/session/service.py` (L2 Facade: save_objective_draft / confirm_objective)
* `app/runtime/graphs/nodes/experiment_objective.py` (new)
* `app/runtime/graphs/nodes/route_after_admit.py`
* `app/runtime/graphs/factory.py`
* `app/api/routers/sessions.py` (endpoints + snapshot DTO)
* tests: `test_persistence_repo_experiments.py`, `test_runtime_emitted_apply.py`, `test_events_codec.py`, `test_import_hygiene.py`, `test_persistence_repo_snapshot.py`, objective endpoint test, objective routing test, Mind-stub test.

Portal (`BIC-agent-portal`):
* `src/lib/agent-client.ts`
* `src/stores/workspaceStore.ts`
* `src/components/workspace/ExperimentObjectiveStep.tsx`
* `src/components/workspace/TaskConfigPane.tsx` (stage-driven step status, objective step only)
* tests: objective form validation, baseline switching, error mapping, draft/confirm flow, snapshot hydration, live objective-confirm.

## 12 · Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| `RxnSmiles` validator 500s on bad user SMILES | normalize + try/except in the adapter; map to 422 field error before building the request. |
| Parent `06-21` rebuilds stage/event/subagent → collision | PRD D5: update parent `implement.md` to consume; this task is the single source. Flag in finish step. |
| Events package imports the enum → import-hygiene test fails | use the `ConfirmKindLiteral` mirror; never import `app.core.enums` in `app/events/**`. |
| Stub data mistaken for real chemistry | stub returns contract-typed but clearly-marked deterministic values; task notes record stub mode; FE shows source-of-truth values only when present. |
| Snapshot/live stage drift | hydrate stage from snapshot AND advance on the live event in the same slice; test both paths. |
| Objective confirm bypasses dual-path | confirm MUST emit `ExperimentObjectiveConfirmedEvent` through the three-piece tx, never a bare repo write. |

## 13 · Rollout / Rollback

* Additive migration; downgrade drops `name` + `stage`.
* Stub-mode default means no live Mind dependency to ship.
* Rollback: stop consuming `stage`/objective endpoints; columns harmless if left; drop via downgrade if needed.
* No new external service/key for the stubbed path.
