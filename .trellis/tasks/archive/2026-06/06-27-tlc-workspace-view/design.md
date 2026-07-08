# Design — TLC Workspace view on the Consumable Maintenance page

> Read `prd.md` first (requirements + locked decisions D1–D4 + R5 result).
> Grounded in `research/r5-robot-completion-trace.md`, `research/be-box-grid-contract.md`,
> `research/fe-view-contract.md`. Spec authority: `.trellis/spec/backend/tlc-placement.md` §6/§6a/§6b.

## 1. Scope & boundaries

This is a **read layer over existing writes** plus a small fill/clear extension. The robot
already authors Workspace occupancy on completion (R5 = YES via `PlacementWriter`, not the
`log_handler.py` path the PRD guessed). Three layers touched:

- **BIC-lab-service** (BE): one new read endpoint + extend the existing slot-PUT to recognise
  Workspace slot ids.
- **BIC-agent-portal** (FE): one new `TlcWorkspaceView` composing the existing `RackPlaneView`
  + `SampleTubeBoxGrid`, mounted on `/consumables`.
- **BIC-shared-types**: none — FE types are local in `lab-service-client.ts` (by existing
  convention), kept in sync with BE Pydantic by hand.

Explicitly NOT touched: robot slot ids/bounds (silica stays 4), `SlotId` codec, `planner.py`
`Field(le=…)`, the TLC-params work (`TlcParamsForm.tsx` etc.), any locking/pre-dispatch check.

## 2. The two distinct slot sets (do not conflate — §6a)

| Set | LocationType(s) | Used by | This task |
|---|---|---|---|
| **TLC Rack** (storage/display) | `tlc_rack_box_2ml_slot` | existing `GET /preparations/sample-tube-boxes` | untouched |
| **TLC Workspace** (robot dispatch) | the 6 `tlc_*_slot` (2mL/50mL/tip/silica/tank/lid) | new endpoint | **this task reads these** |

Occupancy of a Workspace slot is **direct**: `tlc_inventory.location_id = <slot id>`
(`what_at(slot.id)`), because the `locations` rows ARE the real placement addresses — unlike the
positional RackArea bridge. Counts are DB-driven (`len(get_by_type(...))`): 3/3/3 · 4/3/3.

## 3. Backend design

### 3.1 New read endpoint (R1)

`GET /preparations/tlc-workspace` → `PreparationService.get_tlc_workspace()`.

Thin router in `app/api/routers/preparations.py` (mirror `get_sample_tube_boxes`, lines 52–62):
`response_model`, no logic, delegate to the service.

**Response envelope — reuse `RackView` / `RackAreaView` / `RackSlotView`** (already FE-modelled),
extended with a robot block + the box→cell payload for the two tube-box areas. Concretely:

```
TlcWorkspaceResponse {
  robot_block: TlcRobotBlockView      # display-only (D4): 操作台 + 废弃区 occupancy
  shelves: list[RackView]             # Shelf 1 + Shelf 2, each areas grouped into 3 floors
  tube_boxes: list[SampleTubeBoxView] # box→cell payload for the 2mL + 50mL areas (D3)
}
```

- Each shelf is one `RackView{ code, display_name, areas: [RackAreaView] }`.
  - **Shelf 1:** floor `L1` = `tlc_tube_box_2ml` (3 slots), `L2` = `tlc_tube_box_50ml` (3),
    `L3` = `tlc_tip_box` (3).
  - **Shelf 2:** `L1` = `tlc_silica_plate` (4), `L2` = `tlc_developing_tank` (3),
    `L3` = `tlc_developing_tank_lid` (3).
- `RackAreaView.area_code` carries the FE switch key (e.g. `tlc_tube_box_2ml`, …). The 2mL/50mL
  areas additionally have their box→cell data in `tube_boxes` (bucketed by `area_code`/floor on FE).
- `RackAreaView.is_maintainable`: **`false` for `tlc_developing_tank_lid`** (D3/R3 read-only gate),
  `true` for all other shelf areas. This single flag drives the FE non-clickable behaviour with no
  special FE branch (research §4).
- `RackSlotView.occupied` per slot from `what_at(slot.id)`; `display_label` = `f"{i:02d}"`.
  Box areas (2mL/50mL) may keep their slots minimal (presence) since the cell grid renders via
  `tube_boxes`; tip/silica/tank/lid render as plain occupied/empty cards (D3).
- `display_name`: English, matching convention (e.g. "2 mL Tube Box", "Silica Plate",
  "Developing Tank", "Developing Tank Lid", "Tip Box", "50 mL Tube Box"). The `locations` rows have
  no display_name, so the service supplies these per area (research §6).

New Pydantic models live in `app/data/schemas/preparation.py` next to the existing views.
**DB-driven counts only** — area capacity = `len(get_by_type(<LocationType>))`, never a literal.

### 3.2 Service method shaping

`get_tlc_workspace()` (template: `get_sample_tube_boxes`, `preparation_service.py:289–360`):

1. For each of the 6 Workspace `LocationType`s: `locations.get_by_type(type)` → sort by slot index.
2. Per slot: `tlc_inventory.what_at(slot.id)` → occupant (occupied/free, D2).
3. For 2mL/50mL: drill `tlc_inventory.contents(box.id)` to build `SampleTubeCellView[]` (reuse the
   box-grid cell logic; axes from `box_grid(ObjectType.TUBE_BOX_2ML / TUBE_BOX_50ML)`).
4. Robot block: read `what_at("ws_bic_09_wb_001")` + `what_at("ws_bic_09_wb_002")` → display-only view.
5. Assemble two `RackView` shelves + `tube_boxes` + `robot_block`.

No write here. No commit (read path).

### 3.3 Extend slot-PUT for Workspace (R3, D1)

The existing `PUT /preparations/slots/{slot_id}` → `update_slot` resolves a **`RackSlot`** and 404s
on a raw Workspace `locations` id (be-box-grid §4 caveat). D1: extend the flow to recognise a
Workspace slot id and write `tlc_inventory` directly.

- In `update_slot` (`preparation_service.py:458`): if `slot_id` is not a `RackSlot` but matches a
  Workspace slot `LocationType`, route to a new branch that:
  - **fill** (`occupied=true`): insert one `tlc_inventory` row with `location_id = slot_id`,
    `object_type` derived from the slot's `LocationType` (the placed object: box/plate/tank/tip).
    Reuse `TlcMaintenanceBridge` semantics — extend the bridge with a `fill_at(slot_id)` /
    `clear_at(slot_id)` pair that writes/deletes by `location_id` (vs the existing
    `fill_one`/`clear_one` which are slot-less + positional). This mirrors how `PlacementWriter`
    authors `location_id` on robot completion (R5), keeping one write convention.
  - **clear** (`occupied=false`): delete the `tlc_inventory` row at `location_id = slot_id`.
- Response: the recomposed view. Two options — return the full `TlcWorkspaceResponse` area, or
  reuse `AreaMaintenanceResponse{area: RackAreaView}`. **Choose `AreaMaintenanceResponse`** to keep
  the FE mutation path identical (it already expects `{area}`); the FE then invalidates the
  workspace query to refresh box→cell payloads.
- `material_source` stays `tlc_inventory`; one-way bridge dependency preserved (BE never imports the
  prep service into `app/tlc/*`).

Tank-lid: `is_maintainable=false` already blocks the FE from issuing the PUT; BE additionally
rejects a write to a `tlc_developing_tank_lid_slot` defensively (fail loud, not silent).

## 4. Frontend design

### 4.1 New component `TlcWorkspaceView`

`src/components/preparations/TlcWorkspaceView.tsx`. Composition (research §5 caveat: `RackPlaneView`
has no left-panel concept, so the left block is new composition):

```
<section>                              # the whole workspace view
  <RobotWorkspaceBlock .../>           # left: 操作台 + 废弃区, display-only (D4)
  <div>                                # right: two shelves
    <RackPlaneView racks={[shelf1]} renderAreaBody=… renderAreaBadge=… .../>
    <RackPlaneView racks={[shelf2]} .../>
  </div>
</section>
```

- **Reuse `RackPlaneView`** for both shelves (PRD: match its styling). Floors map cleanly to
  `L1/L2/L3` (rendered top-first per `floorSortValue`).
- **`renderAreaBody`** keyed on `area.area_code`: `tlc_tube_box_2ml` / `tlc_tube_box_50ml` →
  `<SampleTubeBoxGrid boxes={byArea[area.area_code]} />` (NO `title`); everything else → `null`
  (default plain slot grid renders — D3). Mirror `ConsumablesPage.tsx:215–226`.
- **`renderAreaBadge`** for the box areas: derive `${filled}/${total}` by reducing `box.filled` /
  `box.total` (research §3) — never a literal.
- **Tank-lid read-only**: comes for free from `area.is_maintainable === false` (research §4); no FE
  branch.
- **`RobotWorkspaceBlock`**: a small new presentational component showing the two robot locations'
  occupancy, no actions (D4). Plain card matching `RackPlaneView` board styling.

### 4.2 Page wiring (`ConsumablesPage.tsx`)

- Add a query `tlcWorkspaceQueryOptions()` (TanStack, `staleTime: 10_000`) + key
  `preparationQueryKeys.tlcWorkspace()` under the existing `all = ['lab-preparations']` prefix so
  `invalidatePreparationCaches` already covers it after fill/clear (research §6).
- Mount `<TlcWorkspaceView>` inside the existing `<main>` `flex flex-col gap-6` block
  (`ConsumablesPage.tsx:172–228`), reusing the page's `maintenanceMode` + the single
  `MaintenanceAction` `useMutation` (pass `onSlotSelect` / `renderAreaActions` down, same contract).
- Slot fill/clear flows through the **unchanged** `updatePreparationSlot` client (D1) →
  `{ kind: 'slot', occupied: !slot.occupied, materialKey: area.material_key }`.

### 4.3 Types

New `TlcWorkspaceResponse` / `TlcRobotBlockView` types added **locally** in
`src/lib/lab-service-client.ts` (header cites the BE Pydantic source), reusing the existing
`RackView` / `RackAreaView` / `RackSlotView` / `SampleTubeBoxView`. No BIC-shared-types changes.

## 5. Data flow (occupied/free, D2)

```
robot finishes run → #.result → PlacementWriter writes tlc_inventory.location_id   (existing, R5)
chemist fill/clear → PUT /preparations/slots/{wsSlotId} → bridge.fill_at/clear_at   (new, D1)
                          ↓ writes/deletes tlc_inventory row by location_id
GET /preparations/tlc-workspace → what_at(slot.id) → occupied/free + box cells       (new, R1)
                          ↓
TlcWorkspaceView renders shelves + robot block; tank-lid non-clickable
```

A slot is **occupied** iff a `tlc_inventory` row exists at its `location_id`. No `state` is read or
written for Workspace slots (D2 — `state` deferred per R5).

## 6. Contract / spec impact (Rule 10)

This adds a new cross-service contract (FE ↔ lab-service): the `GET /preparations/tlc-workspace`
response shape + the extended slot-PUT accepting Workspace slot ids. **Update
`.trellis/spec/backend/tlc-placement.md`** with a new subsection (e.g. §6c) documenting:
- the Workspace read endpoint (the 6 slot types it reads, occupied/free occupancy, DB-driven counts);
- the extended slot-PUT (`fill_at`/`clear_at` by `location_id`, tank-lid rejected);
- the explicit Rack-vs-Workspace distinction reaffirmed (§6a still holds).
Spec update is part of the same change set (Rule 10), done in Phase 3.3.

## 7. Trade-offs & alternatives considered

- **Reuse `RackView`/`RackAreaView` vs a bespoke shape.** Chosen reuse: maximises FE reuse (the
  switch, the gate, the slot card all already exist), at the cost of a slightly loaded envelope
  (`tube_boxes` carried alongside areas). Bespoke shape would duplicate FE rendering — rejected.
- **Extend slot-PUT (D1) vs expose Workspace as RackAreas vs new PUT.** D1 chosen by Drake: smallest
  surface, single `tlc_inventory` write convention shared with `PlacementWriter`. RackArea exposure
  risks §6a conflation; a separate PUT duplicates fill/clear + adds an FE mutation path.
- **Occupied/free (D2) vs used/disposed.** DB only authors `location_id` on Workspace slots; surfacing
  `state` would require faking it or extending `PlacementWriter` (PRD-deferred) — rejected.
- **Robot block display-only (D4).** "Filling" 操作台/废弃区 has no defined consumable semantics; wiring
  writes would invent a half-defined contract — deferred.

## 8. Risks / rollback

- **Risk:** extending `update_slot` could regress the existing RackSlot path. Mitigation: branch only
  when `slot_id` resolves to a Workspace `LocationType` AND no `RackSlot` matches; existing path
  untouched; cover with a test (fill→read→clear on a real Workspace slot).
- **Risk:** tip-box slots are not seeded (allocator mints them) — they read empty until a run/fill.
  Expected; not a bug. Note in implement validation so it isn't mistaken for a wiring failure.
- **Rollback:** the endpoint + component are additive; reverting the FE mount + BE route removes the
  feature with no migration. The slot-PUT extension is behind the Workspace-id branch — revert that
  branch to restore prior behaviour.

## 9. Acceptance mapping

| AC (prd) | Covered by |
|---|---|
| Endpoint returns robot block + 2 shelves × 3 floors, real counts 3/3/3·4/3/3, live occupancy | §3.1, §3.2 |
| Page renders layout; tank-lid read-only, else manageable; CDP-verified | §4, gate via `is_maintainable` |
| Fill/clear changes Lab Service DB (before/after) | §3.3 (D1), §5 |
| R5 documented | DONE — prd.md "R5 result" + research file |
| BE ruff + pyright + pytest green; FE typecheck + biome | implement.md validation |
