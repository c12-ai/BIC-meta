# Research: agent-service ELN sourcing for TLC pure/crude tube data

- **Query**: How does the ELN report pipeline source TLC stage data, and where would pure/crude purity fit?
- **Scope**: internal
- **Date**: 2026-07-09

---

## 1. ELN report builder — module map

The ELN pipeline is entirely under `app/eln/`. Entry point is `ELNService.build_report` in `app/eln/service.py`.

**Full pipeline (no IO after the DB transaction closes):**

1. `app/eln/service.py:52–72` — opens a read-only DB transaction, reads:
   - `experiment` row (via `tx.experiments.get`)
   - all `plans` for the experiment (`tx.plans.list_by_experiment`)
   - for each plan, all `jobs` (`tx.jobs.list_by_plan`)
   - for each job, all `trials` (`tx.trials.list_by_job`) — picks the **last** (latest attempt)
   - Asserts all trials have `phase == "done"` (the all-confirmed gate) before proceeding.
2. After the transaction: resolves reactant FW via `ChemClient` (degrades to `{}` on any failure).
3. Calls `build_report_context(experiment, pairs, fw_by_smiles)` — pure, no IO.
4. Downloads image bytes from URLs in the context (`_fetch_images`).
5. Calls `render_docx(ctx, lang, images)` → returns `bytes`.

**`build_report_context` in `app/eln/aggregator.py:206–249`** — takes `(experiment, list[tuple[JobSnapshot, TrialSnapshot]], fw_by_smiles)` and dispatches by `job.executor`:
- `"cc"` → `_apply_cc(ctx, trial)` (reads `trial.params["from_user"]`, `trial.params["recommended"]`, `trial.analysis`)
- `"re"` → `_apply_re(ctx, trial)` (reads `trial.params["recommended"]`)
- `"tlc"` → `_apply_tlc(ctx, trial)` (reads `trial.analysis` only — see §3 below)

**Data source: agent DB rows only.** The aggregator never queries lab-service at report time. Every field it reads comes from `TrialSnapshot.params` (JSONB column `trials.params`) or `TrialSnapshot.analysis` (column `trials.analysis`).

---

## 2. `_apply_tlc` — what it reads today

`app/eln/aggregator.py:189–203`:

```python
def _apply_tlc(ctx: ReportContext, trial: TrialSnapshot) -> None:
    """Capture the annotated TLC plate image URL (Figure 1)."""
    blob = trial.analysis or trial.result
    if not isinstance(blob, dict):
        return
    candidate = blob if "plates" in blob else blob.get("result")
    if not isinstance(candidate, dict):
        return
    try:
        tlc = TLCPlateRecognition.model_validate(candidate)
    except ValidationError as exc:
        logger.warning("ELN: TLCPlateRecognition parse failed for trial %s: %s", trial.trial_id, exc)
        return
    if tlc.plates and tlc.plates[0].boxed_pic_url:
        ctx.tlc_image_url = tlc.plates[0].boxed_pic_url
```

It reads **only `trial.analysis`** and extracts a single field: the boxed plate image URL. It does NOT read `trial.params` at all today, so the `lab_logistics.sample_tubes` list (which has `tube_id`, `box_id`, `cell`) is currently never touched by the ELN pipeline.

The `ReportContext` model (`app/eln/models.py`) has no TLC execution/tube field today. The TLC section in the report renders only the plate image (Figure 1) and TLC eluent info — the eluent comes from `_apply_cc` (the CC `from_user.solvents` / `solvent_ratio` that was also used for TLC monitoring), not from the TLC trial itself.

---

## 3. TLC lab-logistic confirm path — what agent-service stores

**TLC lab-logistics struct** — `app/events/form_payloads.py:311–330`:

```python
class TLCLabLogistics(BaseModel):
    sample_tubes: list[ObjectLocation] = Field(default_factory=list)
```

**`ObjectLocation`** — `bic_shared_types/common/object_location.py:24–35`:

```python
class ObjectLocation(BaseModel):
    tube_id: str          # e.g. "tube_2ml_017"
    box_id: str           # parent tube box
    cell: TubeCell        # row (WellRow A–D) + col (1–5)
    object_type: Literal[ObjectType.TUBE_2ML] = ObjectType.TUBE_2ML
```

`ObjectLocation` has **no `purity` field today**. It carries only physical placement identity (which tube, which box, which cell).

**Write path**: when the chemist confirms the TLC params form (confirm_kind `"params"`), `FormConfirmedEvent.apply` (`app/events/runtime_emitted.py:658–677`) writes `form_values` — the full `{from_user, recommended, lab_logistics}` dict — to `trials.params` via `tx.trials.update_fields`. So `trial.params["lab_logistics"]["sample_tubes"]` persists the list of `ObjectLocation` dicts agent-side after confirm.

**What `_apply_tlc` ignores**: even though `trial.params` holds `lab_logistics.sample_tubes`, `_apply_tlc` never reads `trial.params` at all — it only reads `trial.analysis`.

---

## 4. Source recommendation analysis

The purity field (`纯品/粗品`) does not exist anywhere in the current system. It will be introduced per the task PRD: lab-service gains `tlc_inventory.properties` (jsonb) with at least `{purity, exp_id, exp_name}`, written at tube insert time.

**Option A — portal sends purity in the confirm payload; agent-service persists it with TLC params:**

- At confirm time, the portal sends `lab_logistics.sample_tubes` enriched with a `purity` field per tube.
- Agent-service stores it in `trial.params["lab_logistics"]["sample_tubes"][*].purity` (or as a parallel list).
- `_apply_tlc` reads `trial.params["lab_logistics"]["sample_tubes"]` and populates new fields on `ReportContext`.
- **Modules that change**: `ObjectLocation` (BIC-shared-types, or a new agent-local type), `TLCLabLogistics`, `_apply_tlc`, `ReportContext`, renderer TLC section, plus `TLCLabLogistics` confirm path in portal.
- **Pattern match**: this is exactly how CC does it — `sample_cartridge_location` is stored in `trial.params["lab_logistics"]` and the ELN CC section reads `trial.params["from_user"]` / `trial.params["recommended"]`. The report stays a "deterministic aggregation of confirmed data" (Production PRD §10): purity is a chemist-confirmed fact at form-confirm time, stored agent-side, never re-queried.

**Option B — report export queries lab-service inventory read API at export time:**

- `ELNService.build_report` issues a lab-service HTTP request after the DB transaction closes (same position as `_resolve_fw` for the chem service).
- The lab-service `tlc_inventory.properties` is the source.
- **Modules that change**: `ELNService` (adds a `LabClient` dependency and a new degrade path), `_apply_tlc` / `ReportContext` / renderer (same as option A).
- **Pattern conflict**: option B violates the established pattern. The report aggregator comment (`aggregator.py:1–9`) states it is "Pure: takes already-read snapshots, returns a ReportContext. No IO." The service layer's existing external call (`_resolve_fw` for the chem client) is the sole exception and is explicitly modeled as optional enrichment that degrades silently. A second live external call for required execution data would make the report depend on lab-service availability at export time, which contradicts "deterministic aggregation of confirmed data" (PRD §10) — purity is confirmed data, not optional enrichment.
- **Also**: there is no existing pattern in `ELNService` for a required live lab-service query; introducing one creates a new failure mode (lab-service down = purity missing from report, even though the user confirmed it).

**Recommendation (with evidence)**: **Option A is the correct choice.** The evidence:

1. `FormConfirmedEvent.apply` at `app/events/runtime_emitted.py:658–677` already persists the full confirmed `{from_user, recommended, lab_logistics}` to `trial.params` — purity can ride in `lab_logistics.sample_tubes` at zero extra write cost.
2. The aggregator pattern (`app/eln/aggregator.py`) is pure / no-IO by design; option A keeps this contract intact.
3. Option B requires a `LabClient` dependency injected into `ELNService` — `app/api/dependencies.py:83–94` shows `ELNService` currently takes only `persistence`, `registry`, and `chem_client`; adding a lab client is a bigger contract change.
4. The PRD §10 "deterministic aggregation of confirmed data" means purity is sourced from agent-confirmed state (option A), not a live external read (option B).

**Caveat**: Option A requires the `ObjectLocation` type (currently in BIC-shared-types) to gain a `purity` field, OR a new agent-local type `TLCTubeAssignment` wraps `ObjectLocation` plus purity. Because `ObjectLocation` is shared-types (also consumed by the dispatch path), the cleaner path may be a new agent-local type in `app/events/form_payloads.py` that the portal sends at confirm time — the dispatch path continues to use plain `ObjectLocation`, and the ELN read uses the enriched type. This avoids touching shared-types for a report-only field.

---

## 5. Where TLC execution details render today (zh + en)

In `render_docx` (`app/eln/renderer.py:446–531`):

- **Section "03 — 反应监测 / Reaction Monitored"** (`renderer.py:502–507`): calls `_reaction_monitored(lang, ctx)` which renders `ctx.observed_rf` and `ctx.tlc_eluent` as prose. Below that prose, `_figure(doc, "Figure 1 · TLC plate", _img(ctx.tlc_image_url))` embeds the plate image. This is the natural home for new TLC execution details (sample tubes, purity assignment).
- The TLC plate image URL comes from `_apply_tlc` reading `trial.analysis.plates[0].boxed_pic_url`.
- No separate TLC section exists — TLC monitoring is woven into "Reaction Monitored" (section 03).

**zh label**: "反应监测" (section 03 heading). **en label**: "Reaction Monitored".

The new pure/crude tube info would sit in `_reaction_monitored` prose or as a sub-block between the monitored prose and Figure 1. Both `_reaction_monitored` and `_workup` use `_write_prose` / `_pick(lang, zh, en)` for bilingual output — the new field should follow the same `_pick` pattern.

---

## 6. Omit-never-fabricate pattern

`aggregator.py:1–9` documents the contract: "Specialist sections (CC/RE) parsed defensively — drift/absence logs a warning and leaves those fields `None` (→ narrative omits them)." The specific mechanism in `_apply_cc`, `_apply_re`, `_apply_tlc` is `try/except ValidationError` → log + return, leaving all ctx fields at their `None` default.

`ReportContext` fields are all `T | None = None` by default (`models.py`). The renderer checks for `None` before emitting prose (`_reaction_monitored` returns `None` if `ctx.observed_rf is None`; the render loop skips the section entirely if the builder returns `None`).

For the new purity field: if `trial.params` has no `lab_logistics.sample_tubes` purity data (e.g., tube was assigned before this feature shipped), `_apply_tlc` should set the new context field to `None`, and the renderer should omit the clause — exactly matching the existing pattern. No placeholder or invented string is ever used.

---

## Caveats / Not Found

- `ObjectLocation` has no `purity` field today. Purity does not exist anywhere in BIC-agent-service or BIC-shared-types.
- The TLC trial `params` are fully written at confirm time, but `_apply_tlc` currently ignores `trial.params` entirely and only reads `trial.analysis`. This gap is exactly where the new field needs to be wired.
- The ELN aggregator test (`tests/unit/test_eln_aggregator.py`) has no TLC-params test case — `_apply_tlc` is only exercised with a TLC analysis dict in the test file; a new test for TLC `lab_logistics` params will be needed.
- The renderer test (`tests/unit/test_eln_renderer.py`) and the integration test (`tests/integration/test_eln_endpoint.py`) do not exercise TLC lab-logistics fields.
