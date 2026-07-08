# Design — Generalize sample-tube cell maintenance to shelf storage boxes

Repo: `BIC-lab-service`. Parent decisions: D1 (popup maintains shelf + bench), D2
(maintain-then-select), D3 (2–4 bench dispatch contract unchanged).

## Current state (verified 2026-07-05)

- Storage boxes ALREADY exist as `tlc_inventory` rows with `location_id` = a
  `tlc_rack_box_2ml_l{F}_slot_{N}` location (`seed.py:413-427`); seed provides 5 slots per floor
  for L1+L2 (`seed.py:374-375`) — already matching the 配置表. Boxes are present on l2 slots 1–3
  and l1 slot 1; the rest are empty slots (`present=False` in the storage view).
- `update_bench_sample_tube_cell` (`preparation_service.py:488`) is bench-only ONLY because of its
  address gate: `where_is(box_id)` must resolve to a parseable dispatchable SlotId. The actual
  cell write (create/delete `tube_2ml` with `parent_object_id=box`, `cell_col/cell_row`) is
  location-agnostic.
- `update_slot` (`preparation_service.py:796`) has two write paths: RackSlot areas (generic +
  the sample-cartridge special-item exception) and a Workspace path for raw `locations`-row slots
  (`_resolve_workspace_slot` → `_update_workspace_slot`), which authors `tlc_inventory` occupancy
  by `location_id`. Storage box slots are raw `locations` rows of type `TLC_RACK_BOX_2ML_SLOT` —
  they are simply not in the Workspace map today.
- `TlcInventory` enforces `ck_tlc_inventory_placed` (`location_id OR parent_object_id NOT NULL`);
  `parent_object_id` FK is `ondelete="SET NULL"` — deleting a box row without handling contents
  would trip the check constraint.

## Changes

### 1. Cell endpoint accepts storage boxes

`update_bench_sample_tube_cell` → `update_sample_tube_cell` (route
`PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}` unchanged).

- Replace the `where_is` dispatchable-SlotId gate with: box row is top-level
  (`location_id IS NOT NULL`) and its location's `type` ∈
  {`TLC_TUBE_BOX_2ML_SLOT` (bench), `TLC_RACK_BOX_2ML_SLOT` (storage)}. Everything else 400s with
  the existing message shape.
- Cell validation and occupant create/delete logic unchanged.
- Response: return the view matching the box's home — `get_sample_tube_boxes(source="bench")` for
  a bench box, `source="storage"` for a shelf box — so the FE refreshes the grid it is rendering.
- Generalize `_next_bench_sample_tube_id` → `_next_sample_tube_id` (same collision-safe pattern,
  base derived from box id + cell). Existing bench ids are untouched.
- Update route summary/docstring (bench-only wording is now wrong).

### 2. Box add/remove rides the existing `update_slot` endpoint

No new endpoint. Add a storage-slot branch in `update_slot`, following the
`_update_workspace_slot` convention (resolve the `locations` row by type, author `tlc_inventory`
by `location_id`):

- `occupied=true` on an empty `TLC_RACK_BOX_2ML_SLOT` → create ONE `tube_box_2ml` row at the slot
  (`state="unused"`, minted id `tube_box_2ml_l{F}_{next}` pattern consistent with seed).
  Idempotent when the slot already holds a box.
- `occupied=false` → delete the box row AND its contained tubes in the same transaction
  (explicit content delete first — the SET-NULL FK would otherwise violate
  `ck_tlc_inventory_placed`). Physical reality: the box leaves the shelf with its tubes.
- `material_key` guard mirrors the existing paths (expects the sample-tube area code).
- Precedent: this is the same special-item allowance shape as the existing sample-cartridge
  exception — storage tube-box slots are popup-editable without becoming
  `is_maintainable=true` (consumables-page editable).

### 2b. `SampleTubeBoxView.slot_id` (addendum, 2026-07-05)

`SampleTubeBoxView` (`app/data/schemas/preparation.py:243`) carries no slot location id, so the FE
cannot address `PUT /preparations/slots/{slot_id}` for an empty shelf slot (`present=False`,
`box_id=None`). Add an additive field `slot_id: str | None` — the `locations` row id (e.g.
`tlc_rack_box_2ml_l2_slot_4`) — populated by BOTH sources (bench and storage). Additive and
optional: existing FE consumers are unaffected.

### 3. Dispatch stays bench-only (pin, not change)

`_validate_tlc_objects` is untouched. Add a regression test: a task create referencing a shelf
`box_id` still 400s.

### 4. Seed

No seed change required (verified above). **Drake's rule (2026-07-05): any lab-service seed data
change requires Drake's explicit decision — never change seed autonomously.** If implementation
finds drift vs the 配置表, leave seed untouched and surface the drift for Drake to decide.

## Rejected alternatives

- **Auto-create box on first cell fill / auto-remove on last clear**: cannot represent a real
  physical state (empty box on shelf), and silently mints/destroys box identity as a side effect
  of tube edits. The explicit slot-tap-adds-box flow also matches the Consumable Maintenance
  interaction precedent (点击槽位图标 = 在该槽位添加对应物品) and the approved popup mockup.
- **New box-level endpoint**: `update_slot` already expresses fill/clear-at-a-location for raw
  `locations` slots; a new route would duplicate that contract (DRY).

## Contract impact (Rule 10)

- FE ↔ lab-service: the cell endpoint's accepted `box_id` domain widens; `update_slot` gains a
  slot type. Route docstrings updated in the same change; portal-facing behavior lands in the
  portal child; PRD-level wording lands in the PRD child.
