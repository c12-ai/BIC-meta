# Research: The exact `ObjectLocation` field set for chemist-chosen TLC sample tubes

- **Query**: Derive the EXACT fields the stubbed `ObjectLocation` (commented out in `bic_shared_types/experiment_task/http/tlc.py`) must carry so a chemist can pick which sample tubes the TLC robot aspirates — derived from what BIC-lab-service ACTUALLY needs, not invented.
- **Scope**: mixed (lab-service primary, shared-types contract)
- **Date**: 2026-06-26
- **Confirmed givens (Drake, fixed)**: two-level addressing (box on a rack-slot; tube in a tube-slot/cell inside the box); chemist picks the **`tube_id`**; `objects` is `list`, `min_length=2, max_length=4`; this REPLACES today's `TLCAllocator._first_available(TUBE_BOX_2ML)` + `_tube_ids(box, count=1)` auto-pick.

---

## LEAD: Proposed `ObjectLocation` field set

The chosen sample tubes **already exist in `tlc_inventory`** with a parent box + cell (seed places `tube_2ml_001..005`; the robot's `place` op is the write path that records any new placement — see Q3). Therefore the lab can resolve box + slot + cell from the `tube_id` alone via `where_is()`. **The only field that MUST cross the wire is `tube_id`.** Everything else is LAB-DERIVED.

```python
# bic_shared_types/experiment_task/http/tlc.py  (or common/tlc.py next to TLCParam)

class ObjectLocation(BaseModel):
    """One chemist-chosen TLC sample tube. The chemist picks the tube; the lab derives
    its box / rack-slot / box-cell from tlc_inventory (TlcInventoryRepository.where_is)."""

    tube_id: str = Field(min_length=1)           # REQUIRED on the wire — the 2ml sample tube id
    object_type: Literal[ObjectType.TUBE_2ML] = ObjectType.TUBE_2ML  # OPTIONAL/defaulted — see note 2


class CreateTLCTaskRequest(CreateTaskRequestBase):
    ...
    param: TLCParam
    objects: list[ObjectLocation] = Field(min_length=2, max_length=4)  # chemist's chosen sample tubes
```

### Field justification + REQUIRED-on-wire vs LAB-DERIVED

| Candidate field | Verdict | Why / lab-side need (file:line) |
|---|---|---|
| `tube_id: str` | **REQUIRED on wire** | The only thing the chemist actually chooses (Drake). Today auto-picked by `_tube_ids(box2.object_id, count=1)` → `sorted(t.id …)[:count]` (`service.py:174-175,235-246`). It flows into `SpottingSpec.sample_tube_ids` (`planner.py:129`) and onward to `ObjectRef(type=TUBE_2ML, id=tube_id)` for cap-handling tracking (`planner.py:643`). It is also the key `where_is(tube_id)` resolves box+slot+cell from (`inventory.py:43-64`). |
| `object_type` | **OPTIONAL / defaulted** | TLC sample tubes are always `TUBE_2ML` (the request is single-purpose; box is 2ml, `_tube_ids` reads the 2ml box only — `service.py:175`). Carry it only as a typed guard / future-proof discriminator; default `TUBE_2ML`. Lab does not need it to resolve placement (the row already has `object_type`). |
| `box_id` (`parent_object_id`) | **LAB-DERIVED — do NOT put on wire** | `where_is(tube_id)` reads `row.parent_object_id`, loads the parent, returns its slot (`inventory.py:57-64`). Seed: `tube_2ml_001` → `parent_object_id="tube_box_2ml_001"` (`seed.py:430`). |
| `rack_slot` (box's `location_id`) | **LAB-DERIVED — do NOT put on wire** | Derived from the parent box row's `location_id` → `SlotId.parse(parent.location_id)` (`inventory.py:62-64`). Seed: `tube_box_2ml_001.location_id = "tlc_tube_box_2ml_slot_1"` (`seed.py:429`). The planner re-derives the box slot index from allocation (`service.py:148` `tube_box_2ml_slot=_slot_index(box2)`), not from the request. |
| `tube_slot` / `cell` (`cell_col`+`cell_row`) | **LAB-DERIVED — do NOT put on wire** | `where_is` reconstructs the `Cell` from `cell_col`(letter)/`cell_row`(number) via `_cell_of` (`inventory.py:64,225-230`). Seed: `tube_2ml_001` → `cell_col="A", cell_row=1` (`seed.py:430`). NOTE the planner does NOT currently consult the cell — it derives col from list position (`idx+1`) and row from `plate.row` (`planner.py:641-651`); see Q2 caveat. |

**Bottom line for the implementer**: a one-field `ObjectLocation { tube_id }` is sufficient *for the lab to place the chosen tube*, GIVEN the tube is already in `tlc_inventory`. The list constraint `min_length=2, max_length=4` lives on `CreateTLCTaskRequest.objects`, not on `ObjectLocation`. The open decision (Q3) is whether "already in inventory" is a safe assumption or whether the chemist may declare a brand-new placement — that decides whether the full address must also ride the wire.

---

## Q1 — What addressing does the robot op program need for a sample tube?

**The robot op addresses a tube by box-internal CELL (row letter + col number) + tube_type — NOT by tube_id, NOT by slot.**

The aspirate op is `TlcCentrifugeTubeAspirateOp`, which inherits `TLCCentrifugeTubeAspirateRequest` (`tlc_ops.py:669-671`). That request model (`pipetting_robot_protocol/tlc.py:36-67`):

```python
class TLCCentrifugeTubeAspirateRequest(BaseModel):   # POST /tlc/centrifuge-tube/aspirate
    tube_type: CentrifugeTubeType   # "2mL" | "50mL"
    volume: float = Field(gt=0)     # µL
    row: WellRow                    # A–D for 2ml box (model_validator enforces range by tube_type)
    col: int = Field(ge=1)          # 1..5 for 2ml box
```

So the **liquid-handling op carries `{tube_type, row, col}` only** — no tube identity. The tube `id` shows up elsewhere, in the talos pick/place choreography for cap removal: `ObjectRef{type, id}` (`tlc_ops.py:276-284`) carried by `PickOp.object` / `PlaceOp.object` (`tlc_ops.py:521-536`), where the cell address is the discriminated-union `Location` member `TubeBox2mlLoc{at: BoxAt, row: WellRow, col: 1..5}` (`tlc_ops.py:437-448`). `BoxAt` is itself a discriminated union including `TubeBox2mlSlotLoc{slot_from_left: 1..3}` (`tlc_ops.py:361-363,432-434`).

**Resolution chain the op program ultimately needs**: `box slot (slot_from_left)` + `cell (row letter, col number)` + `tube_type` + (for tracking) the tube's `ObjectRef.id`. None of these is the tube_id at the aspirate level — the aspirate is purely positional.

## Q2 — How does `plan_from_request` consume the tube today, and where does chemist-chosen `tube_id` plug in?

**The seam is `SpottingSpec.sample_tube_ids` (`planner.py:129`).** Today's auto-pick (`service.py:174-175`):

```python
sample_tube_ids = await self._tube_ids(box2.object_id, count=1)   # auto-pick: sorted(ids)[:1] or synthetic
```

That list flows into `SpottingSpec(sample_tube_ids=sample_tube_ids, …)` (`service.py:196-204`). The planner's `_spot_plate` then (`planner.py:636-685`):
- maps **list position → col**: `for idx, tube_id in enumerate(plate.sample_tube_ids): col = idx + 1`
- uses **`plate.row` for the row** (a single `WellRow`, default `WellRow.A` — `service.py:198`)
- uses `tube_id` only as `ObjectRef(type=TUBE_2ML, id=tube_id)` for the cap open/close pick/place tracking (`planner.py:643,673`).

> **CAVEAT (real gap the implementer must close):** the planner does NOT call `where_is(tube_id)` and does NOT read each tube's true `(cell_col, cell_row)`. It assumes all chosen tubes lie in **one contiguous row** (`plate.row`) at **cols 1..n in list order**. This matches the seed (tubes 001-005 all in row A, cols 1-5) and the physical recipe (a 6-channel pipette aspirates a whole row in one shot — `planner.py:654-663`). So chemist-chosen `tube_id`s only produce a correct program **if the chosen tubes occupy one row at consecutive columns**. If a chemist picks tubes scattered across rows/cols, the current planner would mis-address them. Replacing `_tube_ids` with chosen ids is necessary but **not sufficient** — either (a) the lab must validate the chosen tubes share a row and order them by `where_is().cell` col, or (b) the planner must be taught to address each tube by its resolved cell. This is a design decision for the implementer; flagging it loud here.

**Confirm `where_is(tube_id)` returns (slot, cell):** YES. `where_is` (`inventory.py:43-64`) returns `LocationAddress{slot: SlotId, cell: Cell|None}` (`domain.py:408-416`); for a nested tube it resolves the parent box's `location_id` → `SlotId.parse` (the rack-slot) and the tube's `cell_col/cell_row` → `Cell` (the tube-slot). So given a `tube_id` already in inventory, the lab can fully derive box + rack-slot + box-cell. **This is why `ObjectLocation` need only carry `tube_id` — IF the tube is already placed.**

## Q3 — DECISION POINT: is the chosen tube already in `tlc_inventory`, or is the chemist DECLARING a new physical placement?

**Evidence for "already placed":**
- Seed places sample tubes WITH parent box + cell: `("tube_2ml_001", "tube_2ml", None, "tube_box_2ml_001", "A", 1)` … through `_005` (`seed.py:429-434`). `location_id=None` (nested), `parent_object_id="tube_box_2ml_001"`, `cell_col="A"`, `cell_row=1..5`.
- The 2ml box itself is placed on a rack-slot: `tube_box_2ml_001.location_id="tlc_tube_box_2ml_slot_1"` (`seed.py:429`).
- There IS an existing "register placement" write path: `TlcPlacementWriter._place_tube_into_box` (`placement.py:125-140`) runs when the **robot reports a `place` op succeeded** — it calls `TubeBox.insert(tube_id, row, col)` and `persist_box`, writing `parent_object_id + cell`. So new placements are recorded by the robot's confirmed action, not by the request.
- `available_of_type` / `_first_available` assume the tube row already exists in `tlc_inventory` (`inventory.py:82-98`, `allocate.py:144-153`).
- The seed task table marks `sample_tube` allocation as `manual_slot` (`seed.py:282`) — "lab supplies identity, then resolves it" (per `allocate.py:6-8`) — i.e. the instance pre-exists and the chemist names which one.

**Evidence for "chemist declares a NEW placement":** None found in code. There is no request-driven "write this tube into box B at cell (col,row)" path. The only placement writer is robot-`place`-driven (`placement.py:103-140`).

### Crisp either/or for Drake

- **(A) Tube-already-placed** *(matches all current evidence)* — The chemist picks from tubes the lab already knows (seeded / previously placed by the robot). `ObjectLocation = { tube_id }` (+ optional `object_type`). The lab resolves box / rack-slot / cell via `where_is(tube_id)`. No new write path needed. **Risk**: chemist can only choose among tubes already registered in `tlc_inventory`; a tube the chemist physically put in but never registered would not be selectable.

- **(B) Chemist-declares-placement** *(matches Drake's phrasing "physically places and tells the robot to pick")* — The chemist asserts "I put sample tube X into box B, rack-slot S, cell (col,row)". Then `ObjectLocation` must carry the **full address**: `tube_id` + `box_id` (parent) + `rack_slot` (the box's `location_id` / `TubeBox2mlSlotLoc.slot_from_left`) + `tube_slot` (cell: `cell_col` letter + `cell_row` number, i.e. `WellRow` + 1..5), so the lab can WRITE that placement (`TlcInventoryRepository.persist_box` / `_set_placement`, `inventory.py:119-152`) BEFORE planning. This needs a new request-driven placement write (none exists today).

**My read of the evidence**: code is 100% (A); Drake's verbal "chemist physically places" leans (B). The phrase "physically places and tells the robot to pick" is ambiguous between *"places a tube the lab already tracks"* (A) and *"declares a placement the lab must record"* (B). **This must be decided before the field set is final** — it is the single fork that determines whether `ObjectLocation` is one field (A) or four (B).

## Q4 — Location / slot enums available to express rack_slot and tube_slot (cell)

Sourced from real shared-types enums (all in `bic_shared_types/`):

| Concept | Type / enum | Values | Source |
|---|---|---|---|
| tube identity | `str` | free string `= ObjectRef.id` (e.g. `tube_2ml_017`) | `tlc_ops.py:276-284`; `tlc_inventory.py` model docstring |
| object_type | `ObjectType` (StrEnum) | `tube_2ml`, `tube_box_2ml`, … | `tlc_ops.py:200-218` |
| rack-slot (box on table) | `TubeBox2mlSlotLoc.slot_from_left: int` | `Field(ge=1, le=3)` | `tlc_ops.py:361-363` |
| rack-slot kind | `LocationKind.TLC_BEFORE_CC_TUBE_BOX_2ML_SLOT` | discriminator | `tlc_ops.py:237` |
| box-cell row | `WellRow` (StrEnum) | 2ml box: `A,B,C,D` | `pipetting_robot_protocol/enums.py:33-44`; `tlc_ops.py:446` |
| box-cell col | `int` literal | 2ml box: `1,2,3,4,5` | `tlc_ops.py:447` |
| tube_type | `CentrifugeTubeType` (StrEnum) | `2mL`, `50mL` | `pipetting_robot_protocol/enums.py:26-30` |
| DB cell storage | `cell_col: str(1)` (letter) + `cell_row: int` (number) | axis-SWAPPED vs protocol — see note | `tlc_inventory.py` model; `domain.py:21-26` axis note |

> Axis note: protocol uses `row`=letter, `col`=number; DB columns are `cell_col`=letter, `cell_row`=number (swapped names, same physical meaning). `Cell.for_box(object_type, col=letter, row=number)` validates against `_BOX_GRID` (`domain.py:85-88,396-405`). For (B), the wire should use the PROTOCOL axes (`WellRow` row + `1..5` col) to match what the robot op and `_place_tube_into_box` already speak (`placement.py:137`).

## Q5 — Downstream wiring impact (seam list only; implementer designs the change)

Given `ObjectLocation` lands in `CreateTLCTaskRequest.objects`, to USE chemist `tube_id`s instead of `_first_available`/`_tube_ids`:

1. **`app/tlc/service.py:159-211 `plan_from_request`** — replace `sample_tube_ids = await self._tube_ids(box2.object_id, count=1)` (line 175) with the chemist's `[o.tube_id for o in req.objects]`. The 2ml box (`box2`) should then be derived FROM the chosen tubes (their shared `parent_object_id` via `where_is`) rather than from `_first_available(TUBE_BOX_2ML)` (line 169 / `allocate_round_materials` line 98-99). Decide what `allocate_round_materials` still owns (50ml solvent box, plate, tip boxes stay auto; only the 2ml sample box + its tubes become chemist-driven).
2. **`app/tlc/service.py:235-246 `_tube_ids`** — becomes dead for the sample-tube path (still used for solvent tubes at line 174 `count=n_solvents`). Either keep for solvents only or split.
3. **`app/tlc/allocate.py:93-103 `allocate_tracked` / `:144-153 `_first_available`** — the `TUBE_BOX_2ML` allocation must be reconciled with "use the box the chosen tubes live in" instead of first-available. Tip boxes / plate / 50ml box allocation unaffected.
4. **`app/tlc/service.py:108-153 `build_round_spec`** — already takes `sample_tube_ids` as a parameter (line 116), so the non-request path is ready; only the request path (`plan_from_request`) hardcodes the auto-pick.
5. **`app/tlc/planner.py:636-685 `_spot_plate` + `:125-134 SpottingSpec`** — see Q2 CAVEAT: if chosen tubes are not one contiguous row, the planner's `col = idx+1` / single `plate.row` assumption breaks. Either enforce a row-contiguity precondition in `service.py` (validate via `where_is().cell`) or extend the planner to per-tube cell addressing. `SpottingSpec.sample_tube_ids` constraint is `min_length=1, max_length=5` (planner.py:129) — does NOT match Drake's `2..4`; the new `objects` constraint lives on the request, but the planner's spec bound may need aligning.
6. **(Only if decision = B)** new request-driven placement write before planning, reusing `TlcInventoryRepository.persist_box` / `_set_placement` (`inventory.py:119-152`) — there is NO such path today (only robot-`place`-driven `placement.py:103-140`).
7. **shared-types contract chores** — adding `ObjectLocation` + `CreateTLCTaskRequest.objects` requires the full contract-repo gate (regenerate `schemas/`, examples, OpenAPI, client wrapper) per `BIC-shared-types/AGENTS.md`. The `# objects: list[ObjectLocation]  # 暂不实现` stub at `experiment_task/http/tlc.py:19-20` is the exact uncomment point.

---

## Files cited

| File | Role |
|---|---|
| `BIC-shared-types/bic_shared_types/experiment_task/http/tlc.py:14-20` | `CreateTLCTaskRequest` + the `objects` stub to uncomment |
| `BIC-shared-types/bic_shared_types/common/tlc.py:27-38` | `TLCParam` (solvents + ratio only — what the request carries today) |
| `BIC-shared-types/bic_shared_types/pipetting_robot_protocol/tlc.py:36-67` | `TLCCentrifugeTubeAspirateRequest` — the aspirate op carries `{tube_type,row,col}`, no tube_id |
| `BIC-shared-types/bic_shared_types/pipetting_robot_protocol/enums.py` | `WellRow`, `CentrifugeTubeType` |
| `…/robot_protocol/skills/tlc_ops.py:200-488` | `ObjectType`, `ObjectRef`, `TubeBox2mlLoc`, `TubeBox2mlSlotLoc`, `Location` union |
| `BIC-lab-service/app/tlc/service.py:159-246` | `plan_from_request`, `_tube_ids` (the auto-pick seam) |
| `BIC-lab-service/app/tlc/planner.py:125-134,636-685` | `SpottingSpec`, `_spot_plate` (list-index→col assumption) |
| `BIC-lab-service/app/tlc/inventory.py:43-64,225-230` | `where_is` returns (slot, cell); `_cell_of` |
| `BIC-lab-service/app/tlc/domain.py:381-416` | `Cell`, `LocationAddress`, axis note |
| `BIC-lab-service/app/tlc/placement.py:103-140` | `_place_tube_into_box` — the existing (robot-driven) placement WRITE path |
| `BIC-lab-service/app/tlc/allocate.py:93-153` | `allocate_tracked`, `_first_available` (today's auto-pick) |
| `BIC-lab-service/app/data/models/tlc_inventory.py` + `schemas/tlc_inventory.py` | `tlc_inventory` columns: `parent_object_id`, `cell_col`, `cell_row` |
| `BIC-lab-service/app/data/seed.py:282,378,429-438` | sample tubes seeded WITH parent box + cell |
| `BIC-lab-service/app/utils/task_resolver.py:211-245` | TLC resolver → `plan_from_request` |
