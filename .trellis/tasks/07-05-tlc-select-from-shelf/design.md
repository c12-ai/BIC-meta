# Design — TLC select-from-shelf with resolved carry coordinates

Repo scope: `BIC-lab-service` (core) + `BIC-agent-portal` (selection surface) + PRDs.
Parent decision D4. Drake's directive (2026-07-05): the 2ml storage boxes must follow the SAME
codec / allocate logic as the other inventories in `tlc_inventory` — no parallel slot family.

## Verified current state (all traced 2026-07-05)

- `SlotId` (`app/tlc/domain.py:123`) IS the location↔protocol codec: ids like
  `tlc_supply_shelf_l3_right_c5` parse to `shelf_layer/shelf_side/shelf_col` — the wire
  `TlcSupplyShelfLoc`. Tip boxes are seeded at such slots (`seed.py:444-445`); the canonical
  supply-shelf location rows are GENERATED from `SUPPLY_SHELF_COORDS` via the codec, plus two D7
  floor-decoupled extras (`l3_left_c3`, `l4_right_c5`).
- The `tlc_rack_box_2ml_l{F}_slot_{N}` rows (10, `seed.py:374-375`) are a SECOND, display-only
  family ("Display/inventory only ... NOT the robot's Workspace dispatch slots") that cannot
  express side and is unparseable by `SlotId` — this family is retired by this task.
- `_pickup_materials` (`planner.py:635`) is ROUND-1-ONLY and carries exactly four items from the
  supply shelf: 2ml box, 50ml box, 300ul tip box, 1250ul tip box. Coordinates come from
  `TLCRoundSpec.supply_*` fields whose defaults (`SUPPLY_SHELF_COORDS`) are NEVER overridden
  today — the fixed-coordinate bug. Plate/tank/waste start on the bench and are not carried.
- `prepare_session_binding` (`service.py:262`) allocates plate/box50/tank expecting BENCH
  pre-placement; `plan_round_from_binding` (`service.py:306`) writes declared placements for the
  chemist's 2ml box, resolves its BENCH slot index, and re-allocates tip boxes per round
  (deterministic; `allocate_tip_box` already splits instance (shelf-located) from destination
  (free bench slot) — but the origin coords are ignored).
- `PlacementWriter` applies op effects on robot completion, so after round 1 the carried boxes'
  DB locations become their bench slots; rounds ≥2 skip pickup via the `round_index` branch.

## Changes

### 1. Seed: one shelf family, bench starts empty (Drake-approved delta)

`app/data/seed.py` + its canonical migration copy, in sync; also update the seed-coverage
drift-guard test's independent slot list.

- ADD supply-shelf location rows for the sample-tube region: `tlc_supply_shelf_l2_right_c2..c5`
  and `tlc_supply_shelf_l1_right_c1..c5` (9 new; `l2_right_c1` already generated from
  `SUPPLY_SHELF_COORDS`).
- REMOVE the 10 `tlc_rack_box_2ml_l*_slot_*` location rows and the `tlc_rack_box_2ml_slot`
  LocationType usage (enum member removed — YAGNI).
- RE-HOME shelf boxes (tubes ride via `parent_object_id`):
  `tube_box_2ml_l2_001..003` → `l2_right_c1..c3`; `tube_box_2ml_l1_001` → `l1_right_c1`.
- REMOVE the bench-seeded `tube_box_2ml_001` and its tubes — bench 2ml slots start EMPTY (robot
  parking).
- MOVE `tube_box_50ml_001` (+ its 2 solvent tubes) from the bench slot to
  `tlc_supply_shelf_l1_left_c1` — bench 50ml slot starts empty.
- Tip boxes unchanged.

### 2. Shelf regions: where each object type may live on the shelf

Small table in `app/tlc/domain.py` next to `SUPPLY_SHELF_COORDS`, sourced from the 配置表:

```py
SUPPLY_SHELF_REGIONS: dict[ObjectType, ShelfRegion] = {
    TUBE_BOX_2ML:  ShelfRegion(layers={1, 2}, side="right"),   # 样品管盒 L1/L2 RIGHT
    TUBE_BOX_50ML: ShelfRegion(layers={1, 2}, side="left"),    # 展开剂组 L1/L2 LEFT
    TIP_BOX_300UL: ShelfRegion(layers={3, 4}, side="right"),
    TIP_BOX_1250UL: ShelfRegion(layers={3, 4}, side="left"),
}
```

(Exact tip regions per 配置表 L3/L4 rows; D7 extras `l3_left_c3`/`l4_right_c5` must stay inside
their type's region — verify and, if the D7 comment contradicts, keep D7 behavior and note it.)
Used by: storage view scoping, maintenance gates, and origin validation at task create.

### 3. Storage views and maintenance follow the codec

`preparation_service.py`:

- `get_sample_tube_boxes(source="storage")`: slots = supply-shelf locations whose parsed SlotId
  falls in `SUPPLY_SHELF_REGIONS[TUBE_BOX_2ML]`; floor label = `f"L{shelf_layer}"`; ordering by
  (layer desc, col). `_rack_box_slot_meta` (regex on the retired family) is deleted — parsing goes
  through `SlotId.parse` like everything else.
- `update_sample_tube_cell` gate: storage side = parsed kind is `TLC_SUPPLY_SHELF` AND in the
  2ml region (bench side unchanged).
- `_is_storage_box_slot` / `_update_storage_box_slot`: same region check; box-id minting keeps the
  `tube_box_2ml_l{F}_{next}` human pattern.
- `SampleTubeBoxView.slot_id` values change family — contract shape unchanged (portal treats it
  opaquely).

### 4. Task create: bind the chemist's box, validate shelf origin

- `_validate_tlc_objects`: the objects' single box must resolve to a 2ml box whose CURRENT
  location parses to the 2ml shelf region (replaces the bench requirement; the dispatch pin test
  inverts). Tubes must exist in that box at the declared cells (existing checks stay).
- `plan_round_from_binding`: `box2_id` = the box from `req.objects` (already the case via
  `write_declared_placements`); its bench DESTINATION slot is allocator-picked
  (`_pick_free_slot(TLC_BEFORE_CC_TUBE_BOX_2ML_SLOT)`) at round 1 instead of `_box_slot_index`
  (which currently expects the box already bench-placed). Rounds ≥2: the box IS bench-placed
  (PlacementWriter applied round 1's ops) — `_box_slot_index` keeps working; branch on
  `round_index` / parsed current location kind.

### 5. Allocation: shelf origin → bench destination

`allocate.py` `allocate_tracked`:

- Pre-placed at the TARGET bench kind → current behavior (plate/tank; carried boxes on rounds ≥2).
- Pre-placed at `TLC_SUPPLY_SHELF` within the object type's region → allocation slot =
  `_pick_free_slot(target bench kind)` (destination), and the allocation carries the parsed
  ORIGIN coords (extend `Allocation` with `origin: SlotId | None`).
- Anything else → the existing loud ValueError.
- `allocate_tip_box`: unchanged selection; additionally expose the instance's parsed origin.

### 6. Planner spec: origins resolved, never defaulted

- `TLCRoundSpec.supply_2ml_* / supply_50ml_* / supply_spot_tip_* / supply_pep_tip_*` are populated
  by the service from the allocations' origins (round 1). `SUPPLY_SHELF_COORDS` remains as the
  canonical seed-home reference and schema default, but a dispatched round-1 task always carries
  instance-derived values.
- `SessionBinding` gains the box50 origin (bound at prep; round 1 replays it). Tip origins are
  re-derived per round from the deterministic instances (only round 1 emits pickup).

### 7. Portal: selection from shelf, bench group out

- Selection grid sources `source=storage`; selection gate unchanged (2–4, one box, one row,
  contiguous, col 1).
- Remove the chemist-facing bench maintenance group (from `07-05-portal-shelf-bench-maintenance`);
  shelf groups remain the primary maintenance surface. Bench state stays visible only in the
  existing read-only TLC Workspace view.
- Hint text: "Prepare and select sample tubes on the shelf — the robot fetches the box to its
  bench itself."
- Fixtures: slot ids move to the `tlc_supply_shelf_*` family; add a dispatch-payload assertion
  that `objects[].box_id` is the shelf box.

### 8. PRDs / specs

- Root Production PRD rule 7 rewords (shelf = maintenance AND selection surface; bench = robot
  parking; robot carries all four box types round-1 with coordinates resolved from inventory).
- Portal project PRD TLC flow + acceptance mirror; both change logs.
- Lab-service spec: record the "one codec, one allocator, origins from placements" rule via
  trellis-update-spec if a TLC/backend spec page exists.

## Rejected alternatives

- **Keep `tlc_rack_box_2ml_*` + add a mapping to coords**: two slot families for one physical
  shelf, a second codec to maintain, and the FE/lab boundary keeps leaking display ids into
  dispatch paths — exactly what Drake's directive rules out.
- **Chemist picks the bench destination slot**: the robot owns bench parking (protocol places to
  a free slot); exposing it invites contradictions with PlacementWriter's post-op state.

## Risks / open points

- The D7 floor-decoupled tip slots must be re-checked against `SUPPLY_SHELF_REGIONS` (design §2).
- Emulator (mars mock) tolerance: it doesn't verify origins, so e2e proves payload VALUES, not
  physical truth — the live-bench run in the parent's integration pass is the real proof.
- Renaming location rows changes ids the robot never sees (locations are service-internal), so no
  wire impact; portal sees new `slot_id` values through the same contract shape.
