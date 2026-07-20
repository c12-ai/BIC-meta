# Research: BIC-agent-portal TLC Surfaces

- **Query**: TLC rack/tube-box surface, workbench areas, developing tank in UI (R1 + R2)
- **Scope**: internal
- **Date**: 2026-07-10

## Summary

The Consumable Maintenance page renders TWO distinct sections:

1. **TLC Rack** (the chemist-facing shelf) — from `GET /preparations/racks`, rendered by `RackPlaneView`. Areas whose `area_code === 'sample_tube'` replace the flat slot strip with the `SampleTubeBoxGrid` box→cell grid. The TLC Rack is currently the chemist surface for tube-box stock.
2. **TLC Workspace** (the robot's working bench) — from `GET /preparations/tlc-workspace`, rendered by `TlcWorkspaceView` **below** the TLC Rack. Shows a left `RobotWorkspaceBlock` (read-only bench/disposal slots) + a right merged `RackPlaneView` (Shelf 1 + Shelf 2 combined), where 2mL/50mL tube-box areas use `SampleTubeBoxGrid` and tip/silica/tank/lid areas render plain slot cards.

The developing tank (`tlc_developing_tank`) appears in the TLC Workspace's right merged-rack section (via the `/preparations/tlc-workspace` endpoint's `shelves`). It renders as a plain slot card labeled 'D'. There is **no** chemist surface today for declaring what is inside a developing tank (no contents/solvent input). The tank lid (`tlc_developing_tank_lid`) is `is_maintainable=false` at the BE so it renders non-clickable; the tank area itself may be maintainable (click-to-toggle) but carries no content properties.

The Material Preparation right panel (TLC executor) shows only storage-source sample-tube boxes — it fetches `GET /preparations/sample-tube-boxes?source=storage` and renders them through `TubeSelectorGrid` (which has the 添加纯品/添加粗品 add-mode insert pattern). It does **not** render any rack or workspace area.

---

## Q1 — Consumable Maintenance page

**Component**: `ConsumablesPage` at `src/pages/consumables/ConsumablesPage.tsx:39`

**Area/rack layout source**: `GET /preparations/racks` → `RackLayoutResponse { racks: RackView[] }`. Each `RackView` has `areas: RackAreaView[]`. No hardcoded area IDs in the portal; everything comes from the API response. The `rackLayoutQueryOptions()` call at line 43 fetches this.

**TLC sample-tube boxes today**:
- Areas with `area_code === 'sample_tube'` (`ConsumablesPage.tsx:229`) get the `SampleTubeBoxGrid` (from `GET /preparations/sample-tube-boxes`, bucketed by `box.floor`).
- Boxes for L2 vs L1 are separated by `box.floor` value and go to the right `area_code === 'sample_tube'` area on that floor.
- This is the **TLC Rack** (the chemist-facing shelf), not the workbench.

**Is there a "TLC Workspace" / workbench area rendered?** Yes — `TlcWorkspaceView` is rendered at `ConsumablesPage.tsx:241-251`, sourced from `tlcWorkspaceQueryOptions()` → `GET /preparations/tlc-workspace`. The component is visually placed **below** the TLC Rack. Inside it, the left column shows the robot block (display-only); the right column shows a merged rack with all workspace shelf areas including tank, lid, tip, silica, and 2mL/50mL tube-box areas.

**Editability by area in Consumable Maintenance**:
- TLC Rack `sample_tube` areas: replaced by the box→cell `SampleTubeBoxGrid` which is **read-only** on the Consumable Maintenance page (no click handler passed; `is_maintainable` is `false` for specific items per PRD rule 7). The `renderAreaBody` branch skips the slot grid entirely.
- Other rack areas (tip boxes, silica columns, waste drums, etc.): `is_maintainable=true` areas become editable slot buttons in maintenance mode. `handleSlotSelect` gates on `maintenanceMode && area.is_maintainable` (line 79).
- TLC Workspace: `tlc_developing_tank_lid` is explicitly `is_maintainable=false` per BE (comment at `TlcWorkspaceView.tsx:35`). The tank itself may be maintainable slot-wise.
- Maintenance mode toggled by the upper-right "Enter Maintenance Mode" / "Exit" button (`ConsumablesPage.tsx:143-157`). The fill/clear area-level buttons only appear for `area.is_maintainable === true` areas.

---

## Q2 — TLC Lab Logistic / Material Preparation right panel

**Component**: `MaterialPreparationPanel` at `src/components/workspace/material-preparation/MaterialPreparationPanel.tsx`

When `executor === 'tlc'`, the panel renders `TlcPreparationBody` (line 497-509).

**What the right panel fetches and renders**:
- `sampleTubeBoxesQueryOptions(undefined, 'storage')` — i.e. `GET /preparations/sample-tube-boxes?source=storage` (line 134-135). This is the **shelf storage** source, not the bench.
- These boxes are passed to `TubeSelectorGrid` (via `TlcPreparationBody → TubeSelectorGrid`).
- The `TubeSelectorGrid` renders the box→cell grid with 添加纯品/添加粗品 armed-mode insert buttons.

**Does anything reference a workbench area or workbench slots here?**
No. The comment at line 132-133 explicitly states: "The bench 2ml slot is robot-internal parking; the chemist never sees it here." No rack is fetched for TLC executor (rack fetch is gated `enabled: executor === 'cc'` at line 131). No workspace area IDs are referenced.

**CC right panel** (for completeness, asked about lab logistic surface):
- Fetches `rackLayoutQueryOptions()` (`enabled: executor === 'cc'`) and renders `PreparationBody → RackPlaneView` scoped to `manualRequirement.allowed_area_ids` (which comes from the BE requirements endpoint, so no hardcoded area IDs in the portal for CC either).

---

## Q3 — Developing tank in UI today

**Where the developing tank appears**: It shows up only in the TLC Workspace section of the Consumable Maintenance page (the component `TlcWorkspaceView`). The workspace data comes from `GET /preparations/tlc-workspace` → `TlcWorkspaceResponse.shelves` (a list of `RackView`s for Shelf 1 + Shelf 2).

**Rendering**: Inside `TlcWorkspaceView`, areas with `area_code` in `_BOX_GRID_AREA_CODES` (`tlc_tube_box_2ml` / `tlc_tube_box_50ml`) get `SampleTubeBoxGrid`; all others (including `tlc_developing_tank` and `tlc_developing_tank_lid`) fall through to `RackPlaneView`'s default plain slot grid. The slot label function `slotLabel` in `RackPlaneView.tsx:424-425` maps `material_key === 'tlc_developing_tank'` → `'D'` and `material_key === 'tlc_developing_tank_lid'` → `'D'`.

**Placement/declare by user**: There is **NO** way for the chemist to declare what is inside a developing tank via the current UI. The plain slot card only shows occupied/empty state (toggled in maintenance mode if `is_maintainable=true`). No content properties (solvent system, ratio, or "empty" state) exist anywhere in the portal for the tank.

**Tank lid**: `is_maintainable=false` (hardcoded from BE; `TlcWorkspaceView.tsx:35`). No click handler fires.

**Readiness cards**: The developing tank appears as a physical inventory item to check (via the workspace view), but there is no `RequirementView` card for it in the Material Preparation requirements panel (PRD rule 10 says workspace-resident items like the developing tank are not user-assigned per task).

---

## Q4 — Area naming / IDs the portal knows

**The portal uses NO hardcoded area IDs** (UUIDs from the DB). All area filtering is API-driven:
- Consumable maintenance: renders whatever `GET /preparations/racks` returns.
- CC right panel: filters by `requirement.allowed_area_ids` from `GET /preparations/requirements`.
- TLC Material Prep: doesn't filter by area ID at all; shows `source=storage` boxes.

**Area codes the portal branches on** (hardcoded strings in source):
- `'sample_tube'` — `ConsumablesPage.tsx:229,234` — determines whether `SampleTubeBoxGrid` replaces slot strip in TLC Rack main view.
- `'tlc_tube_box_2ml'` and `'tlc_tube_box_50ml'` — `TlcWorkspaceView.tsx:17` — determines whether `SampleTubeBoxGrid` replaces slot strip in TLC Workspace view.

**Material keys with portal-level display branches** (from `RackPlaneView.tsx:420-434` and `localized-display-name.ts`):
- `tlc_developing_tank` → label 'D', zh name '展开缸'
- `tlc_developing_tank_lid` → label 'D', zh name '展开缸盖'
- `tlc_tip_box` → label 'T'
- `tlc_silica_plate` → zh '硅胶板'
- `tlc_tube_box_2ml` → zh '2 mL 试管盒'
- `tlc_tube_box_50ml` → zh '50 mL 试管盒'
- `sample_tube` → zh '样品管'
- `operating_bench` → zh '操作台'

**Rack/workspace naming in UI labels**:
- zh: `'TLC Rack': 'TLC 架'` (`localized-display-name.ts:44`) — the rack name comes from the API's `display_name`; this is a display fallback.
- `preparations.tlcWorkspace` i18n key → zh: "TLC 工作台", en: "TLC Workspace" (`locales/{zh,en}/translation.json:1121`).
- No "架子" (shelf as a Chinese name) appears in the portal source; the shelf concept is referred to as "TLC Rack" / "TLC 架" (the full rack structure) or the `sample_tube` `area_code`.
- No "工作台" text is hardcoded in components other than the i18n key value. The TlcWorkspaceView renders it via `t('preparations.tlcWorkspace')`.

---

## Q5 — Delta analysis for R1 and R2

### R1: Move tube boxes from workbench area to rack (架子/shelf)

**Current state**: The TLC Workspace (`TlcWorkspaceView`) shows the 2mL and 50mL tube-box areas using `area_code` values `'tlc_tube_box_2ml'` / `'tlc_tube_box_50ml'`. The TLC Rack section (main `RackPlaneView` in `ConsumablesPage`) shows the `sample_tube` area with `SampleTubeBoxGrid`. These two hardcoded `area_code` values in `TlcWorkspaceView.tsx:17` (`_BOX_GRID_AREA_CODES`) are the only portal-side branch that distinguishes box-grid from slot-grid in the workspace.

**If tube boxes move to a different area in the lab config**:
The only hardcoded portal constants that would break are:
1. `area_code === 'sample_tube'` in `ConsumablesPage.tsx:229,234` — if the new rack area code changes, the `SampleTubeBoxGrid` won't replace the slot strip.
2. `_BOX_GRID_AREA_CODES = new Set(['tlc_tube_box_2ml', 'tlc_tube_box_50ml'])` in `TlcWorkspaceView.tsx:17` — if the workspace area codes change, the box-grid won't render in the workspace.
3. `SampleTubeBoxesSource = 'storage' | 'bench'` in `lab-service-client.ts:246` and the `?source=storage` query in `MaterialPreparationPanel.tsx:135` — if "rack" becomes a new source type on the lab-service API, the portal needs to add that source option.
4. i18n display names in `localized-display-name.ts` — no functional breakage, just display.

**Note**: The PRD and existing code comments already distinguish the TLC Rack (chemist surface, `source=storage`) from the TLC Workspace bench (robot-internal). If R1 means renaming or reorganizing the BE area structure from `sample_tube` → some new area code, the two `area_code === 'sample_tube'` branches in `ConsumablesPage.tsx` must be updated. If it means adding a new rack view (a dedicated "架子" endpoint), the Consumable Maintenance page would need a new query + render block alongside `RackPlaneView` and `TlcWorkspaceView`.

UNVERIFIED: Whether the lab-service already exposes a dedicated "TLC Rack" (架子) area in `/preparations/racks` with a distinct area code, or whether what is currently called the TLC Rack in the portal IS the 架子 and the re-scoping only affects which physical areas render in the Workspace section vs. the main rack section.

### R2: Declaring developing tank contents (solvent system + ratio)

**Where it would naturally live**: The developing tank appears in `TlcWorkspaceView` as a plain slot card. The existing add-mode button pattern (`addMode === 'pure' | 'crude'` arms empty cells for TLC tube assignment) provides a direct analogy. For tank contents:
- An "armed fill" button (e.g. "Record Solvent System" / "Empty Tank") could arm the tank slot for click-to-declare, similar to the 添加纯品/添加粗品 buttons in `TlcPreparationBody`.
- The click would call a new lab-service endpoint (likely `PUT /preparations/tlc-workspace/tank/{tank_id}/contents` or similar) with `{ solvent_system: string, ratio: string } | { empty: true }`.
- The tank slot would need to surface the recorded contents (as text or badge on the slot card), which today shows only 'D' and occupied/empty state.
- No `TubeCellProperties` equivalent exists for tank areas today — the `RackSlotView.item` shape (`SlotItemView`) has no content properties field; adding tank contents would require either a new endpoint or extending `SlotItemView` with optional `properties`.

**Alternatively**, the declare pattern could live in the Consumable Maintenance page's maintenance mode only (not per-task), since the developing tank is a workspace-resident item not user-assigned per task (PRD rule 10 footnote). This would keep the tank surface out of Material Preparation.

---

## Files Found

| File Path | Description |
|---|---|
| `src/pages/consumables/ConsumablesPage.tsx` | Consumable Maintenance page; renders TLC Rack + TLC Workspace; main page component |
| `src/components/preparations/TlcWorkspaceView.tsx` | TLC Workspace (robot bench) view; shows tank, lid, tip, silica, 2mL/50mL boxes |
| `src/components/preparations/RackPlaneView.tsx` | Generic rack/area/slot renderer; hardcodes material_key → label 'D' for developing tank |
| `src/components/preparations/SampleTubeBoxGrid.tsx` | Read-only box→cell grid; used both in TLC Rack (consumable page) and Workspace |
| `src/components/workspace/material-preparation/MaterialPreparationPanel.tsx` | TLC Material Prep right panel; fetches source=storage boxes; renders TubeSelectorGrid |
| `src/components/workspace/forms/TubeSelectorGrid.tsx` | Add-mode insert grid; 添加纯品/添加粗品 arms empty cells; no tank/area surface |
| `src/lib/lab-service-client.ts` | All lab-service API types; `SampleTubeBoxesSource = 'storage'|'bench'`; TLC types |
| `src/lib/lab-service-queries.ts` | Query options; `sampleTubeBoxesQueryOptions`, `tlcWorkspaceQueryOptions` |
| `src/lib/localized-display-name.ts` | zh display name map; 'TLC Rack' → 'TLC 架'; tlc_developing_tank → '展开缸' |
| `src/lib/preparation-rack-projection.ts` | `formatRackLabel`, `formatConsumableAreaCount` utilities |
| `src/locales/en/translation.json:1109-1124` | i18n keys for preparations; tlcWorkspace → "TLC Workspace" |
| `src/locales/zh/translation.json:1121` | tlcWorkspace → "TLC 工作台" |

## Caveats / Not Found

- UNVERIFIED: The actual lab-service API response shape for `/preparations/racks` vs `/preparations/tlc-workspace` area codes — specifically whether the "TLC Rack" (架子) and "TLC Workspace bench" are already separate in the BE response, or whether the frontend currently shows both under one merged view.
- UNVERIFIED: Whether `is_maintainable=true` or `false` for the `tlc_developing_tank` area slot (the tank lid is explicitly `false` per code comment; the tank itself is not explicitly stated in the portal source — this is a lab-service config detail).
- The lab-spatial-prototype page (`src/pages/lab-spatial-prototype/`) has its own `PreparationMaterialConcept` type with `areaCode: 'sample_tube'` (line 218) — this is a prototype/demo page, not the production Consumable Maintenance page.
