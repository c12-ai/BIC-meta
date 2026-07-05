# Unify spec+param phases into single params phase

## Goal

Collapse the current 2-phase per-specialist flow (`collecting_spec → collecting_params`) into a single `collecting_params` phase. Each specialist (CC, RE, future TLC) exposes one unified Pydantic form where some fields are user-provided (or extracted by the agent from chat) and some are returned by `MindClient.recommend_param`. Product wants a single form surface per specialist, not two sequential sub-forms.

Hard cutover: no backward compat, dev DB reset, old `spec` surfaces deleted.

## What I already know

### Current 2-phase flow (from BE/FE/contracts discovery in this session)

- **BE state machine** (`app/runtime/types/specialist.py:45-51` — path corrected by review M5; `graphs/specialists/specialist.py` does not exist):
  `Literal["collecting_spec", "collecting_params", "submitting", "conducting", "done"]`
- **BE drafts** (`SpecialistState`): `spec_draft`, `params_draft`, `user_input_draft` (3 dicts).
- **BE DB** (`app/data/models.py:201-254`): `trials.spec` JSONB + `trials.param` JSONB (with nested `__user_input` key).
- **BE tools** split by phase:
  - Spec phase: `update_cc_spec`, `validate_cc_spec`, `recognize_tlc_plate`, `request_spec_confirmation`
  - Param phase: `recommend_cc_params`, `update_cc_params`, `update_cc_user_input`, `validate_cc_params`, `request_param_confirmation`
- **BE events** (`app/events/runtime_emitted.py`):
  - `TaskSpecSetEvent` + `TaskParamSetEvent` (two separate write-through events)
  - `FormConfirmedEvent.confirm_kind ∈ {"plan", "spec", "param", "result_review"}`
  - `_FORM_CONFIRM_PHASE_ADVANCE` has 2 rows for the spec→params and params→submitting transitions
- **BE OriginalAction union** (`app/events/form_payloads.py:267-441` — range corrected by review N5: confirm actions 267-310, discriminator 362, union 391-441): `CCSpecConfirmAction` + `CCParamConfirmAction` + `RESpecConfirmAction` + `REParamConfirmAction` (4 specialist actions).
- **Shared types** (`BIC-shared-types`):
  - `CCStandaloneParamRequest` = spec sent to Mind (`bic_shared_types/mcp_protocol/cc.py:54-62`)
  - `CCParamResponse` = Mind → Apex param recommendation
  - `CCUserParams`, `CCUserInput` (vendored in `form_payloads.py`)
- **FE store** (`workspaceStore.ts:49-121`): `spec`, `specConfirmed`, `param`, `paramConfirmed`.
- **FE UI** (`ParameterDesignPanel.tsx`): `MiniStepRail` (Spec → Params), two `SectionShell` blocks gated on spec confirmation.
- **FE types** (`specialist-forms.ts:1-9`): hand-ported from BE Pydantic, known drift risk, TODO comment asks for codegen.
- **FE→BE submit**: `POST /sessions/{id}/forms/confirm` with `confirm_kind="spec"` or `"param"`.

### Contract refetch findings (2026-06-11, supersedes earlier Mind-contract assumptions)

- **PR #56** (`agent/bic-pm/dra-5-mind-contracts`, the branch `pyproject.toml` pins; venv re-synced to branch head `7f090c8` on 2026-06-12 — see Addendum) **deleted `CCStandaloneParamRequest`** and replaced it with a unified `CCParamRequest` (`bic_shared_types/mcp_protocol/cc.py:94-108`):
  ```python
  class CCParamRequest(CCProtocolModel):
      sample_quantity: SampleQuantity        # {quantity: float, unit: MassUnit}
      tlc_param: TLCParam                    # {solvents, solvent_ratio}
      tlc_result: TLCResult                  # {product_rf | None, plates: [TLCPlateResult]}
      product_rf: float                      # user-selected product spot Rf, [0,1]
  ```
  Docstring: "Apex extracts the selected product spot from the user-confirmed TLC result (or user-entered values in standalone mode); the full TLCResult and the TLC image are not needed by Mind for column choice."
- `tlc_image_url` and `rf_values` (list) are **gone from the Mind request**. Only the single `product_rf` matters to Mind.
- **RE unchanged**: `REStandaloneParamRequest` (volume_ml, solvents, solvent_ratio) survives; new alias subclass `REParamRequest` added.
- **New material-parse API** (`mcp_protocol/experiment.py`): `ExperimentMaterialParseRequest/Response`, `ExperimentGoalConfirmRequest/Response` — experiment-goal confirmation, upstream of specialists (plan-phase concern, likely out of scope here).
- **Agent-service is broken at import right now**: `app/infrastructure/mind_client.py:13` imports the deleted `CCStandaloneParamRequest` (venv already has PR #56 tip). This task's PR2 is also the fix.
- **Diverged branch `feat/contract-repo-upgrade`** (no open PR): capability-first restructure (`mcp_protocol` → `model_service.http` + deprecation shim, `task_protocol`+`apex` → `experiment_task/{http,mq}`), shared caller-owned `MindClient`/`LabClient` HTTP wrappers, generated `ts/enums.ts`, JSON schemas/examples/OpenAPI. **Conflict (Rule 5)**: it still carries the old `CCStandaloneParamRequest` shape — it predates PR #56's contract minimization. PR #56 is newer and installed → treat PR #56 as authoritative for the Mind contract; repo-upgrade adoption is a separate concern.

### Drake's confirmed decisions

- **Field model**: **Three nested sub-models** per specialist form. Example for CC (updated 2026-06-11 for `CCParamRequest`):
  ```python
  class CCFromUserFields(BaseModel):           # user-provided or agent-extracted
      sample_quantity: SampleQuantity | None   # {quantity, unit} — replaces sample_amount_g
      solvents: list[Solvent] | None           # → CCParamRequest.tlc_param.solvents
      solvent_ratio: list[PositiveInt] | None  # → CCParamRequest.tlc_param.solvent_ratio
      tlc_file_key: str | None                 # durable MinIO key (06-08 task); presigned only at recognize boundary
      rf_values: list[float] | None            # recognize_tlc_plate output (context for pick)
      product_rf: float | None                 # user-selected product spot Rf → Mind

  # Mind output: reuse existing shared-types CCParam directly (column_type,
  # solvent_system, gradient_solvent, solvent_gradient) — no duplicate model.

  class CCLabLogistics(BaseModel):             # lab-only, never sent to Mind
      sample_cartridge_location: str | None    # user-set, agent-set, or auto-derived

  # RE mirror (fields from CreateRETaskRequest, currently in REUserInput):
  # class RELabLogistics(BaseModel):
  #     flasks: list[FlaskVolume] | None
  #     collect_config: list[int] | None

  class CCParamsForm(BaseModel):
      from_user: CCFromUserFields
      recommended: CCParam | None              # bic_shared_types.common.cc.CCParam
      lab_logistics: CCLabLogistics
  ```
  Each sub-model uses `Field(description=...)` for LLM hints. `recommend_*_params` reads `from_user`, validates it, builds **`CCParamRequest`** (PR #56 Mind contract: `sample_quantity` + `tlc_param=TLCParam(solvents, solvent_ratio)` + `tlc_result=TLCResult(product_rf=product_rf, plates=[])` + `product_rf`), and writes only into `recommended`. User/agent extraction writes into `from_user` and `lab_logistics`. RE builds `REStandaloneParamRequest` as before.
- **UI grouping**: FE renders only **two visible sub-sections**: "From you" and "Recommended". Fields from the BE `lab_logistics` sub-model render *inside* the "From you" sub-section — chemist sees no distinction. Every field in "From you" (which covers BE `from_user` AND BE `lab_logistics`) shows a **"Required"** badge. BE structural split is invisible to the chemist; it exists only for tool scoping and the Mind request boundary.
- **Mind contract** (updated 2026-06-11): CC uses **`CCParamRequest`** (PR #56; `CCStandaloneParamRequest` deleted upstream), RE uses `REStandaloneParamRequest` (unchanged). Apex builds the request from `from_user` at the call site — not a shared model with the form.
- **TLC prerequisite inside CC standalone** (Drake, 2026-06-11): each specialist's job is based on the previous one — sequence: **Exp Object → Plan → TLC → CC → Flask Collection → RE**. Until the TLC specialist ships, CC's `collecting_params` emulates the TLC prerequisite: chemist uploads a plate image, agent calls `recognize_tlc_plate` (`TLCPlateRecognitionRequest` → `rf_values`), chemist picks the product spot → `product_rf`. **Reverses Q6**: `recognize_tlc_plate` STAYS registered for CC.
- **Forms live in agent-service** (Drake, 2026-06-11): `CCParamsForm` / `REParamsForm` + sub-models defined in `app/events/form_payloads.py` (precedent: spec-era models were already vendored there). **Zero changes to BIC-shared-types in this task.** Pin stays on `agent/bic-pm/dra-5-mind-contracts` (PR #56). `feat/contract-repo-upgrade` adoption is a future task; its stale CC contract flagged to the contracts team.
- **Migration**: Hard cutover. Delete spec-phase code, drop `trials.spec`, reset dev DB.
- **TLC scope**: CC + RE only. TLC specialist deferred.
- **FE codegen**: Stay hand-ported. Drift TODO remains.
- **Mind gate**: Strict gate inside the tool. Validates `from_user` subset via Pydantic before calling Mind.

## Assumptions (temporary)

- Unified phase name is `collecting_params` (keep existing literal, drop `collecting_spec`).
- Single DB column `trials.params JSONB` replaces both `trials.spec` and `trials.param`.
- A single `FormConfirmedEvent(confirm_kind="params")` advances the phase to `rts`.
- **Phase rename (Drake, 2026-06-12)**: `submitting` → `rts` ("ready to submit" — the old name read like an in-flight action). Wire/DB value is lowercase `"rts"` to match existing literal casing (`done`, `conducting`); "Ready to submit" is display/prompt wording only. BE-only blast radius: FE `src/` never consumes phase literals (verified by grep 2026-06-12); portal test hits are comments. Prose "turn-submitting" comments in `app/main.py` / `core/lifespan.py` / `core/exceptions.py` are NOT the phase and stay.
- ~~`recognize_tlc_plate` removed from CC~~ — reversed again by Q8/Q9: stays registered for CC.
- ~~L4 schema doc path~~ — resolved by Q7.
- ~~TLC image upload without recognition~~ — superseded by Q8/Q9: upload + recognition both kept.
- ~~`TLCResult(product_rf=..., plates=[])` acceptability~~ — **Resolved (Drake, 2026-06-12): legit.** Standalone CC sends `TLCResult(product_rf, plates=[])`; structurally valid (no `min_length` on `plates`), accepted as the contract.
- ~~Mind endpoint for the unified `CCParamRequest`~~ — **Resolved (Drake, 2026-06-12): use a fake/placeholder path for now.** `MindClient.recommend_param` is stubbed with hard-coded return values anyway (see End-to-end check criteria), so the route string is a placeholder constant; swapping in the real endpoint when the Mind team confirms it is a one-line change. Review finding F3 closed.

## Open Questions

1. ~~**TLC scope**~~ — **Resolved**: CC + RE only. TLC specialist out of scope. `recognize_tlc_plate` placement still needs Q6 below.
2. ~~**FE codegen**~~ — **Resolved**: Stay hand-ported. FE rewrites `specialist-forms.ts` by hand for the new shape. `description=` is BE/LLM-only; FE owns its own label/tooltip copy. Drift TODO remains for a future task.
3. ~~**Mind recommend gating**~~ — **Resolved**: Strict gate inside the tool. `recommend_cc_params` / `recommend_re_params` validate the `from_user` sub-model via Pydantic; if missing, return a `ToolMessage` naming the missing fields. No phase machine involvement.
4. ~~**Field grouping in UI**~~ — **Resolved**: BE keeps three sub-models. FE renders only two visible sub-sections: "From you" (BE `from_user` + `lab_logistics`) and "Recommended" (BE `recommended`). "Required" badge on every "From you" field.
5. ~~**`CCStandaloneParamRequest` rename**~~ — **Resolved**: Kept as Mind contract name. Apex builds the request from `from_user` at the call site. Not coupled to form sub-models.
6. ~~**`recognize_tlc_plate` placement**~~ — **REVERSED by Q8/Q9 (2026-06-11)**: stays registered for CC. TLC is the prerequisite for CC; until the TLC specialist ships, CC standalone emulates it via upload + recognize inside `collecting_params`. When the TLC specialist lands, CC will consume the upstream confirmed TLC result instead (future task).
8. ~~**CC `from_user` redesign vs `CCParamRequest`**~~ — **Resolved** (Drake, 2026-06-11): TLC stays the prerequisite, emulated inside CC standalone. Chemist uploads plate image → agent calls `recognize_tlc_plate` → `rf_values` → chemist picks product spot → `product_rf`. Chemist also types `solvents` + `solvent_ratio` (→ `tlc_param`) and `sample_quantity`. Agent builds `TLCResult(product_rf=product_rf, plates=[])` (recognition returns only `rf_values` — no spot/bbox data to fill `plates`; contract docstring says Mind doesn't need it for column choice).
9. ~~**TLC image upload fate**~~ — **Resolved**: upload kept AND recognition kept. Reverses Q6: `recognize_tlc_plate` stays registered for CC; FE keeps `uploadAndAnalyzeTlc` + "Re-analyze plate".
10. ~~**Branch/pin strategy**~~ — **Resolved**: stay on PR #56 pin (`agent/bic-pm/dra-5-mind-contracts`). Forms vendored in `app/events/form_payloads.py`; BIC-shared-types untouched this task. Repo-upgrade conflict (stale CC contract on `feat/contract-repo-upgrade`) flagged to contracts team, adoption deferred.
11. ~~**L4 spec doc**~~ — **Resolved by inspection**. Spec docs to update:
   - `BIC-agent-service/.trellis/spec/backend/contracts.md` (cross-layer contracts)
   - `BIC-agent-service/.trellis/spec/backend/L3/state.md`, `specialist_tools.md`, `events.md`, `mind.md`
   - `BIC-agent-service/.trellis/spec/backend/L4/persistence.md` (trials schema), `domain-types.md`, `events.md`
   - `BIC-agent-portal/.trellis/spec/backend-contract.md` (FE↔BE contract mirror)

## Requirements

### Phase machine

- Single `collecting_params` phase per specialist (CC, RE). `collecting_spec` removed.
- `submitting` renamed to `rts` everywhere the phase literal appears: `runtime/types/specialist.py:48` (literal), `middleware/guardrail.py:43,46` (submit gate), `middleware/dynamic_prompts.py:138,275` (prompt tables), `graphs/specialists/tools.py:146` (phase→tool table), `graphs/nodes/reception_node.py:345` (in-flight check), plus unit tests (`test_phase_advance.py`, `test_specialists_*`, `test_reception_*`, `test_form_confirmed_apply.py`, …) and scenario scripts (`scripts/fixtures.py`, `run_demo_e2e.py`, `harness_ctx.py`, `run_scenarios.py`).
- `_FORM_CONFIRM_PHASE_ADVANCE` becomes:
  ```python
  {
      ("collecting_params", "params"): "rts",
      ("conducting", "result_review"): "done",
  }
  ```

### Data model — three nested sub-models per specialist

- `CCParamsForm = { from_user: CCFromUserFields, recommended: CCParam | None, lab_logistics: CCLabLogistics }`
- `CCFromUserFields = { sample_quantity: SampleQuantity | None, solvents, solvent_ratio, tlc_file_key, rf_values, product_rf }`. (`tlc_file_key` is the durable MinIO key per task 06-08; **`CCParamRequest` carries no image field**, so presigned-URL minting survives only inside `recognize_tlc_plate`.)
- `REParamsForm` mirrors the same three-sub-model shape (`from_user` = volume_ml, solvents, solvent_ratio — no TLC fields).
- **All form models defined in `app/events/form_payloads.py`** (agent-service), replacing the spec-era vendored models. BIC-shared-types untouched.
- Each sub-model uses `Field(description=...)` for LLM semantic hints.
- Mind request models consumed as-is from shared-types: **`CCParamRequest`** (PR #56) for CC, `REStandaloneParamRequest` for RE. Apex builds the request from `from_user` at the recommend call site.
- **Section semantics** (Drake's canonical statement, 2026-06-10):
  1. `from_user` — user filled, or agent extracted from user input. Also the basis for the Mind recommend request body.
  2. `recommended` — Mind output, requested via the existing shared-types req body built from section 1.
  3. `lab_logistics` — some fields auto-derived/inferred, some user-set; agent can also set from user input. Never sent to Mind.
- **Dispatch composition**: the lab job params = `recommended` + `lab_logistics` (mapped into `CreateCCTaskRequest` / `CreateRETaskRequest` by `submit_l4_execution`). `from_user` exists to drive recommendation, not dispatch.
- **Shared-types anchoring** (Drake, 2026-06-10): params sent to Mind AND to Robot (Mars) are based on `bic-shared-types`. Therefore:
  - `recommended` sub-model **reuses `CCParam` / `REParam` directly** (`bic_shared_types/common/`) instead of defining new `CCRecommendedFields` / `RERecommendedFields` — they would be field-identical duplicates. Draft state may hold a partial dict; strict `CCParam` validation happens at `validate_*_params` / confirm / dispatch.
  - Mind request: **`CCParamRequest`** (PR #56 unified contract) for CC; `REStandaloneParamRequest` unchanged for RE.
  - Robot request: `CreateCCTaskRequest` / `CreateRETaskRequest` unchanged; `submit_l4_execution` passes `recommended` (already a `CCParam`/`REParam`) straight into `param` — no mapping layer needed for that field.

### Tool surface — two write tools + recognize (CC) + recommend + validate + confirm per specialist

- `update_cc_from_user(fields)` — merges into `state.params_draft["from_user"]`. `CCFromUserFields` is **all-Optional by design** (incremental draft model); there is NO separate strict variant of it.
- `update_cc_lab_logistics(fields)` — merges into `state.params_draft["lab_logistics"]`.
- `recognize_tlc_plate(tlc_file_key)` — **stays registered for CC** (Q6 reversed): mints a presigned URL from the durable `tlc_file_key` (06-08 pattern), calls Mind plate recognition (`TLCPlateRecognitionRequest`), writes `tlc_file_key` + `rf_values` into `params_draft["from_user"]`. Chemist (or agent, from chat) then picks `product_rf`. When the TLC specialist ships, CC will instead consume the upstream confirmed TLC result (future task).
- `recommend_cc_params()` — **the gate is constructing `CCParamRequest`** (strict shared-types model, PR #56) from `params_draft["from_user"]`: `sample_quantity` → as-is, `tlc_param=TLCParam(solvents, solvent_ratio)`, `tlc_result=TLCResult(product_rf=product_rf, plates=[])`, `product_rf`. On `ValidationError` → soft `ToolMessage` listing the missing/invalid fields (the all-Optional draft model is never the gate — it would be vacuous). On success: calls `mind.recommend_param`, writes `response.param` (a `CCParam`) to `params_draft["recommended"]`. Delete `_RECOMMEND_FALLBACK` and the `MindNoticeEvent(phase="pre")` emission from this path.
- `validate_cc_params()` — succeeds iff: (a) `CCParamRequest` constructible from `from_user`, (b) `recommended` parses as full strict `CCParam`, (c) `lab_logistics` complete (i.e., `CreateCCTaskRequest` constructible). Intent: "valid" == "recommendable AND dispatchable".
- `request_params_confirmation()` — terminal; emits `FormRequestedEvent(confirm_kind="params", original_action=CCParamsConfirmAction(params: CCParamsForm))`.
- Mirror set for RE (gate model: `REStandaloneParamRequest`; no recognize tool).
- `app/infrastructure/mind_client.py` rewritten for the new contract (`CCParamRequest` import — **currently broken at import time**, this task fixes startup).

### Fast-path TLC recognize (duo-panel — found in review 2026-06-11)

There are **two** recognize paths; both stay (duo-panel principle) and both must write the **same shape**:
- **Agent tool** `recognize_tlc_plate` — writes into graph-state `params_draft["from_user"]` (covered above).
- **FE fast path** `POST /sessions/{id}/tlc/recognize` → `SessionService.recognize_tlc_plate` → `FastPathHandlers.handle_tlc_recognize` (`fast_path_handlers.py:509`). Currently: presigns from `tlc_file_key`, calls Mind, then `tx.trials.merge_spec_keys(task_id, {tlc_file_key, rf_values})` + appends `TLCRecognizedEvent` (bypass event) + broadcasts.

Required changes:
- `TrialsRepo.merge_spec_keys` → replaced by a `merge_params_keys`-style helper that merges **nested under the `from_user` sub-object** of `trials.params` (top-level JSONB `||` merge would put `tlc_file_key`/`rf_values` at the wrong level). Postgres `jsonb_set`/nested merge or read-modify-write inside the transaction.
- `TLCRecognizedEvent` (`bypass_emitted.py:111`) wire shape unchanged (`tlc_file_key`, `rf_values`); its docstring/persistence notes retargeted from `trials.spec` to `trials.params.from_user`.
- Rehydration consistency: a fast-path write followed by agent rehydrate must land in `params_draft["from_user"]` (whole-blob rehydrate already covers this once the merge nests correctly).
- FE: `tlc_recognized` case in `event-dispatcher.ts` / `workspaceStore` / `sse-client.ts` retargets `spec.rf_values` → `params.from_user.rf_values` (+ `tlc_file_key`).

### Draft state

- `SpecialistState.params_draft: dict` — single dict shaped as `{from_user: {...}, lab_logistics: {...}, recommended: {...}}`.
- `spec_draft`, `user_input_draft` **removed** from `SpecialistState`.

### Database

- New column `trials.params JSONB`.
- Drop columns `trials.spec`, `trials.param`.
- Single Alembic migration; dev DB reset documented.

### Events

- `TaskSpecSetEvent` **removed**.
- `TaskParamSetEvent` **renamed** to `TaskParamsSetEvent(trial_id, params: dict)` — a rename, not a new event: all emit sites updated in the same PR; wire kind becomes `"task_params_set"`; writes `trials.params`. **Emission point (corrected by review 2026-06-12, finding C3)**: today's set-events are emitted from the **update tools** (`tools.py:275,549,1170,1302`), NOT at form-request time, and FE live form sync depends on that timing (`workspaceStore.ts:78`, `CcSpecForm.tsx:140-142` re-sync chat-driven edits before any `form_requested`). New rule: **every tool that mutates `params_draft` emits `TaskParamsSetEvent` with the full params dict** — `update_*_from_user`, `update_*_lab_logistics`, `recommend_*_params` (after writing `recommended`), and agent-tool `recognize_tlc_plate` (after writing `tlc_file_key`/`rf_values`). The FE fast path keeps its separate `TLCRecognizedEvent`.
- `FormConfirmedEvent.confirm_kind` literal: `"plan" | "params" | "result_review"` (drops `"spec"`, `"param"`).
- **`ConfirmKind` enum plumbing (review 2026-06-12, finding C1 — was missing from scope)**: `app/core/enums.py:26-44` `ConfirmKind(StrEnum)` becomes `{PLAN, PARAMS, RESULT_REVIEW}`. `coerce()` alias table updated: `"param"` → `PARAMS` (absorb LLM drift), `"spec"` rejected (`ValueError`), `"params"` is now canonical (today `coerce("params")` silently remaps to `"param"` — left as-is, the phase-advance lookup would silently miss and the phase would never advance). All enum consumers updated in PR1:
  - `app/api/routers/sessions.py:113` (request body field) and `sessions.py:119-120` (decision-less confirm validator: `{SPEC, PARAM}` → `{PARAMS}` — keeps the duo-panel user-initiated confirm path alive)
  - `app/runtime/graphs/nodes/specialist_dispatcher.py:65-71` (`confirm_followup_kinds`)
  - `app/runtime/graphs/nodes/route_entry.py:66`
  - `app/runtime/graphs/nodes/reception_node.py:275-304` (`_validate_form_values` branches on SPEC/PARAM, writes `spec_draft`/`params_draft` → single PARAMS branch writing `params_draft`)
  - `app/runtime/graphs/specialists/cc.py:169-200`, `re.py:155-186` (`_emit_form_node` picks SPEC vs PARAM by phase → always PARAMS; builds `CCParamsConfirmAction` from `params_draft` — structural rewrite, not just prompts)
  - `app/data/turn_schemas.py:41`, `app/session/orchestrator.py:385-428` (CAS on expected kind), `app/session/service.py:159-312`
- `_FORM_CONFIRM_PHASE_ADVANCE`: row `("collecting_spec", "spec")` **deleted** (not just absent); table has exactly the 2 rows shown above.
- `OriginalAction` union: `CCSpecConfirmAction` + `CCParamConfirmAction` collapse to `CCParamsConfirmAction(specialist_kind="cc", params: CCParamsForm)`. Same for RE.
- **FE→BE confirm payload shape (explicit contract)**: `form_values = { from_user: {...}, recommended: {...}, lab_logistics: {...} }` — replaces today's `{ params, user_input }` split assembled in `CcParamForm.toValues()`.
- **Confirm-time validation is NEW** (review F5 follow-on): today `form_values` ships verbatim (`service.py:271` — "Non-plan events ship form_values verbatim"). For `confirm_kind="params"`, the confirm path must validate `form_values` against strict `CCParamsForm` / `REParamsForm` (full `CCParam`/`REParam` in `recommended`, incl. cross-field validators) **before** appending `FormConfirmedEvent`, returning **422 with field-level details** on failure. Without this, invalid hand-edits would surface only at `submit_l4_execution` — too late and ungated.

### Override behavior (no tracking)

- User can edit any field including `recommended.*`. Latest typed value persists in FE local state.
- **Corrected by review (2026-06-10)**: edits are carried to BE **only on form confirm** (`submitFormConfirm` with `form_values`). `submitUserMessage` sends only `{text}` — form edits do NOT flow with chat messages. If the chemist edits then chats without confirming, the agent works on the BE-side draft, not the FE edits. Accepted MVP behavior; no message-submit form-sync mechanism.
- If a subsequent Mind recommend overlaps, recommendation **overwrites** user value. No UI override badge. No state tracking.
- **FE confirm gate** (amended by review F5, Drake 2026-06-11): **presence gate only** — the confirm CTA stays disabled until all `recommended` fields are present, `lab_logistics` is complete, and `from_user` is recommendable. Cross-field rules (`gradient_solvent ∈ solvent_system`, ratio/solvents length match, gradient step rules) are **NOT replicated in FE**: BE is the single authority — a 422 from `POST /forms/confirm` is surfaced as a visible form-level error and the form stays editable. No FE rule duplication, no pre-validation endpoint.

### Mind failure → hard failure (supersedes D16 soft-fallback for recommend path)

- Two distinct failure cases — do not conflate:
  - **`from_user` incomplete** (Pydantic validation of the draft fails): **soft** — tool returns a `ToolMessage` naming the missing fields. No event, no raise.
  - **Mind call fails** (`MindCallError`, or Mind's response fails response-model validation): tool **raises**. The existing `ToolErrorHandlingMiddleware` catches it and emits `TurnFailedEvent` (per existing D47 design).
- No `MindNoticeEvent` soft notice on the raise path. No automatic LLM fallback. No 4th write tool for `recommended`.
- **Conversation state**: phase stays at `collecting_params`. State is NOT rolled back.
- **Recovery path (re-corrected by review 2026-06-12, finding M1 — the old premise is stale)**: the duo-panel decision-less confirm already exists — `decision_id` may be omitted, FE submits with `task_id` only and BE mints the decision (`ParameterDesignPanel.tsx:113-115`, `sessions.py:102`, `service.py:190-210`). So after a failed Mind turn the chemist CAN directly hand-edit any field — including empty `recommended` ones — and confirm, without waiting for the agent to re-emit a form request. Alternatively the chemist retries via chat and the agent re-runs `recommend_*_params`. Requirement: the decision-less confirm validator must accept `confirm_kind="params"` (see `ConfirmKind` plumbing above), or this path dies in the rename.
- L3 `mind.md` updated: the D16 soft-fallback contract is superseded for the `recommend_*_params` path. Other Mind call sites (e.g., analyze) keep their existing failure handling unless touched separately.

### Dispatch mapping (`submit_l4_execution`)

- `tools.py` `submit_l4_execution` currently builds `CreateCCTaskRequest(param=..., sample_cartridge_location=...)` from `state.params_draft` + `state.user_input_draft` (`tools.py:837-912`). Rewrite to read `params_draft["recommended"]` (→ `param`) and `params_draft["lab_logistics"]` (→ `sample_cartridge_location` / RE equivalents). Task-protocol request types (`CreateCCTaskRequest`, `CreateRETaskRequest`) are **unchanged** — Lab service contract untouched.
- Precondition error messages referencing `user_input_draft` updated.

### Rehydration (`reception_node`)

- `_INITIAL_PHASE` (`reception_node.py:72`) becomes `"collecting_params"`.
- Rehydrate reads `trials.params` → `state.params_draft` as the **whole blob, no sub-field extraction** (replaces the `trial.spec` → `spec_draft` and `trial.param` → `params_draft` paths at `reception_node.py:297,363`).

### Specialist prompts

- The prompt ladder (tool call order, phase semantics) is rewritten for the new tool surface across: `runtime/constants.py`, `middleware/dynamic_prompts.py`, `middleware/after_tool.py`, `graphs/specialists/cc.py`, `graphs/specialists/re.py`, `graphs/plan_tools.py`. New ladder: extract/ask → `update_*_from_user` + `update_*_lab_logistics` → `recommend_*_params` → `validate_*_params` → `request_params_confirmation`.

### SpecialistState flags

- `spec_validated` removed (`runtime/types/specialist.py:100`). `params_validated`, `params_confirmed` survive; guardrail logic for `submit_l4_execution` unchanged, but its phase check string updates `"submitting"` → `"rts"` (`guardrail.py:43,46`).

### Spec docs (Rule 10)

Updated in the same change set:
- `BIC-agent-service/.trellis/spec/backend/contracts.md`
- `BIC-agent-service/.trellis/spec/backend/L3/{state,specialist_tools,events,mind}.md`
- `BIC-agent-service/.trellis/spec/backend/L4/{persistence,domain-types,events}.md`
- `BIC-agent-service/.trellis/spec/backend/mind-agent-contract-call-chain.md` (added 2026-06-12, Drake — stale vs v1.1.2a1, see Addendum)
- `BIC-agent-portal/.trellis/spec/backend-contract.md`

### Hard cutover

- No dual-write. No legacy code paths. Delete `collecting_spec`, `spec_draft`, `user_input_draft`, `TaskSpecSetEvent`, `CCSpecConfirmAction`, `RESpecConfirmAction`, `CCUserParams`, `REUserParams`, `CCUserInput`, `REUserInput`, `CCBeginSpec`, `REBeginSpec` references end-to-end.

## End-to-end check criteria (Drake, 2026-06-12)

The task is "done" only when this full conversational flow works against the live stack. **Mind side: `MindClient` recommend methods may be stubs returning hard-coded values for now** — the flow is what's under test, not Mind's intelligence.

1. **Happy path parity**: the user can go from initial input all the way to task dispatch, like before the refactor.
2. **Extraction + recommend**: from the initial user input, the agent extracts `from_user` fields and uses those values to call `MindClient` (stubbed, hard-coded return) to get `recommended` params.
3. **Missing-field gate**: if the user didn't specify some required field, the agent must NOT fire the recommend call — it asks the user for the missing inputs instead.
4. **Chat-driven re-recommend**: after the 1st round, the user can say "change field X to Y" — the agent updates the field AND automatically fires another recommend round.
5. **Manual override + partial recommend**: the user can hand-write some fields himself and ask the agent to recommend the others.

Terminal condition for every path above: task dispatched → watched until the lab task finishes → task analyze auto-fired → user confirms the analyze result → flow advances to the next job (**CC → RE**).

## Acceptance Criteria

### Phase + state
- [x] `SpecialistPhase` literal: `Literal["collecting_params","rts","conducting","done"]`. No `collecting_spec` references in `BIC-agent-service` **excluding `alembic/versions/` history** (old migrations legitimately reference the old default; history is not rewritten) **and excluding `tests/fixtures/streaming/design_exp_trace.jsonl` IF it is kept** — preferred: regenerate or delete that fixture (no test loads it; only its README references it — review finding M4).
- [x] No `"submitting"` phase-literal references remain in `BIC-agent-service` (guardrail, dynamic_prompts, tools phase table, reception_node in-flight check, tests, scripts all say `"rts"`). Prose "turn-submitting" comments (`main.py`, `core/lifespan.py`, `core/exceptions.py`) exempt.
- [x] `SpecialistState` has no `spec_draft` or `user_input_draft` fields; only `params_draft`.

### Data model
- [x] `CCParamsForm`, `CCFromUserFields`, `CCLabLogistics` defined in `app/events/form_payloads.py`; `recommended` field typed as existing `CCParam` (no duplicate `CCRecommendedFields` model).
- [x] `CCFromUserFields` = `{ sample_quantity: SampleQuantity | None, solvents, solvent_ratio, tlc_file_key, rf_values, product_rf }` — matches `CCParamRequest` constructibility (`tlc_file_key`/`rf_values` are recognition context, not sent to Mind recommend).
- [x] `REParamsForm`, `REFromUserFields`, `RELabLogistics` defined in `app/events/form_payloads.py`; `recommended` field typed as existing `REParam`.
- [x] All sub-model fields carry `Field(description=...)`.
- [x] **BIC-shared-types untouched** — *amended (Drake, 06-12): the `agent/bic-pm/dra-5-mind-contracts` branch was deleted upstream; pin moved to tag `rev = "v1.1.2a1"` (same contract surface).*
- [x] Removed from `form_payloads.py`: `CCBeginSpec`, `REBeginSpec`, `CCUserParams`, `REUserParams`, `CCUserInput`, `REUserInput` (+ their `*Partial` variants).

### Tool surface
- [x] CC tools (in `tools.py`): `update_cc_from_user`, `update_cc_lab_logistics`, `recognize_tlc_plate`, `recommend_cc_params`, `validate_cc_params`, `request_params_confirmation`. No `update_cc_spec`, `update_cc_params`, `update_cc_user_input`, `validate_cc_spec`, `request_spec_confirmation`.
- [x] RE tool set mirrors CC (minus `recognize_tlc_plate`).
- [x] `recognize_tlc_plate` stays registered for CC; writes `rf_values` into `params_draft["from_user"]`.
- [x] `recommend_cc_params` gate = constructing `CCParamRequest` (with `tlc_param=TLCParam(solvents, solvent_ratio)`, `tlc_result=TLCResult(product_rf, plates=[])`); `recommend_re_params` gate = `REStandaloneParamRequest`. On missing fields returns `ToolMessage` naming them; on Mind call/response error **raises** (handled by middleware → `TurnFailedEvent`).
- [x] `app/infrastructure/mind_client.py` imports/signatures updated for `CCParamRequest`; `BIC-agent-service` starts cleanly (currently broken at import).
- [x] Fast path: `POST /sessions/{id}/tlc/recognize` works against the unified shape — `handle_tlc_recognize` merges `{tlc_file_key, rf_values}` **nested under `trials.params.from_user`** (new `merge_params_keys`-style repo helper; `merge_spec_keys` removed); `TLCRecognizedEvent` wire shape unchanged.
- [x] Agent tool and fast path write the identical `from_user` field shape (one shared mapping, no drift).
- [x] `submit_l4_execution` builds `CreateCCTaskRequest` / `CreateRETaskRequest` from `params_draft["recommended"]` + `params_draft["lab_logistics"]`; no `user_input_draft` reference.
- [x] `reception_node`: `_INITIAL_PHASE == "collecting_params"`; rehydrates `params_draft` from `trials.params`; no `spec_draft` rehydration.
- [x] Specialist prompts (constants, dynamic_prompts, after_tool, cc.py, re.py, plan_tools) rewritten for the new tool ladder; no references to spec tools or `collecting_spec`.
- [x] `SpecialistState.spec_validated` removed; `params_validated` / `params_confirmed` survive; `submit_l4_execution` guardrail logic unchanged with phase check retargeted to `"rts"`.

### DB
- [x] Alembic migration drops `trials.spec`, `trials.param`; adds `trials.params JSONB`.
- [x] `trials.phase` `server_default` changed from `"collecting_spec"` to `"collecting_params"`.
- [x] Dev DB reset documented in PR description. Note: `pending_decisions.kind` rows store `"spec"`/`"param"` strings (`decisions_repo.py:57`) — safe only because of the dev reset; mention in migration notes (review N7).

### Events
- [x] `TaskSpecSetEvent` removed.
- [x] `TaskParamsSetEvent` defined and wired (writes `trials.params`).
- [x] `FormConfirmedEvent.confirm_kind` literal: `"plan" | "params" | "result_review"`.
- [x] `_FORM_CONFIRM_PHASE_ADVANCE` has 2 rows: `("collecting_params","params") → "rts"` and `("conducting","result_review") → "done"`.
- [x] `OriginalAction` union has `CCParamsConfirmAction` and `REParamsConfirmAction`; old `*SpecConfirmAction` + `*ParamConfirmAction` removed.

### FE
- [x] `ParameterDesignPanel.tsx` renders one `SectionShell` per specialist with **two** visible sub-headings: "From you" / "Recommended". BE `lab_logistics` fields render inside the "From you" sub-section.
- [x] Every field in the "From you" sub-section (covering BE `from_user` + `lab_logistics`) displays a "Required" badge. Fields in "Recommended" do not.
- [x] `MiniStepRail` removed (or repurposed; no more Spec→Params step labels).
- [x] `workspaceStore`: state has `params`, `paramsConfirmed`; no `spec` / `param` / `specConfirmed` / `paramConfirmed`. `onFormCleared()` handles `confirmKind === 'params'`; footer branches no longer key off `spec`/`param`.
- [x] `ConfirmKind` TS type (`src/types/events.ts`) = `'plan' | 'params' | 'result_review'`; `pendingForm.formKind` and all literal checks updated.
- [x] `FORM_STEP` routing table (`workspaceStore.ts:155-163`) has a `'params'` entry; auto-switch routes to the parameter step.
- [x] `event-dispatcher.ts`: `case 'task_params_set'` added with a unified store mutator; `task_spec_set` / `task_param_set` cases removed. `sse-client.ts:57-58` `KINDS` allowlist registers `task_params_set`, drops the old kinds (compile-enforced by `_MissingKind` — review N6).
- [x] Confirm CTA disabled until assembled `form_values` pass the presence gate (all `recommended` fields present, `lab_logistics` complete, `from_user` recommendable).
- [x] A 422 from `POST /sessions/{id}/forms/confirm` (cross-field validator failure on hand-edited values) renders as a visible form-level error; the form stays editable; no FE replication of BE cross-field rules.
- [x] Submit payload assembled as `{ from_user, recommended, lab_logistics }` (replaces `CcParamForm.toValues()`'s `{ params, user_input }`).
- [x] `uploadAndAnalyzeTlc()` kept (upload → `from_user.tlc_file_key` → recognize → `rf_values`); retargeted to the unified form shape.
- [x] FE renders `rf_values` as a pick-one control (chips/select) writing `from_user.product_rf`; manual `product_rf` entry possible as fallback.
- [x] `sample_quantity` rendered as quantity + unit inputs (replaces `sample_amount_g`).
- [x] `specialist-forms.ts` rewritten by hand for the new shape (no codegen this task).
- [x] `RecommendationBasis` "Re-analyze plate" button stays visible (Q6 reversed).
- [x] `ResultConfirmationPane` renders summaries from the unified `{from_user, recommended, lab_logistics}` shape; stale header comment updated.

### Cross-layer
- [x] `POST /sessions/{id}/forms/confirm` accepts `confirm_kind="params"`.
- [x] Confirm path validates `form_values` as strict `CCParamsForm` / `REParamsForm` before `FormConfirmedEvent` append; invalid payload → 422 with field-level details (validation is new — today `form_values` ships verbatim).
- [x] FE→BE→FE round-trip for CC + RE works against live backend.

### Specs (Rule 10)
- [x] `BIC-agent-service/.trellis/spec/backend/contracts.md` updated.
- [x] `BIC-agent-service/.trellis/spec/backend/L3/{state,specialist_tools,events,mind}.md` updated.
- [x] `BIC-agent-service/.trellis/spec/backend/L4/{persistence,domain-types,events}.md` updated.
- [x] `BIC-agent-service/.trellis/spec/backend/mind-agent-contract-call-chain.md` updated to match v1.1.2a1 — no references to removed classes (`CCStandaloneParamRequest`, `CompoundLibraryMatch*`, `TLCParamRequest/Response`, `TLCMixcaseMolecule`, `TLCMixcaseRequest.molecules`).
- [x] `BIC-agent-portal/.trellis/spec/backend-contract.md` updated.

### Data model (additions from review)
- [x] `RELabLogistics = { flasks: list[FlaskVolume] | None, collect_config: list[int] | None }` (fields required by `CreateRETaskRequest`; currently in `REUserInput`).
- [x] `CCFromUserFields` / `REFromUserFields` are all-Optional draft models; NO strict variants — required-ness is enforced by constructing `CCParamRequest` / `REStandaloneParamRequest` (recommend gate) and `CreateCCTaskRequest` / `CreateRETaskRequest` (dispatch gate). *(fixed from deleted `CCStandaloneParamRequest`, review N2)*

### Scripts
- [x] All BE scenario scripts under `BIC-agent-service/scripts/` grepped for `collecting_spec` / `spec_draft` / `confirm_kind="spec"` / `confirm_kind="param"` / `"submitting"`; each affected script updated or disabled in the same change set (known hits: `fixtures.py`, `run_demo_e2e.py`, `harness_ctx.py`, `run_scenarios.py`).

### Tests
- [x] `cc-re-chained-flow.spec.ts` rewritten for single-phase flow; passes.
- [x] `manual-live-demo.spec.ts` rewritten (incl. the post-accept caption fix to "Confirmed result review."). *Note: runs under `playwright.live.config.ts`, not part of the default-suite sweep — not re-executed in the final 14-spec run.*
- [x] `task-progress-stream.spec.ts` updated where it traverses the form flow; passes.
- [x] `tlc-upload-chain.spec.ts` updated for the unified form (upload + recognize survive; assertions retarget `from_user.tlc_file_key` / `rf_values` / `product_rf`).
- [x] New BE scenario script under `BIC-agent-service/scripts/` exercising Mind failure → `TurnFailedEvent`.

## Definition of Done

- Tests added/updated for the unified flow (CC + RE end-to-end).
- Lint / typecheck / CI green across `BIC-agent-service`, `BIC-agent-portal`, `BIC-shared-types`.
- L3 + L4 specs updated in the same change set.
- Dev DB reset script documented if migration requires it.
- No `spec_draft` / `collecting_spec` / `TaskSpecSetEvent` references remain in code.

## Out of Scope (explicit)

- TLC specialist implementation **and** TLC-aware design slot. Re-revisit when TLC code lands (CC will then consume the upstream confirmed TLC result instead of in-form upload+recognize).
- `feat/contract-repo-upgrade` adoption (re-pin, `model_service.http` import paths, shared `MindClient`/`LabClient`, `ts/enums.ts`) — future task; branch conflict flagged to contracts team.
- Material-parse / goal-confirm API (`mcp_protocol/experiment.py`) — plan-phase concern, separate task.
- Pydantic→TS codegen pipeline. FE stays hand-ported; drift TODO survives this task.
- Override-state tracking on `recommended` fields (no UI badge for user-edited recommendations).
- 4th write tool for `recommended` sub-model (Mind failure path raises instead).
- D16 soft-fallback contract for Mind failures during recommend (superseded; other Mind paths unchanged).
- Result-review phase changes.
- Plan phase changes.
- Any BFF reintroduction.
- Robot / Lab service contract changes.

## Technical Notes

### Files to touch (high-level)

- **BIC-agent-service**:
  - `app/runtime/types/specialist.py` (phase literal — path corrected, review M5)
  - `app/runtime/types/dispatch.py` (`SpecialistDispatchInputs` drops `spec_draft`/`user_input_draft` — review M3)
  - `app/runtime/graphs/specialists/tools.py` (tool consolidation + `submit_l4_execution` mapping rewrite)
  - `app/runtime/graphs/specialists/cc.py`, `re.py` (prompts **and** `_emit_form_node` structural rewrite: ConfirmKind selection by phase → always PARAMS, builds `CCParamsConfirmAction` from `params_draft` — review M6)
  - `app/core/enums.py` + `app/api/routers/sessions.py` + `app/runtime/graphs/nodes/{specialist_dispatcher,route_entry}.py` + `app/data/turn_schemas.py` + `app/session/{orchestrator,service}.py` (`ConfirmKind` plumbing — review C1)
  - `app/runtime/graphs/nodes/plan_subgraph.py:489` (seed first specialist phase)
  - `app/runtime/graphs/nodes/reception_node.py:72,297,363` (initial phase + rehydration from `trials.params`)
  - `app/runtime/graphs/plan_tools.py`, `app/runtime/constants.py`, `app/runtime/middleware/dynamic_prompts.py`, `app/runtime/middleware/after_tool.py` (prompt ladder + phase references)
  - `app/runtime/middleware/guardrail.py` (`submitting` → `rts` phase check)
  - `app/runtime/types/specialist.py:100` (drop `spec_validated`)
  - `app/events/runtime_emitted.py:50-54, 327-543, 566-612` (events + phase-advance table)
  - `app/events/form_payloads.py:54-371` (OriginalAction union)
  - `app/data/models.py:201-254` (Trial schema + `phase` server_default)
  - New Alembic migration
- **BIC-shared-types**: **no changes** (pin stays on `agent/bic-pm/dra-5-mind-contracts`, PR #56). Form models live in `app/events/form_payloads.py`. Also touch `app/infrastructure/mind_client.py` (broken import → `CCParamRequest`).
- **BIC-agent-portal**:
  - `src/components/workspace/ParameterDesignPanel.tsx` (collapse two SectionShells; footer branches; `pendingForm.formKind` checks)
  - `MiniStepRail` — inline component at `ParameterDesignPanel.tsx:215-230`, not a separate file (review N3); `ParameterDesignLayout.tsx:24` takes `rail` as optional prop, so removal is dropping the prop
  - `src/components/workspace/forms/CcSpecForm.tsx`, `CcParamForm.tsx`, `ReSpecForm.tsx`, `ReParamForm.tsx` (merge per specialist; new submit payload assembly)
  - `src/components/workspace/ResultConfirmationPane.tsx` (unified-shape summaries)
  - `src/stores/workspaceStore.ts` (`spec`/`param` → `params`; `onFormCleared`; `FORM_STEP` table; auto-switch)
  - `src/lib/event-dispatcher.ts` (case `task_params_set`; drop old cases)
  - `src/lib/tlc-client.ts` + `src/components/workspace/TlcUploadControl.tsx` (retarget upload+recognize to unified form; `rf_values` → `product_rf` pick control)
  - `src/types/events.ts` (`ConfirmKind` literal)
  - `src/types/specialist-forms.ts` (hand rewrite)
- **Specs (Rule 10)**:
  - `.trellis/spec/backend/L3/specialist_tools.md`
  - `.trellis/spec/backend/L3/state.md`
  - `.trellis/spec/backend/L3/events.md`
  - `.trellis/spec/backend/L3/mind.md`
  - L4 trials schema doc (path TBD)
- **Tests**: `cc-re-chained-flow.spec.ts`, `manual-live-demo.spec.ts`, `task-progress-stream.spec.ts`, `tlc-upload-chain.spec.ts`.

### Drift risk

FE `specialist-forms.ts` is hand-ported from BE Pydantic with an explicit TODO for codegen. This refactor renames or replaces most of those types; we chose to stay hand-ported (Q2) — drift TODO survives.

## Decision (ADR-lite)

**Context**: Product wants a single form surface per specialist instead of the current 2-phase (spec → params) sequence. The current shape has three drafts on BE (`spec_draft`, `params_draft`, `user_input_draft`), two DB columns (`trials.spec`, `trials.param`), and two FE sections gated by spec confirmation. A flat Pydantic model with `description=` hints was the initial direction, but Drake chose **nested sub-models** to make group structure explicit on both BE and FE.

**Decision** (amended 2026-06-11 after contract refetch; phase rename added 2026-06-12):
1. Unified phase: `collecting_params` only. `collecting_spec` deleted. `submitting` renamed to `rts` ("ready to submit") — the old name read like an in-flight action while the phase actually means "params confirmed, waiting for the submit tool". Lowercase `"rts"` on the wire/DB to match existing literal casing.
2. Form model: **three nested sub-models** per specialist (`FromUserFields`, `recommended: CCParam/REParam`, `LabLogistics`), **vendored in `app/events/form_payloads.py`** — BIC-shared-types untouched this task.
3. Tool surface: **two write tools** (from_user, lab_logistics) + `recognize_tlc_plate` (CC only) + `recommend` + `validate` + `request_params_confirmation`. No write tool for `recommended`.
4. Mind contract: CC uses **`CCParamRequest`** (PR #56 unified contract; `CCStandaloneParamRequest` deleted upstream), RE uses `REStandaloneParamRequest`. Apex constructs the request from `from_user` at call site; standalone `tlc_result` built as `TLCResult(product_rf, plates=[])`.
5. Mind failure → **hard fail**: tool raises, middleware emits `TurnFailedEvent` (existing event). Phase stays. FE editable form lets chemist edit `recommended` manually and confirm.
6. DB: one `trials.params JSONB` column. Hard cutover. Drop `trials.spec`, `trials.param`.
7. FE: hand-ported types (no codegen). Single `SectionShell` with **two** visible sub-headings ("From you" / "Recommended"). BE `lab_logistics` fields render inside "From you" — chemist sees no distinction. "Required" badge on every "From you" field.
8. `recognize_tlc_plate` **stays registered for CC** (Q6 reversed): TLC is CC's prerequisite; standalone CC emulates it via in-form upload + recognize until the TLC specialist ships. Specialist sequence vision: Exp Object → Plan → TLC → CC → Flask Collection → RE.
9. Pin stays on `agent/bic-pm/dra-5-mind-contracts`; `feat/contract-repo-upgrade` adoption deferred (its CC contract is stale — conflict flagged, Rule 5).

**Consequences**:
- Smaller user-facing flow (one form, not two). One confirmation click instead of two.
- LLM workflow changes: must call multiple write tools in one turn (DRY broken in favor of source-clarity).
- D16 soft-fallback for recommend path is **deprecated**. Chemist sees a hard error if Mind is down; recovery is manual edit + confirm.
- Hand-port drift on FE types persists until a future codegen task.
- TLC specialist work is unblocked but not started; `recognize_tlc_plate` will move at that time.

## Implementation Plan (small PRs)

**PR1 — BE core (forms, mind client, state, tools, events, prompts)** *(BIC-agent-service)*

> Merged from former PR1+PR2 (review finding F2): startup is broken by BOTH `mind_client.py` and `tools.py` importing the deleted `CCStandaloneParamRequest` — the form-model PR and the tools rewrite cannot ship separately; only their union restores a startable service.

- Define `CCParamsForm` + sub-models, `REParamsForm` + sub-models in `app/events/form_payloads.py`.
- Delete `CCBeginSpec`, `REBeginSpec`, `CCUserParams`, `REUserParams`, `CCUserInput`, `REUserInput` + `*Partial` variants.
- Rewrite `app/infrastructure/mind_client.py` for `CCParamRequest` (type unions, `recommend_param` signature).
- `SpecialistPhase` literal collapse + `submitting` → `rts` rename (incl. guardrail, prompt tables, phase→tool table, reception in-flight check).
- `SpecialistState` cleanup (`spec_draft`, `user_input_draft`, `spec_validated` removed).
- Replace tool functions with the new tool set (CC: 6 incl. `recognize_tlc_plate`; RE: 5); recommend gates = `CCParamRequest` / `REStandaloneParamRequest`.
- `submit_l4_execution` mapping rewrite (`recommended` → `param`, `lab_logistics` → `sample_cartridge_location` / RE equivalents).
- `reception_node`: initial phase + rehydration from `trials.params`.
- Specialist prompt ladder rewrite (constants, dynamic_prompts, after_tool, cc.py, re.py, plan_tools).
- Event types: `TaskParamsSetEvent`, updated `FormConfirmedEvent`, updated `OriginalAction` union, updated `_FORM_CONFIRM_PHASE_ADVANCE`.
- `recommend_*` tool raises on Mind call/response error; soft `ToolMessage` on incomplete `from_user`.
- `ConfirmKind` enum + all consumers (enums.py, sessions.py router, specialist_dispatcher, route_entry, reception_node `_validate_form_values`, cc.py/re.py `_emit_form_node`, turn_schemas, orchestrator, service) — see Events section.
- `app/runtime/types/dispatch.py:51-53`: `SpecialistDispatchInputs` drops `spec_draft` / `user_input_draft` (review finding M3).
- **BE unit/integration tests updated in this PR** (review finding M2): `test_specialists_tools.py`, `test_specialists_cc.py` / `_re.py`, `test_form_confirmed_apply.py`, `test_phase_advance.py`, `test_reception_node.py`, `test_reception_pick_in_flight_task.py`, `test_specialists_rehydrate.py`, `test_runtime_emitted_apply.py`, `test_session_service_submit_form_confirm_persist.py`, `test_l3_reception_node_split_e2e.py`, `test_l4_e2e_turn.py` (imports deleted `CCStandaloneParamRequest`).
- Update L3 specs (`state.md`, `specialist_tools.md`, `events.md`, `mind.md`) in same change set.

**PR2 — BE persistence (DB migration + fast path)** *(BIC-agent-service)*
- Alembic migration: drop `trials.spec`, `trials.param`; add `trials.params`.
- Update `Trial` ORM model.
- Wire write-through in `FormConfirmedEvent.apply`, `TaskParamsSetEvent.apply`.
- `TrialsRepo.merge_spec_keys` → nested `merge_params_keys` (merges under `params.from_user`); retarget `handle_tlc_recognize` + `TLCRecognizedEvent` persistence notes (review finding F1).
- Update L4 specs (`persistence.md`, `domain-types.md`, `events.md`).
- Update `BIC-agent-service/contracts.md`.

**PR3 — FE unified UI** *(BIC-agent-portal)*
- Rewrite `specialist-forms.ts` to mirror the three sub-models.
- Collapse `CcSpecForm` + `CcParamForm` → `CcParamsForm`; same for RE.
- `ParameterDesignPanel.tsx`: single `SectionShell`, **two** visible sub-headings ("From you" / "Recommended" — fixed from "three", review N1), "Required" badges on all "From you" fields.
- Delete `MiniStepRail` (or repurpose).
- `workspaceStore`: `params` + `paramsConfirmed`.
- `event-dispatcher.ts`: handle `task_params_set`, drop `task_spec_set`; `tlc_recognized` retargets `params.from_user.rf_values` + `tlc_file_key`.
- `rf_values` pick-one control → `product_rf`; `sample_quantity` quantity+unit inputs; "Re-analyze plate" stays.
- Update `BIC-agent-portal/.trellis/spec/backend-contract.md`.

**PR4 — E2E tests + scenarios** *(both repos)*
- Rewrite `cc-re-chained-flow.spec.ts`, `manual-live-demo.spec.ts`, `task-progress-stream.spec.ts`.
- Update `tlc-upload-chain.spec.ts` for the unified form.
- New BE scenario under `BIC-agent-service/scripts/` exercising Mind-failure → `TurnFailedEvent`.

Note: PR1+PR2 are BE-contract-first; PR3 follows the BE merge (FE mirrors new payload shapes by hand). PR4 ships last.

**PR1/PR2 boundary (corrected by review 2026-06-12, finding C2)**: PR1 as originally split cannot land green — it reads `trial.params` (rehydration) and wires `TaskParamsSetEvent.apply`, but the ORM column + migration were in PR2 (`AttributeError` at runtime). Resolution: **PR1 and PR2 are a stacked pair, merged together as one unit** (same rationale as the earlier F2 merge of forms+tools). They stay two PRs only for review ergonomics; CI/deploy gate is their union. PR1 and PR2 each carry the BE unit/integration test updates for the files they break (finding M2) — DoD "CI green" applies per merged unit, not per stacked PR.

**FE sequencing dependency (2026-06-11) — RESOLVED**: the TLC file_key work (`fix/tlc-thumbnail-survives-refresh`) was fast-forward merged to portal `main` (`79c99bc`) and pushed on 2026-06-11 (tsc clean). PR3 branches off `main`. Note: the push bypassed the repo's "changes must go through a PR" protection rule (Drake has bypass rights); future merges may want the PR flow.

---

## Addendum (2026-06-12) — merged from closed task `BIC-agent-service/.trellis/tasks/06-10-mind-contract-mock-server`

Drake closed the 06-10 task (MindClient new methods + mock server; mock server dropped earlier) and asked for its findings to land here.

### Dependency state change (supersedes "tip `86427c0` installed")

- `uv lock --upgrade-package bic-shared-types && uv sync` run on 2026-06-12: lock + venv now at
  branch head **`7f090c8`** (still v1.1.2a1). The earlier `1.0.5`/`1.1.0a1` installs are gone.
- Diff `86427c0 → 7f090c8` is one commit ("apply review validators from #57"), **no model shape
  changes** — PR1 design assumptions survive. Contents:
  - `REStandaloneParamRequest`: new validator `len(solvent_ratio) == len(solvents)` — the
    `recommend_re_params` gate now enforces this for free; FE 422 path covers hand-edits.
  - `TLCMixcaseRequest`: new validator `0 <= target_window.lo < target_window.hi <= 1`.
  - `TLCMixcaseTrial.molecules`: now `min_length=1`.
  - `CCParamRequest` docstring reworded: now "Apex **sends the confirmed upstream TLC parameter
    and result**, plus the Rf of the user-selected product spot". This weakens the old docstring
    justification for `TLCResult(product_rf, plates=[])` in standalone mode (Assumptions §,
    `plates=[]` item). Structurally `plates` still has no `min_length`, so it validates — but the
    intent reads more "real TLCResult expected". **Resolved (Drake, 2026-06-12): legit, ship it.**

### Verified breakage inventory (against `7f090c8`, 2026-06-12)

- `app/infrastructure/mind_client.py:13` — `ImportError: cannot import name 'CCStandaloneParamRequest'` (verified by import).
- References to the deleted class: `app/runtime/graphs/specialists/tools.py:59,457`,
  `scripts/demo_l4.py:43,359`, `tests/integration/test_l4_e2e_turn.py:42,250`,
  `tests/unit/test_specialists_tools.py:349` (docstring), comments in `app/events/form_payloads.py:49-65`.
- `recognize_tlc_plate` call sites already pass `reference_type` (PMC/SMC) at
  `tools.py:364` and `fast_path_handlers.py:553` — no breakage there.

### Full v1.1.2a1 Apex→Mind surface (reference for future tasks)

| Request | Response | MindClient today |
|---|---|---|
| `ExperimentMaterialParseRequest` | `ExperimentMaterialParseResponse` | missing — future task (plan-phase) |
| `ExperimentGoalConfirmRequest` (+`basis_material_hint`) | `ExperimentGoalConfirmResponse` | missing — future task (plan-phase) |
| `TLCMixcaseRequest` | `TLCMixcaseResponse` | missing — future task (TLC specialist) |
| `TLCResultRequest` (carries `rxn`) | `TLCResultResponse` | missing — future task (TLC specialist) |
| `TLCPlateRecognitionRequest` | `TLCPlateRecognitionResponse` | exists (`/api/tlc/tlc_plate_rawjudge`) |
| `CCParamRequest` (unified) | `CCParamResponse` | **this task (PR1)** — replaces deleted standalone |
| `CCResultRequest` | `CCResultResponse` | exists (`/api/cc/result-protocol`) |
| `REStandaloneParamRequest` / `REParamRequest` | `REParamResponse` | exists (2 routes) |
| `REResultRequest/Response` | — | intentionally none: docstring says not backed by a Mind HTTP endpoint (Mars-side realtime) |

Removed in v1.1.x (must not appear in code or specs): `CCStandaloneParamRequest`,
`CompoundLibraryMatch*` (superseded by `ExperimentMaterialParse*`), `TLCParamRequest/Response`
(TLC param recommendation goes through Mixcase only), `TLCMixcaseMolecule` /
`TLCMixcaseRequest.molecules`.

### Spec doc addition (Drake, 2026-06-11/12)

- `BIC-agent-service/.trellis/spec/backend/mind-agent-contract-call-chain.md` (untracked, new)
  is stale vs v1.1.2a1: still documents `CompoundLibraryMatch`, `TLCMixcaseRequest.molecules`,
  pre-`basis_material_hint` GoalConfirm, and pre-unification CC contracts. Drake: update it
  whenever API contracts change → added to the Rule-10 spec list and acceptance criteria above.
  Scope note: update at least the sections this task touches (CC param unification, RE, removed
  classes); the goal-confirm/material-parse sections should be corrected to v1.1.2a1 shapes even
  though their client methods remain future-task work.

### Still-open question carried over

- **Endpoint paths**: no agreed path is recorded anywhere (repo, shared-types, specs) for the new
  routes (`ExperimentMaterialParse`, `ExperimentGoalConfirm`, `TLCMixcase`, `TLCResult`).
  **For this task** the unified `CCParamRequest` endpoint is resolved: fake/placeholder path +
  stubbed `MindClient` (Drake, 2026-06-12 — F3 closed). The Drake/Mind consensus doc is still
  needed before the future endpoint task that wires real routes.
