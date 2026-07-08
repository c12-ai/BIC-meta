# Check Results — tlc-select-from-shelf

## 2026-07-05

Implementation by `shelf-impl` / `portal-impl` subagents (sonnet); reviewed and gate-verified in
the main session. All uncommitted pending Drake's go-ahead.

### Lab-service (steps 1–8)

Delivered per design: `SUPPLY_SHELF_REGIONS` (domain), Drake-approved seed delta (9 shelf rows
added, 10 rack rows retired, 4 boxes re-homed, bench 2ml box removed, 50ml box → `l1_left_c1`),
migration `a7f3b2e1c9d5` (idempotent inserts; re-home before retiring slots; child-before-parent
deletes), storage view/gates on the codec (`_rack_box_slot_meta` deleted,
`tlc_rack_box_2ml_slot` LocationType retired), validation inverted (shelf region required, bench
400), `Allocation.origin` three-case allocation, `SessionBinding.box50_origin`, spec `supply_*`
populated from origins at round 1.

Main-session review caught and had fixed:

- **BUG (fixed)**: `plan_round_from_binding` wrote the box's bench `location_id` at PLAN time.
  `PlacementWriter._handle_place` already authors box moves on skill SUCCESS, so the plan-time
  write was redundant on success and harmful before it — a round-1 re-plan (robot-busy) would
  have omitted the carry ops, and a re-create would 400. Removed; destination slot selection is
  now spec-only. Regression test added (re-plan yields identical supply coords).
- **GAP (fixed)**: implement.md step 7's coordinate assertions were missing entirely.
  `tests/tlc/test_supply_coords.py` added (4 tests): exact layer/side/col equality with seeded
  slots for all four carried items; non-default-slot leakage check; re-plan resilience; round-2
  plan contains no supply-shelf picks.
- **Deviation (accepted, was unreported)**: `tests/e2e/test_sample_tube_boxes_bench.py` was
  rewritten despite a stay-unmodified instruction — unavoidable, the approved seed delta empties
  the bench; the rewrite pins the new truth (bench starts empty, storage is the default source).

Gate (main-session run): `make ci` — ruff ✓, format ✓, pyright ✓, **pytest 391 passed** (387 → 391
with the four coordinate tests).

### Portal (steps 9–11)

TLC selection sources `source=storage`; bench maintenance group and bench query removed; hint
"Prepare and select sample tubes on the shelf — the robot fetches the box to its bench itself.";
fixtures on the `tlc_supply_shelf_*` slot family; L3 form spec updated.

Gate (main-session run): typecheck clean; focused
`material-preparation-layout.spec.ts` **7/7 passed** including the dispatch-payload assertion
(`objects[].box_id` = shelf box) and bench-group-absent assertion. `pnpm test` 73/73 and lint
(pre-existing warnings only) per portal-impl's run.

### Outstanding

- Live-bench TLC run (parent integration criterion) — pending bench availability.
- Commits pending Drake (lab-service 21 files incl. prior task; portal: this task's files only —
  tree shared with the concurrent 07-02 session).
