# Research: BE box-grid contract the TLC Workspace endpoint must mirror

- **Query**: Document the existing TLC Rack / box-grid BE contract (router, service, models, RackArea concept, PUT fill/clear flow, layering convention, seed) so the new `GET /preparations/tlc-workspace` endpoint can mirror it.
- **Scope**: internal (BIC-lab-service, with FE call-site cross-ref in BIC-agent-portal)
- **Date**: 2026-06-27
- **Repo**: `/Users/drakezhou/Development/BIC/BIC-lab-service` (prior TLC Rack box-grid task committed at `901e849`)

---

## 0. TL;DR contract to mirror

| Concern | Existing (TLC Rack box grid) | New endpoint must |
|---|---|---|
| Read endpoint | `GET /preparations/sample-tube-boxes[?floor=L2]` | add `GET /preparations/tlc-workspace` |
| Service method | `PreparationService.get_sample_tube_boxes(floor)` | add a `get_tlc_workspace()` method |
| Response model | `SampleTubeBoxesResponse` → `SampleTubeBoxView` → `SampleTubeCellView` | add typed Pydantic models in `app/data/schemas/preparation.py` |
| Occupancy source | `tlc_inventory` rows via `TlcInventoryRepository` + `LocationRepository.get_by_type(...)` | read the 6 Workspace `LocationType`s + `tlc_inventory.what_at(slot_id)` |
| Counts | DB-driven (count of `locations` rows of the type) — never hard-coded | same — count Workspace slot rows per kind from DB |
| Write (fill/clear) | `PUT /preparations/slots/{slot_id}`, `PUT /preparations/areas/{area_id}/{fill,clear}` (RackArea/RackSlot path) | reuse the existing PUT flow (see §4 — caveat: Workspace slots are NOT RackAreas today) |

---

## 1. The existing TLC Rack / box-grid endpoint

### Files Found

| File Path | Description |
|---|---|
| `app/api/routers/preparations.py` | Thin router for all `/preparations/*` endpoints |
| `app/services/preparation_service.py` | `PreparationService` — all reads + maintenance writes |
| `app/data/schemas/preparation.py` | Pydantic request/response models |
| `app/tlc/inventory.py` | `TlcInventoryRepository` — `what_at`/`contents`/`available_of_type` |
| `app/tlc/domain.py` | `box_grid()` accessor, `SlotId` codec, `LocationKind` |
| `app/repositories/location.py` | `LocationRepository.get_by_type(...)` |
| `app/data/models/location.py` | `LocationType` enum (the 6 Workspace + 1 Rack slot types) |
| `.trellis/spec/backend/tlc-placement.md` | §6 / §6a / §6b — the cross-layer contract |

### Route definition (`preparations.py:52-62`)

```python
@router.get(
    "/sample-tube-boxes",
    response_model=SampleTubeBoxesResponse,
    summary="Get sample-tube boxes as a box→cell grid",
)
async def get_sample_tube_boxes(
    preparation_service: PreparationServiceDep,
    floor: Annotated[str | None, Query(description="Restrict to one TLC-rack floor, e.g. L2")] = None,
) -> SampleTubeBoxesResponse:
    """Return one entry per TLC-Rack box slot (optionally one floor) with its tube-cell grid."""
    return await preparation_service.get_sample_tube_boxes(floor)
```

Router prefix: `router = APIRouter(prefix="/preparations", tags=["preparations"])` (`preparations.py:43`). Routers are auto-discovered on startup (any file in `app/api/routers/` exporting `router`).

### Response models (`app/data/schemas/preparation.py:277-315`)

```python
class SampleTubeCellView(BaseModel):
    row: str                # cell_col LETTER (box grid)
    col: int                # cell_row NUMBER (box grid)
    tube_id: str | None = None
    state: str | None = None
    filled: bool

class SampleTubeBoxView(BaseModel):
    box_id: str | None = None
    present: bool
    floor: str | None = None
    slot_index: int
    label: str
    rows: list[str]         # grid axes (dynamic, not constant)
    cols: list[int]
    filled: int
    total: int
    cells: list[SampleTubeCellView]

class SampleTubeBoxesResponse(BaseModel):
    boxes: list[SampleTubeBoxView]
```

### Spec §6 summary (the prior task's contract)

`.trellis/spec/backend/tlc-placement.md` §6 / §6a / §6b is the authoritative contract:

- **§6 maintenance bridge.** TLC materials live in `tlc_inventory`, NOT `inventory_items`. A new `material_source = 'tlc_inventory'` routes TLC RackAreas / TaskMaterialRules to `TlcMaintenanceBridge` (`app/tlc/maintenance.py`). One-way dependency: `preparation_service`/`command_validator` import the bridge; `app/tlc/*` never imports the prep service. Tip boxes are always-satisfiable (`_ALWAYS_AVAILABLE = 9999`); other keys count non-disposed rows. Existing `inventory_item`/`consume`/`container_rack` branches are untouched — the `tlc_inventory` branch is added alongside.
- **§6a — TLC Rack (storage) vs TLC Workspace (robot): two DISTINCT box-slot sets that MUST NOT be conflated.**
  - **TLC Workspace** = `tlc_tube_box_2ml_slot_{1..3}` (`LocationType.TLC_TUBE_BOX_2ML_SLOT`) — the robot's physical dispatch addresses, bounded 1-3 (`planner.tube_box_2ml_slot` is `ge=1, le=3`), parsed by the `SlotId` codec, shipped in `TLCRoundSpec`. NEVER add display slots here or exceed 1-3 — robot-protocol contract.
  - **TLC Rack** = `tlc_rack_box_2ml_l{F}_slot_{N}` (`LocationType.TLC_RACK_BOX_2ML_SLOT`, 5 per floor, floor-encoded id). Storage/display ONLY. The box-grid endpoint reads THESE; the robot never addresses them. Floor + index parsed from the id by string convention (NOT `SlotId` addresses).
- **§6b — the box→cell grid endpoint.** `GET /preparations/sample-tube-boxes[?floor=L2]` exposes the **TLC Rack** inventory as nested box→tube-cell grid:
  - One entry per TLC-Rack box SLOT, not per box. Card count = number of `tlc_rack_box_2ml_slot` locations — dynamic, DB-driven, NEVER hard-coded.
  - Present slot → `present=true` + real tube cells; empty slot → `present=false`, `box_id=null`, all cells empty.
  - Cell axes from `domain.box_grid(ObjectType.TUBE_BOX_2ML)` (public accessor — do NOT reach into `_BOX_GRID` from outside `domain.py`). A cell is `filled` when a real `tube_2ml` child sits at `(cell_col=row-letter, cell_row=col-number)`.
  - FE (`SampleTubeBoxGrid`) renders per `sample_tube` floor, in place of the flat slot strip, via `RackPlaneView`'s `renderAreaBody` / `renderAreaBadge` overrides.

> **Key takeaway for the new endpoint:** the prior box-grid endpoint reads the **TLC Rack** storage slots. The new Workspace endpoint reads the **robot's Workspace dispatch slots** (the 6 `TLC_*_SLOT` types) — the OTHER set in §6a. Same shaping pattern, different `LocationType`s.

---

## 2. How `PreparationService` reads slot `locations` + `tlc_inventory` occupancy and shapes them

The box-grid read (`get_sample_tube_boxes`) is the direct template. It reads physical box-slot `locations` rows via `LocationRepository.get_by_type(...)`, then per-slot occupancy via `TlcInventoryRepository.what_at(slot.id)` / `.contents(box.id)`.

Repository accessors (`preparation_service.py:121-133`):

```python
@property
def tlc_inventory(self) -> TlcInventoryRepository:
    """Direct ``tlc_inventory`` repo for box/cell composition (sample-tube box grid)."""
    if not hasattr(self, "_tlc_inventory"):
        self._tlc_inventory = TlcInventoryRepository(self.db)
    return self._tlc_inventory

@property
def locations(self) -> LocationRepository:
    """Location repo — used to enumerate physical box slots for the sample-tube grid."""
    if not hasattr(self, "_locations"):
        self._locations = LocationRepository(self.db)
    return self._locations
```

Shaping code (`preparation_service.py:289-360`):

```python
async def get_sample_tube_boxes(self, floor: str | None = None) -> SampleTubeBoxesResponse:
    grid = box_grid(ObjectType.TUBE_BOX_2ML)
    if grid is None:                                    # defensive
        return SampleTubeBoxesResponse(boxes=[])
    cols, rows = grid                                   # cols = letters, rows = numbers
    total = len(cols) * len(rows)

    wanted_floor = floor.upper() if floor else None
    slots = await self.locations.get_by_type(LocationType.TLC_RACK_BOX_2ML_SLOT, limit=1000)
    slots_with_meta = [(slot, *self._rack_box_slot_meta(slot.id)) for slot in slots]
    slots_with_meta = [
        (slot, slot_floor, slot_index)
        for slot, slot_floor, slot_index in slots_with_meta
        if wanted_floor is None or slot_floor == wanted_floor
    ]
    slots_with_meta.sort(key=lambda t: (t[1] or "", t[2] is None, t[2] or 0, t[0].id))

    box_views: list[SampleTubeBoxView] = []
    for display_index, (slot, slot_floor, slot_index) in enumerate(slots_with_meta, start=1):
        index = slot_index or display_index
        occupants = await self.tlc_inventory.what_at(slot.id)          # physical occupant at the slot
        box = next((o for o in occupants if o.object_type == ObjectType.TUBE_BOX_2ML.value), None)
        tube_by_cell = (
            {
                (tube.cell_col, tube.cell_row): tube
                for tube in await self.tlc_inventory.contents(box.id)   # tubes nested in the box
                if tube.cell_col is not None and tube.cell_row is not None
            }
            if box is not None
            else {}
        )
        cells: list[SampleTubeCellView] = []
        filled = 0
        for col in cols:
            for row in rows:
                tube = tube_by_cell.get((col.value, row))
                if tube is not None:
                    filled += 1
                cells.append(SampleTubeCellView(
                    row=col.value, col=row,
                    tube_id=tube.id if tube is not None else None,
                    state=tube.state if tube is not None else None,
                    filled=tube is not None,
                ))
        box_views.append(SampleTubeBoxView(
            box_id=box.id if box is not None else None,
            present=box is not None,
            floor=slot_floor, slot_index=index, label=f"{index:02d}",
            rows=[col.value for col in cols], cols=list(rows),
            filled=filled, total=total, cells=cells,
        ))
    return SampleTubeBoxesResponse(boxes=box_views)
```

Floor/index parsing from the (display) slot id (`preparation_service.py:362-372`):

```python
@staticmethod
def _rack_box_slot_meta(location_id: str) -> tuple[str | None, int | None]:
    """Parse ``tlc_rack_box_2ml_l{F}_slot_{N}`` → (floor ``"L{F}"``, 1-based index ``N``)."""
    match = re.fullmatch(r"tlc_rack_box_2ml_l(\d+)_slot_(\d+)", location_id)
    if match is None:
        return (None, None)
    return (f"L{int(match.group(1))}", int(match.group(2)))
```

`TlcInventoryRepository` primitives (`app/tlc/inventory.py`):

- `what_at(location_id)` (`inventory.py:66-74`): `WHERE location_id = :id`, physical occupants only, NO recursion — returns the box at the slot, never nested tubes.
- `contents(object_id)` (`inventory.py:76-80`): direct children via `parent_object_id` — the tubes inside a box.
- `available_of_type(object_type)` (`inventory.py:82-98`): non-disposed instances of an `object_type`, ordered by id — used by the maintenance bridge to surface occupancy / count readiness.

> **For the Workspace endpoint:** the 6 Workspace slot types hold single physical objects (box / plate / tank / lid / tip box), not nested tubes. So the per-slot occupancy read is just `what_at(slot.id)` (the box / plate / tank). The 2ml/50ml box areas may *additionally* drill into `contents(box.id)` to render the inner cell grid (PRD R2: reuse the box→cell grid for 2mL/50mL).

---

## 3. The `RackArea` concept — where defined, how areas/floors/slots are modeled

### Definitions

- ORM model `RackArea` / `RackSlot`: imported from `app.data.models.preparation` (`preparation_service.py:24`).
- Pydantic views: `app/data/schemas/preparation.py`.

`RackAreaView` (`preparation.py:242-254`):

```python
class RackAreaView(BaseModel):
    id: str
    floor: str
    area_code: str
    display_name: str
    material_key: str
    material_source: str
    is_maintainable: bool
    capacity: int
    available_count: int
    slots: list[RackSlotView]
```

`RackSlotView` (`preparation.py:231-239`):

```python
class RackSlotView(BaseModel):
    id: str
    location_id: str | None = None
    slot_index: int
    display_label: str | None = None
    occupied: bool
    item: SlotItemView | None = None
```

`RackView` / `RackLayoutResponse` (`preparation.py:257-269`): `RackView{ id, code, display_name, areas: list[RackAreaView] }` → `RackLayoutResponse{ racks: list[RackView] }`.

### How floors/areas/slots are modeled

The `GET /preparations/racks` read composes Rack → Area → Slot (`preparation_service.py:139-189`):

```python
async def get_rack_layout(self) -> RackLayoutResponse:
    racks = await self.racks.get_all_ordered()
    rack_views = [await self._build_rack_view(rack.id, rack.code, rack.display_name) for rack in racks]
    return RackLayoutResponse(racks=rack_views)

async def _build_area_view(self, area: RackArea) -> RackAreaView:
    slots = await self.slots.get_by_area_id(area.id)
    slot_views, available_count = await self._build_slot_views(area, slots)
    return RackAreaView(id=area.id, floor=area.floor, area_code=area.area_code, ...)
```

Per-area occupancy dispatches by `material_source` (`preparation_service.py:166-189`) — `inventory_item` / `consume`(silica) / `consume`(sample-cartridge) / `container_rack` / `tlc_inventory`. The TLC branch `_tlc_inventory_slot_views` (`preparation_service.py:259-283`) spreads non-disposed instances across area slots **positionally** (TLC RackSlots carry no `location_id` link to the TLC placement slots — they are display-only grid positions):

```python
async def _tlc_inventory_slot_views(self, area, slots):
    instances = await self.tlc_bridge.available_instances(area.material_key)
    available_count = len(instances)
    for index, slot in enumerate(slots):
        if index < len(instances):
            instance = instances[index]
            views.append(_occupied_slot_view(slot, SlotItemView(
                id=instance.id, material_key=area.material_key,
                display_name=area.display_name, state=instance.state)))
        else:
            views.append(_empty_slot_view(slot))
    return views, available_count
```

### How the prior task shaped a multi-floor / multi-box layout

The box grid does NOT use the RackArea/floor model for its layout. Instead it:
1. enumerates physical `locations` rows of `LocationType.TLC_RACK_BOX_2ML_SLOT` (5 per floor);
2. parses floor + index from the slot id (`_rack_box_slot_meta`, regex on `tlc_rack_box_2ml_l{F}_slot_{N}`);
3. sorts by `(floor, index, id)` and emits one `SampleTubeBoxView` per slot, each carrying its `floor`.

The FE then groups boxes by `floor`. Seed: L2 = 3 boxes (18/100 tubes), L1 = 1 box (5/100), 5 slots/floor (`tlc-placement.md` §6b; seed `seed.py:443-457`).

> **For the Workspace endpoint (PRD layout):** the PRD asks for a robot block + Shelf 1 (3 floors: 2mL / 50mL / tip box) + Shelf 2 (3 floors: silica plate / developing tank / tank lid). The natural shaping is: group the 6 Workspace `LocationType`s into shelves/floors in the response shape (DB-driven counts from the slot-row count per type). This is a NEW response shape (robot block + shelves × floors) — the box-grid `SampleTubeBoxView` is reusable only for the 2mL/50mL cell-grid sub-areas.

---

## 4. The fill / clear / update PUT flow (what `updatePreparationSlot` hits)

### FE call sites

- `BIC-agent-portal/src/lib/lab-service-client.ts:212-238` — `updatePreparationSlot(slotId, payload)` → `PUT /preparations/slots/{slotId}`; `fillPreparationArea(areaId)` → `PUT /preparations/areas/{areaId}/fill`; `clearPreparationArea(areaId)` → `PUT /preparations/areas/{areaId}/clear`.
- Wired in `MaterialPreparationPanel.tsx:34-39,108-115` and `ConsumablesPage.tsx:20-51`.

### BE routes (`preparations.py:86-119`)

```python
@router.put("/slots/{slot_id}", response_model=AreaMaintenanceResponse, ...)
async def update_slot(slot_id: str, request: SlotMaintenanceRequest, preparation_service: PreparationServiceDep):
    return await preparation_service.update_slot(slot_id, request)

@router.put("/areas/{area_id}/fill", response_model=AreaMaintenanceResponse, ...)
async def fill_area(area_id: str, preparation_service: PreparationServiceDep):
    return await preparation_service.fill_area(area_id)

@router.put("/areas/{area_id}/clear", response_model=AreaMaintenanceResponse, ...)
async def clear_area(area_id: str, preparation_service: PreparationServiceDep):
    return await preparation_service.clear_area(area_id)
```

### Request / response bodies

- Request `SlotMaintenanceRequest` (`preparation.py:358-370`): `{ occupied: bool, material_key: str | None }`, `extra="forbid"`. `occupied=true` fills, `false` clears.
- Response `AreaMaintenanceResponse` (`preparation.py:373-380`): `{ area: RackAreaView }` — the recomposed area so the FE updates in place.

### Service method + what it writes to DB (`preparation_service.py:458-485`)

```python
async def update_slot(self, slot_id: str, request: SlotMaintenanceRequest) -> AreaMaintenanceResponse:
    slot = await self.slots.get(slot_id)
    if slot is None:
        raise not_found_error("RackSlot", slot_id)
    area = await self._require_slot_editable_area(slot.area_id)
    if request.occupied:
        if request.material_key is not None and request.material_key != area.material_key:
            raise bad_request_error(...)
        await self._fill_slot(area, slot)
    else:
        await self._clear_slots(area, [slot])
    await self.commit()
    return AreaMaintenanceResponse(area=await self._build_area_view(area))
```

The DB write dispatches on `area.material_source` (`_create_slot_item` `preparation_service.py:550-597`, `_clear_slots` `preparation_service.py:630-670`). For `material_source == "tlc_inventory"`:
- **Fill** → `self.tlc_bridge.fill_one(area.material_key)` (`preparation_service.py:591-595`): creates ONE fresh `tlc_inventory` row, `state="unused"`, no slot, id `tlcmnt_{object_type}_{NNN}` (`maintenance.py:101-114`).
- **Clear** → positional: maps each occupied slot to the instance at its position (first N slots hold the N available instances, ordered by `slot_index`), then `self.tlc_bridge.clear_one(instance.id)` deletes the row (`preparation_service.py:659-670`, `maintenance.py:116-121`).

Occupancy for fill/clear is computed positionally over the WHOLE area (`_occupied_slot_ids`, `preparation_service.py:617-626`).

> **IMPORTANT caveat for the Workspace endpoint (§4 reuse).** This PUT flow keys off **`RackSlot` → `RackArea`** rows. The 6 Workspace slot types are seeded as **`locations` rows only** (robot dispatch addresses) — they are NOT RackAreas/RackSlots today (no `rack_tlc` area maps to `tlc_tube_box_2ml_slot` etc.; the TLC RackAreas use material_keys `sample_tube` / `developing_solvent_system` / `dispensing_tip_box` / `spotting_tip_box` / `silica_plate` / `waste_tip_box`, see seed §6). So `updatePreparationSlot(slotId)` as-is will 404 (`RackSlot` not found) for a raw Workspace `locations` id. The new endpoint/maintenance wiring must decide how to bridge Workspace slots into the PUT path (e.g. expose them as RackAreas, or add a Workspace-specific write that authors `tlc_inventory` placement directly). This is a design decision, not a settled contract — flag it in design.

---

## 5. Router → service layering convention (thin router, typed Pydantic, DB-driven counts)

Representative example — the box-grid endpoint:

- **Thin router** (`preparations.py:52-62`): declares `response_model=SampleTubeBoxesResponse`, accepts a typed `Query` param, and does nothing but `return await preparation_service.get_sample_tube_boxes(floor)`. No business logic.
- **Typed Pydantic everywhere**: request `SlotMaintenanceRequest` / `ValidatePreparationRequest`; responses `SampleTubeBoxesResponse` / `AreaMaintenanceResponse` / `RackLayoutResponse`. No `dict[str, Any]` on the wire (project rule: "Use strongly-typed Pydantic models for all request/response bodies"). Service receives pre-validated Pydantic models.
- **DB-driven counts (no hard-coding)**: the box count = `len(slots)` from `LocationRepository.get_by_type(LocationType.TLC_RACK_BOX_2ML_SLOT)` (`preparation_service.py:307`); the cell grid axes come from `box_grid(ObjectType.TUBE_BOX_2ML)` (`preparation_service.py:300`), `total = len(cols) * len(rows)`. Nothing is a literal count.
- **Services commit, repositories flush only**: `update_slot` ends with `await self.commit()` (`preparation_service.py:484`); repos never commit (`BaseService` owns the transaction). DI: `PreparationServiceDep` / `CommandValidatorDep` from `app.api.dependencies`.
- **One-way TLC bridge**: `preparation_service` imports `TlcMaintenanceBridge` / `TlcInventoryRepository`; `app/tlc/*` never imports the prep service (`preparation_service.py:113-119`, `maintenance.py` docstring).

---

## 6. `app/data/seed.py` — how the 6 TLC Workspace slot types are seeded

### The 6 Workspace slot types (`seed.py:374-385`, `_TLC_SLOT_INDEXED`)

```python
_TLC_SLOT_INDEXED: list[tuple[str, int, str]] = [
    ("tlc_cap_staging_2ml", 4, "tlc_cap_staging_2ml"),
    ("tlc_cap_staging_50ml", 2, "tlc_cap_staging_50ml"),
    ("tlc_tube_box_2ml", 3, "tlc_tube_box_2ml_slot"),          # 2mL tube box  ×3
    ("tlc_tube_box_50ml", 3, "tlc_tube_box_50ml_slot"),        # 50mL tube box ×3
    ("tlc_tip_box", 3, "tlc_tip_box_slot"),                    # tip box       ×3
    ("tlc_developing_tank", 3, "tlc_developing_tank_slot"),    # developing tank ×3
    ("tlc_developing_tank_lid", 3, "tlc_developing_tank_lid_slot"),  # tank lid ×3 (read-only per PRD)
    ("tlc_silica_plate", 4, "tlc_silica_plate_slot"),          # silica plate  ×4  (KEEP 4)
    ("tlc_disposal_bin", 2, "tlc_disposal_bin_slot"),
]
```

### location_id format + slot-row generation (`seed.py:405-421`, `_build_tlc_slot_rows`)

Indexed kinds expand to `{stem}_slot_{i}` (1-based, **no zero-pad** — the `SlotId` codec parses bare integers). So the rows are e.g. `tlc_tube_box_2ml_slot_1..3`, `tlc_silica_plate_slot_1..4`, `tlc_developing_tank_lid_slot_1..3`. Every id round-trips through `SlotId.parse(...).location_id`. `name == id`, `type` = the `LocationType` value, `parent_id = None` (placement is by codec, not hierarchy).

```python
for stem, count, loc_type in _TLC_SLOT_INDEXED:
    for i in range(1, count + 1):
        loc_id = f"{stem}_slot_{i}"
        rows.append({"id": loc_id, "name": loc_id, "type": loc_type, "parent_id": None})
```

### LocationType enum (`app/data/models/location.py:45-54`)

```python
TLC_TUBE_BOX_2ML_SLOT = "tlc_tube_box_2ml_slot"
TLC_RACK_BOX_2ML_SLOT = "tlc_rack_box_2ml_slot"   # storage/display (NOT a Workspace dispatch slot)
TLC_TUBE_BOX_50ML_SLOT = "tlc_tube_box_50ml_slot"
TLC_TIP_BOX_SLOT = "tlc_tip_box_slot"
TLC_DEVELOPING_TANK_SLOT = "tlc_developing_tank_slot"
TLC_DEVELOPING_TANK_LID_SLOT = "tlc_developing_tank_lid_slot"
TLC_SILICA_PLATE_SLOT = "tlc_silica_plate_slot"
```

Enumerate via `LocationRepository.get_by_type(location_type, limit=...)` (`app/repositories/location.py:23`).

### The `SlotId` codec / `Field(le=...)` bounds (PRD: do NOT change)

The robot-protocol bounds for these slots live in `app/tlc/planner.py` (`TLCRoundSpec`):

```python
silica_plate_slot: int = Field(ge=1, le=4)         # planner.py:131  → silica plate STAYS 4
developing_tank_slot: int | None = Field(default=None, ge=1, le=3)  # planner.py:145
tube_box_2ml_slot: int = Field(default=1, ge=1, le=3)               # planner.py:155
tube_box_50ml_slot: int = Field(default=1, ge=1, le=3)              # planner.py:156
tip_box_spot_slot: int = Field(default=1, ge=1, le=3)               # planner.py:157
tip_box_pep_slot: int = Field(default=2, ge=1, le=3)                # planner.py:158
```

The `SlotId` codec maps each slot kind to its protocol address via `_SlotSpec` (`domain.py:309-341`), with per-kind `(min, max)` bounds, e.g.:

```python
_SlotSpec(LocationKind.TLC_BEFORE_CC_TUBE_BOX_2ML_SLOT, ..., "tube_box_2ml", "index", 1, 3),
_SlotSpec(LocationKind.TLC_BEFORE_CC_TUBE_BOX_50ML_SLOT, ..., "tube_box_50ml", "index", 1, 3),
_SlotSpec(LocationKind.TLC_BEFORE_CC_TIP_BOX_SLOT, ..., "tip_box", "index", 1, 3),
_SlotSpec(LocationKind.TLC_BEFORE_CC_DEVELOPING_TANK_SLOT, ..., "developing_tank", "index", 1, 3),
_SlotSpec(LocationKind.TLC_BEFORE_CC_DEVELOPING_TANK_LID_SLOT, ...),
_SlotSpec(LocationKind.TLC_BEFORE_CC_SILICA_PLATE_SLOT, ..., "silica_plate", "index", 1, 4),
```

> These bounds (`le=3` / `le=4`) and the slot ids are a **robot-protocol contract** (`TLCRoundSpec`, `SlotId`, dispatch). Per the PRD: do NOT change them. The endpoint reads them; it must not alter or exceed them.

### display_name language (English on the RackArea, NOT on the locations rows)

The `locations` rows for the 6 Workspace slot types have NO human-facing `display_name` — `name == id` (the slot id). The 3 new TLC *workstations* DO carry Chinese names (`seed.py:350-354`): `TLC备料货架区` / `TLC操作台` / `TLC废弃区`. But the maintenance-page `display_name` lives on `RackArea` rows, which are **English** (`seed.py:181-248`): e.g. `"Dispensing Tip Box - 1250 µL"`, `"Spotting Tip Box - 12.50 µL"`, `"Developing Solvent System"`, `"Sample Tube"`, `"Silica Plate"`.

> **For the Workspace endpoint:** the existing TLC RackAreas (material_source `tlc_inventory`) cover `sample_tube`, `developing_solvent_system`, `dispensing_tip_box`, `spotting_tip_box`, `silica_plate`, `waste_tip_box` — these are the maintenance-page material keys, English `display_name`. The 6 Workspace **slot types** (`tlc_tube_box_2ml_slot` …) are a *different* axis (physical robot dispatch positions). There is no existing English `display_name` for the Workspace slot positions themselves; if the response needs per-block labels, the endpoint must supply them (PRD: match the English `display_name` convention). Do NOT propose changing the seeded slot ids / counts / bounds.

---

## 7. Caveats / things the design phase must decide (not settled contract)

1. **Workspace slots are `locations` rows only — NOT RackAreas/RackSlots.** The existing fill/clear PUT flow (`update_slot` → `RackSlot.get(slot_id)`) will 404 on a raw Workspace `locations` id. PRD R3 says "reuse the existing `updatePreparationSlot` / fill / clear PUT flow" — that reuse requires either (a) exposing the 6 Workspace types as new RackAreas/RackSlots, or (b) a new Workspace write path that authors `tlc_inventory` placement directly. This is the biggest open design question.
2. **TLC Rack vs TLC Workspace must stay distinct (§6a).** The box-grid endpoint reads `TLC_RACK_BOX_2ML_SLOT` (storage). The new endpoint reads the robot's `TLC_TUBE_BOX_2ML_SLOT` (+ the other 5 Workspace types). Do not conflate; do not add display rows to the Workspace dispatch slots.
3. **Occupancy on Workspace slots is `what_at(slot_id)` (direct), not positional.** Unlike the maintenance-bridge RackArea path (which spreads instances positionally because RackSlots have no `location_id` link), the Workspace `locations` rows ARE the real placement slots — `tlc_inventory.location_id` points at them. So `what_at(slot.id)` gives the true occupant per slot. (Seed: box at `tlc_tube_box_2ml_slot_1`, 50ml box at `tlc_tube_box_50ml_slot_1`, plate at `tlc_silica_plate_slot_1`, tanks+lids at slots 1-2 — `seed.py:435,459,463,465-468`. Tip boxes are NOT seeded; allocator mints them — slots will read empty until a run/fill.)
4. **Silica plate count is 4, not 3.** PRD-confirmed: `tlc_silica_plate_slot` is `le=4`, seeded ×4. DB-driven count will yield 4; don't normalize to 3.
5. **R5 (robot-completion update) NOT covered here.** This file is the read/write box-grid contract. The R5 trace (`log_handler.py` `EntityUpdateService` + `tlc_inventory` updates on robot completion) is a separate research item — note that per `tlc-placement.md` §5 the robot does NOT report TLC placement; `PlacementWriter` (result_handler Phase 1) authors `tlc_inventory.location_id` on `place` ops, and that write is LOCATION-only (no state). The maintenance bridge fill/clear is the human refill path.
