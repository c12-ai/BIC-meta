# Generalize sample-tube cell maintenance to shelf storage boxes

Parent: `07-05-lab-logistics-gap-remediation` (decisions D1–D3 recorded there). Complex — add
`design.md` and `implement.md` before `task.py start`.

## Goal

Lab-service lets the Material Preparation popup maintain TLC sample tubes in the shelf storage
boxes (TLC Rack L1/L2), not only in the bench dispatch box, while keeping dispatch bench-only.

## Requirements

1. `PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}` accepts shelf storage boxes in
   addition to bench boxes (today `update_bench_sample_tube_cell` rejects non-bench box ids).
   One endpoint, one response shape (`SampleTubeBoxesResponse`), source-appropriate scoping.
2. **Empty storage slot handling** (key design point for `design.md`): a `TLC_RACK_BOX_2ML_SLOT`
   can be `present=False` (no box object). Decide and implement ONE of:
   - box auto-created on first cell fill (and auto-removed when last cell cleared), or
   - explicit box-level add/remove maintenance operations.
   Either way every created record must satisfy the inventory integrity rule: concrete
   `location_id` or `parent_object_id`, never placeless rows.
3. Seed and 配置表 alignment: seed data provides the TLC Rack storage box slots per the config
   table (L1+L2 RIGHT, 5 slots per floor, 5×4 cells). `app/data/seed.py` and
   `0002_seed_test_data.py` stay in sync.
4. Dispatch validation is UNCHANGED: `_validate_tlc_objects` continues to accept only bench
   `box_id`s (parseable SlotIds); a shelf tube must never become dispatchable directly.
5. Maintenance writes remain honest inventory mutations (create/delete `tlc_inventory` rows) with
   event logging consistent with the bench-cell implementation.

## Constraints

- Services commit, repositories never commit; validate at API boundary (existing rules).
- No new endpoint unless the design review shows the existing route cannot express box-level
  add/remove cleanly.
- Shared types untouched (no robot protocol change).

## Ordering

- Independent of the PRD child; the portal child depends on THIS task's endpoint behavior.

## Acceptance Criteria

- [ ] Filling and clearing a cell in a shelf storage box persists real `tlc_inventory` rows with
      valid physical layout (location or parent), verified by tests.
- [ ] Maintaining a cell in an absent-box slot works per the chosen design (auto-create or explicit
      box add), with no placeless rows at any point.
- [ ] Bench-cell maintenance behavior is byte-identical to before (existing e2e
      `test_sample_tube_boxes_bench.py` still green, unmodified assertions).
- [ ] A dispatch attempt referencing a shelf `box_id` still 400s.
- [ ] `make ci` green (ruff, format, pyright, pytest full suite).
