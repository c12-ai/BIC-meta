# Research: Prior-Step Evidence Loading for FP Specialist

- **Query**: How does a specialist subgraph access the prior step's confirmed result evidence, and how should fp.py populate FPUpstreamContext from the confirmed CC result?
- **Scope**: internal
- **Date**: 2026-07-06

## Findings

### 1. How TLC Evidence Flows to CC (the Existing Mechanism)

CC accesses the preceding TLC outcome via a **deterministic code-level carry-forward** at fresh planned dispatch. There is no runtime API call — it reads `ctx` (the frozen `SessionContext`) directly.

**Key entry point**: `reception_node.py`

```
app/runtime/graphs/nodes/reception_node.py
  _carryforward_from_robot_tlc(state, cc_seq)  → lines 487–572
  _prior_is_robot_tlc(state, cc_seq)            → lines 469–484
  _prior_job_by_seq(jobs, cc_seq)               → lines 453–466
```

**Mechanism (lines 487–572 in reception_node.py)**:

1. `_prior_job_by_seq` finds the job with the highest `seq` strictly less than the CC job's `seq`. Sparse-seq safe (manual steps have no job row, so `cc_seq - 1` is unreliable).
2. `_prior_is_robot_tlc` checks that the prior job is a `tlc` executor AND has `type == "robot"` (from `plans.params.steps[seq]`).
3. `_carryforward_from_robot_tlc` reads the **latest trial** for that prior TLC job via `ctx.latest_trial(prior_job.job_id)` (context.py:237), then reads `trial.params` (a `dict`). The trial's `params.from_user.tlc_result` (a `TLCPlateRecognition` blob) and `params.from_user.product_rf` are copied byte-faithfully. The `params.recommended` section is read as a `TLCParam` to extract `solvents` and `solvent_ratio`.
4. The built `CCFromUserFields` seed (model-validated) is dumped into `bundle["params_draft"] = {"from_user": <seed>}` and passed to the specialist via `specialist_inputs`.

**What is carried** (line 505–572):
- `tlc_result` (TLCPlateRecognition blob from TLC trial `params.from_user.tlc_result`)
- `product_rf` (float from TLC trial `params.from_user.product_rf`)
- `solvents` + `solvent_ratio` (from TLC trial `params.recommended` parsed as TLCParam)
- `sample_quantity` is deliberately NOT carried — it is always chemist input.

**Plan-topology gate** (lines 469–484, 699–706):
- `prior_is_robot_tlc` is also set on `bundle["prior_is_robot_tlc"] = True` when plan topology shows a robot TLC predecessor, even before TLC results exist. The CC subgraph uses this flag to suppress the `recognize_tlc_plate` tool (cc.py:611–613).

### 2. Where Confirmed CC Result Evidence Lives After result_review Confirm

**Storage path**:

1. `analyze_cc_result` tool calls `_analyze_result(state, runtime, mind, "cc")` in `tools.py:735–808`.
2. `_cc_result_response_to_evidence(response)` (tools.py:735) maps the ChemEngine CC result into a typed `CcEvidence` model (form_payloads.py:733).
3. `_analyze_result` emits `TaskResultAnalyzedEvent(trial_id=..., evidence=CcEvidence(...))` (runtime_emitted.py:733).
4. `TaskResultAnalyzedEvent.apply()` (runtime_emitted.py:766–777) persists the evidence to **`trials.analysis`** as a camelCase JSON blob (`evidence.model_dump(by_alias=True)`). Table: `trials`, field: `analysis` (JSONB, nullable).

**`TrialSnapshot.analysis`** (trials_repo.py:149) is thus the persisted location. It is a raw `dict[str, Any] | None` — the deserialized camelCase dump of `CcEvidence`.

The **confirmed params** (`from_user`, `recommended`, `lab_logistics`) are persisted to **`trials.params`** by `FormConfirmedEvent.apply()` (runtime_emitted.py:594–613) when the chemist confirms the params form. `trials.params` is also `dict[str, Any] | None`.

After result_review confirm, `trials.analysis` holds the typed CC evidence body (camelCase), and `trials.params` holds the confirmed CC params (including `recommended.solvent_system`).

### 3. Cleanest Mechanism for fp.py to Fetch Confirmed CC Evidence on Phase Entry

The existing pattern is **`ctx.latest_trial(job_id)`** — no repository call needed within the subgraph. The frozen `SessionContext` loaded before each turn already contains all trials.

**Step-by-step for fp.py**:

1. Use `_prior_job_by_seq` (reception_node.py:453) to find the CC job (the job with the highest `seq` strictly less than the FP job's `seq`). This is the same sparse-seq-safe utility TLC→CC uses.
2. Call `ctx.latest_trial(cc_job.job_id)` (context.py:237) to get the `TrialSnapshot`.
3. Read `trial.analysis` (a `dict | None`) and validate it into a typed `CcEvidence` model: `CcEvidence.model_validate(trial.analysis)`. This gives access to `rack_cols`, `rack`, `fractions`, etc.
4. Read `trial.params` (a `dict | None`) to get the confirmed CC params. The `recommended` section parses as `CCParam` (from bic_shared_types.common.cc): `CCParam.model_validate(trial.params["recommended"])`. This gives `solvent_system`.

**Key functions/classes with file:line**:

| Symbol | File | Line |
|---|---|---|
| `_prior_job_by_seq` | `app/runtime/graphs/nodes/reception_node.py` | 453 |
| `ctx.latest_trial` | `app/core/context.py` | 237 |
| `TrialSnapshot.analysis` | `app/repositories/trials_repo.py` | 149 |
| `TrialSnapshot.params` | `app/repositories/trials_repo.py` | 147 |
| `CcEvidence` (authority) | `app/events/form_payloads.py` | 733 |
| `CCParam.solvent_system` | `.venv/…/bic_shared_types/common/cc.py` | 57 |
| `_carryforward_from_robot_tlc` | `app/runtime/graphs/nodes/reception_node.py` | 487 |

### 4. Where CCParam.solvent_system Lives After CC Params Confirm

`CCParam.solvent_system` is a `list[Solvent]` field on `CCParam` (.venv/.../bic_shared_types/common/cc.py:57).

After CC params confirm:
- `FormConfirmedEvent.apply()` (runtime_emitted.py:604) writes `form_values` (the full `{from_user, recommended, lab_logistics}` dict) into `trials.params`.
- `trials.params["recommended"]` is the camelCase-serialized `CCParam` dict. `CCParam.model_validate(trial.params["recommended"])` reconstructs it, and `.solvent_system` is a `list[Solvent]`.

The `CCParamsForm.recommended` field in form_payloads.py:167 is typed `CCParam | None`.

**Reading path in fp.py**:
```python
cc_trial = ctx.latest_trial(cc_job.job_id)
params = cc_trial.params or {}
recommended_raw = params.get("recommended")
cc_param = CCParam.model_validate(recommended_raw) if recommended_raw else None
solvent_system = cc_param.solvent_system if cc_param else None
```

### Files Found

| File Path | Description |
|---|---|
| `app/runtime/graphs/nodes/reception_node.py` | carry-forward logic + prior_is_robot_tlc; lines 444–706 |
| `app/core/context.py` | SessionContext + latest_trial()/find_trial(); lines 237–261 |
| `app/repositories/trials_repo.py` | TrialSnapshot schema (params, analysis fields); lines 130–178 |
| `app/events/form_payloads.py` | CcEvidence, FpEvidence, CCParam authority shapes; lines 693–901 |
| `app/events/runtime_emitted.py` | TaskResultAnalyzedEvent.apply() persists to trials.analysis; lines 733–777 |
| `app/runtime/graphs/specialists/tools.py` | _cc_result_response_to_evidence + _analyze_result; lines 735–808 |
| `app/runtime/graphs/nodes/specialist_dispatcher.py` | TLC→CC carryforward seed persist (TaskParamsSetEvent); lines 66–222 |
| `.venv/.../bic_shared_types/common/cc.py` | CCParam.solvent_system field; line 57 |

## Caveats / Not Found

- There is no existing `FPUpstreamContext` type or `fp.py` — both must be created under this task.
- The carry-forward mechanism for TLC→CC reads `ctx` directly in `reception_node` at fresh planned dispatch time. FP's upstream context (CC result) should follow the same pattern: read in `reception_node` on fresh planned FP dispatch, carry into `specialist_inputs["params_draft"]` or a new `fp_upstream` bundle key, and persist via `TaskParamsSetEvent` in `specialist_dispatcher` (mirroring the TLC→CC seed persist at line 202–222 of specialist_dispatcher.py).
- `_prior_job_by_seq` is defined in `reception_node.py` as a module-private function. fp.py calling it means either importing it from there (acceptable) or inlining the same sparse-seq logic.
- `trials.analysis` is stored as camelCase JSON (by_alias=True dump). `CcEvidence.model_validate(...)` with `populate_by_name=True` can parse it directly since CcEvidence uses `alias_generator=to_camel` with `populate_by_name=True` (form_payloads.py:736).
