# Research: STORAGE-rack vs BENCH slot taxonomy mismatch (TLC dispatch)

- **Query**: Map the STORAGE-rack vs BENCH slot taxonomy mismatch that blocks TLC dispatch; recommend the correct bridge (no code changes).
- **Scope**: internal (BIC-lab-service + BIC-agent-portal), read-only
- **Date**: 2026-06-27

---

## ROOT CAUSE (one line)

The FE tube selector is fed by `GET /preparations/sample-tube-boxes`, which returns **only STORAGE-rack boxes** (`LocationType.TLC_RACK_BOX_2ML_SLOT`, ids `tlc_rack_box_2ml_l*_slot_*`), but the dispatch path (`where_is → SlotId.parse`) accepts **only BENCH boxes** (`LocationType.TLC_TUBE_BOX_2ML_SLOT`, ids `tlc_tube_box_2ml_slot_{1..3}`). The two halves shipped in the **same commit `b36273f`** never shared a taxonomy: the selector surfaces a family of slots that `SlotId.parse` is hard-coded to reject (`unrecognized TLC slot id`), so every selectable tube lands on a slot the planner refuses → dispatch is structurally impossible.

## RECOMMENDED BRIDGE

**(a) — the FE selector must surface the BENCH box(es) the planner accepts**, *conditional on one physical fact (Q4) only Drake can confirm*: that the robot picks sample tubes from the **bench** 2 mL box slot (`tlc_tube_box_2ml_slot_*`), not from the storage rack.

- If the robot picks from the **bench** (almost certainly true — see Q4): fix is **(a)**. The feature intent is "the chemist selects the tube the robot will pick"; the only box the robot can address is the bench box, so the selector must show bench boxes. `get_sample_tube_boxes` should read `TLC_TUBE_BOX_2ML_SLOT` (or reuse the Workspace box-grid path it already has), not `TLC_RACK_BOX_2ML_SLOT`.
- If a storage→bench **move** is part of the real workflow (the robot first relocates the box from the rack onto the bench): then **(c)** is correct — but **no such move op exists in the model today** (verified below), so (c) is net-new work and should not be assumed.

**(d) is a band-aid** (re-seed so the dispatchable box appears in the selector's storage query) and **(b) is wrong** (widening `SlotId.parse` to accept storage ids would let the planner emit a robot address the robot can't reach, unless a move op also exists). Detail and exact file:line for every option in §5.

> Decision hinges on Q4 (§4), which is a physical fact, not a code fact. Posed as a crisp question for Drake at the end.

---

## Findings

### 1. The two slot families — full inventory

There are **two distinct `LocationType`s** for 2 mL tube-box slots, intentionally separated, plus the planner codec that only knows one of them.

#### BENCH family — the robot's dispatch address

| Aspect | Value |
|---|---|
| `LocationType` | `TLC_TUBE_BOX_2ML_SLOT = "tlc_tube_box_2ml_slot"` — `BIC-lab-service/app/data/models/location.py:45` |
| Protocol `LocationKind` | `TLC_BEFORE_CC_TUBE_BOX_2ML_SLOT` |
| Id scheme | `tlc_tube_box_2ml_slot_{1..3}` |
| Seeded | `app/data/seed.py:378` — `("tlc_tube_box_2ml", 3, "tlc_tube_box_2ml_slot")` (3 indexed slot rows) |
| Box seeded on it | `tube_box_2ml_001` on `tlc_tube_box_2ml_slot_1` — `app/data/seed.py:435`, with 5 tubes A1..A5 (`seed.py:436-440`) |
| Physical meaning | The robot's **Workspace dispatch slot** — bounded 1-3 — that the pipetting robot actually picks from. Comment at `location.py:46-48`: "robot dispatch address, bounded 1-3 … the robot never addresses [the rack]." |
| Codec accepts it? | **YES** — `_SlotSpec(LocationKind.TLC_BEFORE_CC_TUBE_BOX_2ML_SLOT, TubeBox2mlSlotLoc, "tube_box_2ml", "index", 1, 3)` at `app/tlc/domain.py:325` |

#### STORAGE-rack family — display/inventory only

| Aspect | Value |
|---|---|
| `LocationType` | `TLC_RACK_BOX_2ML_SLOT = "tlc_rack_box_2ml_slot"` — `app/data/models/location.py:49` |
| Protocol `LocationKind` | **none** — there is no `LocationKind` for it; it is not a robot address |
| Id scheme | `tlc_rack_box_2ml_l{F}_slot_{N}` (floor-encoded, F∈{1,2}, N∈{1..5}) |
| Seeded | `app/data/seed.py:400-401` — 5 slots/floor for L2 and L1 (10 storage slot rows) |
| Backing `rack_areas` | `seed.py:236,248` — area `sample_tube` on `rack_tlc`, `material_source="tlc_inventory"`, capacity 5/floor |
| Boxes seeded on it | `tube_box_2ml_l2_001/_002/_003` (L2 slots 1-3) and `tube_box_2ml_l1_001` (L1 slot 1) — `seed.py:443,446,453,456` |
| Physical meaning | TLC-Rack **storage/maintenance** slots (5 per floor). Comment at `location.py:46-48` and `seed.py:441`: "TLC Rack DISPLAY boxes (storage, 5 slots/floor) — drive the maintenance-page box grid only." |
| Codec accepts it? | **NO** — there is no `_SlotSpec` for `tlc_rack_box_2ml_slot` in `_SLOT_SPECS` (`domain.py:309-342`). `SlotId.parse` falls through the loop and **raises** `ValueError(f"unrecognized TLC slot id: {location_id!r}")` at `domain.py:154`. |

#### The codec (`SlotId.parse`)

- `app/tlc/domain.py:136-154` — `parse()`: requires the `tlc_` prefix (`domain.py:147-148`), then tries each `_SlotSpec`. If none matches → `raise ValueError("unrecognized TLC slot id: ...")` at `domain.py:154` (the exact live-error message).
- `app/tlc/domain.py:309-342` — `_SLOT_SPECS`: 21 specs. The only 2 mL tube-box spec is the BENCH one (`domain.py:325`). **No storage-rack spec exists.**
- Note: `parse` **raises** on an unknown id; it does **not** return `None`. This matters for the validator path (§3).

### 2. What the FE selector actually surfaces

`GET /preparations/sample-tube-boxes` → `PreparationService.get_sample_tube_boxes()` at `app/services/preparation_service.py:401-472`.

- `preparation_service.py:419` — `slots = await self.locations.get_by_type(LocationType.TLC_RACK_BOX_2ML_SLOT, ...)`. **Hard-coded to the STORAGE family.** It never reads `TLC_TUBE_BOX_2ML_SLOT`.
- `preparation_service.py:474-484` — `_rack_box_slot_meta` parses ids with regex `tlc_rack_box_2ml_l(\d+)_slot_(\d+)` — storage-id shape only.
- The endpoint docstring (`preparation_service.py:402-411`) says it explicitly: "Reads the TLC Rack storage box slots (`TLC_RACK_BOX_2ML_SLOT`, 5 per floor) — **NOT the robot's Workspace dispatch slots**."
- Router: `app/api/routers/preparations.py:54-63` (`/preparations/sample-tube-boxes`, optional `floor` query).

**Why built this way**: the box grid was first built for the **consumables / maintenance page** (`BIC-agent-portal/src/components/preparations/SampleTubeBoxGrid.tsx`, `ConsumablesPage.tsx`), where boxes live in the storage rack for refill. The `TubeSelectorGrid` reused that same data shape and same endpoint (the FE comment in `TubeSelectorGrid.tsx:1-9` says it "reuses the same lab-service data shapes as the read-only `SampleTubeBoxGrid`"). The dispatch feature inherited the **storage** data source by reuse, not by design.

**FE wiring** (confirms the storage source reaches dispatch):
- `BIC-agent-portal/src/components/workspace/forms/TlcParamsForm.tsx:46` — `useQuery(sampleTubeBoxesQueryOptions())` (no floor arg → all storage boxes).
- `TubeSelectorGrid.tsx:148-154` — each selected cell emits `{ boxId: box.box_id, tubeId: cell.tube_id, ... }`. `box.box_id` is the **storage box id** (e.g. `tube_box_2ml_l1_001`). That id becomes `ObjectLocation.box_id` in the `CreateTLCTaskRequest`.

So the FE hands the lab a storage box id, and the box sits on a storage slot the planner rejects.

### 3. What `plan_from_request` / the planner needs

Dispatch chain for a chosen tube's box→slot (read-only trace):

1. `app/tlc/service.py:186` — `plan_from_request(req)` is the task-path entry.
2. `service.py:199` — `write_declared_placements(req.objects)` inserts the declared tube cells into the chosen box (loads the box by `objects[0].box_id`, `service.py:177-184`). This **does not** re-validate the slot.
3. `service.py:200` — `box2_slot = await self._box_slot_index(box2_id)`.
4. `service.py:254-259` — `_box_slot_index` calls `await self.inventory.where_is(box_id)`.
5. `app/tlc/inventory.py:54-55` — `where_is`: `if row.location_id is not None: return LocationAddress(slot=SlotId.parse(row.location_id))`.
6. `SlotId.parse("tlc_rack_box_2ml_l1_slot_1")` → **raises** `ValueError("unrecognized TLC slot id: 'tlc_rack_box_2ml_l1_slot_1'")` at `domain.py:154`. **This is the live-error site.**

**Required slot for acceptance**: the chosen box must sit on a **BENCH** slot whose id matches `tlc_tube_box_2ml_slot_{1..3}` (`LocationKind.TLC_BEFORE_CC_TUBE_BOX_2ML_SLOT`, codec spec at `domain.py:325`). Only the seed box `tube_box_2ml_001` (on `tlc_tube_box_2ml_slot_1`, `seed.py:435`) satisfies this — and that box is **never surfaced** by the selector (§2).

**Validator path note (why the error was raw, not a clean 400)**: `CommandValidator._validate_tlc_objects` *intends* to clean-400 with "is not on a known rack-slot" — `app/services/command_validator.py:509-511` does `address = await inventory.where_is(box_id); if address is None ...`. But `where_is` **raises** (not returns `None`) for a storage id (step 6 above), so the guard at `command_validator.py:510` never executes; the raw `ValueError` propagates. The validator's 400 is dead code against the storage family. (If the fix keeps any storage path, this guard should be hardened to catch the raise — but the primary fix removes the storage box from the selector entirely.)

### 4. The physical reality (Q4) — the decisive fact

What the **code** tells us (strong, but not a hardware ground-truth):

- The model treats the **bench** slot as the robot's address and the **rack** slot as storage. Verbatim, `location.py:46-48`: storage slots are "display/inventory … the robot never addresses them"; bench slots are the "robot dispatch address." `seed.py:432-434` says the bench box "is the box the chemist-declared-placement / planner flow addresses … its `location_id` must stay a parseable Workspace slot for `where_is`/SlotId."
- **No storage→bench move op exists.** I searched `app/tlc/` and the shared protocol: `TubeBox.move_to` (`domain.py:464`) only rewrites a box's `location` field in the inventory model; `app/tlc/placement.py` authors location *from succeeded robot ops* (`_move_box`, `placement.py:121`) but there is **no planner op** and **no `LocationKind`** that represents "pick box from storage rack and place on bench." The planner (`app/tlc/planner.py`) addresses only bench/Workspace `LocationKind`s. There is no rack→bench transfer in the op vocabulary.

**Implication**: as modeled, the robot can only pick sample tubes from the **bench** 2 mL box slot. The storage rack is a *different* location with no path into the dispatch program. So the selector is showing the **wrong** boxes.

**The one fact I cannot prove from code (Q4 for Drake)**:

> In the real lab, does the robot pick the sample tube **directly from the bench 2 mL box slot** (`tlc_tube_box_2ml_slot_*`) — meaning the chemist must place tubes into the bench box, and the selector should show bench boxes (**fix a**)? Or does the chemist place tubes into a **storage-rack** box that the robot must first **move onto the bench** before picking — meaning a storage→bench move op is genuinely missing from the model (**fix c**, net-new)?

Everything in the code points to the bench (fix a). Confirm before implementing.

### 5. The correct bridge — options with tradeoffs + exact file:line

#### (a) FE selector surfaces the BENCH box(es) the planner accepts — RECOMMENDED (if Q4 = "robot picks from bench")

- **Change**: `get_sample_tube_boxes` reads `LocationType.TLC_TUBE_BOX_2ML_SLOT` instead of `TLC_RACK_BOX_2ML_SLOT`.
- **Touches**:
  - `app/services/preparation_service.py:419` (the `get_by_type(TLC_RACK_BOX_2ML_SLOT)` call) and `:474-484` (`_rack_box_slot_meta` regex, which is storage-id-shaped).
  - Note: `preparation_service.py:558-617` already has `_workspace_box_views` that reads `TLC_TUBE_BOX_2ML_SLOT` for the Workspace view — the bench-box grid logic **already exists** and can be reused, reducing this to wiring.
- **Pros**: matches the feature intent ("chemist picks the tube the robot picks") and the modeled physical reality; the only box on a parseable slot (`tube_box_2ml_001`) becomes selectable; the planner/validator need **zero** change.
- **Cons**: the consumables/maintenance page still wants the storage view — so this likely needs a **separate** bench-box selector data source, not a repurpose of the shared endpoint (the maintenance page must keep showing storage boxes). The current single-endpoint reuse (FE `TubeSelectorGrid` ↔ storage endpoint) is the thing to split. Possibly: add a `source=bench` / dedicated selector endpoint, or have the FE selector consume the Workspace box grid instead.

#### (b) Widen `SlotId.parse` to also accept the storage-rack family — WRONG

- **Change**: add a `_SlotSpec` (and a `LocationKind` + protocol `Location` member) for `tlc_rack_box_2ml_slot`.
- **Touches**: `app/tlc/domain.py:309-342` (`_SLOT_SPECS`), plus a new `LocationKind` and `Location` member in `bic-shared-types` (`robot_protocol/skills/tlc_ops`).
- **Why wrong**: the planner would then emit a robot address pointing at a **storage** slot the robot cannot reach (per Q4 / the model). It makes `parse` succeed but produces a physically-undispatchable program — it hides the bug instead of fixing it. Only valid if the robot genuinely picks from storage (Q4) *and* a transfer op exists (it doesn't).

#### (c) Dispatch remaps/moves storage→bench before planning — correct ONLY if Q4 = "robot moves box from storage"

- **Change**: introduce a storage→bench move step (a `LocationKind` + planner op + placement authoring) so a storage box is relocated onto a bench slot before `_box_slot_index`.
- **Touches**: new op in `app/tlc/planner.py`; new `LocationKind`/`Location` in shared types; `app/tlc/service.py:186-252` (`plan_from_request`) to prepend the move; `app/tlc/placement.py` to author the new location.
- **Pros**: physically correct *if* the rack→bench move is part of the real workflow.
- **Cons**: substantial net-new work; **no such op exists today** (§4). Don't pursue unless Q4 confirms the robot moves the box.

#### (d) Re-seed so the dispatchable box appears in the selector's storage query — BAND-AID

- **Change**: put a dispatchable box on a slot the storage query surfaces (e.g. also seed `tube_box_2ml_001` content under a `tlc_rack_box_2ml_*` slot), or move the bench box onto a storage slot.
- **Touches**: `app/data/seed.py:431-457` (and the mirror `alembic/versions/*seed*` + any seed migration `d5f2a8c4...`).
- **Why band-aid**: the selector would surface a box, but its `location_id` is still a **storage** id → `SlotId.parse` still raises. To make (d) work you'd have to also do (b) or (c). On its own it does **not** fix dispatch. The explicit seed comment at `seed.py:432-434` warns *against* moving the bench box onto the rack precisely because it must stay parseable. Reject.

---

## Caveats / Not Found

- **Q4 is unresolved by code** (§4). The recommendation (a) is conditional on Drake confirming the robot picks sample tubes from the **bench** 2 mL box, not from the storage rack. If the real workflow has the robot move the box from storage→bench, the answer flips to (c) and is net-new work.
- The `task.py current` script reported **no active task**; I wrote to the path given in the task brief (`.trellis/tasks/06-26-06-26-tlc-params-form-ui-dispatch/research/`). If that is not the intended target, flag it.
- I did **not** read the full diff of `b36273f` line-by-line; the commit message + the seed/codec/endpoint state confirm the split (bench box pre-existed; the 3 storage demo boxes + the storage-only selector endpoint both landed in this session). The "one bench box was dispatchable; the new demo boxes went on storage slots" origin story is corroborated by `seed.py:435` (bench, pre-existing comment) vs `seed.py:443-457` (storage demo boxes).
- A secondary, real bug: `command_validator.py:509-511`'s clean-400 guard is **dead** for storage ids because `where_is`/`SlotId.parse` *raises* rather than returns `None`. Even after the primary fix, if any storage box id can still reach the validator, this guard should catch the `ValueError`. Noted, not fixed.

---

# Physical model — robot pick source (Q4 resolved from the op program)

- **Query**: Where does the TLC robot physically pick the sample tube from — directly from a BENCH 2mL box (`tlc_tube_box_2ml_slot_*`), or does the workflow first MOVE the box from a STORAGE rack onto the bench? Decides fix (a) surface bench boxes vs fix (c) add a storage→bench move step.
- **Scope**: internal (BIC-lab-service `app/tlc/` + BIC-shared-types `robot_protocol/skills/tlc_ops.py` + seed + TLC spec/design docs), read-only
- **Date**: 2026-06-27

## ANSWER (one line)

**Fix (a) — the robot picks sample tubes from a BENCH box slot (`tlc_tube_box_2ml_slot_*`); there is NO storage-rack→bench move, so the selector must surface bench-reachable boxes, not `tlc_rack_box_2ml_*` storage boxes.**

The emitted op program proves it three ways: (1) the only box-move in the program fetches from the **supply shelf** (`tlc_supply_shelf`, station `sa_004`) and lands on a **bench** slot, and that move's source is a HARDCODED spec default — it has nothing to do with the chemist's chosen box; (2) every sample-tube aspirate addresses the box `at` a **bench** `TubeBox2mlSlotLoc` (`slot ∈ 1..3`); (3) the storage rack (`tlc_rack_box_2ml_slot`) has **no `LocationKind`, no `_SlotSpec`, no op** — it is unreachable by the robot by construction. The prior diagnosis's "no rack→bench move exists" conclusion is confirmed AND sharpened: there is a move op, but it is shelf→bench, not rack→bench, and it ignores the chosen box entirely.

> One real-world caveat that does NOT change the verdict but Drake should know: the model assumes the chosen box is **already on a bench slot** at request time (placed there by a human via the §6c Workspace fill path, or seeded). The op program never relocates the chemist's specific box from wherever inventory says it lives — it just emits an aspirate against `tube_box_2ml_slot`. So "robot picks from bench" is true; "the box gets to the bench" is a human/seed precondition, not a robot op. See Q5.

---

## Q1 — The op sequence for one sample-tube round (what `pick`/aspirate actually addresses)

Entry: `plan_round` (`app/tlc/planner.py:297`). Round 1 calls `_pickup_materials` (`planner.py:308,532`); then `_spot_plate` (`planner.py:317,636`) does the actual sample-tube handling. The aspirate op for samples:

`_spot_plate` (`planner.py:636-685`) — for each sample tube it opens the lid (`_open_lid`), then ONE row-aspirate, then closes each lid:

- **Open** (`planner.py:646`, via `_open_lid` `planner.py:436-478`): `PickOp(object=tube_2ml, source=_box_2ml_cell(box2_slot, row, col))` then choreography through `cap_station`. The tube's source is a **box cell** built by `_box_2ml_cell` (`planner.py:246-248`):
  ```python
  def _box_2ml_cell(box_slot: int, row: WellRow, col: int) -> Location:
      at = TubeBox2mlSlotLoc(slot_from_left=box_slot)        # ← BENCH slot, 1..3
      return TubeBox2mlLoc(at=at, row=row, col=col)
  ```
  So the tube is addressed as "cell (row,col) inside a box that is `at` a **`TubeBox2mlSlotLoc`** (the bench 2mL slot)". `box2_slot = spec.tube_box_2ml_slot` (`planner.py:638`), bounded `ge=1, le=3` (`planner.py:155`).
- **Aspirate** (`planner.py:655-663`): `TlcCentrifugeTubeAspirateOp(tube_type=ML_2, volume, row=plate.row, col=1)` — the pipette aspirate carries no Location; it implicitly draws from the box the tubes were just opened in (the bench-slot box). It NEVER references a storage-rack address.
- **Close** (`planner.py:677`): returns each tube to `_box_2ml_cell(box2_slot, ...)` — same bench slot.

**`TubeBox2mlSlotLoc`** (shared-types `tlc_ops.py:361-363`): `type = TLC_BEFORE_CC_TUBE_BOX_2ML_SLOT`, `slot_from_left: int = Field(ge=1, le=3)`. This is the bench dispatch slot. There is no storage-rack variant of `BoxAt` (`tlc_ops.py:432-434`): `BoxAt = PipettingAgvSlotLoc | TubeBox2mlSlotLoc | TubeBox50mlSlotLoc | WorkStationLoc` — a box's `at` can be the AGV tray, a bench tube-box slot, a 50mL bench slot, or a work-station, but **never** `tlc_rack_box_2ml_slot` (which has no protocol member at all).

**Is the box assumed already on the bench, or fetched?** Round 1 fetches it — but from the SHELF, see Q2. The sample aspirate itself assumes the box is `at` the bench slot (`TubeBox2mlSlotLoc`).

## Q2 — Is there ANY storage→bench (rack→deck) move op? (the decisive search)

**There is a box MOVE op, but its source is the SUPPLY SHELF, not the storage rack — and it ignores the chosen box.**

`_pickup_materials` (`planner.py:532-577`), round 1 only:
```python
seq.op(AgvMoveOp(op_id=…, station=spec.supply_station))                       # drive AGV to sa_004 (planner.py:534)
box2 = ObjectRef(type=TUBE_BOX_2ML, id=spec.tube_box_2ml_id)
seq.op(PickOp(object=box2, source=_supply_shelf(spec.supply_2ml_layer,
                                                spec.supply_2ml_column)))     # PICK from SUPPLY SHELF (planner.py:537-541)
seq.op(PlaceOp(object=box2,
               to=_table_slot(TLC_BEFORE_CC_TUBE_BOX_2ML_SLOT,
                              spec.tube_box_2ml_slot)))                        # PLACE onto BENCH slot (planner.py:542-548)
```
- The PICK source is `_supply_shelf(...)` → `TlcSupplyShelfLoc` (`planner.py:222-223`; shared-types `tlc_ops.py:413-418`, `LocationKind.TLC_SUPPLY_SHELF`). That is the **TLC 备料货架区 / supply shelf** at station `sa_004`, NOT the `tlc_rack_box_2ml_*` storage rack and NOT the chemist's chosen box's location.
- The PICK source coordinates are **hardcoded spec defaults**: `supply_2ml_layer=3`, `supply_2ml_column=1` (`planner.py:151-152`), `supply_station=WS_BIC_09_SA_004` (`planner.py:150`). `plan_from_request` (`service.py:231-251`) builds the spec WITHOUT setting any `supply_*` field, so these defaults always apply — the move always fetches from shelf L3/C1 regardless of which box the chemist picked.
- The PLACE dest is `tube_box_2ml_slot` (bench), bounded 1..3.

**No rack→bench (`tlc_rack_box_2ml_*` → `tlc_tube_box_2ml_slot_*`) op exists anywhere.** Confirmed by:
- The storage rack has **no `LocationKind`** (`tlc_ops.py:221-247` lists every kind; `tlc_rack_box_2ml_slot` is absent — it is a LabService-only `LocationType`, `location.py`), so no op can address it.
- No `_SlotSpec` for it in the codec (`domain.py` `_SLOT_SPECS`; prior diagnosis §1/§3) — `SlotId.parse('tlc_rack_box_2ml_l1_slot_1')` RAISES.
- `app/tlc/inventory.py` `TubeBox.move_to` / `persist_box` only rewrite a row's `location_id` field (`inventory.py:119-148`); they are write-side inventory bookkeeping, not robot ops, and they are not invoked to relocate a storage box onto the bench in the dispatch path.

The corroborating archived research `agv-vs-shelf-pickup.md:9` states the verdict directly: **"START_TLC round-1 pickup (取料) is SHELF → TABLE DIRECT"** (supply shelf → work table), with three authoritative sources agreeing (`agv-vs-shelf-pickup.md:11-18`). The `_agv` helper was vestigial/dead even for the shelf path.

**Decisive signal**: no rack→bench move op exists and the only box-move is a hardcoded shelf→bench fetch → **fix (a)**, not (c). (c) would require a net-new `LocationKind` + op + codec spec for the storage rack — none of which exists.

## Q3 — What the two box-slot families mean physically + workstation mapping

Three distinct families touch 2mL boxes (the prior diagnosis named two; the op program reveals the supply shelf as the actual fetch source — a third):

| Family / id scheme | `LocationType` (LabService) | Protocol `LocationKind`? | Workstation / area | Role |
|---|---|---|---|---|
| `tlc_tube_box_2ml_slot_{1..3}` | `TLC_TUBE_BOX_2ML_SLOT` | **YES** `TLC_BEFORE_CC_TUBE_BOX_2ML_SLOT` (`tlc_ops.py:237,362`) | **wb_001 操作台** (operating bench) — the §6c Workspace "robot's working bench" (`tlc-placement.md:360-362`) | The robot's BENCH dispatch slot. Box-cell aspirate addresses this (Q1). Seed box `tube_box_2ml_001` sits here (`seed.py:435`). |
| `tlc_supply_shelf_l{3,4}[_c{n}]` | `TLC_SUPPLY_SHELF` | **YES** `TLC_SUPPLY_SHELF` (`tlc_ops.py:233,413`) | **sa_004 备料货架区** (staging/supply shelf area) | The SUPPLY SHELF the round-1 pickup fetches the box FROM (Q2). Seeded `seed.py:396-397`. |
| `tlc_rack_box_2ml_l{F}_slot_{N}` (5/floor) | `TLC_RACK_BOX_2ML_SLOT` | **NONE** | maintenance-page **storage/display ONLY** (`tlc-placement.md:323-326`, `seed.py:398-401`) | TLC Rack storage. The robot **never addresses it** (`tlc-placement.md:325`). The FE tube selector wrongly reads THIS (prior diagnosis §2). |

Workstation seed (`seed.py:350-354`):
- `LOC_WS_SA_004 = "ws_bic_09_sa_004"` → "TLC备料货架区" (staging_area) = **supply shelf area** — where pickup sources from.
- `LOC_WS_WB_001 = "ws_bic_09_wb_001"` → "TLC操作台" (general) = **operating bench** — where the bench box slots live; `planner.main_station = WS_BIC_09_WB_001` (`planner.py:149`).
- `LOC_WS_WB_002 = "ws_bic_09_wb_002"` → "TLC废弃区" (general) = disposal.

So: **`tlc_rack_box_2ml_l*_slot` → (no workstation; storage/maintenance only)**; **`tlc_tube_box_2ml_slot` → wb_001 操作台 (bench)**. The supply-shelf fetch source maps to **sa_004**. The storage rack and the supply shelf are NOT the same thing — the storage rack is a display-only inventory surface with no robot path at all.

The TLC spec `tlc-placement.md` §6a (`tlc-placement.md:314-326`) states the bench/storage distinction verbatim: "There are TWO racks holding 2ml tube boxes, and they MUST NOT be conflated… TLC Workspace — `tlc_tube_box_2ml_slot_{1..3}`… The robot picks sample boxes from here… TLC Rack — `tlc_rack_box_2ml_l{F}_slot_{N}`… Storage/display ONLY… the robot never addresses them."

## Q4 — The PipettingAgvSlot.TUBE_BOX tray story

`PipettingAgvSlot.TUBE_BOX` (`tlc_ops.py:179-191`) is the離心管盒位 (slot 2) on the **pipetting-robot AGV tray** — a staging surface the pipetting robot operates from. `PipettingAgvSlotLoc` (`tlc_ops.py:337-341`) is a valid `BoxAt` (`tlc_ops.py:432-434`), so a box's `at` CAN be the AGV tray.

But for sample handling **in the current planner, the box stays on the BENCH slot, not the AGV tray**:
- `_spot_plate` addresses every sample cell via `_box_2ml_cell` whose `at = TubeBox2mlSlotLoc` (bench), never `PipettingAgvSlotLoc` (`planner.py:246-248,650,681`).
- There is no `架料到移液 AGV` (stage-to-AGV) op emitted. `agv-vs-shelf-pickup.md:106-113` flags this as an unconfirmed dispensing-phase question: the protocol doc example shows the box staged onto the AGV before dispensing, but the planner keeps it on the bench. The TLC spec records it as an open blocker: "**AGV-staging-before-dispensing is unconfirmed**" (`tlc-placement.md:440-442`).

How a box gets onto the AGV tray: not by any sample-handling op the planner emits today. So `tlc_tube_box_2ml_slot` is the **bench** position (wb_001), NOT the AGV tray. The AGV-tray-vs-bench question is a separate, unresolved dispensing-phase detail that does NOT bear on the selector fix — either way the box is on a robot-reachable BENCH/AGV surface addressed by a protocol `LocationKind`, never on the storage rack.

## Q5 — Reconcile with the feature intent ("chemist places tubes, robot picks them")

Model B (the §5b declared-placement contract, `tlc-placement.md:227-285`): the chemist physically puts each 2mL sample tube into a box cell and DECLARES `{tube_id, box_id, cell}` on the request. `plan_from_request` writes those into `tlc_inventory` (`service.py:199`), then plans against the chemist's `box_id`.

The physical story that is CONSISTENT with the emitted program:

1. The chemist's chosen box must **already sit on a bench slot** at request time. `plan_from_request` derives the box's bench slot via `_box_slot_index` → `where_is(box_id)` → `SlotId.parse(box.location_id)` (`service.py:200,254-259`; `inventory.py:54-55`). For this to succeed, `box.location_id` MUST be a parseable BENCH id (`tlc_tube_box_2ml_slot_*`). If the box is on a storage-rack slot, `SlotId.parse` RAISES (prior diagnosis §3) — dispatch is impossible.
2. The robot then opens/aspirates each declared tube from that **bench** box slot (Q1). It does NOT fetch the chemist's box from storage — the only fetch (`_pickup_materials`) is a hardcoded shelf→bench move for a generic box, and even that targets the bench `tube_box_2ml_slot`, never the storage rack.

So the consistent story is: **"the chemist places sample tubes into a BENCH box (already on the robot's bench, slot 1..3), declares them, and the robot picks them off the bench."** The selector must therefore offer **bench boxes** (the box(es) on `tlc_tube_box_2ml_slot_*`, surfaced by the §6c Workspace view), NOT the storage-rack boxes the current `GET /preparations/sample-tube-boxes` returns. This is exactly fix (a).

The storage-box story ("chemist places tubes into a storage box that the robot moves onto the bench") is INCONSISTENT with the program: there is no rack→bench move, `where_is`/`SlotId.parse` rejects a storage `location_id`, and the storage rack has no protocol address. Fix (c) would be net-new modeling work with zero current code backing it.

## Residual question for Drake (does NOT block fix (a) selection, but worth a one-line confirm)

The CODE answer is unambiguous: robot picks from the bench, fix (a). The one thing not encoded anywhere is the **physical hand-off**: in the real lab, does the chemist place sample tubes into a box that is **physically on the robot's bench (wb_001) at that moment**, or into a box on a side rack that a HUMAN (or the round-1 shelf-pickup) carries to the bench before the run? The program assumes the chosen box's `location_id` is already a bench slot — it does not relocate the chemist's specific box. If in reality the chemist loads tubes into a storage/staging box that then needs to reach the bench, that hand-off is a **human/process step or a §6c Workspace-fill action**, not a robot op — and the selector should still show bench boxes (where the box will be when the robot runs). Precise question:

> When the chemist declares sample tubes for a TLC run, is the box they load **already sitting on the robot's bench slot (`tlc_tube_box_2ml_slot_1..3`, wb_001 操作台)** at declare time — i.e. the FE selector should list the 1–3 bench boxes? Or do they load a box on the side storage rack expecting the system/human to move it to the bench first? (The code only supports the former; the latter would need a new move op = fix c.)

## Caveats / Not Found

- The "hardcoded shelf fetch ignores the chosen box" point is a SEPARATE latent issue from the selector taxonomy bug: even once the selector offers a bench box, round-1 `_pickup_materials` emits a PICK from supply-shelf L3/C1 for a generic `tube_box_2ml_id` — it does not fetch the chemist's specific declared box from wherever it physically is. For the seed/happy path the chosen box already equals the bench box (`tube_box_2ml_001` on `tlc_tube_box_2ml_slot_1`), so the program is self-consistent; but the pickup source is a fixed default, not derived from the chosen box. Flagged, not in scope to fix here.
- AGV-tray-during-dispensing is an acknowledged open question (`tlc-placement.md:440-442`, `agv-vs-shelf-pickup.md:106-113`) — orthogonal to the selector fix.
- I confirmed the op vocabulary against `BIC-shared-types/bic_shared_types/robot_protocol/skills/tlc_ops.py` (the source repo), not only the installed `.venv` copy; both are present and identical in the relevant `LocationKind`/`BoxAt`/`TubeBox2mlSlotLoc` definitions.
