# Research: BIC-lab-service TLC planner, inventory model, rack config, endpoints, robot ops, solvent schema

- **Query**: R1 (TLC rack vs workbench for tube boxes) and R2 (developing-tank solvent reuse via properties)
- **Scope**: internal
- **Date**: 2026-07-10

---

## Summary

1. **TLCPlanner** is at `app/tlc/planner.py`. `_prepare_solvents` is the 配液 step. It always runs — there is no conditional "skip if existing tank has solvents". The tank is assumed empty at its workbench slot.
2. **tlc_inventory** model is at `app/data/models/tlc_inventory.py`. `properties` is a `JSONB` nullable column. Purity is persisted via `PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}` (preparation_service.py, line 609). Developing tanks currently have `properties=None` in the seed.
3. **Lab material config**: the TLC rack (`rack_tlc`) has L1/L2 for sample tubes + solvent system, and L3/L4 for tip boxes. The WORKBENCH (`_TLC_WORKSPACE_SHELVES` in preparation_service) tracks 6 slot types: `tube_box_2ml`, `tube_box_50ml`, `tip_box`, `developing_tank`, `developing_tank_lid`, `silica_plate`. Tube boxes (2ml and 50ml) currently appear in BOTH the workbench view and the supply-shelf (TLC Rack) view. The supply shelf (physical "TLC Rack") is the chemist surface; bench is robot parking.
4. **Endpoints**: `PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}` inserts a sample-tube inventory row with `properties`. The developing-tank equivalent insert endpoint does NOT exist yet — the tank is pre-seeded, not placed by the chemist.
5. **Robot ops**: No existing "carry tank from storage slot to working slot" op. The planner's `_prepare_solvents` always picks the tank from `TLC_BEFORE_CC_DEVELOPING_TANK_SLOT` (a workbench slot where the tank is already pre-seated). To "skip solvent prep and reuse existing tank", the planner would need to skip `_prepare_solvents` entirely; there is no reuse/carry op in the current op set.
6. **Matching**: solvent system/ratio for a round comes from `TLCParam` (`solvents: list[Solvent]` + `solvent_ratio: list[PositiveInt]`), carried on `CreateTLCTaskRequest.param` (shared-types `bic_shared_types/common/tlc.py`).

---

## Q1 — TLCPlanner: where is 配液 / solvent preparation generated?

**File**: `/Users/drakezhou/Development/BIC/BIC-lab-service/app/tlc/planner.py`  
**Class**: `TLCPlanner` (line 366)  
**Method that generates a full round**: `plan_round(spec: TLCRoundSpec)` (line 376)

The round builds ops in this order (lines 386–414):
1. `_pickup_materials` (round 1 only) — AGV shelf→bench carry
2. `_dispose_previous` (rounds ≥2) — dispose prior plate
3. **`_prepare_solvents`** (line 401) — **this is the 配液 step**
4. `_spot_plate`
5. `_immerse_and_aim`
6. `_observe_developed_plate`

**`_prepare_solvents` detailed op sequence** (lines 812–888):

```python
# 1. Lid off tank → lid slot
PickOp(object=lid, source=tank_home)          # tank_home = TLC_BEFORE_CC_DEVELOPING_TANK_SLOT[tank_slot]
PlaceOp(object=lid, to=lid_slot)              # lid_slot  = TLC_BEFORE_CC_DEVELOPING_TANK_LID_SLOT[tank_slot]

# 2. Parallel: pipetting AGV enters bench ‖ talos picks the tank
parallel([
    PipettingAgvMoveOp(station=main_station),
    PickOp(object=tank, source=tank_home),
])
PlaceOp(object=tank, to=agv_slot(PLATE_OR_VESSEL))  # tank rides AGV open

# 3. Stage materials
PickOp+PlaceOp: TIP_BOX_1250UL → agv_slot(TIP_BOX)
PickOp+PlaceOp: TUBE_BOX_50ML  → agv_slot(TUBE_BOX)
PickOp+PlaceOp: WASTE_TIP_BIN  → agv_slot(WASTE_TIP)

# 4. Mount single-channel pipette
PickOp+PlaceOp pipette body → head
CommonPipetteReplaceOp(SINGLE_CHANNEL)

# 5. Chained batch-open all 50ml solvent tubes
_open_all(tube_type=ML_50, ...)

# 6. Per solvent (1 or 2):
CommonTipMountOp(source_id=ordinal+1)
TlcCentrifugeTubeAspirateOp(tube_type=ML_50, volume=solvent.aspirate_volume, ...)
TlcDevelopingTankDispenseOp(volume=solvent.dispense_volume)
CommonTipEjectOp(dest_pos=TLC_PEP_DEP)

# 7. Chained LIFO close all 50ml tubes
_close_all(...)
```

The developing tank is addressed as `ObjectRef(type=ObjectType.DEVELOPING_TANK)` (anonymous — no id in op, line 835). `tank_home` is always a workbench developing-tank slot (`TLC_BEFORE_CC_DEVELOPING_TANK_SLOT`, index = `spec.tank_slot`).

---

## Q2 — tlc_inventory model: `properties` column and purity persistence

**ORM model**: `/Users/drakezhou/Development/BIC/BIC-lab-service/app/data/models/tlc_inventory.py` (line 19)

```python
class TlcInventory(StringIdBase):
    __tablename__ = "tlc_inventory"
    object_type: Mapped[str]              # e.g. "developing_tank", "tube_2ml"
    location_id: Mapped[str | None]       # FK → locations; NULL when nested in a box
    parent_object_id: Mapped[str | None]  # self-FK; tube→box containment
    cell_col: Mapped[str | None]          # WellRow letter (tubes only)
    cell_row: Mapped[int | None]          # 1-based number (tubes only)
    state: Mapped[str]                    # "unused" / "used" / "disposed"
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # opaque metadata
```

**`properties` column** (line 46): JSONB, nullable. The docstring says it holds opaque experiment metadata e.g. `{"exp_id": "...", "purity": "pure"}`. It is:
- Written at INSERT time only (via `_upsert`, line 182–219 in `inventory.py`)
- NEVER rewritten on placement-only moves (comment at line 216): `# properties is NOT updated on placement-only moves (preserved as-is)`
- NULL for non-experiment objects (developing tanks in the seed)

**How sample-tube purity is persisted** (endpoint that writes properties):

`PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}`  
→ `preparation_service.py` `set_sample_tube_cell()` (~line 543)  
→ when `request.occupied=True` and no occupant exists, calls `tlc_inventory.create(obj_in=TlcInventoryCreate(..., properties=request.properties))` (line 601–611)

**Request schema** (`SampleTubeCellMaintenanceRequest`, `preparation.py` line 377):
```python
class SampleTubeCellMaintenanceRequest(BaseModel):
    occupied: bool
    properties: dict | None = None  # opaque bag, e.g. {"exp_id":"...", "exp_name":"...", "purity":"pure"}
```

**Developing tanks in the seed** (`app/data/seed.py`, lines 433–434):
```python
("developing_tank_001", "developing_tank", "tlc_developing_tank_slot_2", None, None, None),
("developing_tank_002", "developing_tank", "tlc_developing_tank_slot_3", None, None, None),
```
Both have `properties=None` (6-tuple; no properties field). `object_type="developing_tank"`, `location_id="tlc_developing_tank_slot_2"` (a workbench slot, NOT a rack slot). There is NO `object_type` value for developing tanks on the TLC rack — tanks only live on workbench slots in the current schema.

---

## Q3 — Lab material configuration: TLC rack vs TLC workbench areas

**Config source**: `app/data/seed.py` (`PREP_AREA_SPECS`) + `app/services/preparation_service.py` (`_TLC_WORKSPACE_SHELVES`)

### TLC Rack (chemist-facing supply shelf, "rack_tlc")

From `PREP_AREA_SPECS` (lines 180–251 of seed.py), the `rack_tlc` rack has these areas:

| Floor | area_code | display_name | material_source | is_maintainable |
|---|---|---|---|---|
| L4 | dispensing_tip_box | Dispensing Tip Box - 1250 µL | tlc_inventory | True |
| L4 | spotting_tip_box | Spotting Tip Box - 12.50 µL | tlc_inventory | True |
| L3 | dispensing_tip_box | Dispensing Tip Box - 1250 µL | tlc_inventory | True |
| L3 | spotting_tip_box | Spotting Tip Box - 12.50 µL | tlc_inventory | True |
| L2 | developing_solvent_system | Developing Solvent System | tlc_inventory | True |
| L2 | sample_tube | Sample Tube | tlc_inventory | True |
| L1 | developing_solvent_system | Developing Solvent System | tlc_inventory | True |
| L1 | sample_tube | Sample Tube | tlc_inventory | True |

The TLC Rack serves: tip boxes (L3/L4), developing solvent system (L1/L2), and sample tubes (L1/L2). **No developing tanks and no tube boxes** on the TLC Rack currently.

### TLC Workbench (robot-facing bench, `_TLC_WORKSPACE_SHELVES`)

Defined in `preparation_service.py` starting around line 104 (`_TLC_WORKSPACE_SHELVES`). The workbench has 2 "shelves" (effectively columns), each with 3 floor areas. Location types used:

- `tlc_tube_box_2ml` (bench slots 1-3) — where robot parks the 2ml box
- `tlc_tube_box_50ml` (bench slots 1-3) — where robot parks the 50ml box
- `tlc_tip_box` (bench slots 1-3) — where robot parks tip boxes
- `tlc_developing_tank_slot` (slots 1-4; wire-protocol caps at 3) — developing tank home
- `tlc_developing_tank_lid_slot` (slots 1-4) — lid slot, read-only
- `tlc_silica_plate_slot` (slots 1-4) — silica plate home

**Tube boxes** (`tube_box_2ml`, `tube_box_50ml`) currently appear as workbench areas in the workspace view. The chemist's surface for 2ml boxes is the supply-shelf (TLC rack, L1/L2 RIGHT side), but the workbench view also renders them (robot bench parking). These are DISTINCT: `TLC_SUPPLY_SHELF` kind for the rack, `TLC_BEFORE_CC_TUBE_BOX_2ML_SLOT` for the bench.

**Developing tanks currently ONLY appear on the workbench** (slots 2 and 3 in seed). There is no rack area for developing tanks, and the `SUPPLY_SHELF_REGIONS` dict in `domain.py` (lines 118-123) only covers `TUBE_BOX_2ML`, `TUBE_BOX_50ML`, `TIP_BOX_300UL`, `TIP_BOX_1250UL` — NOT `DEVELOPING_TANK`.

**Items on workbench that are chemist-maintainable via API**: The `GET /preparations/tlc-workspace` endpoint shows the workspace, but currently no workbench area exposes an insert/maintenance endpoint for developing tanks. The only chemist-facing write on the workbench is `PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}` for 2ml tube boxes on bench or shelf.

---

## Q4 — Endpoints for insert/assign and consumable maintenance

### Insert-and-assign endpoint (used for sample tubes):
`PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}`  
→ router: `/Users/drakezhou/Development/BIC/BIC-lab-service/app/api/routers/preparations.py` (around line 79–99)  
→ service: `preparation_service.py` `set_sample_tube_cell()`  
→ creates a `tlc_inventory` row with `parent_object_id=box_id`, `cell_col`, `cell_row`, and **`properties`** (opaque bag from request)

### Sample-tube box view (chemist surface):
`GET /preparations/sample-tube-boxes?floor=&source=`  
→ `preparation_service.py` `get_sample_tube_boxes()`  
→ returns `SampleTubeBoxesResponse` with `SampleTubeBoxView` list

### Could developing-tank placement reuse insert endpoint?
**No**, the current insert endpoint is box-cell specific. Developing tanks are pre-seeded and placed at workbench slots, not placed by the chemist. A new endpoint (or extension of the workspace write surface) would be needed to let a chemist declare a solvent-filled tank.

### Where would solvent/ratio property be accepted?
In `_upsert()` (`inventory.py`, line 182), the `properties` parameter can accept any dict. If a developing-tank write endpoint were added, the request schema would need a `properties` dict containing e.g. `{"solvent_system": ["PE", "EA"], "solvent_ratio": [3, 1]}`. The `_upsert` call would pass that dict as `properties`. The `TlcInventoryCreate` schema (`data/schemas/tlc_inventory.py`, line 21) already has `properties: dict | None`.

---

## Q5 — Robot protocol: ops for moving a developing tank / skipping solvent prep

### Current solvent-prep op sequence (from Q1)
The `_prepare_solvents` method (planner.py line 812) always:
1. Picks the tank from its workbench slot
2. Places it on the pipetting AGV
3. Aspirates each solvent from the 50ml box into the tank
4. Returns the tank to its workbench slot (in `_spot_plate` teardown, line 929)

### Is there a "carry developing tank from storage to working position" op?
**No distinct carry op exists** for the developing tank. The current protocol assumes the tank is already at its `TLC_BEFORE_CC_DEVELOPING_TANK_SLOT` (workbench slot 2 or 3). There are only 3 workbench developing-tank slots (the codec stops at 3, comment at domain.py line 386).

The robot op set includes `PickOp` and `PlaceOp` which are generic. A "reuse existing tank" scenario could be implemented by:
- Checking if a workbench slot already has a tank whose `properties.solvent_system` and `properties.solvent_ratio` match the target
- If yes: skip `_prepare_solvents` entirely; the tank is already at `tank_home`, ready for `_immerse_and_aim`
- If no: proceed with normal `_prepare_solvents` (fill the tank)

The planner itself would need a conditional branch — there is currently no "skip prep" path. The planner is called from `TLCService.plan_round_from_binding()` which always calls `self._round_command(spec, round_index)` → `self._planner.plan_round(spec)`.

**UNVERIFIED**: Whether the robot firmware handles a developing tank that already has solvent inside when the robot attempts to move it onto the AGV (the tank would be open and filled). This is a physical concern about spill risk that the protocol documents don't explicitly address.

---

## Q6 — Matching: target solvent system + ratio schema

**Source**: `/Users/drakezhou/Development/BIC/BIC-shared-types/bic_shared_types/common/tlc.py` (line 27)

```python
class TLCParam(BaseModel):
    """TLC 实验参数 — 溶剂体系与配比。"""
    solvents: list[Solvent]         # list of Solvent enum values (e.g. ["PE", "EA"])
    solvent_ratio: list[PositiveInt] # positive ints, same length as solvents (e.g. [3, 1])
```

**`CreateTLCTaskRequest`** (`bic_shared_types/experiment_task/http/tlc.py`, line 17):
```python
class CreateTLCTaskRequest(CreateTaskRequestBase):
    task_type: Literal[TaskType.THIN_LAYER_CHROMATOGRAPHY]
    param: TLCParam                          # solvent system for ALL rounds
    objects: list[ObjectLocation]            # 2–4 sample tubes declared by chemist
    target_window: TLCRfGoal                 # Rf acceptance window
```

The `AppendTLCRoundRequest` (line 32) also carries `param: TLCParam` per round.

**At dispatch time**, `TLCService.plan_round_from_binding()` (service.py line 316) reads:
- `round_param.solvents` — the solvent list (list of `Solvent` enum)
- `round_param.solvent_ratio` — the integer ratio

These become `SolventDispense` objects with `aspirate_volume = total * ratio[i] / sum(ratio)`.

**For a "match existing tank" check**, the comparison would be:
- `tank.properties["solvent_system"]` == `[s.value for s in round_param.solvents]`
- `tank.properties["solvent_ratio"]` == `round_param.solvent_ratio`

The `Solvent` enum values would need to be normalized (same casing/representation) for a reliable match.

---

## Files Found

| File Path | Description |
|---|---|
| `/Users/drakezhou/Development/BIC/BIC-lab-service/app/tlc/planner.py` | TLCPlanner class; `_prepare_solvents` at line 812, `plan_round` at line 376 |
| `/Users/drakezhou/Development/BIC/BIC-lab-service/app/tlc/service.py` | TLCService; `plan_round_from_binding` at line 316 |
| `/Users/drakezhou/Development/BIC/BIC-lab-service/app/data/models/tlc_inventory.py` | ORM model; `properties` column at line 46 |
| `/Users/drakezhou/Development/BIC/BIC-lab-service/app/tlc/inventory.py` | TlcInventoryRepository; `_upsert` at line 182 |
| `/Users/drakezhou/Development/BIC/BIC-lab-service/app/tlc/allocate.py` | TLCAllocator; developing-tank allocation via `allocate_tracked` |
| `/Users/drakezhou/Development/BIC/BIC-lab-service/app/data/seed.py` | Seed data; developing tank rows at line 433, TLC rack areas at line 183 |
| `/Users/drakezhou/Development/BIC/BIC-lab-service/app/services/preparation_service.py` | TLC workspace and sample-tube-box endpoints; `set_sample_tube_cell` ~line 543 |
| `/Users/drakezhou/Development/BIC/BIC-lab-service/app/api/routers/preparations.py` | REST endpoints; sample-tube-box PUT at line 79 |
| `/Users/drakezhou/Development/BIC/BIC-lab-service/app/data/schemas/preparation.py` | `SampleTubeCellMaintenanceRequest` at line 377 (has `properties: dict | None`) |
| `/Users/drakezhou/Development/BIC/BIC-lab-service/app/tlc/domain.py` | SlotId codec; `SUPPLY_SHELF_REGIONS` at line 118; `PlacementPolicy.developing_tank_slot` at line 571 |
| `/Users/drakezhou/Development/BIC/BIC-shared-types/bic_shared_types/common/tlc.py` | `TLCParam` schema (solvents + solvent_ratio) |
| `/Users/drakezhou/Development/BIC/BIC-shared-types/bic_shared_types/experiment_task/http/tlc.py` | `CreateTLCTaskRequest` (carries TLCParam) |

## Caveats / Not Found

- **UNVERIFIED**: Whether the robot firmware can handle a solvent-filled developing tank being picked up and placed on the AGV (physical spill concern for reuse scenario). The protocol docs were not read from robot team's mars_doc files.
- **UNVERIFIED**: The exact Solvent enum values used in `TLCParam.solvents` — could not import `bic_shared_types` at runtime. The enum is in `bic_shared_types/common/enums.py`.
- The `_TLC_WORKSPACE_SHELVES` constant definition in `preparation_service.py` was not fully read (lines 104–196); the slot type names above are inferred from the grep output and the `get_tlc_workspace` method structure.
- No robot-team mars_doc files were located in BIC-lab-service — the robot protocol reference for developing-tank pick/carry ops could not be verified independently.
