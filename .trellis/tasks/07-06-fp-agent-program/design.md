# FP Agent — Technical Design (program level)

Scope: the cross-child contracts and data flow. Child-local design detail lives in each child's design.md, authored at child activation.

## 1. Architecture: FP is a fourth specialist, template = RE

- New `app/runtime/graphs/specialists/fp.py` (`build_fp_subgraph(llm, lab)`) — no MindClient dependency: FP has no ChemEngine endpoint; the recommendation is a deterministic derivation from CC evidence and the result evidence is synthesized locally.
- Phase machine mirrors CC/RE: `collecting_params` → `rts` → `conducting` → `done`.
- **Deterministic-first emission** (python-expert review): the pre-fill is complete by construction (every upstream well has a status), so the params form is emitted through the deterministic backstop path on phase entry — same pattern as the objective stage's promote-complete-draft-to-emit_form and the duo-panel principle (decision minting must not depend on an LLM tool call). The LLM + tools (`update_fp_containers`) serve chat-driven edits only; keep the LLM, keep it simple.
- Routing wiring (all fail-loud today, so every hop must be added):
  - `runtime/types/specialist.py`: `SpecialistKind` += `"fp"` (:78); `executor_to_kind("fp") -> "fp"`; `classify_step_dispatch` robot fp → `"specialist"` (:137, stub disposition retired).
  - `specialist_dispatcher.py:59`: `_KIND_TO_SUBGRAPH["fp"] = "fp_subgraph"`; delete the stub branch (:113–124).
  - `factory.py`: register `fp_subgraph_node`; `specialists/__init__.py`: export `build_fp_subgraph`.
- Dispatch: `specialists/tools.py` `_submit_l4` gains an fp branch building `CreateFPTaskRequest` (shared-types v1.2.0; lab client union already accepts it — zero lab-client change).
- Terminal handling: standard `TaskStatusMsgPayload` pipe (task-type agnostic, verified). On `completed`, the fp subgraph synthesizes `FpEvidence` from the confirmed container config + CC fraction rows and emits the result-review form.

## 2. DTOs (agent-owned FE↔BE contract, `app/events/form_payloads.py`; FE mirrors in TS)

Naming follows the existing conventions: `FP*` for params-form types (like `CCParamsForm`/`REParamsForm`), `Fp*` for evidence/review (like the existing `FpEvidence`, `ReResultReviewAction`).

Python-expert review refinements (2026-07-06):

- **Wire casing is split by family (ADR #1, form_payloads.py:705).** Evidence bodies (`FpMappingRow`, `FpEvidence`) MUST carry `ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)` — the FE consumes them off the wire in camelCase. Params-form types (`FPContainer`, `FPParamsForm`, …) stay snake_case with `extra="forbid"`, matching `CCParamsForm`/`REParamsForm`.
- **Validation placement mirrors RE:** `FPFromUserFields`/`FPContainer` stay LENIENT (incremental draft — same reason `REFromUserFields` is all-Optional with "required-ness enforced by the recommend gate"). No `model_validator` that could hard-fail a partial draft write; all container invariants live in the pure dispatch-gate function (§3). Exception: `name` `max_length=5` stays on the model — cheap contract guarantee, FE caps input, an over-length LLM tool write fails loud.
- **Defaults use `Field(default_factory=list)`** (never `= []`), matching codebase style.

```python
# --- params form -----------------------------------------------------------

FPContainerType = Literal["flask", "waste"]

TUBE_VOLUME_ML: Final[int] = 15  # 1 collection tube = 15 ml (Drake, 2026-07-06)


class FPContainer(BaseModel):
    """One FP collection container (lower-panel row)."""
    model_config = ConfigDict(extra="forbid")

    id: str                                   # stable client id: "flask-1", "waste-1"
    type: FPContainerType
    name: str = Field(max_length=5)           # display name: 烧瓶1 / 废液瓶 (≤5 chars)
    volume: FlaskVolume | None = Field(
        default=None,
        description="Flask spec for dispatch; None for waste. Flasks default to 500ml at dispatch.",
    )
    tubes: list[str] = Field(default_factory=list)  # rack positions, e.g. ["A4", "A5"]


class FPUpstreamContext(BaseModel):
    """Read-only upper panel: a VERBATIM subset of the confirmed CcEvidence —
    FP adds no new information (Drake review, 2026-07-06). CC analysis carries
    MULTIPLE ranges with per-row status (several product rows are possible,
    plus suspect/waste rows), so no derived single-range or main-peak field
    exists here; the rows and the well map ARE the basis (R2)."""
    model_config = ConfigDict(extra="forbid")

    rack_cols: int                             # = CcEvidence.rack_cols (grid layout)
    rack: list[RackTube]                       # = CcEvidence.rack (per-well label + status)
    fractions: list[FractionRow]               # = CcEvidence.fractions (peak rows: tubes range + status)


class FPFromUserFields(BaseModel):
    """User-editable container/tube assignment (lower panel).
    Pre-fill from upstream well statuses: product wells → 烧瓶1,
    suspect + waste wells → 废液瓶, idle wells unassigned.
    Multi-flask: each flask is its own FPContainer with its own tubes[]
    (disjoint sets enforced); dispatch maps flask ordinal k → collect_config
    value k."""
    model_config = ConfigDict(extra="forbid")

    containers: list[FPContainer] | None = None


class FPParamsForm(BaseModel):
    """Unified FP params form — the single per-specialist form surface."""
    model_config = ConfigDict(extra="forbid")

    upstream: FPUpstreamContext = Field(default_factory=FPUpstreamContext)
    from_user: FPFromUserFields = Field(default_factory=FPFromUserFields)


class FPParamsConfirmAction(BaseModel):
    """Params-confirm action (mirrors CCParamsConfirmAction shape)."""
    specialist_kind: Literal["fp"] = "fp"
    confirm_kind: Literal["params"] = "params"
    form: FPParamsForm


# --- result evidence (REPLACES the current canned FpEvidence shape) --------
# Classification vocabulary = FractionStatus minus "idle" plus "mixed":
# an assigned row can never be idle, so the type encodes that impossibility
# (rule 11) instead of reusing FractionStatus wholesale. Values stay in the
# CC vocabulary; 主峰/边缘峰/杂质 are the i18n display names.

FpRowClass = Literal["product", "suspect", "waste", "mixed"]


class FpMappingRow(BaseModel):
    """One row of the final container → tube mapping table (R4).
    camelCase on the wire (evidence-family ADR #1)."""
    container_name: str                        # 烧瓶1 / 废液瓶
    container_type: FPContainerType
    tubes: str                                 # display form, e.g. "A4-A20, A25"
    tube_count: int
    classification: FpRowClass
    volume_ml: int                             # tube_count * TUBE_VOLUME_ML


class FpEvidence(BaseModel):
    """Typed FP result-review evidence — synthesized agent-side on terminal
    `completed` (the robot reports no structured fraction data)."""
    kind: Literal["fp"] = "fp"
    mapping: list[FpMappingRow]
    collected_volume_ml: int                   # Σ flask rows
    discarded_volume_ml: int                   # Σ waste rows
    solvent_system: str | None                 # display + RE bridge; see note below


class FpResultReviewAction(BaseModel):
    specialist_kind: Literal["fp"] = "fp"
    confirm_kind: Literal["result_review"] = "result_review"
    evidence: FpEvidence
```

FE TypeScript mirrors (`src/types/specialist-forms.ts`, `src/components/workspace/result/result-stage-model.ts`) use the same field names in camelCase where the existing FE mirrors do. The old `FpEvidence {mapping: PoolMappingRow[], summary}` shape and `PoolMappingRow`/`FpSummaryRow` are REPLACED on both sides in the same change set (agent-owned contract, no external consumer; MED005 canned fixture updated accordingly). No backward-compat shims.

## 3. Dispatch mapping (pure function, unit-tested)

NO new standalone builder pattern (corrected on Drake's review, 2026-07-06 —
CC/RE/TLC construct their `CreateXxTaskRequest` INLINE as `_submit_l4`
branches, gated by `xx_params_form_problems()` in form_payloads, the "single
authority" shared by the validate tool, the L2 confirm gate, and dispatch).
FP follows the SAME three-part convention:

```python
# form_payloads.py — completeness authority, matches cc/re/tlc siblings
def fp_params_form_problems(form: FPParamsForm) -> list[str]: ...
    # unique names ≤5 chars; tube in at most one container; ≥1 flask with
    # ≥1 tube; assigned labels resolve to exactly one non-idle rack well

# form_payloads.py — pure mapping helper (the transformation is real logic,
# unlike CC/RE/TLC's trivial field picks, so it gets a named, unit-tested fn)
def map_containers_to_collect(form: FPParamsForm) -> tuple[list[FlaskVolume], list[int]]:
    flasks = [
        c.volume if c.volume is not None else FlaskVolume.ML_500   # explicit None check, not `or`
        for c in containers if c.type == "flask"
    ]                                                              # list order = flask ordinal
    # collect_config: ONE element per rack well, len == len(upstream.rack),
    # same flat order as CcEvidence.rack (rack_cols-wide, row-major).
    # KEYED BY WELL INDEX, not label — RackTube.label can be "" for idle
    # wells, so labels are resolved to indices once and the array is built
    # positionally:
    #   k (1-based flask ordinal) if well i's tube is in flask k's tubes[]
    #   0 for waste-assigned, unassigned, and idle/empty wells

# tools.py _submit_l4 — new elif branch, exactly parallel to cc/re/tlc:
# validate draft → fp_params_form_problems → RuntimeError fail-loud →
# flasks, collect_config = map_containers_to_collect(form) →
# CreateFPTaskRequest(task_id=task_uuid, flasks=flasks, collect_config=collect_config)
```

Indexing semantics (Drake, 2026-07-06): the array covers the WHOLE rack —
e.g. a 5×6 rack of 30 tubes yields 30 elements — and element i is the
disposition of rack tube i. Structurally identical to `CcEvidence.rack`
(flat list + `rack_cols`), so the mapping alignment is index-for-index.

Robot-team alignment (RULED by Drake, 2026-07-06): follow the shared-types
example as the contract reference — `"flasks": ["500ml"], "collect_config":
[0, 1, 1, 0]` (currently sitting in `create-re-task.example.json`; it moves
into the new `create-fp-task.example.json` with the example fix). VALUE
semantics are aligned by construction (`CollectCCFractionsLabParams` is the
exact model the robot receives; lab resolver passes `collect_config` through
untransformed, `task_resolver.py:166`). Array coverage / index origin follows
Drake's definition (one element per rack tube, element i = tube i, same flat
order as `CcEvidence.rack`). #81's ordering confirmation remains a
nice-to-have, NOT a gate; the robot mock only validates command shape (it
replays canned updates without interpreting the array), which is sufficient
for dev-loop verification.

Unit-test plan (all pure functions — `prefill_containers(rack)`,
`fp_params_form_problems(form)`, `map_containers_to_collect(form)`,
`synthesize_fp_evidence(form, solvent_system)`):
- partition property: every rack well gets exactly one disposition; `len(collect_config) == len(rack)`; Σ non-zero elements == Σ flask tube counts;
- ordinal property: flask k's tubes map to value k, order-stable under container list order;
- volume math: `tube_count × 15`, totals split collected vs discarded (5 collected = 75, 3 discarded = 45);
- mixed-class rows: a container holding product + suspect tubes yields `classification="mixed"`;
- failure cases raise with precise messages: duplicate tube across containers, unknown/idle tube label, empty flask, duplicate names, name > 5 chars;
- evidence wire shape: camelCase round-trip (`model_dump(by_alias=True)` ↔ FE mirror).

`TUBE_VOLUME_ML` lives in the FP domain module (`fp.py` or a domain constants module), NOT in `form_payloads.py` — it is business math for evidence synthesis, not a wire type.

OPEN (lab-service GitHub issue #81, non-blocking): robot multi-flask capability and max flask count (Q1/Q2). The portal operator configures a single flask (R1) until answered. Q3 (indexing) is answered — recorded on the issue.

Shared-types evidence audit (2026-07-06): there is NO `create-fp-task.example.json` — the FP endpoint is missing its contract example (violates the shared-types "adding an endpoint updates ALL of these" rule). The only `collect_config` example anywhere is `[0, 1, 1, 0]` sitting in the STALE `create-re-task.example.json`, which still carries `flasks`/`collect_config` even though `CreateRETaskRequest` v1.2.0 dropped them. Field docs (`CollectCCFractionsLabParams`) define value semantics (0=丢弃, N=收集到第 N 个茄形瓶; validator bounds 0..len(flasks)) but NOT the index origin. Follow-up in BIC-shared-types: add the FP example, strip the stale RE example fields, regenerate per the contract-repo gate — small change set, can ride alongside the specialist child.

Solvent-system note (Drake Q1, 2026-07-06): FP itself never needs the solvent system — it is absent from `FPUpstreamContext` and from execution params. It appears ONLY in `FpEvidence`, sourced at synthesis time from the confirmed CC params (`CCParam.solvent_system` — note it is NOT in `CcEvidence`), because (a) the FP result tab displays 实际合并液体积与体系比例 per R4, and (b) it hands RE its recommend basis in one object. Alternative (RE reads CC params directly, FpEvidence drops the field) is viable if Drake prefers.

## 4. FP → RE bridge

`REFromUserFields` requires exactly `{volume_ml, solvents, solvent_ratio}` for its recommend gate. On RE start, when confirmed FP evidence exists for the experiment, the RE subgraph pre-fills:
- `volume_ml` = `FpEvidence.collected_volume_ml`
- `solvents` / `solvent_ratio` = parsed from `FpEvidence.solvent_system` (e.g. "PE/EA 5:1" → [PE, EA], [5, 1])

v1.2.0 split note (Drake Q4): the split changed BOTH task params — FP gained flasks/collect_config, RE kept only `param: REParam` (水浴温度、气压梯度). Both forms update accordingly: the FP form owns container/tube assignment; the RE form drops the dead `RELabLogistics` section and keeps from_user (volume/solvents/ratio) + recommended REParam only.

This replaces the MED005 FP→RE bridge fixture as the live path.

## 5. RE dead-field removal (R5)

Remove `RELabLogistics` (flasks/collect_config), the `update_re_lab_logistics` tool, and the FE ReForm section that renders them. The stale docstring "maps 1:1 onto CreateRETaskRequest" is confirmed wrong at v1.2.0. Spec updates ride the same change set (Rule 10).

## 6. Data flow summary

```
CC result confirmed (FractionRow[], collect range, main peaks, solvent system)
  → reception routes robot fp → fp_subgraph
  → build FPParamsForm (upstream = CC facts; from_user pre-filled default assignment)
  → FormRequestedEvent(params) → portal upper/lower panels + rack grid → user confirms
  → _submit_l4(fp): containers → CreateFPTaskRequest → lab POST /tasks/
  → robot runs collect_column_chromatography_fractions → MQ task_status terminal
  → synthesize FpEvidence (mapping, 15ml math, totals, solvent system)
  → FormRequestedEvent(result_review) → portal FP result card → user accepts
  → cursor advances to RE; RE pre-fills its recommend basis from FpEvidence
```
