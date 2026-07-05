# Research: R5 — Robot-completion path writes to TLC Workspace slots?

- **Query**: Does the lab service ALREADY update the 6 TLC Workspace robot slots' occupancy when the robot finishes a TLC run? Trace the exact MQ → handler → DB write path with file:line.
- **Scope**: internal (BIC-lab-service)
- **Date**: 2026-06-27
- **Repo**: `/Users/drakezhou/Development/BIC/BIC-lab-service`

## Verdict

**YES (with one nuance about WHEN).** The robot-completion path DOES write all 6 Workspace slot
types' occupancy into `tlc_inventory.location_id`. Occupancy of a Workspace slot is **derived**
(`WHERE location_id = :slot_id`), never a flag — so writing an object's `location_id` to a slot
IS the occupancy write.

Two distinct writes touch these slots, in two phases of a TLC run:

1. **At task confirm / dispatch** (`TLCService` → `TLCAllocator` → planner): chooses which slot
   each object goes to and bakes the addresses into the dispatched `tlc_ops`. The allocator mints
   tip-box rows but does NOT write their `location_id` yet (occupancy at allocation time is by
   row-existence + an in-pass `_reserved_slots` set — `allocate.py:155-166`).
2. **On robot success** (`#.result` → `ResultHandlerService._infer_tlc_placement` →
   `PlacementWriter`): replays every succeeded `place` op and writes the object's final
   `location_id` (and box-cell / parent for tubes). **This is the robot-completion write the PRD
   asks about.** It is authored by LabService itself because, by agreement, the TLC robot does NOT
   report placement back (`placement.py:1-21`).

So: the robot-completion path writes Workspace-slot occupancy via `PlacementWriter`, and it covers
**all 6 slot types** (each maps to a `LocationKind.TLC_BEFORE_CC_*_SLOT` the writer can address).

## Findings

### The 6 Workspace slot types and their identifiers

| PRD slot type | `locations.type` enum (`app/data/models/location.py`) | `LocationKind` (shared-types, used by writer/planner) | seed count |
|---|---|---|---|
| `tlc_tube_box_2ml_slot` | `LocationType.TLC_TUBE_BOX_2ML_SLOT` (`location.py:45`) | `TLC_BEFORE_CC_TUBE_BOX_2ML_SLOT` (1-3) | 3 |
| `tlc_tube_box_50ml_slot` | `LocationType.TLC_TUBE_BOX_50ML_SLOT` (`location.py:50`) | `TLC_BEFORE_CC_TUBE_BOX_50ML_SLOT` (1-3) | 3 |
| `tlc_tip_box_slot` | `LocationType.TLC_TIP_BOX_SLOT` (`location.py:51`) | `TLC_BEFORE_CC_TIP_BOX_SLOT` (1-3) | 3 |
| `tlc_silica_plate_slot` | `LocationType.TLC_SILICA_PLATE_SLOT` (`location.py:54`) | `TLC_BEFORE_CC_SILICA_PLATE_SLOT` (1-4) | 4 |
| `tlc_developing_tank_slot` | `LocationType.TLC_DEVELOPING_TANK_SLOT` (`location.py:52`) | `TLC_BEFORE_CC_DEVELOPING_TANK_SLOT` (1-3) | 3 |
| `tlc_developing_tank_lid_slot` | `LocationType.TLC_DEVELOPING_TANK_LID_SLOT` (`location.py:53`) | `TLC_BEFORE_CC_DEVELOPING_TANK_LID_SLOT` (1-3) | 3 |

Seeded as `locations` rows in `seed.py:375-385` (`_TLC_SLOT_INDEXED`, expanded to
`{stem}_slot_{i}`) via `_build_tlc_slot_rows()` (`seed.py:405-421`) and inserted at
`seed.py:582-588`. Occupancy is tracked in `tlc_inventory.location_id` (FK → `locations.id`),
`tlc_inventory.py:36`.

The slot codec lives in `app/tlc/domain.py:SlotId` (`domain.py:101-182`); the per-kind specs at
`domain.py:309-342` cover exactly these 6 (plus the other 17 TLC kinds). `SlotId.location_id`
(`domain.py:156-161`) round-trips a `locations` row id ↔ a protocol `Location` address.

---

### 1. `log_handler.py` — `EntityUpdateService` and the `#.log` writer

- `EntityUpdateService` (`log_handler.py:49`) is the **sole writer of CC/RE entity states** on the
  `#.log` channel. Entry point `handle_robot_log(data)` (`log_handler.py:458`) parses the MQ dict
  as `RobotResult`, loops `result.updates`, and routes each via
  `process_entity_update` (`log_handler.py:105`).
- Its `match` (`log_handler.py:118-136`) handles ONLY: `RobotUpdate`, `SilicaCartridgeUpdate`,
  `SampleCartridgeUpdate`, `TubeRackUpdate`, `RoundBottomFlaskUpdate`, `CCSExtModuleUpdate`,
  `CCSystemUpdate`, `EvaporatorUpdate`. These write to `consume`, `container`, `container_rack`,
  `devices`, `robots` (`_update_consumable` :217, `_update_container_rack` :245,
  `_update_container` :271, `_update_device` :355, `_update_evaporator` :402).
- **It NEVER references `tlc_inventory` or any TLC Workspace slot.** There is no `TlcInventory`
  case in the union, and grep confirms `tlc_inventory` appears in zero lines of `log_handler.py`.

> Conclusion for hop 1: the `#.log` writer does NOT touch the 6 Workspace slots. The TLC robot's
> intermediate log updates (if any) are not the channel that persists Workspace occupancy.

---

### 2. Where `tlc_inventory` rows are inserted / updated / deleted (full grep)

Writers of `tlc_inventory` (across `app/`, excluding tests/alembic):

| Site | Operation | Trigger |
|---|---|---|
| `app/tlc/inventory.py:119 persist_box` | upsert box + nested tube rows (`location_id`, parent, cell) | called by `PlacementWriter` (robot success) + `TLCService.declare_placement` |
| `app/tlc/inventory.py:150 set_location` | one-field `location_id` write (plain object onto slot) | called by `PlacementWriter._place_plain` (robot success) |
| `app/tlc/inventory.py:154 delete_unplaced_lab_minted` | delete orphan lab-minted tip-box rows | dispatch-failure / abandon cleanup |
| `app/tlc/inventory.py:177 _set_placement` / `:192 _upsert` | low-level row writes (location/parent/cell/state) | internals of the two above |
| `app/tlc/allocate.py:132 _mint` (`repo.create`) | INSERT a fresh lab-minted tip-box row (NO slot) | task confirm/dispatch (`TLCService`) |
| `app/services/preparation_service.py:591-... (case "tlc_inventory")` | maintenance fill → create one row; clear → delete rows | **human Maintenance page**, NOT robot |
| `app/tlc/maintenance.py:102 fill / :117 clear` | create/remove one `tlc_inventory` instance | human maintenance bridge |
| `app/data/seed.py:659-667` / alembic seeds | INSERT seed inventory rows | DB reset / migration |

Readers of `tlc_inventory` (occupancy): `inventory.py:where_is` (:43), `what_at` (:66),
`contents` (:76), `available_of_type` (:82), `load_box` (:100); `preparation_service.py:319`
(`what_at` for the sample-tube-box grid); `command_validator.py:665` (readiness count).

**Robot-completion-triggered writers = `persist_box` + `set_location` (+ the orphan-delete on
failure), all invoked exclusively by `PlacementWriter`.** Everything else is task-confirm-time
(allocator mint) or human-maintenance-time (prep service / maintenance bridge) or seed.

---

### 3. Exact robot-completion code path (hop by hop)

```
Robot finishes a TLC op-skill (START_TLC / END_TLC)
  → MQ #.result queue
  → mq_consumer → handle_robot_result(data)                      result_handler.py:50
  → RobotResult.model_validate(data)                              result_handler.py:63
  → ResultHandlerService.process_result(result)                  result_handler.py:72,125
      → mark skill completed (code 200)                          result_handler.py:153-156
      → read-only drift validation of updates (NO writes here)   result_handler.py:165-166, _validate_entity_update :250
      → if result.is_success():                                  result_handler.py:171
          _infer_tlc_placement(result, task_id)                  result_handler.py:172, 211
            → guard: result.skill_type in TLC_OP_SKILLS          result_handler.py:227  (placement.py:52 = {START_TLC, END_TLC})
            → SkillRepository(...).get(skill_id) → skill.params   result_handler.py:232
            → async with session.begin_nested():  (SAVEPOINT)    result_handler.py:238
                writer = PlacementWriter(session)                result_handler.py:239
                await writer.infer_and_write(skill.params, id)   result_handler.py:240
  → PlacementWriter.infer_and_write                              placement.py:83
      → extract_tlc_ops(params) → params.lab_params.tlc_ops      placement.py:61-72, 91
      → for each op: _dispatch_op                                placement.py:92-93
          → op.op == "place"? → _handle_place                    placement.py:95-97, 103
              → resolve dest_kind = LocationKind(dest.type)      placement.py:115
              → tube into box cell → _place_tube_into_box        placement.py:118-119  → repo.persist_box  inventory.py:119
              → box object → _move_box                           placement.py:120-121  → repo.persist_box  inventory.py:119
              → plain object → _place_plain                      placement.py:122-123  → repo.set_location inventory.py:150
                  → dest_slot = SlotId.from_address(dest)        placement.py:153  (decodes to one of the 6 TLC_BEFORE_CC_*_SLOT)
                  → repo.set_location(object_id, dest_slot.location_id)   placement.py:155
                      → row.location_id = <slot id>; flush       inventory.py:184-189
  → back in process_result: store SkillResult, clear robot skill result_handler.py:180-197
  → await self.session.commit()  (flushes the SAVEPOINT writes)  result_handler.py:199
```

**The DB write to a Workspace slot is `inventory.py:184` (`row.location_id = location_id`)** for
plain objects (silica plate, developing tank, lid, tip box) and `inventory.py:127-148`
(`persist_box`) for the 2ml/50ml boxes (box's own `location_id` is the slot; cascade leaves nested
tubes deriving their position from the parent).

Atomicity / isolation notes:
- The writer runs in the SAME Phase-1 session as result finalization, inside a **nested SAVEPOINT**
  (`result_handler.py:238`) so a placement bug never strands the skill IN_PROGRESS
  (`result_handler.py:218-244`). NO commit inside the writer — the Phase-1 `commit()` flushes it.
- Guarded strictly by `skill_type ∈ {START_TLC, END_TLC}` (`result_handler.py:227`,
  `placement.py:52`), so CC/RE results never enter this path — the `log_handler` sole-writer rule
  for CC/RE entities is untouched.

Which of the 6 slots a `place` resolves to is decided UPSTREAM at dispatch by the planner baking
`SlotId(...).to_address()` into each op's `to` field — see `planner.py:546` (2ml box),
`:556` (50ml box), `:566/:575` (tip boxes spot/pep), `:712` (silica plate),
`:696/:719/:734` (developing tank), `:703/:727` (tank lid). The writer just decodes those addresses
back (`SlotId.from_address`, `placement.py:127,144,153`) and persists `location_id`.

---

### 4. Plain YES / NO / PARTIAL with evidence

**YES — the robot-completion path already writes occupancy for all 6 Workspace slot types**, via
`PlacementWriter` on `#.result` success. Per-slot evidence:

- **2ml box slot / 50ml box slot** — box `place` → `_move_box` (`placement.py:142-149`) →
  `persist_box` writes the box's `location_id` to `tlc_tube_box_2ml_slot_*` /
  `tlc_tube_box_50ml_slot_*` (`inventory.py:127-136`). Planner targets at `planner.py:546,556`.
- **tip box slot** — tip box is a plain object → `_place_plain` → `set_location`
  (`placement.py:151-156`, `inventory.py:150`). Planner targets at `planner.py:566,575`.
- **silica plate slot** — plain → `_place_plain` → `set_location`. Planner target `planner.py:712`.
- **developing tank slot** — plain → `_place_plain` → `set_location`. Planner targets
  `planner.py:696,719,734`.
- **developing tank lid slot** — plain → `_place_plain` → `set_location`. Planner targets
  `planner.py:703,727`.

Caveat that makes it *almost* PARTIAL (worth flagging for the design's conflict section):

- **It is conditional on the op being a `place` whose `to` decodes to a Workspace slot, and on the
  skill SUCCEEDING.** Pure-staging ops (pick/clamp/aspirate/open_lid/…) carry no placement and are
  skipped (`placement.py:98-99`). If a TLC run is abandoned or fails before the `place`, the slot
  occupancy reflects the *last successfully authored* placement, not the intended final layout. The
  seeded baseline (`seed.py:431-468`) pre-places boxes/plate/tanks/lids at slot 1/2, so a fresh DB
  is never empty.
- **`state` is NOT written on placement** (only `location_id`/parent/cell). Lifecycle
  (`used`/`disposed`) is explicitly deferred (`placement.py:15-18`, `placement.py:172`
  `_log_move` writes only `location_id` in the event payload). Objects keep the `state` allocation
  gave them (`unused`). So "occupied vs free" is authored; "used vs unused" on a Workspace slot is
  NOT authored by the robot-completion path today.
- **Anonymous tip boxes**: their row is minted at dispatch with NO slot (`allocate.py:132-140`);
  its `location_id` is only written when a `place` op for that minted id succeeds. Until then the
  slot is derived-free.

---

### `seed.py` definition + RackArea / API exposure (PRD says NOT yet exposed — verified)

- The 6 Workspace slot types are seeded purely as `locations` rows (`seed.py:375-385, 405-421`) with
  `parent_id = NULL` (placement is by the `SlotId` codec, not a `locations` hierarchy —
  `seed.py:405-411`). Tracked inventory seeded at `_TLC_INVENTORY_INSTANCES`
  (`seed.py:431-479`) places one object per kind at slot 1 (and tank/lid at slots 1-2).

- **No `RackArea` exposes these 6 Workspace slots — VERIFIED.** The seeded `rack_tlc` RackAreas
  (`seed.py:181-248`) use `material_source = 'tlc_inventory'` but their `material_key`s are
  `dispensing_tip_box`, `spotting_tip_box`, `developing_solvent_system`, `sample_tube` — surfaced by
  COUNTING `tlc_inventory` rows by `object_type` and spreading them positionally across
  display-only RackSlots (`preparation_service.py:259-283 _tlc_inventory_slot_views`;
  `maintenance.py:71-99`). RackSlots "carry no `location_id` link to the TLC placement slots"
  (`preparation_service.py:262-264`).

- The only place that reads occupancy of a real TLC placement-slot `locations` row for display is
  `get_sample_tube_boxes` (`preparation_service.py:289-333`), and it deliberately reads the **TLC
  Rack STORAGE box slots** (`LocationType.TLC_RACK_BOX_2ML_SLOT`, `seed.py:398-402`,
  `preparation_service.py:307`) — explicitly commented "NOT the robot's Workspace dispatch slots"
  (`preparation_service.py:292-294`, and the same disclaimer in `seed.py:399`).

- Grep confirms the 6 `LocationKind.TLC_BEFORE_CC_*_SLOT` kinds appear only in
  `app/tlc/{domain,planner,service,allocate,placement}.py` (internal placement engine) — there is
  **no router, MCP tool, or RackArea that returns these Workspace slots' occupancy to a client.**

> So the data is being maintained (written on robot completion), but there is currently NO API /
> RackArea surface exposing the 6 Workspace slots. This matches the PRD claim. Building the
> Workspace view = adding a READ/expose layer over `tlc_inventory.what_at(<workspace slot id>)`;
> the write side already exists.

## Caveats / Not Found

- `python3 ./.trellis/scripts/task.py current --source` returned `(none)`, but the task dir
  `.trellis/tasks/06-27-tlc-workspace-view` exists with `prd.md`; output was written there.
- I did NOT run the code; this is a static trace. The SAVEPOINT/commit semantics are read from
  source + the CLAUDE.local lessons, not executed.
- "Conflict handling" the PRD gates on: the design must account for (a) occupancy is
  derived-by-row-existence (no free/occupied flag), (b) only `location_id` is authored on
  completion — not `state`, and (c) the write is best-effort inside a SAVEPOINT that may roll back
  silently on a placement bug (`result_handler.py:242-244` logs and continues).
