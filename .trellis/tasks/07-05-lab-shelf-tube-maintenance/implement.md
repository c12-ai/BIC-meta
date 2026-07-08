# Implementation Plan — lab-shelf-tube-maintenance

Repo: `BIC-lab-service` (run everything with `uv run` from the repo root).

## Ordered checklist

1. [x] **Generalize the cell endpoint** (`app/services/preparation_service.py`)
   - Rename `update_bench_sample_tube_cell` → `update_sample_tube_cell`; replace the
     `where_is` gate with the location-type gate (bench `TLC_TUBE_BOX_2ML_SLOT` or storage
     `TLC_RACK_BOX_2ML_SLOT`), per design §1.
   - Return `get_sample_tube_boxes(source=...)` matching the box's home.
   - Generalize `_next_bench_sample_tube_id` → `_next_sample_tube_id`.
   - Update the router call site + route summary/docstring (`app/api/routers/preparations.py:78`).
2. [x] **Storage-slot branch in `update_slot`** (`preparation_service.py:796`), per design §2:
   box create on fill (idempotent), box+contents delete on clear, `material_key` guard.
3. [x] **Tests** (`tests/e2e/`, mirror `test_sample_tube_boxes_bench.py` style):
   - fill + clear a cell in a seeded storage box (rows persist with valid placement; response is
     the storage view);
   - cell write to a box id that is neither bench nor storage 400s;
   - box add on an empty storage slot, then cell fill inside it;
   - box remove deletes the box and its tubes, no constraint violation, no orphan rows;
   - dispatch pin: task create referencing a storage `box_id` 400s;
   - existing bench e2e (`test_sample_tube_boxes_bench.py`) unmodified and green.
4. [x] **Full gate**: `make ci` (ruff check, format check, pyright, full pytest) — re-run the
   whole chain after any fix.

## Validation commands

```bash
uv run pytest tests/e2e/test_sample_tube_boxes_bench.py   # unchanged-behavior pin
make ci                                                    # full 4-step gate
```

## Rollback

Single revertable commit in BIC-lab-service; no migration, no seed change expected (design §4).

## Review gates

- After step 2: confirm no `is_maintainable` semantics changed for consumables-page areas.
- Before commit: route docstrings no longer say "bench-only"; spec/contract wording checked
  (design "Contract impact").
