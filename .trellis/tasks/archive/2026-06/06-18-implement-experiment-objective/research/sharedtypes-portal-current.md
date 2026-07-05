# Research: shared-types Mind protocol + portal Experiment Objective (current state)

- **Query**: Audit live state of (A) BIC-shared-types Mind experiment protocol and (B) BIC-agent-portal Experiment Objective form, to ground design.md.
- **Scope**: internal (two repos: BIC-shared-types @ v1.1.6a1, BIC-agent-portal)
- **Date**: 2026-06-21
- **Verified against**: live code (supersedes the earlier `shared-types-experiment-protocol.md` / `current-code-audit.md`).

---

## TL;DR for the design

**Shared-types pin (what BE will import):** `bic-shared-types == v1.1.6a1`
(`BIC-agent-service/pyproject.toml:158` → `rev = "v1.1.6a1"`; `uv.lock:199` resolves to commit `51c70c49cba2b84c1a9d3135e5a9af3d5e814ace`). The checked-out shared-types repo HEAD **is** that tag/commit, so what I quote below is exactly what the BE gets.

**Contract field names the design MUST use verbatim** (current path = `bic_shared_types.model_service.http.experiment`; the old `mcp_protocol.experiment` path is a DEPRECATED re-export shim that emits a `DeprecationWarning`):

- `ExperimentMaterialParseRequest` → `rxn: RxnSmiles`
- `ExperimentMaterialParseResponse` → `rendered_rxn_url: FileUrl`, `materials: list[ExperimentParsedMaterial]`
  - `ExperimentParsedMaterial` → `role: ExperimentParsedMaterialRole(substrate|reagent|product)`, `smiles: str`, `name: str|None`, `structure_url: FileUrl|None`
- `ExperimentGoalConfirmRequest` → `rxn: RxnSmiles`, `feed_amount_mg: float (gt=0)`, `target_purity_pct: float (gt=0, le=100)`, `target_yield_pct: float (gt=0, le=100)`, `basis_material_hint: str|None`
- `ExperimentGoalConfirmResponse` → `target_weight_mg: float (ge=0)`, `rendered_rxn_url: FileUrl`, `materials: list[ExperimentMaterial]`
  - `ExperimentMaterial` → `role: ExperimentMaterialRole(substrate|reagent)`, `smiles: str`, `amount_mg: float (ge=0)`, `equivalents: float (gt=0)`, `is_baseline: bool`

Client wrapper already exists: `MindClient.parse_experiment_materials(...)` → `POST /api/protocol/experiment/material-parse`; `MindClient.confirm_experiment_goal(...)` → `POST /api/protocol/experiment/goal-confirm`. No new shared-types work needed for the contract itself.

**Biggest portal gaps:**
1. **No POST.** `saveObjectiveDraft` / `confirmObjective` only `set()` into `workspaceStore`; there is no objective client method in `agent-client.ts`. (`workspaceStore.ts:636-637`)
2. **Local target-weight math.** `target_weight_mg` is computed client-side as `refAmount * yield / 100` (mass basis, no MW correction) instead of from `ExperimentGoalConfirmResponse.target_weight_mg`. (`ExperimentObjectiveStep.tsx:127-136`)
3. **Snapshot hydration deliberately ignores objective.** The snapshot already carries `SnapshotExperiment.objective` (BE JSONB column), but `hydrateFromSnapshot` keeps the FE-only draft and never reads it (`workspaceStore.ts:752-755`). **And the store has NO `persist` middleware** (only `devtools`, `enabled: DEV` — `workspaceStore.ts:528-529,1034`), so the comment "objective is restored from FE persistence elsewhere" is INACCURATE — the draft is lost on refresh today.
4. **No molecule/reaction renderer.** No `ketcher`/`rdkit`/`openchemlib`/`smiles` lib in `package.json`; structure cells are `FlaskConical` placeholders. The contract returns server-rendered image URLs (`rendered_rxn_url`, `structure_url`), so "rendering" = `<img src={url}>`, not a client-side drawer.
5. **`ConfirmKind` is NOT in shared-types** — only in agent-service `app/core/enums.py:26` (`plan|params|result_review`). The FE mirrors it as a TS union in `agent-client.ts`. There is no objective `ConfirmKind` member today.

---

## PART A — BIC-shared-types

### A.1 Installed / pinned version

| Where | Evidence |
|---|---|
| `BIC-agent-service/pyproject.toml:27` | `"bic-shared-types",` (dep) |
| `BIC-agent-service/pyproject.toml:158` | `bic-shared-types = { git = "https://github.com/c12-ai/BIC-shared-types", rev = "v1.1.6a1" }` |
| `BIC-agent-service/uv.lock:155` | `git = "...?rev=v1.1.6a1"` |
| `BIC-agent-service/uv.lock:197-199` | `name = "bic-shared-types"`, `version = "1.1.6a1"`, commit `51c70c49cba2b84c1a9d3135e5a9af3d5e814ace` |
| shared-types repo state | `git branch` = `main`, `git describe --tags` = `v1.1.6a1`, HEAD `51c70c4 feat(model_service): mixcase SMILES maps + /api/protocol + CC v1.1.6a1 (#73)` |

**Pinned version = `v1.1.6a1` (commit `51c70c4`). Local checkout == pin**, so quotes below are authoritative.

### A.2 Experiment protocol models (the contract)

**Current path: `bic_shared_types/model_service/http/experiment.py`** (module docstring states it was moved here from `mcp_protocol.experiment`).
**Deprecated path: `bic_shared_types/mcp_protocol/experiment.py`** — pure re-export shim; importing anything under `mcp_protocol` triggers a package-level `DeprecationWarning`. **The design must import from `model_service.http.experiment`, NOT `mcp_protocol`.**

Exact field definitions (verbatim, `model_service/http/experiment.py`):

```python
# helper enums
class ExperimentParsedMaterialRole(StrEnum):   # SUBSTRATE="substrate", REAGENT="reagent", PRODUCT="product"
class ExperimentMaterialRole(StrEnum):          # SUBSTRATE="substrate", REAGENT="reagent"

class ExperimentParsedMaterial(ExperimentProtocolModel):     # L33-45
    role: ExperimentParsedMaterialRole
    smiles: str
    name: str | None = None
    structure_url: FileUrl | None = None        # URL of RDKit-rendered material image

class ExperimentMaterial(ExperimentProtocolModel):           # L55-62
    role: ExperimentMaterialRole
    smiles: str
    amount_mg: float = Field(ge=0)
    equivalents: float = Field(gt=0)
    is_baseline: bool

# requests (Apex/Agent → Mind)
class ExperimentMaterialParseRequest(ExperimentProtocolModel):   # L70-73
    rxn: RxnSmiles

class ExperimentGoalConfirmRequest(ExperimentProtocolModel):     # L76-89
    rxn: RxnSmiles
    feed_amount_mg: float = Field(gt=0)
    target_purity_pct: float = Field(gt=0, le=100)
    target_yield_pct: float = Field(gt=0, le=100)
    basis_material_hint: str | None = None

# responses (Mind → Apex/Agent)
class ExperimentMaterialParseResponse(ExperimentProtocolModel):  # L97-103
    rendered_rxn_url: FileUrl
    materials: list[ExperimentParsedMaterial] = Field(min_length=1)

class ExperimentGoalConfirmResponse(ExperimentProtocolModel):    # L106-113
    target_weight_mg: float = Field(ge=0)
    rendered_rxn_url: FileUrl
    materials: list[ExperimentMaterial] = Field(min_length=1)
```

Base model: `ExperimentProtocolModel(BaseModel)` with `model_config = ConfigDict(extra="ignore")` — extra wire fields are dropped silently.

Type aliases (`bic_shared_types/common/types.py`):
- `FileUrl: TypeAlias = str` — plain string today (URL/path), no validation.
- `RxnSmiles = Annotated[str, AfterValidator(_validate_rxn_smiles)]` — **validates the SMILES has exactly two `>` (format `reactants>agents>products`, agents may be empty) and non-empty reactants+products.** This validator runs on the Agent-built request — the design must normalize/validate user SMILES before constructing the request or pydantic raises `ValueError`.

**Contract semantics worth flagging for the design:**
- Parse step returns substrate **+ reagent + product** rows; goal-confirm returns substrate **+ reagent** rows only (no product row) plus a calculated `target_weight_mg` and per-material `amount_mg` / `equivalents` / `is_baseline`.
- The user picks ONE baseline material and supplies `feed_amount_mg`; `basis_material_hint` (a SMILES) is optional and "guides Mind's recommendation of the remaining material fields."
- `target_weight_mg` is **Mind-calculated** — this is the authoritative replacement for the portal's local `refAmount * yield / 100`.

### A.3 Client wrapper

`bic_shared_types/clients/model_service/http/mind_client.py` — class **`MindClient`** (async, httpx, behind `[http]` extra; injectable `transport` for tests; optional `bearer_token`). Relevant methods:

```python
async def parse_experiment_materials(self, request: ExperimentMaterialParseRequest) -> ExperimentMaterialParseResponse
    # POST /api/protocol/experiment/material-parse          (mind_client.py:61-66)
async def confirm_experiment_goal(self, request: ExperimentGoalConfirmRequest) -> ExperimentGoalConfirmResponse
    # POST /api/protocol/experiment/goal-confirm            (mind_client.py:68-71)
```

(Same client also exposes TLC/CC/RE methods.) Each returns the FULL typed response (no unwrapping). `MindClientError` raised on 4xx/5xx/timeout. `base_url` → Mind backend.

### A.4 ConfirmKind

**NOT in shared-types** (`grep ConfirmKind bic_shared_types/` → no hits). Lives only in `BIC-agent-service/app/core/enums.py:26-49`:
```python
class ConfirmKind(StrEnum):
    PLAN = "plan"; PARAMS = "params"; RESULT_REVIEW = "result_review"
    # .coerce(): "param"->PARAMS, "result"/"review"->RESULT_REVIEW, "spec" REJECTED (ValueError)
```
No objective member exists. If the objective flow needs an HITL confirm kind, that's a new value here (and a mirror in the FE union — see below).

### A.5 TS export tooling

`bic_shared_types/scripts/export_ts_enums.py` generates `ts/enums.ts` — but **only `Solvent`, `ColumnType`, `FlaskVolume`** are registered (the `ENUMS` list). It does **NOT** emit any Experiment/Material/Confirm types (grep of `ts/enums.ts` for experiment/confirm/material → empty). So:
- The portal does **not** auto-consume the experiment protocol from shared-types; it hand-mirrors shapes in `src/types/specialist-forms.ts` / `agent-client.ts` (header comments cite the Python source paths). No generated bridge for objective exists.
- If the design wants the FE typed against the experiment contract, it must either (a) hand-mirror in `agent-client.ts` (the established pattern), or (b) extend the export script (heavier; the script only emits enum value-arrays + string-union types, not full object models — `export_json_schema.py` is the model exporter).

---

## PART B — BIC-agent-portal Experiment Objective form

### B.6 `ExperimentObjectiveStep.tsx` (534 lines)

Header comment (L1-12) states the design constraint explicitly: *"Frontend-only form: the BE has no objective wire contract yet, so Save Draft / Confirm persist into workspaceStore ... and never POST."* and *"Structure tiles ... are placeholders — the portal has no molecule renderer yet."*

**Fields rendered:**
| Section | Field | Notes |
|---|---|---|
| Task | `taskName` (L211-219) | required (zod) |
| Reaction | `smiles` (L236-244) | **optional** per zod (`z.string()`, L62); preview is just the raw SMILES text echoed in a `role="img"` box (L249-263), no rendered structure |
| Reactants (table) | `reactants[]`: `name`, `amountMg`, `equivalents`, `isReference` (radio) | L304-423; add/remove rows; exactly-one-reference invariant enforced in zod (L66-68) and via `setReference`/`removeReactant` (L139-156). Structure cell = `FlaskConical` placeholder icon (L309-317) |
| Targets | `targetPurityPct` (L453-466), `targetYieldPct` (L478-491), `targetWeightMg` (read-only, L499-507) | purity/yield required, max 100; weight is read-only auto-calc |

**Target-weight computation (LOCAL, lines 127-136):**
```ts
const refAmount = Number(watchedReactants?.find((r) => r.isReference)?.amountMg)
const yieldNum = Number(watchedYield)
const targetWeightMg = (... guards ...) ? (refAmount * yieldNum) / 100 : null
```
Comment L125-126: *"A mass basis only (no MW correction) — matches the prototype's calculation."* Displayed `targetWeightMg.toFixed(2)` (L504). **This is the placeholder the Mind `ExperimentGoalConfirmResponse.target_weight_mg` should replace.**

**Save Draft / Confirm (NO POST):**
- `onSaveDraft` (L158-164): `saveObjectiveDraft(getValues())` then `reset(values)`. No network.
- `onConfirm` (L166-173): `handleSubmit` → `confirmObjective(values)`, `reset(values)`, `selectStep('workflow')` (advances stepper, NOT `byUser=true`). No network.

Note the FE field names differ from the contract: FE uses `taskName / smiles / reactants[{name,amountMg,equivalents,isReference}] / targetPurityPct / targetYieldPct`; contract uses `rxn / feed_amount_mg / target_purity_pct / target_yield_pct / basis_material_hint` + `materials[{role,smiles,amount_mg,equivalents,is_baseline}]`. The design must define the FE↔contract mapping (e.g. `isReference` ↔ `is_baseline`, reference row's `amountMg` ↔ `feed_amount_mg`).

### B.7 `workspaceStore.ts` — objective state + actions

State shape (`ObjectiveDraft` / `ObjectiveReactant`, L65-85):
```ts
interface ObjectiveReactant { name: string; amountMg: string; equivalents: string; isReference: boolean }
interface ObjectiveDraft {
  taskName: string; smiles: string; reactants: ObjectiveReactant[]
  targetPurityPct: string; targetYieldPct: string
}
```
(numeric fields are strings so partial input round-trips; zod validates on Confirm.)

State slots (L220-224, defaults L512-513): `objective: ObjectiveDraft | null = null`, `objectiveConfirmed: boolean = false`.

Mutator signatures (L289-290 decl; L636-637 impl):
```ts
saveObjectiveDraft: (draft: ObjectiveDraft) => void   // set({ objective: draft })
confirmObjective:   (draft: ObjectiveDraft) => void   // set({ objective: draft, objectiveConfirmed: true })
```
Comment L633-635 confirms: *"No POST behind either mutator — the BE has no objective wire contract yet."*

**Persistence reality:** store is `create<...>()(devtools(... , { name: 'workspaceStore', enabled: import.meta.env.DEV }))` (L528-529, L1034). **No `persist` middleware → objective is in-memory only, wiped on refresh.** `resetSession: () => set(INITIAL_DATA)` (L1031) also clears it on every session switch (`ChatPage` resets the store per session).

### B.8 `agent-client.ts` — methods + Snapshot types

Exported client functions (no objective endpoint exists):
`createSession`, `submitUserMessage`, `submitFormConfirm`, `submitDecision`, `sseUrl`, `presignFile`, `recognizeTlcPlate`, `uploadFileToPresigned`, `fetchSessionListLive`, `fetchSessionHistoryLive`, `fetchSessionSnapshot`. **No `*objective*` method** (grep → only the `SnapshotExperiment.objective` field).

`Snapshot*` types (mirror `BIC-agent-service/app/api/routers/sessions.py::SessionSnapshotResponse`):
- `SnapshotSession` (L337): `session_id, status, created_at`
- `SnapshotExperiment` (L344): `experiment_id, kind, objective: Record<string, unknown>, status, started_at` ← **objective already on the wire**
- `SnapshotPlanParams` (L355): `steps: {title, executor, type}[]`
- `SnapshotPlan` (L360): `plan_id, experiment_id, status, params, current_job_id, created_at`
- `SnapshotJob` (L373): `job_id, plan_id, seq, executor, title, status, created_at`
- `SnapshotTrial` (L386): `trial_id, job_id, attempt, created_at, status, phase, params, analysis, steps, lab_task_id, started_at, finished_at, analysis_completed`
- `SnapshotDecision` (L404): `decision_id, kind: ConfirmKind|null, original_action, status`
- `SessionSnapshot` (L414): `{ session, experiments[], plans[], jobs[], trials[], pending_decisions[], last_seq }`
- `fetchSessionSnapshot(sessionId)` → `GET /sessions/{id}/snapshot` (L424-430)

BE side confirms `SnapshotExperimentItem.objective: dict[str, Any]` (`sessions.py:298`, populated from `e.objective`, `sessions.py:475`), backed by `experiments.objective` JSONB column default `{}` (`app/data/models.py:107`). **There is no BE write route for objective** (grep of `app/api/routers/` for objective → only the snapshot read field).

### B.9 Molecule / reaction renderer — does one exist to reuse?

**No.** No `ketcher`/`rdkit`/`openchemlib`/`smiles-drawer`/`molecule` library in `package.json` or `src`. The only hits are the two "no molecule renderer yet" comments in `ExperimentObjectiveStep.tsx` (L12, L310). Reaction/structure preview is currently raw SMILES text echo + a `FlaskConical` placeholder icon per row.

**Reuse path the contract enables:** Mind renders server-side and returns image URLs (`rendered_rxn_url`, per-material `structure_url`) — so the "reaction edit action" / structure display becomes an `<img>` fed by those URLs (likely via the existing presign/`get` file flow — `presignFile` exists in `agent-client.ts:189`), not a new client-side chemistry library. No drawing/editing component exists to reuse; SMILES editing today is a plain `<Input>`.

### B.10 Snapshot hydration → objective form on refresh

Cold-load path: `src/lib/session-loader.ts::loadSessionOnce` (L95-155):
1. `Promise.all` fetch `sessionSnapshotQueryOptions` + `sessionHistoryQueryOptions` (L111-114).
2. Replay history events through `dispatchEvent` to rebuild the **chat thread** (L120-122).
3. `workspace.hydrateFromSnapshot(snapshot)` LAST → workspace becomes snapshot-authoritative, derives routing once (L126).
4. Cursor = `snapshot.last_seq`; optionally open live SSE resumed from it (L129, L148-154).

`hydrateFromSnapshot` (`workspaceStore.ts:648-755`) rebuilds plans/jobs/trials/decisions, but for objective it explicitly does (L752-755):
```ts
// Keep the FE-only objective draft across a snapshot hydrate — it
// is restored from FE persistence, not the snapshot.
objective: s.objective,
objectiveConfirmed: s.objectiveConfirmed,
```
**So on refresh the objective form does NOT hydrate from the snapshot, and (no persist middleware) the in-memory draft is also gone → the form resets to `DEFAULT_VALUES`.** The snapshot DOES carry `experiments[].objective`, so the design has a ready source if it chooses to hydrate from it. This "FE persistence" claim is the single most misleading comment in the current code — treat it as a gap, not a working path.

---

## Caveats / Not Found

- I did **not** verify the BE Mind base-url config or whether agent-service already wires `MindClient` for the experiment endpoints (out of scope — Part A asked only for the shared-types contract + pin). The client methods exist in shared-types; whether the BE calls them yet is unconfirmed.
- The FE↔contract field-name mapping (e.g. which reactant row supplies `feed_amount_mg`, how `basis_material_hint` is chosen, product-row handling) is an open design decision — the shapes don't line up 1:1.
- `ConfirmKind` has no objective member; whether the objective confirm is HITL-gated (needs a new `ConfirmKind`) or a direct POST is a design decision, not determinable from current code.
- The earlier `research/shared-types-experiment-protocol.md` and `research/current-code-audit.md` predate this audit; where they cite `mcp_protocol.experiment` as the live path they are STALE — the live path is `model_service.http.experiment`.
