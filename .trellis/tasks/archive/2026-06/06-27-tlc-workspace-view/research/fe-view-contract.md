# Research: FE contract for the new `TlcWorkspaceView`

- **Query**: Gather the frontend contract the new `TlcWorkspaceView` must reuse (SampleTubeBoxGrid, RackPlaneView styling, renderAreaBody override, updatePreparationSlot fill/clear flow, the /consumables page wiring, the data-fetching pattern + types).
- **Scope**: internal (BIC-agent-portal)
- **Date**: 2026-06-27
- **Repo**: `/Users/drakezhou/Development/BIC/BIC-agent-portal`

All paths below are absolute. Line citations are against the working tree at portal `92ee9e1`.

---

## Findings

### Files Found

| File Path | Description |
|---|---|
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/components/preparations/SampleTubeBoxGrid.tsx` | The box→cell grid component (2mL/50mL box-area reuse target) |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/components/preparations/RackPlaneView.tsx` | The shelf/floor/area layout + styling + `renderAreaBody` override engine |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/pages/consumables/ConsumablesPage.tsx` | The `/consumables` page — where existing views are wired + where `TlcWorkspaceView` mounts |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/lib/lab-service-client.ts` | HTTP client + ALL TS types (local, hand-written — NOT shared-types) |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/lib/lab-service-queries.ts` | TanStack Query `queryOptions` + cache-invalidation helpers |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/routes/index.tsx` | `consumablesRoute` definition (`/consumables` → `ConsumablesPage`) |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/router.ts` | Route tree registration |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/lib/preparation-rack-projection.ts` | `formatRackLabel` / `formatConsumableAreaCount` helpers |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/lib/env.ts` | `LAB_API_BASE_URL` = `/lab-api` (line 3) |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/vite.config.ts` | `/lab-api` dev proxy → `:8192` (lines 9, 23-26) |
| `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/components/shell/SidebarNav.tsx` | Sidebar link to `/consumables` (lines 90-102) |

---

### 1. `SampleTubeBoxGrid` — box→cell grid component

**File**: `src/components/preparations/SampleTubeBoxGrid.tsx` (whole file, 81 lines).

**Props** (`SampleTubeBoxGridProps`, lines 4-7):
```ts
interface SampleTubeBoxGridProps {
  boxes: SampleTubeBoxView[]
  title?: string  // OMIT when rendered as a rack-area body (the area block already owns the header)
}
```

**How it renders** (lines 17-81):
- Top-level `<section>` with an outer responsive grid — one card per box SLOT the API returns, count-agnostic (line 26-29): `grid` with `gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 9rem), 1fr))'`.
- `SampleTubeBox` (lines 38-64): one bordered card per box. A **present** box is a solid card (`bg-card ring-border/70`); an **absent/empty** slot is `border-dashed … opacity-50` (lines 43-53). Inner cell grid columns come from the box's own `cols.length` (line 54) — `repeat(${box.cols.length}, …)`. Footer label is `box.label` (line 61).
- `SampleTubeCell` (lines 66-80): one `<span role="img">` per cell. **filled** → `border-success bg-success` solid + shadow; **empty** → `border-2 border-dashed border-border bg-transparent` (lines 73-78). aria-label is `${row}${col}, ${tube_id|empty}` (line 67).

**Reuse note for 2mL/50mL**: pass `boxes={...}` with NO `title` so the `RackPlaneView` area block keeps owning the header+badge. The component is entirely data-driven off `SampleTubeBoxView[]` — no hard-coded counts. (Same data shape will need to be produced by the new BE workspace endpoint for the 2mL/50mL areas.)

---

### 2. `RackPlaneView` — shelf/floor/area layout + styling

**File**: `src/components/preparations/RackPlaneView.tsx` (402 lines). This is the styling the PRD says to MATCH.

Three nested components:
- `RackPlaneView` (lines 27-73): maps `racks[]` → one `RackBoard` per rack, vertically stacked with `divide-y divide-border` (line 49).
- `RackBoard` (lines 75-176): renders ONE rack/shelf.
  - Header (lines 114-126): `display_name` (overridable via `getRackTitle`), optional code `Badge` (gated by `showRackCodeBadge`), right-aligned area-count label (`getAreaCountLabel`).
  - Board container (line 128): `rounded-[var(--radius-xl)] bg-card p-3 shadow-elevation-sm ring-1 ring-border/70`.
  - Left vertical rail + floor pills (lines 130-141): floors are rendered as `data-rack-floor` rows, each with a left-edge floor badge (`L1`/`L2`/`L3`…).
  - Floor → areas: `projectRackRows(rack.areas)` groups areas by `area.floor` then sorts floors **descending** (top shelf first: L4→L3→L2→L1; see `floorSortValue`, lines 313-338). Within a floor, areas lay out in `grid-cols-[repeat(auto-fit,minmax(min(100%,31rem),1fr))]` (line 142).
- `RackAreaBlock` (lines 178-305): renders ONE area (zone) — header with `display_name` + count badge `${available_count}/${capacity}` (line 233, overridable via `renderAreaBadge`), optional `actions` (Fill/Clear), then **either** a `customBody` (the override) **or** the default slot grid (lines 241-302).

**Styling/tone system** (`areaTone`, lines 340-376): two palettes — "sample/container" → success/green; everything else → primary/blue. Drives slot fill/empty/selected/hover classes. `slotLabel` (lines 378-387) decides the single-char glyph shown in an occupied slot (S/W/E/R/…).

**Floor convention** (lines 325-338): floors must be strings like `L1`, `L2`, `L3`. The PRD shelves (Shelf 1 L1/L2/L3, Shelf 2 L1/L2/L3) map cleanly: each shelf = one `RackView`, each floor = areas with `floor: 'L1'|'L2'|'L3'`.

---

### 3. The `renderAreaBody` override pattern

**Contract declared on `RackPlaneView`** (`RackPlaneViewProps`, lines 21-24):
```ts
/** Optional custom body for an area; when it returns non-null, it replaces the slot grid. */
renderAreaBody?: (area: RackAreaView, rack: RackView) => React.ReactNode
renderAreaBadge?: (area: RackAreaView) => string | null
```

**Where it is applied**:
- Threaded down to `RackBoard` then to each `RackAreaBlock` as `customBody` — only on the FIRST chunk of an area (`chunkIndex === 0`), `RackPlaneView.tsx:159-164`.
- In `RackAreaBlock`, `customBody ?? (<default slot grid>)` — if the override returns non-null it REPLACES the default `<Plus>`/glyph slot grid entirely (`RackPlaneView.tsx:241`).
- `renderAreaBadge` similarly overrides the `${available_count}/${capacity}` badge text (`RackPlaneView.tsx:233`, applied at `:162-164`).

**Concrete existing usage** (in `ConsumablesPage.tsx`):
```tsx
renderAreaBody={(area) =>
  area.area_code === 'sample_tube'
    ? <SampleTubeBoxGrid boxes={sampleTubeBoxesByFloor[area.floor] ?? []} />
    : null}                                            // ConsumablesPage.tsx:215-219
renderAreaBadge={(area) => {
  if (area.area_code !== 'sample_tube') return null
  const boxes = sampleTubeBoxesByFloor[area.floor] ?? []
  const filled = boxes.reduce((s, b) => s + b.filled, 0)
  const total  = boxes.reduce((s, b) => s + b.total, 0)
  return `${filled}/${total}`                          // counts derived from API data, NOT hard-coded
}}                                                      // ConsumablesPage.tsx:220-226
```

**Pattern to follow for the new view**: gate on `area.area_code` (e.g. `tlc_tube_box_2ml`, `tlc_tube_box_50ml`) → render `SampleTubeBoxGrid`; return `null` for everything else so the default slot grid applies. The new BE endpoint dictates the `area_code` strings — the FE switch keys off them.

---

### 4. `updatePreparationSlot` + the fill / clear flow

**API client** (`src/lib/lab-service-client.ts`):
- `updatePreparationSlot(slotId, payload)` → `PUT /preparations/slots/{slotId}`, body `SlotMaintenanceRequest { occupied: boolean; material_key?: string }`, returns `AreaMaintenanceResponse { area: RackAreaView }` (lines 171-174, 212-222).
- `fillPreparationArea(areaId)` → `PUT /preparations/areas/{areaId}/fill` (lines 224-230).
- `clearPreparationArea(areaId)` → `PUT /preparations/areas/{areaId}/clear` (lines 232-238).
- Base URL `env.LAB_API_BASE_URL` = `/lab-api` (env.ts:3), proxied to lab-service `:8192` (vite.config.ts:23-26). NOTE: this is a SEPARATE proxy from the agent `/api` proxy.

**Re-export layer** (`src/lib/lab-service-queries.ts:59`): `updatePreparationSlot`, `fillPreparationArea`, `clearPreparationArea` are re-exported alongside `invalidatePreparationCaches(queryClient)` (lines 48-50) which invalidates the whole `['lab-preparations']` key tree on success.

**How a slot card triggers fill vs clear** (`ConsumablesPage.tsx`):
- One TanStack `useMutation` handles a tagged-union `MaintenanceAction` (lines 30-55):
  ```ts
  type MaintenanceAction =
    | { kind: 'slot';  slotId: string; occupied: boolean; materialKey: string }
    | { kind: 'fill';  areaId: string }
    | { kind: 'clear'; areaId: string }
  ```
  `mutationFn` switches: `slot` → `updatePreparationSlot`, `fill` → `fillPreparationArea`, `clear` → `clearPreparationArea`; `onSuccess` → `invalidatePreparationCaches(queryClient)` (lines 40-55).
- **Per-slot toggle** (`handleSlotSelect`, lines 72-80): bails if `!maintenanceMode || !area.is_maintainable || isPending`; otherwise mutates `{ kind: 'slot', occupied: !slot.occupied, materialKey: area.material_key }`. Wired via `onSlotSelect` prop (line 179).
- **Area-level Fill/Clear buttons** via `renderAreaActions` (lines 185-214): only shown when `maintenanceMode && area.is_maintainable`; the Fill button mutates `{ kind: 'fill', areaId }`, Clear mutates `{ kind: 'clear', areaId }`.

**How read-only slots are rendered (the tank-lid gate)**:
- The gate is `area.is_maintainable` (`RackAreaView.is_maintainable`, lab-service-client.ts:78). When false:
  - `handleSlotSelect` early-returns → no slot toggle (ConsumablesPage.tsx:73).
  - `renderAreaActions` returns `null` → no Fill/Clear buttons (ConsumablesPage.tsx:186).
  - Inside `RackPlaneView`, a slot's `canSelect` is false unless `(maintenanceMode && area.is_maintainable)` (or it's in the explicit `maintenanceSelectable`/`selectable` sets) → the `<button>` is `disabled` and gets `cursor-default disabled:opacity-100` (RackPlaneView.tsx:250-254, 281).
- **For the new TlcWorkspaceView**: the cleanest gate is to have the BE mark the `tlc_developing_tank_lid` area `is_maintainable: false`. Then the existing `RackPlaneView` + `ConsumablesPage` logic renders it non-clickable for free — no special FE branch needed. (Confirm the BE endpoint sets this flag; PRD R2/R3 say tank-lid is read-only.)

---

### 5. The Consumable Maintenance page (`/consumables`)

- **Route**: `consumablesRoute` at `path: '/consumables'` → `component: ConsumablesPage` (`src/routes/index.tsx:47-51`); registered in the route tree at `src/router.ts:11-17`. Sidebar link at `src/components/shell/SidebarNav.tsx:90-102` (`Package` icon, label "Consumable Maintenance").
- **Page file**: `src/pages/consumables/ConsumablesPage.tsx` (236 lines).
- **How existing views are wired** (lines 35-235):
  - Two queries: `useQuery(rackLayoutQueryOptions())` (the rack/shelf layout) + `useQuery(sampleTubeBoxesQueryOptions())` (the box grid) (lines 38-39).
  - A `maintenanceMode` toggle (`useState`, line 36) flips the page between view and edit.
  - A shelf `Select` filter (`selectedRackId`, lines 37, 92-107) narrows `visibleRacks`.
  - The single `<RackPlaneView>` (lines 173-227) renders all racks, with `renderAreaBody`/`renderAreaBadge` injecting the `SampleTubeBoxGrid` for `sample_tube` areas.
- **Where `TlcWorkspaceView` would mount**: inside the `<main className="min-w-0">` block (lines 154-230), in the same `<div className="flex flex-col gap-6">` that currently wraps the single `RackPlaneView` (lines 172-228). Two viable shapes:
  1. **Standalone sibling component** `TlcWorkspaceView` rendered next to / above the existing `RackPlaneView` (e.g. its own section in that `flex-col gap-6`), itself composing a left robot block + two `RackPlaneView` shelves with the `renderAreaBody` override for the 2mL/50mL areas. This matches the PRD's "left robot block + right 2 shelves × 3 floors" layout, which the flat `RackPlaneView` alone cannot express (it has no left-panel concept).
  2. It must reuse `RackPlaneView` for the shelves (PRD: "match `RackPlaneView` styling") and reuse the same `maintenanceMode` + `MaintenanceAction` mutation wiring already present on the page.
- **Caveat**: the page currently has ONE workspace data source (racks + sample-tube boxes). The new view needs the new BE endpoint (PRD R1: `GET /preparations/tlc-workspace`). Decide whether `TlcWorkspaceView` owns its own query or the page lifts it — the existing pattern is page-owned queries passed down, but `SampleTubeBoxGrid`-style sub-data (the box→cell payload) is fetched at page level and bucketed by floor (lines 64-70).

---

### 6. Data-fetching pattern + TS types

**Library**: **TanStack Query** (`@tanstack/react-query`), NOT SWR. Confirmed: `import { useMutation, useQuery } from '@tanstack/react-query'` (ConsumablesPage.tsx:1); `queryOptions` factories in `lab-service-queries.ts`.

**Pattern** (`src/lib/lab-service-queries.ts`):
- Centralized query-key factory `preparationQueryKeys` (lines 14-21): `all = ['lab-preparations']`, `.racks()`, `.sampleTubeBoxes(floor?)`, `.requirements(taskKeys)`.
- `queryOptions()` factories: `rackLayoutQueryOptions()` (lines 23-29), `sampleTubeBoxesQueryOptions(floor?)` (lines 31-37) — both `staleTime: 10_000`.
- Mutations invalidate via `invalidatePreparationCaches(client)` → invalidates the whole `['lab-preparations']` subtree (lines 48-50). The new view should add a `tlcWorkspace` key under the same `all` prefix so the existing invalidation covers it after fill/clear.
- The box-grid endpoint specifically: `sampleTubeBoxesQueryOptions()` → `fetchSampleTubeBoxes(floor?)` → `GET /preparations/sample-tube-boxes?floor=` (lab-service-client.ts:189-197).

**TS types — LOCAL, not shared**:
- ALL response/request types are hand-written in `src/lib/lab-service-client.ts` (lines 51-174): `RackView`, `RackAreaView` (incl. `area_code`, `is_maintainable`, `capacity`, `available_count`, `floor`), `RackSlotView`, `SampleTubeBoxView`, `SampleTubeCellView`, `SlotMaintenanceRequest`, `AreaMaintenanceResponse`, etc.
- They are **NOT** imported from BIC-shared-types. The file header (lines 1-4) cites the BE Pydantic schemas as the authority and the types are kept in sync by hand:
  - `BIC-lab-service/app/api/routers/preparations.py`
  - `BIC-lab-service/app/data/schemas/preparation.py`
- The only shared-types mention in `src/` is a comment in `src/types/specialist-forms.ts:8,12` (an unrelated CC/RE param surface) — not used for preparation/rack/box types.
- **Implication for the new view**: define the new `TlcWorkspace*` response types locally in `lab-service-client.ts` (or a sibling), mirroring the new BE Pydantic schema, with the same header citation convention.

**NO FE hard-coded counts**: every count rendered comes from API fields — area badge `${available_count}/${capacity}` (RackPlaneView.tsx:233), box badge derived by reducing `box.filled`/`box.total` (ConsumablesPage.tsx:223-225), cell fill from `cell.filled`. The PRD's "real DB counts 3/3/3 · 4/3/3" must arrive from the BE endpoint, not be literals in the component.

---

## Caveats / Not Found

- **No existing left-panel / robot-block component**: `RackPlaneView` only models stacked horizontal racks (no left "Robot Workspace" block). The PRD's left robot block is NEW composition — `TlcWorkspaceView` must build it (and place the two shelves on the right). It should still reuse `RackPlaneView` for the shelves and the page's existing `maintenanceMode` + `MaintenanceAction` mutation.
- **The new BE endpoint does not exist yet** (PRD R1). The `area_code` strings the FE switch will key off, and the `is_maintainable: false` flag for the tank-lid, are owned by that endpoint. The FE contract above assumes the endpoint reuses the existing `RackView`/`RackAreaView`/`SampleTubeBoxView` shapes; verify when the BE schema lands.
- **Slot vs box duality**: occupancy for plain slots comes via `RackAreaView.slots[]` (RackSlotView), but the 2mL/50mL tube boxes use the richer `SampleTubeBoxView` box→cell shape fetched separately. The new endpoint must decide which shape each workspace area returns (likely: box shape for 2mL/50mL areas, plain slots for tip box / silica plate / tank / lid). This is a BE contract decision, not resolvable from the FE alone.
- Did not inspect `MaterialPreparationPanel.tsx` in depth — it is the workspace-pane (right chat panel) consumer of the same APIs and also uses `RackPlaneView` + `updatePreparationSlot`; it is a secondary reference if a `manualSlotEditable` style of finer-grained gating is ever needed (see its `is_maintainable` usage at lines 165, 499). Not required for this task.
