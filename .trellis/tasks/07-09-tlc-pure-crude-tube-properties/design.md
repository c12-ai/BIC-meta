# Design — TLC pure/crude tube assignment with inventory properties

Sources: `research/lab-service.md`, `research/portal.md`, `research/agent-service-eln.md`
(all 2026-07-09, file:line evidence there — this doc states decisions, not re-derived facts).

> **Post-rebase verification (2026-07-09, after Drake rebased all repos onto latest main):**
> the rebase touched only three plan-relevant files, all additively — lab-service
> `preparation_service.py` (PK-probe in inventory id minting, above our insert branch;
> `_require_slot_editable_area` anchor is now :1065), portal `tlc-params-draft.ts` (appended
> Recommend-button helpers; `tubeSelectionProblem` untouched), agent-service `form_payloads.py`
> (`TlcEvidence.plate_image_url`; `TLCLabLogistics` at :311 unchanged). Shared-types
> `ObjectLocation`, the ELN module, panel/grid/adapter, and all specs are untouched. See §8 for
> the two consequences.

## 1. Semantics: what "select = insert" means end to end

The chemist's click on an EMPTY ("white") cell records a physical act — "I placed my 纯品/粗品
tube here". Therefore:

- **Filled cells stop being selection targets.** Under the old model, selectable = filled cells.
  Under the new model, filled cells are inert/informational (they hold someone's samples); the
  action target is the empty cell, active only while an add-mode (纯品 or 粗品) is armed.
- **Insert is not rolled back on panel close.** The row reflects a physical placement, not a UI
  draft. Explicit removal (undo-click or maintenance) is the only way rows disappear.
- **"Assign to experiment"** = the tube joins the FE draft `lab_logistics.sample_tubes`; the
  lab-service learns the final selection at dispatch exactly as today (`objects` payload —
  unchanged). The `properties.exp_id/exp_name` on the inventory row is traceability metadata,
  not the assignment mechanism.

## 2. Lab-service (the only BE schema change)

**D2.1 — Column.** `tlc_inventory.properties: JSONB NULL`. New alembic revision
(`op.add_column`). Seed untouched — seed INSERT lists columns explicitly, nullable column needs
no default (research/lab-service.md §Q5). No readiness/validator breakage (§Q6).

**D2.2 — No new endpoint.** Extend the existing maintenance/insert path:
- `SampleTubeCellMaintenanceRequest` += `properties: dict | None = None`
  (`app/data/schemas/preparation.py:374`).
- `preparation_service.update_sample_tube_cell` passes it into `TlcInventoryCreate` on the
  `occupied=True` insert branch (`preparation_service.py:600–609`).
- `TlcInventoryCreate`/`TlcInventoryRead` += `properties`. `_upsert` writes it on create and
  NEVER clears it on placement-only updates (same pattern as `object_type`/`state`,
  `app/tlc/inventory.py:182`). `TlcInventoryUpdate` unchanged (insert-time only).
- Removal path is the existing `occupied=False` delete — no change.

**D2.3 — Read path.** `SampleTubeCellView` += `properties: dict | None`
(`preparation.py:229–241`), populated in `get_sample_tube_boxes` (`preparation_service.py:507`).
`tlc-workspace` inherits it via the shared view model.

**D2.4 — Properties contract** (documented in `.trellis/spec`, opaque to lab-service):
`{"exp_id": str, "exp_name": str, "purity": "pure" | "crude"}` — extensible bag, lab-service
never interprets it.

**D2.5 — CC: zero backend change.** The CC sample column lives on `consume`;
`PUT /preparations/slots/{slot_id}` already creates/deletes the row (special-item exception
path, `preparation_service.py:1065`). CC gets no purity and no properties (PRD). The CC change
is FE-only interaction semantics.

**D2.6 — Ordering validation stays FE-side (decision).** The server keeps enforcing the shape
rule (2–4, one box, one row, contiguous from col 1 — `command_validator.py:638`). The purity
ordering (pure block left, crude block right) is FE-validated only: the dispatch payload carries
no purity, and the robot doesn't consume it, so a server check would need an inventory join for
a report-only semantic. KISS. Flagged at review; can be added later without contract change.

## 3. Portal

**D3.1 — TLC add-mode interaction** (`MaterialPreparationPanel.tsx` / `TlcPreparationBody` /
`TubeSelectorGrid.tsx`):
- New state `addMode: 'pure' | 'crude' | null`; two buttons 添加纯品 / 添加粗品 (testids
  `tlc-add-pure` / `tlc-add-crude`) in the selection view of the TLC body.
- `TubeSelectorGrid` gains `addMode` + `onInsert(box, cell)` props. Empty cells render as
  buttons ONLY while `addMode` is armed (new testid scheme `tube-empty-{boxId}-{row}{col}` —
  deliberately distinct from `tube-cell-*` so the live E2E `^="tube-cell-"` selectors never
  match empty cells; research/portal.md §Q6 breakage).
- Empty-cell click → `PUT sample-tube-boxes/{box}/cells/{row}/{col}` with
  `{occupied: true, properties: {exp_id, exp_name, purity}}` → on success, append
  `{tube_id, box_id, cell, purity}` to draft `lab_logistics.sample_tubes` (tube_id read from
  the refreshed box response).
- Filled cells: no longer selectable; render purity badge (纯/粗) when
  `cell.properties.purity` present.
- Undo: clicking a tube that is in the current draft selection (this experiment's insert) →
  `PUT {occupied: false}` + drop from draft. Tubes filled but NOT in the draft are inert.
- `tubeSelectionProblem` keeps the shape validation and adds the ordering rule: within the
  selected row, every `pure` column index < every `crude` column index; ≥1 pure and ≥1 crude
  required (1st = p, last = c follows from block ordering).
- `exp_id`/`exp_name`: agent-side experiment id + display title from the workspace/session
  store already available to the panel (Q4 default).

**D3.2 — CC select-empty = insert** (`PreparationBody` / `RackPlaneView` handler): in selection
view, clicking an EMPTY slot in the allowed sample-cartridge area fires
`PUT /preparations/slots/{slotId}` `{occupied: true, material_key}` then
`withSampleCartridgeLocation(slotLocationId)`. Re-pick moves: clear the previously
session-inserted slot (`{occupied: false}`) before inserting the new one. Occupied slots stop
being selection targets. No purity UI for CC.

**D3.3 — Dispatch payload unchanged.** `buildLabTaskParams` for TLC strips `purity` and sends
plain `ObjectLocation[]` (`tube_id, box_id, cell, object_type`) — shared-types and robot
protocol untouched. CC payload unchanged.

**D3.4 — Types.** FE `ObjectLocation` in `specialist-forms.ts` stays; the draft item type
becomes `ObjectLocation & {purity?: 'pure' | 'crude'}`. `SampleTubeCellView` in
`lab-service-client.ts` += `properties`.

**D3.5 — Draft layer needs NO change.** `tlc-params-draft.ts` treats `sample_tubes` as a
pass-through: `fromValues` copies items by spread (`:38`) and `toValues` returns them verbatim
(`:63`), so `purity` survives the round-trip untouched. Note the rebase-added
`toRecommendPayload` (`:170`-ish) also carries `lab_logistics` to the agent on every Recommend
click — covered by the §8 ordering rule.

## 4. Agent-service (ELN only) — Option A (agent-side confirmed params)

Per research/agent-service-eln.md §4: the report is a deterministic aggregation of confirmed
data; purity is confirmed data, so it rides the confirm payload — no live lab-service query at
export time (that would add a required-availability failure mode and break the aggregator's
no-IO contract).

- `TLCLabLogistics.sample_tubes` item type becomes an agent-LOCAL enriched model
  (`form_payloads.py:311`): `ObjectLocation` fields + `purity: Literal["pure","crude"] | None`.
  Shared-types `ObjectLocation` untouched; dispatch path unaffected (confirm payload ≠ dispatch
  payload).
- `_apply_tlc` (`app/eln/aggregator.py:189`) additionally reads
  `trial.params["lab_logistics"]["sample_tubes"]`; `ReportContext` gains
  `tlc_sample_tubes: list[...] | None = None`.
- Renderer: section 03 反应监测 / Reaction Monitored (`renderer.py:502`) gains a short bilingual
  clause/table (cell position → 纯品/粗品) via the existing `_pick` pattern; `None` → clause
  omitted entirely (omit-never-fabricate, matches `_reaction_monitored`).

## 5. Production-PRD revision (same change set)

- Rule 8 → replaced: assignment = select-empty-slot = insert-and-assign for TLC sample tubes AND
  the CC sample column; selection of another experiment's filled cells is not a thing.
  Supersede note dated 2026-07-09.
- Rule 9 keeps the shape rule; add the purity ordering rule (pure block left, crude block right,
  any mix of counts, ≥1 each).
- Rule 10 TLC row: 样品管 becomes "×2–4 with per-tube 纯品/粗品 declared at placement".
- Acceptance criteria: replace "Selecting an item for a task never creates inventory…" with the
  new semantics; add purity-persistence and ELN lines. UI Interaction Requirements: TLC Lab
  Logistic panel gains the two add-buttons flow.
- Consumable Maintenance page stays read-only for specific items (rule 7 unaffected).

## 6. Sequencing vs 07-06 (held FE config-table refactor)

Decision: **07-09 lands first.** 07-06 is HELD with a zero-behavior-change contract; blocking a
product feature on a held refactor inverts priorities. 07-06 must re-baseline afterwards (its
config interface needs a third interaction mode — add-mode — beyond selection/maintenance;
research/portal.md §Q5). I will add a note to 07-06's prd.md pointing at this task.

## 7. Test impact (from research/portal.md §Q6 + repo gates)

- `material-preparation-layout.spec.ts`: TLC selection case rewrites (filled-cell selection is
  gone; empty-cell add-mode flow is the new canonical interaction); the `toHaveCount(0)`
  empty-cell assertion updates to the new `tube-empty-*` scheme; CC case gains the empty-slot
  insert path. New cases: pure/crude ordering validation, purity badge render, undo.
- `tlc-params-tube-selector.spec.ts` (live E2E): rewrite tube acquisition to add-mode flow.
- Lab-service: unit tests for properties write/preserve/read; migration; existing suite green.
- Agent-service: aggregator unit test for `_apply_tlc` params path (present + absent), renderer
  zh/en case.
- Full gates per repo (ruff/pyright/pytest; pnpm typecheck/lint/test; focused Playwright).

## 8. Cross-repo landing order (post-rebase finding — agent BEFORE portal)

Two verified facts force the order:

- Shared-types `ObjectLocation` is a plain `BaseModel` — default `extra="ignore"`
  (`bic_shared_types/common/object_location.py:24`). An early `purity` key never 422s; it is
  **silently dropped** wherever the agent round-trips the payload through models. Silent loss,
  not a loud failure.
- `FormConfirmedEvent.apply` persists the RAW `form_values` dict
  (`runtime_emitted.py:667`: `update_fields["params"] = dict(self.form_values)`), but the
  specialist entry-pipeline / draft-merge paths (touched by the rebase) can normalize
  `lab_logistics` through `TLCLabLogistics` (`extra="forbid"` at its level, item type
  `ObjectLocation`) on later turns — purity could be stripped in cross-turn re-entry even if
  the first write kept it.

Therefore the landing order is: **lab-service → agent-service (enriched item type) → portal
(send purity)**. The agent lane also audits every TLC `lab_logistics` parse point
(`TLCLabLogistics` references, `_entry_pipeline` draft merge, `specialists/tlc.py`) so purity
survives every normalization, including the new Recommend payload.

## Rollback shape

Single feature, three repos, each independently revertable: lab-service migration is additive
(nullable column — down-revision drops it); portal and agent-service changes are behind no flag
but revert cleanly per repo. No data backfill required. The §8 order also makes partial landing
safe: agent-service accepting `purity` before any producer sends it is a no-op.
