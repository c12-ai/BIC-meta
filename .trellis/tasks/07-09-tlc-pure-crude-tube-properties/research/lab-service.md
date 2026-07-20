# Research: BIC-lab-service — TLC tube properties + CC select-empty-insert

- **Query**: TLC write/read paths, properties column plug-in points, shape rule enforcement, CC sample column model, migration story
- **Scope**: internal
- **Date**: 2026-07-09

---

## Q1 — TLC tube write path: `PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}`

### Router

File: `app/api/routers/preparations.py:79–98`

The handler is `update_sample_tube_cell`. It delegates entirely to `preparation_service.update_sample_tube_cell(box_id, row, col, request)`.

Request schema: `SampleTubeCellMaintenanceRequest` (`app/data/schemas/preparation.py:374–383`).
Currently has only one field: `occupied: bool`. No properties bag today.

### Service

File: `app/services/preparation_service.py:540–616`

`update_sample_tube_cell` does:
1. Loads the `TlcInventory` row for `box_id` and validates it is a `tube_box_2ml` at a known bench or storage shelf slot.
2. If `request.occupied = True` and no tube occupant exists at the cell, it calls `self.tlc_inventory.create(obj_in=TlcInventoryCreate(...))` at line 600–609, passing `parent_object_id=box_id, cell_col, cell_row, state="unused"`. **This is the only insert path for sample tubes.**
3. If `request.occupied = False`, it deletes the matching tube rows.
4. Calls `self.commit()`, then returns the refreshed `SampleTubeBoxesResponse`.

### Repository / persist path

File: `app/tlc/inventory.py`

`TlcInventoryRepository._upsert` (line 182–215): creates or overwrites a `TlcInventory` row. The current signature accepts `object_id, object_type, location_id, parent_object_id, cell_col, cell_row`. **No `properties` field anywhere.**

`persist_box` (line 130–159): called from `write_declared_placements` in `TLCService`. Uses `_upsert` for each tube in the aggregate. Again no `properties`.

### Where `properties` would plug in

| Layer | File | Change |
|---|---|---|
| ORM model | `app/data/models/tlc_inventory.py` | Add `properties: Mapped[dict \| None] = mapped_column(JSONB, nullable=True)` |
| Schema Create | `app/data/schemas/tlc_inventory.py` `TlcInventoryCreate` | Add `properties: dict \| None = None` |
| Schema Read | `app/data/schemas/tlc_inventory.py` `TlcInventoryRead` | Add `properties: dict \| None = None` |
| Maintenance request | `app/data/schemas/preparation.py` `SampleTubeCellMaintenanceRequest` | Add `properties: dict \| None = None` (exp_id, exp_name, purity) |
| Service insert | `app/services/preparation_service.py:600–609` | Pass `properties=request.properties` into `TlcInventoryCreate` |
| Repo `_upsert` | `app/tlc/inventory.py:182–215` | Accept and write `properties` on create (do NOT overwrite on update unless caller passes it) |
| Repo `persist_box` | `app/tlc/inventory.py:130–159` | Preserve existing `properties` column when persisting tube placement (current upsert never touches it, so it is safe by default if `_upsert` does not zero it) |

**Important:** `_upsert` currently does NOT update `object_type` or `state` on an existing row. The same pattern should apply to `properties` — never clear it on a placement-only update.

---

## Q2 — TLC read path: which endpoints return sample-tube box grids

### `GET /preparations/sample-tube-boxes` (`source=storage` or `source=bench`)

File: `app/api/routers/preparations.py:54–77`, service: `preparation_service.get_sample_tube_boxes` (line 439–538).

Response schema: `SampleTubeBoxesResponse` → list of `SampleTubeBoxView` (line 243–268) → list of `SampleTubeCellView` (line 229–241).

**`SampleTubeCellView` current fields**: `row: str, col: int, tube_id: str | None, state: str | None, filled: bool`.

**To surface purity/properties**: add `properties: dict | None = None` to `SampleTubeCellView`. The service builds cells at line 507–521; it reads `tube.id` and `tube.state` from the `TlcInventory` row. Add `tube.properties` there.

### `GET /preparations/tlc-workspace`

File: service `get_tlc_workspace` (line 631–658). Returns `TlcWorkspaceResponse` (line 302–316) which embeds the same `SampleTubeBoxView` list in `tube_boxes`. Same change as above propagates here automatically.

### Lab Logistic panel (agent-service side)

The portal Lab Logistic panel fetches from the agent service, which in turn reads lab-service via MCP or REST. The agent-service ELN-report path needs to reach `properties`. The lab-service read API carrying `properties` in the cell view is the single source of truth.

---

## Q3 — TLC selection/allocation: shape rule enforcement location

### How the dispatched TLC task learns which tubes were selected

The chemist's declared tubes come in via `CreateTLCTaskRequest.objects: list[ObjectLocation]` (from `bic_shared_types`). Each `ObjectLocation` carries `box_id`, `tube_id`, and `cell` (row letter + col number).

`TLCService.write_declared_placements` (`app/tlc/service.py:247–271`) writes these into `tlc_inventory` (the `TubeBox` aggregate). Then `plan_round_from_binding` builds `sample_tube_ids = [o.tube_id for o in sorted(req.objects, key=lambda o: o.cell.col)]` (line 331) and passes them into `SpottingSpec`.

### Shape rule enforcement

**Server-side (BE)**: `CommandValidator._validate_tlc_objects` (`app/services/command_validator.py:638–710`).

Enforces:
1. Count 2–4 tubes (line 650–655).
2. All tubes in ONE box (`box_id` must be unique, line 657–664).
3. ONE contiguous row starting at column 1: same `cell.row` letter, columns form `[1, 2, ..., n]` (lines 670–680).
4. Box must resolve to a real `tube_box_2ml` on a SUPPLY-SHELF slot (not bench).

This runs as domain check `_check_tlc_objects` registered in `_TASK_DOMAIN_CHECKS` (line 207–219) and is called from both the task-create path and the dry-run `POST /preparations/validate`.

**The new PRD requirement (purity ordering: pure block left, crude block right) is NOT currently enforced server-side.** This is FE-only today (the shape rule is server-enforced; purity ordering within that is new).

The purity ordering enforcement (pure cols before crude cols) would be a new server-side validation — or FE-only if Drake decides it. This is a design decision for `design.md`.

---

## Q4 — CC sample column today: tables, endpoints, and what "select empty cell = insert + assign" means

### Tables / models

The CC sample column is tracked in the `consume` table (model: `app/data/models/consumable.py`), NOT in `tlc_inventory`.

Seed: `consume` row `sample_40g_001` with `type=sample_cartridge`, `spec=sample_40g`, `state=unused`, `location_id=bic_09B_l4_001` (the first sample-cartridge slot location). Seed file line ~579.

The `rack_areas` row for CC sample cartridge: `("rack_1", "L4", "sample_cartridge", "Sample Cartridge", "sample_cartridge", "consume", False, 6, 7)` — `is_maintainable=False` (line 110 of `seed.py`). Six `rack_slots` link to the six `sample_cartridge_slot` locations.

### Current assign/maintenance endpoints

The `PUT /preparations/slots/{slot_id}` write endpoint has a branch for `sample_cartridge` areas even though `is_maintainable=False` (it is the "special-item exception path" described in `_require_slot_editable_area`, line 1062–1075 of prep service). Fill creates a new `consume` row; clear deletes it. There is no grid/cell concept for CC — each slot is a single-unit occupant (one `consume` row per slot location).

The GET side: `_location_linked_consume_slot_views` (prep service line 374–388) — reads `consumable.location_id` to match slots.

### What "select empty cell = insert + assign" means for CC

For CC the model is simpler than TLC tubes: a "cell" is a `rack_slot` → `locations` row (one physical slot = one cartridge). "Select empty = insert" would mean: clicking an empty `sample_cartridge_slot` creates a new `consume` row at that `location_id` AND marks it as the experiment-selected cartridge.

However, the CC model has NO per-experiment identity tracking today — there is no `exp_id` / `exp_name` on `consume`. The PRD says CC gets no purity labels; semantics switch only. So for CC the change is purely interaction: clicking empty slot creates the inventory row (which the current `update_slot` already does via the special-item path). The FE interaction changes; the backend payload does not.

**Caveat:** If the design means the new CC assignment also needs an explicit "which experiment selected this" binding (like TLC `properties`), that would require a new column on `consume` or a new table. The current PRD says "semantics switch only; CC gets NO purity labels" — so no new BE column for CC is needed. Verify with Drake at design review.

---

## Q5 — Migration story

### Current migration list (alembic/versions/)

1. `0001_init_schema.py` — initial 11-table schema
2. `0002_seed_test_data.py` — canonical seed
3. `9d25dd2c3177_add_outbox_table.py`
4. `d7b3d83f9f77_add_agent_side_task_id_to_tasks.py`
5. `b1813a458d3f_add_tlc_inventory_table_and_tlc_...py`
6. `c3d4e5f6a7b8_enforce_tlc_inventory_placement_invariant.py`
7. `b2c3d4e5f6a7_remove_tlc_placeholder_rows_and_place_waste_bin.py`
8. `2d60ab0cf374_add_rack_and_inventory_tables.py`
9. `0b3e29d761ed_seed_tlc_slots_and_inventory.py`
10. `d1e2f3a4b5c6_add_tlc_supply_shelf_floor_slots.py`
11. `f4a1c8e6b2d9_tlc_supply_shelf_3d_slots.py`
12. `a7f3b2e1c9d5_tlc_shelf_select_from_shelf.py`
13. `9a2f6c8e4d13_empty_tlc_tube_2ml_dispatch_box.py`
14. `d5f2a8c41b67_seed_three_sample_tube_boxes.py`
15. `e7a3c9f1d28b_tlc_rack_box_slots_per_floor.py`
16. `a1b2c3d4e5f6_seed_tlc_tip_boxes_at_supply_shelf.py`
17. `4c88a9a67075_repoint_fraction_collection_waste_drum_.py`
18. `9f83d1f8d2b7_make_silica_areas_maintainable.py`
19. `c4e1a7f2b9d3_sample_tube_area_capacity_5.py`
20. `f0f4db606be0_drop_task_material_rules.py`

### Adding the nullable JSONB column

A new alembic revision does:

```python
from sqlalchemy.dialects.postgresql import JSONB

op.add_column("tlc_inventory", sa.Column("properties", JSONB, nullable=True))
```

No default value needed (nullable). No seed change needed: `seed.py` inserts seed rows with the raw SQL INSERT at line 621–628, which lists columns explicitly — adding the new column with `nullable=True` and no default means existing inserts stay valid without touching the INSERT statement. **However**, the `seed.py` INSERT statement lists columns explicitly (`id, object_type, location_id, parent_object_id, cell_col, cell_row, state`) so it will not send `properties`, which is correct for seed rows (they carry no properties — per PRD).

The `0002_seed_test_data.py` alembic migration does not touch `tlc_inventory` rows at all (the seed rows come from later migrations). No change needed there.

**Pyright/schema files that must change:**

| File | What changes |
|---|---|
| `app/data/models/tlc_inventory.py` | `Mapped[dict \| None]` column using `JSONB` |
| `app/data/schemas/tlc_inventory.py` | `TlcInventoryCreate`, `TlcInventoryRead` — add `properties: dict \| None = None` |
| `app/data/schemas/preparation.py` | `SampleTubeCellMaintenanceRequest` — add `properties: dict \| None = None`; `SampleTubeCellView` — add `properties: dict \| None = None` |
| `app/tlc/inventory.py` | `_upsert` signature — add `properties: dict \| None = None`; write it on create, preserve it on update |
| `app/services/preparation_service.py` | Pass `properties=request.properties` into `TlcInventoryCreate` at the tube insert (line ~601) |

---

## Q6 — Server-side validation / readiness logic that reads `tlc_inventory` rows

All readiness and validation logic reads rows via:
- `TlcInventoryRepository.available_of_type` — filters by `object_type`, excludes disposal-bin rows. Reads `location_id` only. **No breakage from adding nullable `properties`.**
- `TlcInventoryRepository.contents` — reads all children of a box. Returns full rows. **No breakage.**
- `TlcInventoryRepository.what_at` — reads by `location_id`. **No breakage.**
- `CommandValidator._validate_tlc_objects` — reads `box_id`, `box_row.object_type`, and calls `where_is`. Does not read `properties`. **No breakage.**
- `TlcMaintenanceBridge` — reads `available_of_type` and `contents`. **No breakage.**
- Check constraint `ck_tlc_inventory_placed` — only checks `location_id IS NOT NULL OR parent_object_id IS NOT NULL`. Adding a nullable `properties` column does not change this constraint at all.

**Conclusion: adding a nullable JSONB `properties` column breaks no existing server-side validation or readiness logic.**

---

## Caveats / Not Found

- No existing `properties`, `purity`, `exp_id`, or `exp_name` field anywhere in the TLC inventory code. The column is net-new.
- CC sample column has no grid/cell concept — "select empty" for CC means a single slot → single `consume` row; no changes to `consume` schema are needed if purity labels are excluded (as the PRD states).
- The purity ordering rule (pure block left, crude block right) is not enforced server-side today. Whether to add a BE check or keep it FE-only is a design decision not yet answered in the spec.
- `TlcInventoryUpdate` (`app/data/schemas/tlc_inventory.py:33–41`) also does not have `properties`. Whether to add it depends on whether any update path needs to write `properties` after initial insert. Current design (insert-time only) probably does not need `Update` to carry it — but verify at design stage.
