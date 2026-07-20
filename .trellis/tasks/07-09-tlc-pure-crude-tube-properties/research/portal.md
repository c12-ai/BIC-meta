# Research: Portal Lab-Logistic UI — TLC pure/crude tube assignment

- **Query**: Map current TLC and CC lab-logistic flows; locate insertion points for select=insert semantics and purity labels; enumerate 07-06 conflicts and Playwright breakage.
- **Scope**: internal
- **Date**: 2026-07-09

---

## Q1 — Current TLC flow

### Component map

| Component | File | Role |
|---|---|---|
| `MaterialPreparationPanel` | `src/components/workspace/material-preparation/MaterialPreparationPanel.tsx` | Top-level orchestrator: queries, maintenance state, dispatch |
| `TlcPreparationBody` | same file, line 744 | TLC-specific right-panel: wraps `SpecialItemPreparationModule` with shelf boxes and `TubeSelectorGrid` |
| `SpecialItemPreparationModule` | same file, line 1148 | Generic two-mode panel (selection / maintenance); exposes `material-maintenance-toggle` button |
| `SpecialItemMaintenanceGrid` | same file, line 869 | Renders groups of cells; in TLC maintenance these are shelf-floor groups of tube-cell buttons |
| `TubeSelectorGrid` | `src/components/workspace/forms/TubeSelectorGrid.tsx` | Renders present shelf boxes as toggle buttons; only FILLED cells with a real `tube_id` are selectable (line 183: `selectable = boxId != null && !disabled && cell.filled && cell.tube_id != null`) |
| `tubeSelectionProblem` | `src/components/workspace/forms/tlc-params-draft.ts:82` | Shape validator: one box, one row, contiguous, starts at col 1 |

### State and data flow

- Query: `sampleTubeBoxesQueryOptions(undefined, 'storage')` — `GET /lab-api/preparations/sample-tube-boxes?source=storage` — enabled only when `executor === 'tlc'` (line 132–138).
- Selected tubes live in `draftValues` under `lab_logistics.sample_tubes` as `ObjectLocation[]`.
- Accessor: `selectedSampleTubes(draftValues)` → `coerceTlcParamsForm(values).lab_logistics.sample_tubes` (`material-preparation-adapter.ts:121`).
- Updater: `withSampleTubes(values, next)` writes back into `draftValues.lab_logistics.sample_tubes` (`material-preparation-adapter.ts:124`).
- Toggle handler: `handleTubeToggle` (panel line 318) calls `toggleTubeSelection` (rolling-FIFO 4-cap) and syncs via `onSampleTubesChange`.

### Maintenance API calls (TLC tube cells)

- **Toggle a tube cell**: `PUT /lab-api/preparations/sample-tube-boxes/{boxId}/cells/{row}/{col}` with body `{ occupied: bool }` — fires `updateSampleTubeCell` from `lab-service-client.ts:283`.
- **Add/remove a shelf box slot**: `PUT /lab-api/preparations/slots/{slotId}` with `{ occupied: bool }` — fires `updatePreparationSlot`.
- Both are dispatched from the `maintenanceMutation` in the panel (line 140). On success: `invalidatePreparationCaches(queryClient)`.

### Selection feeds dispatch

`buildLabTaskParams` for `executor === 'tlc'` (adapter `material-preparation-adapter.ts:53`):
```ts
objects: form.lab_logistics.sample_tubes,   // the ObjectLocation[] list
```
Sent to `POST /lab-api/preparations/validate` and then to the agent dispatch call.

`ObjectLocation` shape (`specialist-forms.ts:166`):
```ts
{ tube_id: string, box_id: string, cell: { row: WellRow, col: number }, object_type: 'tube_2ml' }
```

No `purity` field exists today anywhere in this shape.

---

## Q2 — Current CC flow

### Components

CC does **not** use `TlcPreparationBody`. It uses `PreparationBody` (panel line 626), which renders `RackPlaneView` + `SpecialItemMaintenanceGrid`.

| Component | File | Role |
|---|---|---|
| `PreparationBody` | `MaterialPreparationPanel.tsx:626` | CC right panel: rack view for selection, rack-area groups for maintenance |
| `RackPlaneView` | `src/components/preparations/RackPlaneView.tsx` | Renders racks/areas/slots; slot clicks fire `onSlotSelect` |
| `SpecialItemMaintenanceGrid` | same file | In CC maintenance: shows rack area groups (slot cells) for sample cartridge area only (filtered to `manualRequirement.allowed_area_ids`) |

### CC selection

- Query: `rackLayoutQueryOptions()` — `GET /lab-api/preparations/racks` — enabled only when `executor === 'cc'` (line 122–127).
- Selected location lives in `draftValues.lab_logistics.sample_cartridge_location` as a string `locationId`.
- Accessor: `selectedSampleCartridgeLocation(draftValues)` (`adapter:105`).
- Updater: `withSampleCartridgeLocation(values, locationId)` (`adapter:110`).
- Handler: `handleSlotSelect` — when `!maintenanceMode && executor === 'cc'` and slot is in allowed area, calls `withSampleCartridgeLocation` (panel line 297–316).

### CC maintenance API calls

- A slot click in maintenance mode (CC sample cartridge area is `manualSlotEditable` when `manualRequirement?.allowed_area_ids.includes(area.id)`) fires:
  `PUT /lab-api/preparations/slots/{slotId}` with `{ occupied: !slot.occupied, material_key: area.material_key }` — `updatePreparationSlot`.

### CC dispatch payload

`buildLabTaskParams` for `executor === 'cc'` (adapter:44):
```ts
{ task_id, param: form.recommended, sample_cartridge_location: form.lab_logistics.sample_cartridge_location }
```

---

## Q3 — Where the new interaction fits

### What the new model needs

The new "active add-mode → click EMPTY cell → insert+assign" requires:

1. **An active add-mode state**: `addMode: 'pure' | 'crude' | null` in the TLC preparation body (or panel).
2. **Two buttons**: 添加纯品 / 添加粗品 — clicking one sets the active mode.
3. **Click handler on empty cells**: `TubeSelectorGrid` (and the empty-cell `<span>` in `SelectableTubeCell` line 189) currently renders empty cells as non-interactive `<span>` elements. These need to become `<button>` elements in "insert mode", with an `onInsert` callback.
4. **A new API call**: the current `updateSampleTubeCell` (PUT `{ occupied }`) toggles existing inventory. For "insert + assign" you need a **new API endpoint** that creates the `tlc_inventory` row with `properties: { purity, exp_id, exp_name }` AND marks the cell filled AND returns the resulting `tube_id`. The portal cannot call two existing endpoints sequentially and remain consistent; the lab-service must own this as an atomic insert-assign operation.
5. **Purity labels**: after insert, `SampleTubeCellView` returned from the API must carry `purity` (or it's embedded in a new `properties` field). The cell render in `TubeSelectorGrid` and `SpecialItemMaintenanceGrid` would show a 纯/粗 badge.
6. **Removal undo**: clicking an already-inserted tube (from this session) removes it — likely a DELETE or a `PUT { occupied: false }` on the same cell endpoint, cleaning up the inventory row this session created. Maintenance mode for removal still makes sense for tubes from other sessions.

### What is removed

- The two-step "first declare tube in maintenance mode → then select filled cell in selection mode" is replaced by a single-step click in add-mode.
- The `material-maintenance-toggle` and the `SpecialItemMaintenanceGrid` for tube-cell add/remove WITHIN the current experiment's Lab Logistic panel become redundant for the add path. However, maintenance mode for box-level operations (add box to shelf, remove empty box) and for removing tubes from OTHER experiments' assignments likely remains.

### CC parallel change

CC's empty slot in `RackPlaneView` is currently non-selectable if `!slot.occupied`. The new model means clicking an empty slot in CC inserts the sample column inventory and assigns it. This is simpler than TLC (no purity, single item), but still requires a new lab-service insert endpoint for CC.

---

## Q4 — Dispatch payload impact

Current TLC dispatch `objects` field (`buildLabTaskParams` adapter:61):
```ts
objects: form.lab_logistics.sample_tubes,  // ObjectLocation[]
```

`ObjectLocation` (`specialist-forms.ts:166`) has no `purity` field:
```ts
{ tube_id: string, box_id: string, cell: { row, col }, object_type: 'tube_2ml' }
```

**What must change**: purity is stored on the `tlc_inventory.properties` row in lab-service at insert time, not in the dispatch payload (the robot protocol has no purity parameter). The portal sends the same `objects` list (tube_id + box_id + cell) to dispatch as today. Purity is read back only for display (ELN report, labels) from the API response, not injected into the dispatch payload.

Therefore: **`buildLabTaskParams` for TLC does not change**. `ObjectLocation` does not grow a `purity` field. The dispatch payload shape is unchanged.

However, the `SampleTubeCellView` type (returned by `GET /preparations/sample-tube-boxes`) will need to expose the `properties` object (or `purity` field) so the portal can render purity labels. This is a lab-service API change and a portal type update in `lab-service-client.ts` (the `SampleTubeCellView` interface).

---

## Q5 — Conflict with 07-06 (FE lab-logistics config table)

### 07-06 files touched

From `07-06/prd.md` Constraints:
- `src/components/workspace/material-preparation/MaterialPreparationPanel.tsx`
- `src/components/workspace/material-preparation/lab-logistics-config.tsx` (NEW in 07-06)
- `src/lib/material-preparation-adapter.ts`
- `src/components/workspace/ParameterDesignPanel.tsx`
- `tests/material-preparation-layout.spec.ts`

### 07-09 files touched (portal side)

- `src/components/workspace/material-preparation/MaterialPreparationPanel.tsx`
- `src/components/workspace/forms/TubeSelectorGrid.tsx`
- `src/lib/lab-service-client.ts` (new `SampleTubeCellView.properties`, new insert API fn)
- `src/lib/lab-service-queries.ts` (new insert query/mutation)
- `src/types/specialist-forms.ts` (possibly, if `SampleTubeCellView` moved here or client type updated)
- `tests/material-preparation-layout.spec.ts`

### Overlaps

Both tasks touch:
- `MaterialPreparationPanel.tsx` — **direct overlap**
- `tests/material-preparation-layout.spec.ts` — **direct overlap**
- `material-preparation-adapter.ts` — **direct overlap** (07-06 absorbs executor branches into config entries)

### 07-06 assumptions broken by 07-09

07-06 is contracted to be **zero-behavior-change**: "DOM, network calls, gating, and copy identical before/after." This task (07-09) explicitly CHANGES behavior:

1. **TLC selection mode changes**: clicking an empty cell now calls a NEW insert API endpoint (not just toggling the local selection set). This adds a new network call path from within `TlcPreparationBody`'s selection render — which 07-06 is supposed to absorb into the config entry's `selection.render`. If 07-06 lands first, this task's new interaction must go through the `LAB_LOGISTICS_CONFIG['tlc']` entry's `selection.render` function and new maintenance action descriptors. If 07-09 lands first, 07-06 must absorb the new behavior without breaking it.
2. **`TubeSelectorGrid` changes**: the component gains new props (`addMode`, `onInsert`). 07-06 references this component from the config entry's `selection.render`; the prop change must be coordinated.
3. **`material-preparation-adapter.ts`**: 07-06 absorbs the `buildLabTaskParams` executor branches into config entries. 07-09 does NOT change `buildLabTaskParams` for TLC (dispatch payload unchanged), but adds a new insert-API helper. The overlap is low but the file is touched by both.
4. **Playwright spec**: `material-preparation-layout.spec.ts` test `'TLC material preparation selects from shelf and maintenance only shows shelf groups'` asserts that clicking `tube-cell-tube_box_2ml_l2_001-A1` (a FILLED cell) selects it (checks `validate-material-readiness` enabled, then `objects` in validation payload). This test uses **filled cells only**. The spec's existing assertions do NOT interact with empty cells, so the select=insert change on empty cells does not break existing assertions.

   However: 07-09 will add NEW spec cases for the insert flow (clicking an empty cell in add-mode). These new cases are not in conflict with 07-06's existing 7 cases.

5. **The TLC `TubeSelectorGrid`'s core invariant** — "only filled cells with real `tube_id` are selectable" (line 183) — is reversed by 07-09: empty cells become the action target in add-mode. The `pruneStaleTubeSelections` function must also be updated to handle tubes this session inserted (they may have `tube_id` from the lab-service response rather than from pre-existing inventory).

**Sequencing decision needed**: 07-06 is designed as a zero-behavior-change refactor; 07-09 is a behavior change. If 07-06 lands first, 07-09's panel work goes "through the `LAB_LOGISTICS_CONFIG` entry" as the prd.md notes. If 07-09 lands first, 07-06 must absorb the new behavior. The safest order is **07-09 after 07-06** so the config table is already present and 07-09 extends the TLC config entry with new add-mode behavior. Merging them is also viable but complicates the zero-behavior-change contract of 07-06.

---

## Q6 — Playwright specs and breakage

### Primary specs for TLC/CC lab-logistic flows

| Spec file | TLC/CC lab-logistic coverage |
|---|---|
| `tests/material-preparation-layout.spec.ts` | **Main coverage**: 6 cases covering CC rack selection, CC maintenance, TLC shelf selection, TLC maintenance groups, TLC hint text, TLC invalid-selection error; 1 case for CC params form sync |
| `tests/tlc-params-tube-selector.spec.ts` | Live E2E: drives real TLC params form → MaterialPreparation dialog → tube selection → confirm POST; asserts `lab_logistics.sample_tubes` wire shape |
| `tests/tlc-e2e-final-chain.spec.ts` | End-to-end TLC chain including dispatch |
| `tests/tlc-upload-chain.spec.ts` | TLC upload + downstream flow |
| `tests/cc-re-chained-flow.spec.ts` | CC flow including cartridge selection and dispatch |

### Patterns that break under select=insert

The key invariant in `material-preparation-layout.spec.ts` test `'TLC material preparation selects from shelf...'` (line 92):

```ts
await expect(page.getByTestId('tube-cell-tube_box_2ml_l2_001-A3')).toHaveCount(0)
```
This asserts that **empty cell A3** is NOT rendered as a button (no testid) in selection mode. Under the new model, A3 would be rendered as a button (the add-target in add-mode). The test-id format may change (`tube-cell-{boxId}-{row}{col}` currently only applies to selectable = filled cells). If the new empty-cell button reuses the same testid scheme, this assertion breaks.

Also:
```ts
await expect(page.getByTestId('tube-cell-tube_box_2ml_l2_001-A1')).toBeEnabled()
await expect(page.getByTestId('tube-cell-tube_box_2ml_l2_001-A2')).toBeEnabled()
```
These two still work (filled cells remain selectable).

The **stale-prune assertion** (`pruneStaleTubeSelections`) in the adapter and spec must be updated: if a tube was inserted this session (tube_id from the API insert response), it must survive the prune when re-fetched because the lab now returns it as filled.

### Other breakage

`tests/tlc-params-tube-selector.spec.ts` — this is a **live E2E spec**. It finds tube cells by `data-testid^="tube-cell-"` and clicks the first 3 visible selectable cells. If empty cells now also carry `tube-cell-` testids (in add-mode), the selector would pick up empty cells too. This is a **real breakage risk** if the testid scheme is shared.

---

## Files Inventory

| File | Role in this task |
|---|---|
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/components/workspace/material-preparation/MaterialPreparationPanel.tsx` | Top-level: add-mode state, new insert mutation, wire new TLC body behavior |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/components/workspace/forms/TubeSelectorGrid.tsx` | Add-mode props + empty-cell interactivity + purity label rendering |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/components/workspace/forms/tlc-params-draft.ts` | `tubeSelectionProblem` — may need to pass the selection through regardless of whether tubes were pre-existing or inserted this session |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/lib/lab-service-client.ts` | New insert API function; extend `SampleTubeCellView` with `properties` |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/lib/lab-service-queries.ts` | New insert mutation query wrapper |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/lib/material-preparation-adapter.ts` | No `buildLabTaskParams` change; `pruneStaleTubeSelections` helper may need update in `TubeSelectorGrid.tsx` if new inserts return a tube_id |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/types/specialist-forms.ts` | `ObjectLocation` unchanged; `SampleTubeCellView` (if in this file) gains `properties` |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/tests/material-preparation-layout.spec.ts` | Existing TLC fixture: `tube-cell-...-A3` absence assertion breaks; new cases for insert flow needed |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/tests/tlc-params-tube-selector.spec.ts` | Live E2E: `data-testid^="tube-cell-"` selector risks picking empty cells if testid scheme shared |

---

## Caveats / Not Found

- No existing insert-tube API endpoint exists in `lab-service-client.ts`; only `updateSampleTubeCell` (PUT `{ occupied }`) exists. The new atomic insert+assign endpoint is entirely new and must be designed with lab-service.
- `SampleTubeCellView` is defined in `src/lib/lab-service-client.ts` (around line 104). It does not currently carry a `properties` or `purity` field.
- CC's equivalent "insert sample column" path does not exist either; `updatePreparationSlot` only toggles occupancy on an existing inventory slot.
- 07-06 design.md states its config interface (`ExperimentLabLogisticsConfig`) and the `LAB_LOGISTICS_CONFIG` record — the `maintenance.slotClickAction` returns a `MaintenanceAction` descriptor. The new insert-mode is neither a maintenance action nor a selection toggle; it's a third mode that the 07-06 interface does not yet model.
