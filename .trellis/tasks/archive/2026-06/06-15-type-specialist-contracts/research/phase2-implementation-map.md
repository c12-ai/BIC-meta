# Research: Phase 2 Implementation Map — Type CC/RE result-review wire

- **Query**: Phase 2 prepare-for-implementation research for the approved PRD (MVP = type CC/RE result-review with typed `CcEvidence`/`ReEvidence`, emit typed STUB evidence, add 4th `result_review` arm to `OriginalAction`, converge FE cc+re result cards off fixtures).
- **Scope**: internal (BE `BIC-agent-service` + FE `BIC-agent-portal` + shared-types)
- **Date**: 2026-06-15

> Authority precedence note: PRD ADR-lite #2 (Drake, 2026-06-15) = **contract-first, data-stubbed**. Type the wire, stub the data. Keep Mind deferred, fail loud (`MindNoticeEvent(phase="post")` stays). FE `result-stage-model.ts` is the contract authority — BE converges to it.

---

## 1. FE target shapes — EXACT field lists to mirror in BE Pydantic

Verbatim from `BIC-agent-portal/src/components/workspace/result/result-stage-model.ts` (only the cc/re-relevant shapes + shared sub-shapes — TLC/Analysis/FP evidence stay on fixtures this wave).

### `CcEvidence` (L83-92) + nested types

```ts
export type FractionStatus = 'product' | 'suspect' | 'waste' | 'idle'   // L67

export interface RackTube {        // L69-73
  label: string                     // tube number; '' renders an unlabelled idle well
  status: FractionStatus
}

export interface FractionRow {     // L75-81
  peak: string
  tubes: string
  time: string
  area: string
  status: FractionStatus
}

export interface CcEvidence {      // L83-92
  kind: 'cc'
  rackCols: number
  rack: RackTube[]
  rackAlt: string                   // accessible one-line rack description (role="img" label)
  rackCaption: string
  uvTraceLabel: string
  fractions: FractionRow[]
}
```

**Per-field BE-produce vs FE-presentation classification** (all values STUB-fabricated this wave — Mind deferred):

| Field | Type | Optionality | Classification / STUB note |
|---|---|---|---|
| `kind` | `'cc'` literal | required | discriminator — BE sets `"cc"` |
| `rackCols` | number | required | **FE-presentation** (rack-grid column count; fixture used `5`). STUB: static `5`. |
| `rack` | `RackTube[]` | required | **data** (which tubes are product/suspect/waste). STUB: fabricated rack from collect_config or a static map. |
| `rack[].label` | string | required | data — tube number; `''` = idle well |
| `rack[].status` | `FractionStatus` | required | data |
| `rackAlt` | string | required | **FE-presentation/a11y** (caveat-style accessible label). STUB: static or derived string. |
| `rackCaption` | string | required | **FE-presentation** (e.g. "5 × 15 test tube rack…"). STUB: static. |
| `uvTraceLabel` | string | required | **FE-presentation** (UV-trace a11y label). STUB: static. |
| `fractions` | `FractionRow[]` | required | **data** (peak table). STUB: fabricated rows. |
| `fractions[].{peak,tubes,time,area}` | string | required | data — all strings (note `time`/`area` are display strings, not numbers) |
| `fractions[].status` | `FractionStatus` | required | data |

> Fixture reference values: `result-stage-fixtures.ts` L64-97 (CC card). 20-cell rack (5 cols), 3 fraction rows, `rackCols: 5`.

### `ReEvidence` (L139-142) + nested `ReCheckpointRow` (L131-137)

```ts
export interface ReCheckpointRow {   // L131-137
  checkpoint: string
  target: string
  observed: string
  statusLabel: string
  ok: boolean
}

export interface ReEvidence {        // L139-142
  kind: 're'
  checkpoints: ReCheckpointRow[]
}
```

**Per-field classification** (PRD R4: STUB rows derived from RE param targets, `observed = target`, `ok = true`):

| Field | Type | Optionality | Classification / STUB note |
|---|---|---|---|
| `kind` | `'re'` literal | required | discriminator — BE sets `"re"` |
| `checkpoints` | `ReCheckpointRow[]` | required | **data** — STUB rows derived from `params_draft.recommended` (`REParam`) targets |
| `checkpoints[].checkpoint` | string | required | label — STUB static ("Bath temperature", "Pressure", "Rotation speed", "Endpoint") |
| `checkpoints[].target` | string | required | **derivable** from `REParam.temperature_c` + `air_pressure[].pressure_mbar` (display string e.g. "35 °C", "120 mbar") |
| `checkpoints[].observed` | string | required | STUB: `= target` per PRD R4 |
| `checkpoints[].statusLabel` | string | required | **FE-presentation** — STUB static ("Stable"/"Reached") |
| `checkpoints[].ok` | boolean | required | STUB: `true` per PRD R4 |

> Fixture reference: `result-stage-fixtures.ts` L194-226 (RE card) — 4 checkpoints (Bath temperature / Pressure / Rotation speed / Endpoint).
> **RE stub data source (verified):** `state.params_draft["recommended"]` holds a `REParam` (`temperature_c: float`, `air_pressure: list[PressureStep]` where `PressureStep = {duration_min, pressure_mbar}` — `BIC-shared-types/bic_shared_types/common/re.py:20-33`). Rotation speed has **no** source field in `REParam` → that checkpoint row's target must be fully static-stubbed (the fixture used "90 rpm"). Endpoint ("Dry residue") is also fully static. Only Bath-temp + Pressure targets are derivable.

### Shared sub-shapes the evidence cards use

These live on `ResultStageVM` (the card view-model), NOT inside the evidence body. They are populated by FE adapters/fixtures today and are **NOT part of the typed evidence wire** unless the implementer chooses to extend the wire (PRD scope = `CcEvidence`/`ReEvidence` bodies only). Flagged so the implementer knows what the FE card still expects from fixtures vs. wire:

```ts
export interface EvidenceAction {    // L29-35
  label: string
  kind: 'video' | 'log' | 'report'
  href?: string                       // undefined → BE has no link yet; renders disabled
}
export interface AiVerdict {         // L37-40
  tone: 'success' | 'warning' | 'error' | 'info'
  text: string
}
export interface ManualConclusion {  // L42-45
  title: string
  note: string
}
```

**Where they sit on the card VM** (`ResultStageVM`, L153-172): `summary: string`, `confirmLabel: string`, `evidenceActions: EvidenceAction[]`, `aiVerdict?: AiVerdict`, `manualConclusion?: ManualConclusion`, `evidence: ResultStageEvidence`, `raw?: unknown`, `fixture: boolean`.

> **Decision needed by implementer (flag):** The PRD MVP types only the evidence BODY (`CcEvidence`/`ReEvidence`). The card's `summary`/`aiVerdict`/`manualConclusion`/`evidenceActions` are card-chrome that the fixture supplied. When cc/re drop `fixture: true`, the FE adapter must source these from somewhere. Two converging options (raise to Drake if ambiguous, Rule 1):
> - (a) keep `summary`/`aiVerdict`/`manualConclusion`/`evidenceActions` as FE-side static defaults in the adapter (only `evidence` comes from the wire) — minimal, matches MVP scope.
> - (b) extend the BE evidence wire to carry them too — larger contract surface, beyond PRD R1/R6.
> PRD R6 wording ("render the cc + re result cards from the real (stubbed) wire") most naturally reads as (a): the typed evidence body comes off the wire; card chrome stays FE-default. Confirm before implementing.

---

## 2. BE confirm-action / OriginalAction pattern to copy

All in `BIC-agent-service/app/events/form_payloads.py`.

### Existing confirm-action arm (template) — `CCParamsConfirmAction` (L321-335)

```python
class CCParamsConfirmAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_kind: Literal["params"] = "params"      # discriminator part 1
    task_id: str
    specialist_kind: Literal["cc"] = "cc"            # discriminator part 2
    params: CCParamsForm
```

`REParamsConfirmAction` (L338-346) is identical with `specialist_kind="re"` + `params: REParamsForm`. `PlanConfirmAction` (L364-380) is the divergent arm: `confirm_kind="plan"`, no `specialist_kind`, fields `plan_id` + `plan: list[PlanStep]`.

### Discriminator + registration (the 3 edit sites that wire an arm in)

1. **`_action_discriminator` callable** (L383-404): returns `"plan"` when `confirm_kind=="plan"`, else `f"{specialist_kind}_{confirm_kind}"`. Handles both dict (off-wire) and BaseModel inputs.
2. **`OriginalAction` union** (L411-418): `Annotated[Union[Annotated[CCParamsConfirmAction, Tag("cc_params")], Annotated[REParamsConfirmAction, Tag("re_params")], Annotated[PlanConfirmAction, Tag("plan")]], Discriminator(_action_discriminator)]`.
3. **`TYPED_ORIGINAL_ACTIONS` tuple** (L424-428): `(CCParamsConfirmAction, REParamsConfirmAction, PlanConfirmAction)` — runtime `isinstance` registry.
4. **`__all__`** (L446-468): each public class name listed alphabetically.

### Existing `CCParamsForm` 3-sub-model pattern (the consistency template, Rule 8)

`CCParamsForm` (L117-133): `from_user: CCFromUserFields` (L59-100, all-Optional draft) + `recommended: CCParam | None` (shared-type, reused directly) + `lab_logistics: CCLabLogistics` (L103-114, lab-only). Each sub-model is `ConfigDict(extra="forbid")`. The `recommended` field **reuses the shared-types model directly** (`CCParam` / `REParam`) — no duplicate. This is the echo the evidence models should follow for nested rows (define `CcRackTube`/`CcFractionRow`/`ReCheckpointRow` as small BaseModels, compose into `CcEvidence`/`ReEvidence`).

### EXACTLY what a `result_review` arm + `CcEvidence`/`ReEvidence` must add — edit sites in form_payloads.py

A1. **New nested row models** (mirror FE camelCase EXACTLY — FE is contract authority; field names must match byte-for-byte since the FE consumes the wire). Define: `RackTube` (label, status), `FractionRow` (peak, tubes, time, area, status), `CcEvidence` (kind, rackCols, rack, rackAlt, rackCaption, uvTraceLabel, fractions), `ReCheckpointRow` (checkpoint, target, observed, statusLabel, ok), `ReEvidence` (kind, checkpoints). `FractionStatus = Literal["product","suspect","waste","idle"]`.
   - **Naming-convention conflict to surface (Rule 5):** FE uses `camelCase` (`rackCols`, `rackAlt`, `statusLabel`). BE form models here use `snake_case` (`sample_quantity`, `collect_config`) and the wire is consumed by FE hand-mirrors. Since FE consumes THIS evidence off the wire directly (not a hand-mirror), the BE model MUST emit camelCase keys to match `result-stage-model.ts`. Options: (a) use Pydantic `Field(alias=...)` / `model_config = ConfigDict(populate_by_name=True)` + `by_alias=True` on dump, or (b) name the Python fields camelCase. **Flag for Drake / decision in design.** This is the single most important contract-shape decision.
A2. **`ResultReviewConfirmAction` arm**: `confirm_kind: Literal["result_review"]`, `task_id: str`, `specialist_kind: Literal["cc","re"]` (or two arms `Cc`/`Re` like params — see A4 discriminator), `evidence: CcEvidence | ReEvidence` (discriminated by `kind`).
A3. **`_action_discriminator`**: `result_review` currently falls through to `f"{specialist_kind}_{confirm_kind}"` → `"cc_result_review"` / `"re_result_review"`. EITHER add two arms (`CcResultReviewConfirmAction` + `ReResultReviewConfirmAction`, tags `cc_result_review`/`re_result_review`) mirroring the params split, OR add a `result_review`-specific short-circuit. The params-split pattern (two arms) is the most consistent (Rule 8).
A4. **`OriginalAction` union**: add `Annotated[CcResultReviewConfirmAction, Tag("cc_result_review")]` + `Annotated[ReResultReviewConfirmAction, Tag("re_result_review")]`.
A5. **`TYPED_ORIGINAL_ACTIONS` tuple**: append the new class(es).
A6. **`__all__`**: add the new class names.
A7. **Module docstring** (L28-31): currently says "Result-review variant is still deliberately NOT included here: a follow-on ticket will type that payload separately." — UPDATE this to reflect the now-typed arm (Rule 10 / Rule 3 surgical doc fix).
A8. **`ConfirmKindLiteral`** (L51): already includes `"result_review"` — NO change needed.

---

## 3. The wire: TaskResultAnalyzedEvent construction + consumption

### `app/events/runtime_emitted.py`

- **`TaskResultAnalyzedEvent`** (L564-587): `kind="task_result_analyzed"`, `trial_id: str = ""`, `analysis: dict[str, Any] = {}`. `apply()` (L581-587) writes `{"analysis": self.analysis}` to `trials.analysis` (JSONB) via `tx.trials.update_fields`.
  - **Minimal typed change (keep raw-dict path alive for TLC/Analysis/FP):** The cleanest surgical option is **Optional typed sidecar field** — keep `analysis: dict[str, Any]` for the other stages, add `evidence: CcEvidence | ReEvidence | None = None` (typed, discriminated by `kind`). `apply()` writes the typed `evidence` (via `.model_dump(by_alias=True)`) into `trials.analysis` when present, else the raw `analysis` dict. This is surgical (Rule 3) and avoids a union on `analysis` that would break the raw-dict callers. **Alternative** (union on `analysis`) is riskier — the field is consumed as a free-form dict by FE `adaptResultStages` today (see §4). **Flag the choice for design.**
  - The `MindNoticeEvent` (L617-632, `kind="mind_notice"`, `phase="post"`, `reason`) stays — PRD R5 fail-loud signal that evidence is stubbed. NO change.
  - **`TODO(result_review)` at L505-507** (inside `FormConfirmedEvent.apply`): "when chemist-editable fields are added to the result-review form (today form_values is empty), persist them here symmetrically. Tracked in events.md." — MVP keeps result_review `form_values` empty (FE sends `{accept, ...}` only — see `ResultConfirmationPane.tsx:73-74`). This TODO is **out of MVP scope** (no chemist-editable evidence fields). Leave it, but the events.md reference must be kept accurate (Rule 10).

### `app/runtime/graphs/specialists/tools.py` — `_analyze_result` (L501-555)

Current construction:
- L514-530: `analysis_payload: dict[str, Any]`; unconditionally `raise MindCallError` (L518), caught → emits `MindNoticeEvent(trial_id=state.task_id, phase="post", reason=...)` (L520-526) and sets `analysis_payload = {"status":"deferred","notice":...}` (L527-530).
- L534-539: `emit_event(runtime, TaskResultAnalyzedEvent, trial_id=state.task_id, analysis=analysis_payload)`.
- L540-550: `emit_event(runtime, FormRequestedEvent, decision_id=uuid4(), confirm_kind="result_review", original_action={"task_id": state.task_id, "task_type": task_type, "analysis": analysis_payload})`.

**Where the typed stub gets injected:** `task_type` (the function param, "cc"/"re" — passed at L948 `analyze_cc_result` and L1232 `analyze_re_result`, and the auto_analyze node `cc.py:496` / `re.py`) is the **branch point**. Build a typed `CcEvidence` or `ReEvidence` stub here:
- CC branch: construct a static/derived `CcEvidence` stub (mocked rack + fractions).
- RE branch: construct `ReEvidence` with `checkpoints[]` derived from `state.params_draft["recommended"]` (the confirmed `REParam` — `temperature_c`, `air_pressure[].pressure_mbar`), `observed = target`, `ok = true`. Rotation/Endpoint rows fully static.
- Replace `analysis_payload` dict with the typed evidence on `TaskResultAnalyzedEvent` (via the new `evidence=` field per §3 option) AND on `FormRequestedEvent.original_action` (now a typed `*ResultReviewConfirmAction` instead of the free-form dict).
- **Keep `MindNoticeEvent(phase="post")` emit (R5 fail-loud)** — the Mind call stays deferred; the stub is clearly marked.

**Callers of `_analyze_result` (all pass `task_type`):**
- `tools.py:948` `analyze_cc_result` → `_analyze_result(state, runtime, mind, "cc")`
- `tools.py:1232` `analyze_re_result` → `_analyze_result(state, runtime, mind, "re")`
- `cc.py:496` `_auto_analyze_node` → `_analyze_result(state, runtime, mind, "cc")` (the auto-promote node, `cc.py:489-496`, wired at `cc.py:639/664/684`)
- `re.py:422` `_auto_analyze_node` → `_analyze_result(state, runtime, mind, "re")`

### How `FormRequestedEvent.original_action` flows to FE

`FormRequestedEvent` (`runtime_emitted.py:330-402`): `confirm_kind: ConfirmKindLiteral`, `original_action: OriginalAction | dict[str, Any]`. `_enforce_typed_action` validator (L355-382) currently requires typed variants ONLY for `confirm_kind in ("params","plan")` — **once result_review is typed, this guard MUST be extended to include `"result_review"`** (else a raw dict silently bypasses the new typed contract — exactly the fail-loud concern in the validator's own docstring). `apply()` (L384-402) `.model_dump()`s the typed action into `pending_decisions.original_action` (JSONB) via `tx.decisions.insert`.

Wire path to FE (from CLAUDE.md + backend-contract.md): BE SSE → FE `sse-client.ts` (event `form_requested` registered in `KINDS`, L59 lists `task_result_analyzed`) → `event-dispatcher.ts` (`case 'form_requested'` / `case 'task_result_analyzed'` at L174-175) → `workspaceStore`. The FE `events.ts:FormRequestedEvent.original_action: OriginalAction` (L127) is consumed via the `specialist-forms.ts:OriginalAction` union (L164).

---

## 4. FE consumption + fixture removal sites

### `result-stage-fixtures.ts` (cc + re entries)

- **CC fixture**: `const CC` L47-99 (evidence body L64-97). Map entry `cc: CC` at L231.
- **RE fixture**: `const RE` L177-228 (evidence body L194-226). Map entry `re: RE` at L235.
- **`RESULT_STAGE_FIXTURES` map** L230-236: `{ tlc: TLC, cc: CC, analysis: ANALYSIS, fp: FP, re: RE }`.
- **What changes (cc+re only):** TLC/Analysis/FP (`const TLC` L15-45, `const ANALYSIS` L101-148, `const FP` L150-175) STAY. PRD R6 = remove `fixture: true` cc + re cards; render them from the wire. Exactly which lines get deleted/replaced depends on the adapter strategy (below) — the cleanest surgical change is to keep TLC/ANALYSIS/FP fixtures and have the adapter build cc/re VMs from the wire evidence instead of `RESULT_STAGE_FIXTURES[id]`.

### Where the FE currently READS result evidence (today: fixtures only; wire only feeds `raw`)

- **Store ingest:** `workspaceStore.ts:537-547` `onTaskResultAnalyzed` sets `analysis: e.analysis` + `analyzedAt` (e is `TaskResultAnalyzedEvent`, `events.ts:186-190` = `{trial_id, analysis: Record<string,unknown>}`). Dispatched at `event-dispatcher.ts:174-175`.
- **Adapter:** `result-stage-adapters.ts:adaptResultStages` (L27-44) — TODAY: `const base = RESULT_STAGE_FIXTURES[id]` (L34), attaches the free-form `analysis` to the live stage as `vm.raw` (L39-41), and only patches TLC `tlcFileKey` (L36-38). The whole typed evidence body comes from the fixture. **This is the single convergence site:** for `id === 'cc' | 're'`, build the VM's `evidence` from the typed wire payload (the new `CcEvidence`/`ReEvidence`) instead of `RESULT_STAGE_FIXTURES[id].evidence`.
- **Renderer:** `ResultConfirmationPane.tsx:69` `adaptResultStages({ analysis, executor, tlcFileKey })` → maps to `ResultStageCard` (L22). `ResultStageEvidence.tsx` renders the typed bodies; `ResultStageCard.tsx:169` renders the free-form `raw` via the generic AnalysisView fallback.
- **The wire today carries cc/re evidence?** NO — only the free-form `analysis` dict (attached as `raw`). The typed evidence body is 100% fixtures today. After this task, the typed evidence must be carried by the wire (new field on `TaskResultAnalyzedEvent` and/or the typed `original_action.evidence`) and the adapter reads it.

### Existing FE type mirror needing a `result_review` entry

- **`src/types/events.ts`**: `TaskResultAnalyzedEvent` (L186-190) = `{kind, trial_id, analysis: Record<string,unknown>}`. **Needs a typed `evidence?` field** mirroring the BE option chosen in §3. `FormRequestedEvent` (L122-127) already typed via `OriginalAction`.
- **`src/types/specialist-forms.ts`**: `OriginalAction` union (L164) = `ParamsConfirmAction | PlanConfirmAction | ResultReviewConfirmAction`. `ResultReviewConfirmAction` (L158-162) is currently `{confirm_kind: 'result_review', [k:string]: unknown}` (free-form). **Needs to become typed** (carry `task_id`, `specialist_kind`, typed `evidence`) to match the BE arm. The `CcEvidence`/`ReEvidence`/`RackTube`/`FractionRow`/`ReCheckpointRow` TS types ALREADY EXIST in `result-stage-model.ts` — the implementer should reference/import those rather than re-declare (Rule 6 reuse). Header comment block (L1-13 "Codegen TODO") cites form_payloads.py as authority — keep accurate (Rule 10).

---

## 5. Spec + events.md update targets (Rule 10)

**Two events.md files exist — both reference the deferred result-review TODO:**

| Doc | Path | What to update |
|---|---|---|
| **L4 events.md** | `BIC-agent-service/.trellis/spec/backend/L4/events.md` | `FormRequestedEvent` row (L138), `TaskResultAnalyzedEvent` row (L143-area / catalog), `MindNoticeEvent`. Document the new typed `evidence` on `task_result_analyzed` + the typed `result_review` `original_action` arm. (259 lines total.) |
| **L3 events.md** | `BIC-agent-service/.trellis/spec/backend/L3/events.md` | emit-site catalog (referenced by `specialist_tools.md:169`) — `TaskResultAnalyzedEvent` / `MindNoticeEvent` emit sites in `_analyze_result`. |
| **specialist_tools.md** | `BIC-agent-service/.trellis/spec/backend/L3/specialist_tools.md` | `analyze_cc_result` row (L47) + RE mirror (L50) + I-ST-D (L143) describe analyze emitting `TaskResultAnalyzedEvent` — update to note typed stub evidence + the new `result_review` typed arm. |
| **contracts.md** | `BIC-agent-service/.trellis/spec/backend/contracts.md` | result_review confirm-path section (L228-252, L293, L299-302) — `original_action` for result_review currently "only the task_id key / free-form dict"; update for the typed arm. |
| **FE backend-contract.md** | `BIC-agent-portal/.trellis/spec/backend-contract.md` | `task_result_analyzed` row (L326), `mind_notice` (L330), `confirm_kind` union (L77, L446), and the `OriginalAction` / result_review section — this is THE FE↔BE contract doc (Rule 10 FE side). |
| **FE workspace.md** | `BIC-agent-portal/.trellis/spec/ui/L3/workspace.md` | result-pane data strategy (the "evidence from fixtures until BE ships typed payloads" narrative now changes for cc/re). |

> `form_payloads.py` module docstring (L28-31) + `runtime_emitted.py` TODO (L505-507) are the in-code "tracked in events.md" anchors — both must be reconciled with the events.md edits (Rule 10, same change set).

---

## 6. Test surfaces

### BE scenario tests (`BIC-agent-service/scripts/`)

- **`scripts/run_scenarios.py`** — `scenario_monitor_exp` (L467-~555) is THE CC result-review surface. It currently **asserts NO result_review** (L528-530: `assert_event_not_emitted(... FormRequestedEvent, confirm_kind="result_review")`, same for `FormConfirmedEvent`, and `TaskAnalysisCompletedEvent` at L530). Comments L481-485 + L532-544 explicitly say result-review HITL is "deferred to a follow-on ticket" — **this task IS that ticket.** These negative assertions must FLIP to positive (assert result_review form_requested emitted with typed evidence). `scenario_exec_exp` (L310) + `scenario_design_exp` (L194) are the upstream chain (`--all` runs Design→Exec→Monitor).
- **`scripts/assertions.py`** — `assert_form_payload_valid` (L161-~220) + `_PermissiveFormPayloadSchema` (L144-158): the typed-required gate (L196-207) currently treats `typed_required = form_kind in ("params","plan")` (L197) — **must add `"result_review"`** so the harness validates the new typed arm. `assert_event_not_emitted` (L121-141) is the helper the monitor_exp negatives use.
- **`scripts/_harness.py`, `scripts/harness_ctx.py`, `scripts/fixtures.py`** — phase-advance + ctx derivation (`harness_ctx.py` `_advance_phase_on_form_confirm` mirrors `_FORM_CONFIRM_PHASE_ADVANCE`; `("conducting","result_review")→"done"` already present).

### FE E2E specs (`BIC-agent-portal/tests/`)

- **`tests/cc-re-chained-flow.spec.ts`** — the CC→RE chained flow; most likely to reach the result pane / result_review gate.
- **`tests/live-backend.spec.ts`**, **`tests/live-backend-plan.spec.ts`** — full live-backend flows.
- **`tests/task-progress-stream.spec.ts`**, **`tests/progress-display-fixture.spec.ts`** — progress→result transition.
- **`tests/manual-live-demo.spec.ts`** — manual smoke.
- (No spec currently named for result-card rendering specifically — the cc/re evidence rendering is fixture-backed today, so an E2E asserting wire-driven cards is net-new per PRD AC "CC + RE terminal trial → result_review gate shows typed evidence end-to-end".)

---

## PR-by-PR edit map (per PRD R1–R7)

> The PRD does not pre-number PR1/PR2/PR3; the natural seams are **BE types+wire (R1–R5)**, **FE consumption (R6)**, **spec/events.md (R7)**. Mapped below.

### PR1 — BE: typed evidence models + wire + typed stub (R1, R2, R3, R4, R5)

| File | Anchor | Change |
|---|---|---|
| `app/events/form_payloads.py` | after L346 (`REParamsConfirmAction`) | NEW: `FractionStatus` literal, `RackTube`, `FractionRow`, `CcEvidence`, `ReCheckpointRow`, `ReEvidence` models (camelCase keys / aliases — §2 A1 decision) |
| `app/events/form_payloads.py` | after L346 | NEW: `CcResultReviewConfirmAction` + `ReResultReviewConfirmAction` arms (`confirm_kind="result_review"`, `task_id`, `specialist_kind`, `evidence`) |
| `app/events/form_payloads.py` | L383-404 | `_action_discriminator` — verify `result_review` produces `cc_result_review`/`re_result_review` (no change if the `f"{specialist_kind}_{confirm_kind}"` path is used) |
| `app/events/form_payloads.py` | L411-418 | `OriginalAction` union — add two `Annotated[..., Tag("cc_result_review"/"re_result_review")]` members |
| `app/events/form_payloads.py` | L424-428 | `TYPED_ORIGINAL_ACTIONS` — append new classes |
| `app/events/form_payloads.py` | L446-468 | `__all__` — add new class names |
| `app/events/form_payloads.py` | L28-31 | module docstring — drop "result-review NOT included / follow-on ticket" |
| `app/events/runtime_emitted.py` | L564-587 | `TaskResultAnalyzedEvent` — add Optional typed `evidence: CcEvidence \| ReEvidence \| None`; `apply()` writes typed evidence (`.model_dump(by_alias=True)`) to `trials.analysis` when present, else raw dict (§3 — keep raw-dict path) |
| `app/events/runtime_emitted.py` | L355-382 | `FormRequestedEvent._enforce_typed_action` — extend typed-required set to include `"result_review"` |
| `app/events/runtime_emitted.py` | L32-36 | import the new evidence/arm types from `form_payloads` |
| `app/runtime/graphs/specialists/tools.py` | L501-555 `_analyze_result` | branch on `task_type`: build typed `CcEvidence`/`ReEvidence` stub (RE from `state.params_draft["recommended"]`); pass typed `evidence=` to `TaskResultAnalyzedEvent`; pass typed `*ResultReviewConfirmAction` as `original_action`; KEEP `MindNoticeEvent(phase="post")` (R5) |

### PR2 — FE: consume typed wire, drop cc/re fixtures (R6)

| File | Anchor | Change |
|---|---|---|
| `src/types/events.ts` | L186-190 | `TaskResultAnalyzedEvent` — add typed `evidence?` field mirroring BE |
| `src/types/specialist-forms.ts` | L158-164 | type `ResultReviewConfirmAction` (task_id, specialist_kind, evidence) — reuse `CcEvidence`/`ReEvidence` from `result-stage-model.ts` |
| `src/stores/workspaceStore.ts` | L537-547 `onTaskResultAnalyzed` | also store the typed `evidence` (new store field) |
| `src/components/workspace/result/result-stage-adapters.ts` | L27-44 `adaptResultStages` | for `id === 'cc'|'re'`, build `vm.evidence` from the typed wire evidence instead of `RESULT_STAGE_FIXTURES[id].evidence`; clear `fixture` for those; card-chrome decision per §1 flag |
| `src/components/workspace/result/result-stage-fixtures.ts` | `const CC` L47-99, `const RE` L177-228, map L231/L235 | remove/retire the cc+re `fixture: true` cards (keep TLC/ANALYSIS/FP) |
| `src/components/workspace/ResultConfirmationPane.tsx` | L69 | pass the typed evidence through to the adapter |

### PR3 — Specs + events.md (R7) — Rule 10, SAME change set as PR1/PR2

| File | Anchor | Change |
|---|---|---|
| `BIC-agent-service/.trellis/spec/backend/L4/events.md` | L138, L143, catalog | typed `evidence` on `task_result_analyzed`; typed `result_review` arm |
| `BIC-agent-service/.trellis/spec/backend/L3/events.md` | emit-site catalog | `_analyze_result` typed emit sites |
| `BIC-agent-service/.trellis/spec/backend/L3/specialist_tools.md` | L47, L50, L143 | analyze emits typed stub evidence |
| `BIC-agent-service/.trellis/spec/backend/contracts.md` | L228-252, L299-302 | result_review `original_action` now typed |
| `BIC-agent-portal/.trellis/spec/backend-contract.md` | L77, L326, L330, L446 + OriginalAction section | typed `task_result_analyzed.evidence` + typed `result_review` |
| `BIC-agent-portal/.trellis/spec/ui/L3/workspace.md` | result-pane data-strategy section | cc/re now wire-driven (off fixtures) |

### Test PR (folded into PR1/PR2 per Definition of Done)

| File | Anchor | Change |
|---|---|---|
| `BIC-agent-service/scripts/run_scenarios.py` | `scenario_monitor_exp` L528-544 | FLIP negative result_review assertions → positive (typed evidence emitted) |
| `BIC-agent-service/scripts/assertions.py` | L197 | add `"result_review"` to `typed_required` set |
| `BIC-agent-portal/tests/cc-re-chained-flow.spec.ts` | — | assert cc/re result cards render wire evidence (net-new E2E per PRD AC) |

---

## EDIT-SITE CHECKLIST (file:line → what changes)

**BE — form_payloads.py:**
- `form_payloads.py:28-31` → drop "result-review NOT included" docstring para
- `form_payloads.py:~347` (after REParamsConfirmAction) → NEW `FractionStatus`, `RackTube`, `FractionRow`, `CcEvidence`, `ReCheckpointRow`, `ReEvidence`
- `form_payloads.py:~347` → NEW `CcResultReviewConfirmAction` + `ReResultReviewConfirmAction`
- `form_payloads.py:383-404` → verify `_action_discriminator` yields `cc_result_review`/`re_result_review` (likely no edit)
- `form_payloads.py:411-418` → add 2 union members to `OriginalAction`
- `form_payloads.py:424-428` → append to `TYPED_ORIGINAL_ACTIONS`
- `form_payloads.py:446-468` → add names to `__all__`

**BE — runtime_emitted.py:**
- `runtime_emitted.py:32-36` → import new evidence/arm types
- `runtime_emitted.py:355-382` → `_enforce_typed_action` add `"result_review"` to typed-required set
- `runtime_emitted.py:564-587` → `TaskResultAnalyzedEvent` add Optional typed `evidence`; `apply()` dual-path
- `runtime_emitted.py:505-507` → keep/reconcile `TODO(result_review)` comment (no chemist-editable fields in MVP)

**BE — tools.py:**
- `tools.py:501-555` → `_analyze_result` build typed `CcEvidence`/`ReEvidence` stub branching on `task_type`; typed `evidence=` + typed `original_action`; keep `MindNoticeEvent`
- (callers `tools.py:948`, `tools.py:1232`, `cc.py:496`, `re.py:422` — no signature change; they already pass `task_type`)

**FE:**
- `events.ts:186-190` → `TaskResultAnalyzedEvent` add `evidence?`
- `specialist-forms.ts:158-164` → type `ResultReviewConfirmAction`
- `workspaceStore.ts:537-547` → store typed evidence
- `result-stage-adapters.ts:27-44` → cc/re build evidence from wire
- `result-stage-fixtures.ts:47-99,177-228,231,235` → retire cc/re fixtures
- `ResultConfirmationPane.tsx:69` → pass typed evidence

**Specs (Rule 10, same change set):**
- `BE .../L4/events.md:138,143` · `BE .../L3/events.md` · `BE .../L3/specialist_tools.md:47,50,143` · `BE .../contracts.md:228-252,299-302` · `FE backend-contract.md:77,326,330,446` · `FE ui/L3/workspace.md`

**Tests:**
- `scripts/run_scenarios.py:528-544` → flip negatives to positives
- `scripts/assertions.py:197` → add `"result_review"`
- `tests/cc-re-chained-flow.spec.ts` → net-new wire-evidence assertion

---

## OPEN DECISIONS to surface before implementing (Rule 1)

1. **camelCase vs snake_case on the evidence wire** (§2 A1) — FE `result-stage-model.ts` is camelCase; BE form models are snake_case. FE consumes this evidence DIRECTLY off the wire (not a hand-mirror), so BE must emit camelCase keys (alias or camelCase field names). Highest-impact contract-shape decision.
2. **Typed `evidence` sidecar vs union on `analysis`** on `TaskResultAnalyzedEvent` (§3) — sidecar is surgical (keeps raw-dict path for TLC/Analysis/FP); confirm.
3. **Card-chrome source** (§1) — `summary`/`aiVerdict`/`manualConclusion`/`evidenceActions` stay FE-default (MVP reading) vs. carried on the wire. PRD R6 reads as FE-default; confirm.
4. **Single result_review arm with `specialist_kind` vs two arms** (cc/re) — two arms mirrors the params pattern (Rule 8); confirm.
5. **RE rotation-speed checkpoint** has no `REParam` source field — must be fully static-stubbed (only temp + pressure are derivable). Acceptable per "data stubbed" ADR; note it.

---

## Caveats / Not Found

- No dedicated FE result-card E2E spec exists today (cards are fixture-backed) — the PRD AC end-to-end test is net-new.
- `scenario_monitor_exp` currently asserts the ABSENCE of result_review — this is the most likely test-flip surprise for an implementer (the negative assertions look intentional but are explicitly the deferred-ticket scope this task closes).
- Whether `_action_discriminator` needs an edit depends on the arm-split choice (decision #4) — flagged, not asserted.
- The RE stub depends on `state.params_draft["recommended"]` being populated at analyze time (it is, post-confirm — `FormConfirmedEvent.apply` writes `trials.params`, rehydrated into `params_draft`). If a trial reaches analyze with an empty `recommended`, the stub must fall back to fully-static checkpoints (fail-loud, not crash).
