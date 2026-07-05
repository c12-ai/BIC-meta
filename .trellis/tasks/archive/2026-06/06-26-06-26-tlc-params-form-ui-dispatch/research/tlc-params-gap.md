# Research: TLC params payload from BE + the CC↔TLC param-shape diff

- **Query**: What does the BE emit at the TLC params-confirm gate, and how does the TLC param shape differ from CC (Q4 + Q5)?
- **Scope**: mixed (BE-primary for the payload, FE for the diff)
- **Date**: 2026-06-26

## Q4 — What the BE emits at the TLC params-confirm gate

### The form payload shape (the new FE form must render + send this)

The BE emits `FormRequestedEvent(confirm_kind="params", original_action=TLCParamsConfirmAction)` from `_emit_form_node`:

`BIC-agent-service/app/runtime/graphs/specialists/tlc.py:410-441`
```python
async def _emit_form_node(state, runtime) -> dict:
    ...
    params = TLCParamsForm.model_validate(state.params_draft or {})
    original_action: OriginalAction = TLCParamsConfirmAction(
        task_id=state.task_id,
        params=params,
    )
    emit_event(runtime, FormRequestedEvent,
        decision_id=str(_uuid_mod.uuid4()),
        confirm_kind=ConfirmKind.PARAMS.value,
        original_action=original_action,
    )
```

`TLCParamsConfirmAction` (`app/events/form_payloads.py:662-670`):
```python
class TLCParamsConfirmAction(BaseModel):
    confirm_kind: Literal["params"] = "params"
    task_id: str
    specialist_kind: Literal["tlc"] = "tlc"
    params: TLCParamsForm
```

`TLCParamsForm` — the three-sub-model shape, IDENTICAL anatomy to `CCParamsForm` (`form_payloads.py:327-343`):
```python
class TLCParamsForm(BaseModel):
    from_user: TLCFromUserFields = Field(default_factory=TLCFromUserFields, ...)
    recommended: TLCParam | None = Field(default=None, ...)
    lab_logistics: TLCLabLogistics = Field(default_factory=TLCLabLogistics, ...)
```

### `from_user` fields (chemist inputs — what the form must collect)

`TLCFromUserFields` (`form_payloads.py:255-291`):
```python
class TLCFromUserFields(BaseModel):
    rxn: RxnSmiles | None = ...                       # reaction SMILES; required for recommend
    target_window: tuple[float, float] | None = ...   # acceptable product Rf range (lo, hi); required
    tlc_file_key: str | None = ...                    # recognition carry (set by Phase-4 retry loop, not chemist)
    tlc_result: TLCPlateRecognition | None = ...      # recognition carry (Phase-4 write-through)
    product_rf: float | None = ge=0, le=1             # recognized product Rf (Phase-4 write-through)
```

**Crucial:** only `rxn` and `target_window` are CHEMIST inputs for the params form. The trio `tlc_file_key` / `tlc_result` / `product_rf` are written back by the Phase-4 deterministic Rf-retry loop AFTER dispatch (`tlc.py:744-750` write-through in `_evaluate_tlc_result_node`), NOT collected on the params form. There is **no `recognize_tlc_plate` upload during TLC `collecting_params`** (`tlc.py:42-46`, `tools.py:1231-1233`) — the robot runs the plate; recognition is the Mind call on the terminal turn. So the editable TLC params form is much smaller than CC's.

### `recommended` field (Mind output)

`recommended: TLCParam | None`. `TLCParam` (shared type, `bic_shared_types/common/tlc.py:27-38`):
```python
class TLCParam(BaseModel):
    solvents: list[Solvent]          # Solvent enum: PE / EA / DCM / MeOH
    solvent_ratio: list[PositiveInt] # positive ints; length MUST equal len(solvents)
```
Written by `recommend_tlc_params` (`tools.py:1320-1362`, calls `mind.recommend_tlc_mixcase`, stores `response.recommendation.param`). The chemist may also hand-edit it in the form (same as CC).

### `lab_logistics` field — EMPTY for TLC

`TLCLabLogistics` (`form_payloads.py:294-304`) is an empty-but-present model (extra="forbid", no fields). The docstring: `CreateTLCTaskRequest carries only param: TLCParam (plus task_id); there are no cartridge / flask logistics for a TLC plate task.` Present only for shape parity. **This is why TLC must skip `MaterialPreparationPanel`.**

### The recommend gate + completeness rules

`build_tlc_param_request` (`form_payloads.py:455-470`): constructs `TLCMixcaseRequest` from `rxn` + `target_window` (trials=[] first round). `target_window` rule `0 <= lo < hi <= 1` is enforced by `TLCMixcaseRequest`'s own validator (`bic_shared_types/model_service/http/tlc.py:153-159`).

`tlc_params_form_problems` (`form_payloads.py:543-561`): valid == `TLCMixcaseRequest` constructible from `from_user` AND `recommended` present. Lab-logistics is empty → nothing dispatch-gated (`form_payloads.py:550-552`).

### The dispatch request shape (Q4 — `CreateTLCTaskRequest`)

`_submit_l4` TLC branch (`specialists/tools.py:543-559`):
```python
    elif state.specialist_kind == "tlc":
        tlc_form = TLCParamsForm.model_validate(draft)
        tlc_problems = tlc_params_form_problems(tlc_form)
        if tlc_problems or tlc_form.recommended is None:
            raise RuntimeError(...)
        task_request = CreateTLCTaskRequest(
            task_id=task_uuid,
            param=tlc_form.recommended,    # ONLY recommended is dispatched
        )
```

`CreateTLCTaskRequest` (`bic_shared_types/experiment_task/http/tlc.py`):
```python
class CreateTLCTaskRequest(CreateTaskRequestBase):
    task_type: Literal[TaskType.THIN_LAYER_CHROMATOGRAPHY] = ...
    param: TLCParam            # = {solvents, solvent_ratio}
```
So at dispatch, only `recommended` (a `TLCParam`) + the base `task_id` are sent. `from_user` drives recommendation only; `lab_logistics` is empty.

## Q5 — CC vs TLC param-shape diff (the crux of "follow the same pattern")

| Section | CC (`CCParamsForm`) | TLC (`TLCParamsForm`) | Reuse vs differ |
|---|---|---|---|
| `from_user` chemist inputs | `sample_quantity` ({quantity,unit}), `solvents` (Solvent[]), `solvent_ratio` (PosInt[]), `product_rf` | `rxn` (RxnSmiles), `target_window` ((lo,hi) float tuple) | **DIFFER** — completely different chemist fields. TLC needs a SMILES text input + a 2-number Rf-window input. None of CC's from_user fields apply. |
| `from_user` recognition carry | `tlc_file_key`, `tlc_result` (chemist uploads via `TlcUploadControl` during CC collecting_params) | `tlc_file_key`, `tlc_result`, `product_rf` (written by Phase-4 retry loop AFTER dispatch; NOT a form input) | **DIFFER** — CC's TLC upload/SpotIdTable/RecommendationBasis sub-UI does NOT belong on the TLC params form. TLC has no upload during collecting_params. |
| `recommended` | `CCParam`: `column_type`, `solvent_system` (Solvent[]), `gradient_solvent`, `solvent_gradient` (steps) | `TLCParam`: `solvents` (Solvent[]), `solvent_ratio` (PosInt[]) | **DIFFER (much simpler)** — TLC recommended is just a solvent system + ratio. The Solvent-chip parse/label helpers (`SOLVENT_OPTIONS`, `parseSolvents`, `ratioLabel`, `parseRatio` in `CcParamsForm.tsx:185-220`) are directly REUSABLE. The column/gradient UI is not. |
| `lab_logistics` | `CCLabLogistics`: `sample_cartridge_location` (rendered as a `<Select>` inside the form; dispatch routes through `MaterialPreparationPanel`) | `TLCLabLogistics`: EMPTY | **DIFFER** — TLC sends `lab_logistics: {}`. No cartridge select, no MaterialPreparationPanel. |

### Reuse map (concrete)

- **Reuse the scaffold:** `useParamsFormHandle` (`forms/useParamsFormHandle.ts`) — the exact same `{ref, id, initial, toDraft, toValues, isValid}` contract. New TLC form passes `id: 'workspace.params.tlc'`.
- **Reuse the footer + submit path:** `PhaseFooter` + `useSubmitForm.confirm('params', values)` are stage-agnostic. The only blocker is the cc/re gating (see contract-spec.md / Implementation shape).
- **Reuse solvent helpers:** `SOLVENT_OPTIONS`, `SOLVENT_LABEL`, `parseSolvents`, `shortSolventLabel`, `longSolventLabel`, `ratioLabel`, `parseRatio` from `CcParamsForm.tsx` — TLC's `solvents`/`solvent_ratio` (both in `from_user`? NO — TLC from_user has no solvents; the solvent system is only in `recommended`). These helpers apply to the `recommended.solvents` / `recommended.solvent_ratio` editing.
- **Reuse form-chrome:** `FormField`, `PanelTitle`, `STAGE_INPUT_CLASS`, `UnitInput` from `forms/form-chrome`.

### What TLC genuinely needs that CC doesn't have a widget for

1. **Reaction SMILES input** (`from_user.rxn`) — a plain mono text input. No existing CC widget; trivial.
2. **Target Rf window input** (`from_user.target_window` = `(lo, hi)`) — two number inputs, each in [0,1], with `lo < hi`. The BE owns the strict `0 <= lo < hi <= 1` rule (it's in `TLCMixcaseRequest`), so the FE presence-gate just needs both present; cross-field is BE-validated (a 422 surfaces in the alert).

The TLC `recommended` editing (solvents + ratio) maps onto CC's "Eluent System / Eluent Ratio" pattern (`CcParamsForm.tsx:339-355`) but bound to `recommended.solvents`/`recommended.solvent_ratio` instead of `from_user`.

## Coercer note

There is **no `coerceTlcParamsForm`** in `lib/params-coerce.ts` (only `coerceCcParamsForm` and `coerceReParamsForm`, `:89-151`). A TLC coercer must be added, mirroring the existing two, to turn `unknown` (wire) → typed TLC form. There is also **no `TLCParamsForm` TS type** in `src/types/specialist-forms.ts` (it has CC/RE shapes only — confirmed by grep: only `CCParamsForm`/`REParamsForm` interfaces exist). A `TLCParamsForm` TS interface mirroring `form_payloads.py:TLCParamsForm` must be added.
