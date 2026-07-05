# Research: Phase 3 Integration Points — Mind port + L2 Facade + L1 endpoints

- **Query**: Audit live code for adding (a) Mind material/goal port + deterministic stub adapter, (b) L2 `save_objective_draft`/`confirm_objective`, (c) L1 `POST /sessions/{sid}/objective/draft` + `/confirm`. Persist exact file:line integration points.
- **Scope**: internal (BIC-agent-service)
- **Repo / branch**: `/Users/drakezhou/Development/BIC/BIC-agent-service` @ `feat/shared-types-v1-1-6a1-cc-re-migration`
- **Date**: 2026-06-21

---

## Decision-grade summary (read this first)

| Question | Answer (verbatim from live code) |
|---|---|
| **Emit-path API the service MUST use for `ExperimentObjectiveConfirmedEvent`** | `seq = await self._orchestrator.persist_event(event)` then `await self._broadcaster.emit(session_id, event, session_seq=seq)`. `persist_event` (`orchestrator.py:359`) is the three-piece `post_processor.apply(event, tx)` + `session_events.append(event)` in ONE `persistence.transaction()`. **This is the correct path because the event HAS an `apply()`** (`bypass_emitted.py:128`). Do NOT copy the TLC/decision raw-`tx.session_events.append` path — those events have NO `apply` and persist their side-effects manually. |
| **Why NOT `persist_event_with_decision_cas`** | That variant (`orchestrator.py:380`) is for `/forms/confirm` only — it does a `pending_decisions` CAS. Objective-confirm is a direct API (design D6), no pending decision, so use plain `persist_event`. |
| **Service injection into routers** | `Depends(get_session_service)` — `app/api/dependencies.py:35` reads `request.app.state.session_service`. The `SessionService` is constructed in `app/main.py:116` and stored on `app.state` by the composite lifespan. New routes take `service: Annotated[SessionService, Depends(get_session_service)]`. |
| **Mind toggle mechanism** | **NONE — must add.** No `stub`/`fake`/`USE_STUB`/`MIND_` flag exists in `app/core/config.py`. The CC/RE/TLC "stub" is hardcoded inside the agent-service `MindClient` methods themselves (no toggle). The objective port (design §2a) must be added as a new indirection + a config flag (see §5). |
| **Mind objective methods** | The agent-service `MindClient` (`app/infrastructure/mind_client.py`) does **NOT** have `parse_experiment_materials` / `confirm_experiment_goal` — only a `...`-stub `experiment_object_stub` placeholder (line 89). The REAL methods exist on the **shared-types** `MindClient` (`.venv/.../bic_shared_types/clients/model_service/http/mind_client.py:61,68`). Design §2 claim "Client (already exists)" refers to the shared-types client, not the one the app wires today. |
| **L1 test harness entry point** | `tests/integration/test_routes_tlc.py` — live uvicorn + real Postgres `app_client` fixture, `AsyncMock` stub of `app.state.mind_client.*`, `_seed_session` / `_seed_task` helpers, `_L4_TABLES` truncate. Mirror this file for the objective endpoint test. |
| **L2 service test harness entry point** | `tests/unit/test_session_service_tlc.py` — pure-delegation unit test, `_build_service()` builds `SessionService` with all 6 collaborators `MagicMock`/`AsyncMock`. Mirror for `confirm_objective`/`save_objective_draft`. |
| **Codec test** | `tests/unit/test_events_codec.py:351` ALREADY registers `bypass_emitted.ExperimentObjectiveConfirmedEvent` in `_EVENT_FACTORIES`. No codec change needed for the event itself. |

### What is already DONE (greenfield is only the wiring)

- ✅ `ExperimentObjectiveConfirmedEvent` exists with full `apply()` — `app/events/bypass_emitted.py:101-140`.
- ✅ `ExperimentStage` enum + `ConfirmKind.OBJECTIVE` — `app/core/enums.py:96-107`, `:30`.
- ✅ `ConfirmKindLiteral` mirror has `"objective"` — `app/events/form_payloads.py:59`.
- ✅ `ExperimentsRepo` + `ExperimentSnapshot` already carry `name`/`stage`; `_UPDATABLE_FIELDS` includes both — `app/repositories/experiments_repo.py:33,61,64`.
- ✅ Codec round-trip test already parametrizes the event — `tests/unit/test_events_codec.py:347-358`.

### What is MISSING (this phase's work)

- ❌ Event NOT exported from `app/events/__init__.py` (only `DecisionResolvedEvent`/`TaskProgressEvent`/`TLCRecognizedEvent`/`SessionResumedEvent` are — `__init__.py:20-25,55-90`). Add `ExperimentObjectiveConfirmedEvent` to the import block + `__all__`.
- ❌ `save_objective_draft` / `confirm_objective` on `SessionService` (greenfield — grep found none).
- ❌ Two L1 endpoints (greenfield — grep found none).
- ❌ Mind objective port + stub adapter + config toggle (none exist).
- ❌ `MindClientProtocol.experiment_object_stub` is a `...` placeholder, NOT the two real methods (`mind_client.py:89-91`).

---

## Findings

### 1 · L1 router pattern — `app/api/routers/sessions.py`

**Router declaration** (`:24`): `router = APIRouter(prefix="/sessions")`.

**Injection** (`:19`): `from app.api.dependencies import current_user_id, get_session_service`. Every handler takes:
```python
user_id: Annotated[str, Depends(current_user_id)],
service: Annotated[SessionService, Depends(get_session_service)],
```

**Template handler #1 — `submit_form_confirm` (the closest analog: validated body, calls a Facade method that emits an event, echoes `event_id`)** — `app/api/routers/sessions.py:99-156`:
```python
class FormConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision_id: str | None = None
    task_id: str | None = None
    confirm_kind: ConfirmKind
    form_values: dict

    @model_validator(mode="after")
    def _user_initiated_requires_task(self) -> "FormConfirmRequest":
        ...

class SubmitFormConfirmResponse(BaseModel):
    accepted: bool = True
    event_id: str

@router.post("/{session_id}/forms/confirm", status_code=202)
async def submit_form_confirm(
    session_id: str,
    body: FormConfirmRequest,
    user_id: Annotated[str, Depends(current_user_id)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SubmitFormConfirmResponse:
    event_id = await service.submit_form_confirm(
        session_id=session_id,
        user_id=user_id,
        decision_id=body.decision_id,
        confirm_kind=body.confirm_kind,
        form_values=body.form_values,
        task_id=body.task_id,
    )
    return SubmitFormConfirmResponse(event_id=event_id)
```

**Template handler #2 — `recognize_tlc_plate` (the closest analog for the objective DRAFT path: synchronous `status_code=200`, returns a TYPED result echoed in one roundtrip)** — `app/api/routers/sessions.py:200-235`:
```python
class TLCRecognizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    tlc_file_key: str
    mode: TLCPlateRecognitionMode = TLCPlateRecognitionMode.PMC

class TLCRecognizeResponse(BaseModel):
    tlc_result: TLCPlateRecognition

@router.post("/{session_id}/tlc/recognize", status_code=200)
async def recognize_tlc_plate(
    session_id: str,
    body: TLCRecognizeRequest,
    user_id: Annotated[str, Depends(current_user_id)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> TLCRecognizeResponse:
    tlc_result = await service.recognize_tlc_plate(
        session_id=session_id, user_id=user_id,
        task_id=body.task_id, tlc_file_key=body.tlc_file_key, mode=body.mode,
    )
    return TLCRecognizeResponse(tlc_result=tlc_result)
```

**Conventions to match:**
- Bodies are "3-step delegates" (module docstring `:7`): auth dep, validate body, call Facade. No business logic/DB/L3/broadcast in the route.
- `model_config = ConfigDict(extra="forbid")` on every request model → unknown field = FastAPI 422.
- Status codes: `200` for synchronous-result endpoints (draft/confirm both return a body per design §6 → use `200`), `202` for fire-and-forget ack endpoints.
- Request/response classes are L1 pydantic, declared inline in this file directly above their handler.

**Where new handlers go:** Place the two new request/response models + handlers anywhere among the POST handlers (e.g. after `recognize_tlc_plate` at `:235`, before the "Sidebar listing" section at `:238`). The snapshot DTO change (design §9 — add `name`/`stage` to `SnapshotExperimentItem` at `:293-300` + populate at `:472-478`) is a separate but co-located edit in THIS file.

---

### 2 · L2 service Facade — `app/session/service.py`

**Class shape** (`:66-93`): holds `_persistence`, `_registry`, `_orchestrator`, `_broadcaster`, `_fast_path`, `_minio_client`. Holds no state; every method is auth-check-then-delegate. Constructor is keyword-only (`*`).

**Three transaction/emit idioms in the file** (pick per event type):

1. **Plain event WITH `apply()` (USE THIS for `confirm_objective`)** — `submit_user_message` `:138-144`:
   ```python
   event = UserMessageSubmittedEvent(session_id=..., turn_id=..., text=...)
   session_seq = await self._orchestrator.persist_event(event)
   await self._broadcaster.emit(session_id, event, session_seq=session_seq)
   ```
   `persist_event` runs `post_processor.apply(event, tx)` + `session_events.append(event)` in one tx (`orchestrator.py:375-378`). `ExperimentObjectiveConfirmedEvent.apply` (`bypass_emitted.py:128`) will fire here, writing `objective`/`name` + advancing `stage`.

2. **Decision-CAS event** — `submit_form_confirm` `:268-282` (NOT applicable to objective; requires a pending decision).

3. **Bypass event with NO `apply()`** — TLC path (`fast_path_handlers.py:567-575`) writes side-effects manually then `tx.session_events.append`. NOT applicable to objective (objective event has `apply`).

**Full template method — `submit_form_confirm` end-to-end** (`app/session/service.py:161-297`, abridged to the load+emit+return skeleton):
```python
async def submit_form_confirm(self, *, session_id, user_id, decision_id, confirm_kind, form_values, task_id=None) -> str:
    await self._registry.assert_user_owns(session_id, user_id)        # auth FIRST (404/403)
    # ... validation (raises FormValidationError -> 422) ...
    event = await self._build_confirmed_event(...)                    # mint the event
    session_seq = await self._orchestrator.persist_event_with_decision_cas(...)
    if session_seq is None:
        raise DecisionAlreadyResolvedError.for_decision(...)
    try:
        await self._broadcaster.emit(session_id, event, session_seq=session_seq)
    except Exception:
        logger.exception("...broadcast_failed...")                   # post-commit broadcast guarded
    await submit_turn_with_bounded_retry(...)                        # (objective: SKIP — no follow-up turn)
    return event.event_id
```

**For `confirm_objective`, the skeleton is simpler** (no decision CAS, no follow-up turn):
```python
async def confirm_objective(self, *, session_id, user_id, ...) -> str:
    await self._registry.assert_user_owns(session_id, user_id)       # 404/403
    # validate (name present+unique, targets in range, baseline rules) -> FormValidationError(422)
    # Mind goal-confirm via the objective port -> target_weight_mg
    # resolve / read the active experiment_id (see "experiment access" below)
    event = ExperimentObjectiveConfirmedEvent(session_id=..., experiment_id=..., name=..., objective=...)
    session_seq = await self._orchestrator.persist_event(event)      # apply + append in one tx
    await self._broadcaster.emit(session_id, event, session_seq=session_seq)
    return event.event_id
```

**How the service reaches `ExperimentsRepo` / the active experiment:**
- The repos are bundled on the `tx` object: `async with self._persistence.transaction() as tx:` then `tx.experiments`, `tx.plans`, `tx.jobs`, `tx.trials`, `tx.decisions`, `tx.session_events` (seen at `service.py:349-364`, `:405-413`; `tx.experiments.list_by_session` / `tx.trials.get`).
- To find the active experiment in the service (the D40 fallback already does this): `experiments = await tx.experiments.list_by_session(session_id)` then `_pick_active_experiment_for_service(experiments)` (`service.py:406-407`, helper at `:669-673` returns `experiments[0]` — most recent by `started_at DESC`).
- `ExperimentsRepo` API used by the event's `apply`: `tx.experiments.get(experiment_id)` (`experiments_repo.py:87`) and `tx.experiments.update_fields(experiment_id, fields)` (`:144`, only `_UPDATABLE_FIELDS = {name, status, objective, stage, started_at}` allowed).

**For `save_objective_draft` (NO event, NO stage change — design §6):** open `self._persistence.transaction()` directly and call `tx.experiments.update_fields(experiment_id, {"objective": ..., "name": ...})`. There is NO existing draft-only persistence method to copy verbatim; the closest persistence idiom is the `list_user_sessions` read (`service.py:603-604`) — `async with self._persistence.transaction() as tx: ...`.

**Bypass-event emit call site reference (where `DecisionResolvedEvent` is emitted today):** `app/session/fast_path_handlers.py:210-237` (accept) and `:323-344` (reject) — but note this uses raw `tx.session_events.append` (decision events have no `apply`); the objective event must NOT copy this — use `orchestrator.persist_event` instead.

---

### 3 · Three-piece transaction for the objective event

**The exact API the service calls:** `app/session/orchestrator.py:359-378`
```python
async def persist_event(self, event: SessionEventBase) -> int:
    async with self._persistence.transaction() as tx:
        await self._post_processor.apply(event, tx)   # runs event.apply(tx) if defined
        seq = await tx.session_events.append(event)
    return seq
```
- `PostProcessor.apply` (`post_processor.py:31-35`) does `getattr(event, "apply", None)` then `await apply_fn(tx)`. `ExperimentObjectiveConfirmedEvent` HAS `apply` (`bypass_emitted.py:128`), so it runs inside the tx — writing `experiments.objective`/`name` and conditionally `stage="workflow_design"` (idempotent: only from `experiment_objective`).
- Then the service broadcasts: `await self._broadcaster.emit(session_id, event, session_seq=seq)` (mirrors `_emit_lifecycle` at `orchestrator.py:437-440` and `submit_user_message` at `service.py:143-144`).
- This satisfies append-before-emit (I1): `append` returns BIGSERIAL `seq` inside the committed tx; emit is post-commit.

**`apply()` body of record** (`bypass_emitted.py:128-140`): gets the experiment, writes `{objective, name}` always, adds `stage="workflow_design"` only if `experiment.stage == "experiment_objective"` (string literal — events are layer-neutral, cannot import `ExperimentStage`).

---

### 4 · Mind client + infrastructure injection — `app/infrastructure/mind_client.py`

**`MindClientProtocol`** (`:66-93`) — structural type for L3 injection (L4 Convention 2). Current surface: `recommend_param`, `analyze_result`, `recognize_tlc_plate`, **`experiment_object_stub`**, `close`.

**`experiment_object_stub` is a bare placeholder** (`:89-91`) — quoted verbatim:
```python
    async def experiment_object_stub(
        self,
    ) -> None: ...  # TODO(minio-protocol): pending dedicated task
```
This is NOT the design's `parse_experiment_materials`/`confirm_experiment_goal` port. It must be replaced/augmented.

**The concrete agent-service `MindClient`** (`:96-170`) wires CC/RE/TLC as hardcoded L4 stubs (no HTTP, no toggle). Pattern for a stubbed method — `recognize_tlc_plate` (`:160-167`):
```python
async def recognize_tlc_plate(self, request: TLCPlateRecognitionRequest) -> TLCPlateRecognitionResponse:
    boxed_pic_url = request.experiment_data.plates[0].rgb_url
    logger.warning("recognize_tlc_plate is stubbed: returning MED005 TLCPlateRecognitionResponse")
    return med005_tlc_recognition_response(boxed_pic_url=boxed_pic_url).model_copy(deep=True)
```
Stub responses come from `app/data/med005_fixture.py` factory functions returning contract-typed models (`:44-50` imports). The objective stub adapter should follow this — return a contract-typed `ExperimentMaterialParseResponse` / `ExperimentGoalConfirmResponse` with deterministic values (fixed `rendered_rxn_url`, echoed materials, computed `target_weight_mg`).

**The REAL Mind objective methods live in shared-types** — `.venv/lib/python3.12/site-packages/bic_shared_types/clients/model_service/http/mind_client.py:61-71`:
```python
async def parse_experiment_materials(self, request: ExperimentMaterialParseRequest) -> ExperimentMaterialParseResponse:
    """POST /api/protocol/experiment/material-parse — parse reaction SMILES into a material table."""
    payload = await self._post("/api/protocol/experiment/material-parse", request)
    return ExperimentMaterialParseResponse.model_validate(payload)

async def confirm_experiment_goal(self, request: ExperimentGoalConfirmRequest) -> ExperimentGoalConfirmResponse:
    """POST /api/protocol/experiment/goal-confirm — first-round experiment goal confirmation."""
    payload = await self._post("/api/protocol/experiment/goal-confirm", request)
    return ExperimentGoalConfirmResponse.model_validate(payload)
```
Raises `bic_shared_types...MindClientError` on `httpx.HTTPError` (`:102-103`). Note: this is the shared-types `MindClient`, a DIFFERENT class from `app.infrastructure.mind_client.MindClient`. The agent-service does NOT instantiate the shared-types client today.

**How an existing specialist calls Mind to parse/recommend (the pattern the objective port mirrors):** the agent-service `MindClient` is injected via `Runtime(mind=app.state.mind_client, ...)` (`main.py:88-90`) and into `FastPathHandlers(mind=app.state.mind_client, ...)` (`main.py:109-113`). The fast-path consumes it as `self._mind` (`fast_path_handlers.py:147`) and calls `await self._mind.recognize_tlc_plate(request)` (`:555`). So the objective port should be reachable the same way — either as a method on the injected `mind` object, or as a new injected adapter.

**Construction site** — `app/core/lifespan.py:126-127`:
```python
mind_client = MindClient(base_url=settings.mind_base_url)
app.state.mind_client = mind_client
```
Closed at shutdown (`lifespan.py:172`). `mind_base_url` is a computed field `http://{mcp_host}:{mcp_port}` (`config.py:125-128`).

**Toggle search result (grep `stub`/`fake mind`/`MIND_`/`USE_STUB`/`settings`):** NONE exists. The CC/RE/TLC stubs are unconditional inside the methods. There is no env flag to flip stub↔live. The objective port's toggle (design §2a) must be a NEW config field (see §5).

---

### 5 · Settings / config — `app/core/config.py`

`Settings(BaseSettings)` (`:17`), env-driven via `SettingsConfigDict(env_file=".env", case_sensitive=False)` (`:20`). Mind config block (`:83-88`):
```python
# L4 — ChemEngine / MindClient (MCP_ prefix is misleading — see clients.md)
mcp_host: str = ""
mcp_port: int = 8002
```
Derived URL — `mind_base_url` computed field (`:125-128`). The singleton `settings = Settings()` at `:136` is imported as `from app.core.config import settings` (e.g. `service.py:27`).

**Where a MIND objective stub toggle would live:** add a new bool field in the ChemEngine/MindClient block (e.g. `objective_mind_stub: bool = True` → env `OBJECTIVE_MIND_STUB`), defaulting to stub-mode per design §13 ("stub-mode default means no live Mind dependency to ship"). The binding (stub adapter vs real `bic_shared_types.MindClient`) would be chosen in `app/core/lifespan.py` near the existing `mind_client = MindClient(...)` wiring (`:126`) and stored on `app.state`, then injected into the `SessionService` constructor (or the objective port). **No precedent for a feature flag in this file** — this is a new pattern; match the field-block style and document it (Rule 10 — update the L4 clients.md spec).

---

### 6 · RxnSmiles validation — shared-types contract

**Import paths confirmed** (installed `v1.1.6a1`):
- Models: `from bic_shared_types.model_service.http.experiment import (ExperimentMaterialParseRequest, ExperimentMaterialParseResponse, ExperimentGoalConfirmRequest, ExperimentGoalConfirmResponse)` — file `.venv/.../bic_shared_types/model_service/http/experiment.py` (all four present, `:70,76,97,106`). Plus helper types `ExperimentParsedMaterial` (`:33`), `ExperimentMaterial` (`:55`), role enums (`:25,48`).
- `RxnSmiles`: `from bic_shared_types.common.types import RxnSmiles` — file `.venv/.../bic_shared_types/common/types.py:32`.
- Design §2 warns: do NOT import from `mcp_protocol.experiment` (deprecated re-export). The canonical module docstring confirms the move (`experiment.py:1-4`).

**`RxnSmiles` validator** — `bic_shared_types/common/types.py:8-20` (verbatim):
```python
def _validate_rxn_smiles(v: str) -> str:
    parts = v.split(">")
    if len(parts) != 3:
        msg = ("reaction SMILES must contain exactly two '>' characters "
               "(format: 'reactants>agents>products' or 'reactants>>products')")
        raise ValueError(msg)
    reactants, _, products = parts
    if not reactants or not products:
        msg = "reaction SMILES must have non-empty reactants and products"
        raise ValueError(msg)
    return v

RxnSmiles = Annotated[str, AfterValidator(_validate_rxn_smiles)]
```

**Exact exception type to catch + map to 422:** the validator raises a plain `ValueError`. Because it is an `AfterValidator` on a pydantic field, constructing `ExperimentMaterialParseRequest(rxn=bad)` / `ExperimentGoalConfirmRequest(rxn=bad)` raises **`pydantic.ValidationError`** (which wraps the `ValueError`). If you call `_validate_rxn_smiles` directly you get a bare `ValueError`. The request models also enforce: `feed_amount_mg: Field(gt=0)`, `target_purity_pct/target_yield_pct: Field(gt=0, le=100)` (`experiment.py:80-82`) — these also raise `ValidationError` on out-of-range. **Map strategy (design §12):** normalize + `try/except (pydantic.ValidationError, ValueError)` in the adapter BEFORE building the request, then raise `FormValidationError([...])` → 422 (handler at `exception_handlers.py:274-280`, see §8). Do NOT let `ValidationError`/`ValueError` 500.

---

### 7 · Existing objective draft/confirm — greenfield confirmation

`grep -rni "objective" app/api app/session`:
- `app/api/routers/sessions.py:298` — `objective: dict[str, Any]` (the existing snapshot DTO field).
- `app/api/routers/sessions.py:475` — `objective=e.objective` (snapshot population).

**No objective endpoint, no `save_objective_draft`/`confirm_objective` service method exists.** Confirmed greenfield. (The only objective references are the pre-existing read-only snapshot field and the new event in `app/events/bypass_emitted.py:101`.)

---

### 8 · Tests — exact files to mirror

**L1 endpoint test → mirror `tests/integration/test_routes_tlc.py`** (the canonical synchronous-POST route test):
- Fixture `app_client` (`:84-115`): boots a live uvicorn on `127.0.0.1:0` + real Postgres via `_l4_session_factory`, sets `app.state.runtime.invoke = _empty_invoke`, yields `(client, app)`, truncates `_L4_TABLES` (`:38-47`, includes `experiments`/`session_events`) on teardown.
- Seeding: `_seed_session(app)` → `app.state.registry.create_session(...)` (`:118-119`); `_seed_task(app, ...)` inserts experiment+plan+job+trial via `app.state.persistence.transaction()` (`:122-148`) — for objective tests you only need the experiment row (`tx.experiments.insert(experiment_id, session_id, kind=ObjectiveKind.PURIFICATION, objective={})`, `:134-139`).
- Mind stubbing: `_stub_mind_response(app)` (`:151-164`) replaces `app.state.mind_client.<method>` with an `AsyncMock` returning a contract-typed response, AND re-points the already-constructed handler's captured client (`app.state.session_service._fast_path._mind = app.state.mind_client`, `:163`). **For the objective port, the stub-patch target depends on where the port is captured — patch both the `app.state` object and any handler/service that captured it at construction.**
- Test cases to copy: happy 200 + DB/event assertions (`:179-251`), missing-field 422 (`:259-273`), unknown-field 422 (`:276-293`), missing `X-User-Id` 401 (`:301-317`, asserts `{"error_code": "auth_required"}`), wrong-user 403 (`:320-337`), unknown-session 404 (`:340-356`), Mind-failure mapping (`:364-384`). For objective add: bad-RxnSmiles → 422 `form_validation_failed`.

**L2 service test → mirror `tests/unit/test_session_service_tlc.py`** (pure-delegation unit test):
- `_build_service(...)` (`:21-49`) constructs `SessionService` with all six collaborators as `MagicMock`/`AsyncMock` (`registry`, `fast_path`, `persistence`, `orchestrator`, `broadcaster`, `minio_client`).
- Assert: auth runs first (`registry.assert_user_owns.assert_awaited_once_with(...)`), delegate called with exact kwargs, auth-failure short-circuits (`ForbiddenError` propagates, downstream `.assert_not_awaited()`), upstream-error passes through. For objective, also assert the event reaches `orchestrator.persist_event` and `broadcaster.emit` with the right `session_seq`.

**Codec / event registration tests (already partially done):**
- `tests/unit/test_events_codec.py:351` already lists `bypass_emitted.ExperimentObjectiveConfirmedEvent` in `_EVENT_FACTORIES` (`:347-358`) — round-trip is covered. **But** you still need to export the event from `app/events/__init__.py` (currently missing, `:20-25` / `:55-90`).
- `tests/unit/test_runtime_emitted_apply.py` — mirror for an `apply()`-projection test (objective event advancing `stage` + idempotence/no-backward). The event's `apply` is in `bypass_emitted.py` not `runtime_emitted.py`, so the apply test may go in a sibling file; check `tests/unit/test_persistence_repo_experiments.py` for the `update_fields(name/stage)` coverage.
- `test_import_hygiene.py` — guards `app/events/**` cannot import `app.core.enums`; the event already uses string literals, so no new risk.

**Snapshot DTO test → `tests/unit/test_persistence_repo_snapshot.py`** (per design §11 affected-files) for the `name`/`stage` snapshot fields.

---

## Caveats / Not Found

1. **Design §2 "Client (already exists)" is imprecise.** The agent-service `MindClient` does NOT expose `parse_experiment_materials`/`confirm_experiment_goal` — those live ONLY on the shared-types `MindClient` (a different class the app does not instantiate). The implementer must decide: (a) add the two real methods to the agent-service `MindClient`, or (b) introduce the `ObjectiveMaterialPort` indirection + stub adapter (design §2a). The `experiment_object_stub` placeholder (`mind_client.py:89`) signals the intent but is unimplemented. **Surface this to the main agent — it's a real ambiguity, not a guess.**
2. **No Mind toggle precedent.** Adding `objective_mind_stub` to `config.py` and a binding switch in `lifespan.py` is net-new pattern in this codebase (CC/RE/TLC are unconditionally stubbed inside the client). Per Rule 10, the L4 `clients.md` spec must be updated in the same change set.
3. **Snapshot DTO is part of THIS file's edits** (design §9/§11) — `SnapshotExperimentItem` (`sessions.py:293`) needs `name`/`stage`; the `SnapshotRepo` read must surface them. The repo `ExperimentSnapshot` already has the fields (`experiments_repo.py:61,64`), but I did NOT audit `app/repositories/snapshot_repo.py` to confirm it reads them onto the wire — verify before the snapshot DTO change.
4. **`save_objective_draft` has no exact template** — it is the only path with no event and no existing analog; it is a direct `tx.experiments.update_fields(...)` inside `self._persistence.transaction()`. The draft's optional Mind `parse_experiment_materials` call (design §6/§129) goes through the same objective port as confirm.
5. Did not audit §8 routing (`route_after_admit.py` goto union, the objective subagent node) — out of this phase's scope (phase 3 = port + Facade + endpoints). The goto union currently allows only `plan_subgraph`/dispatcher/query-agent (`route_after_admit.py:48-51`) and will need the objective node target in a later phase.
