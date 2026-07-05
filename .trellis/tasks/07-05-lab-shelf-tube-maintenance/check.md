# Check Results — lab-shelf-tube-maintenance

## 2026-07-05

Implementation by `trellis-implement` subagent (sonnet), reviewed line-by-line and amended in the
main session.

Changes (all in `BIC-lab-service`, uncommitted pending Drake's go-ahead):

- `app/services/preparation_service.py` — `update_bench_sample_tube_cell` →
  `update_sample_tube_cell` with a location-type gate (bench `TLC_TUBE_BOX_2ML_SLOT` or storage
  `TLC_RACK_BOX_2ML_SLOT`), source-scoped response; `_next_sample_tube_id` rename; new
  `_is_storage_box_slot` / `_update_storage_box_slot` branch in `update_slot` (box create on
  fill, idempotent; contents-then-box delete on clear); `_next_storage_box_id` minting.
- `app/data/schemas/preparation.py` — additive `SampleTubeBoxView.slot_id` (design §2b),
  populated by both storage and workspace view builders.
- `app/api/routers/preparations.py` — route summary/docstrings updated; no bench-only wording.
- `tests/e2e/test_sample_tube_boxes_storage.py` — six new e2e tests: storage cell fill persists
  with valid placement; storage cell clear; non-bench/non-storage box 400s; box add on empty slot
  then cell fill; box remove deletes box + tubes with no orphans; TLC task create with a storage
  box_id still 400s (dispatch pin).

Main-session review findings and fixes:

- Accepted the agent's synthetic single-slot `AreaMaintenanceResponse` for storage slot ops (the
  FE refreshes the grid via the boxes GET; reuses the endpoint's existing response model).
- FIXED: `_next_storage_box_id` minted from `available_of_type`, which excludes `disposed` rows
  whose PKs still exist — added a probe-until-free loop (same collision-safe pattern as
  `_next_sample_tube_id`).
- Note (accepted): storage tubes minted via the cell endpoint share the `tlcws_` id prefix with
  bench tubes; unique and harmless, flagged for a future rename if it ever confuses.
- Seed: NOT touched (Drake's standing rule — seed changes are his decision). The implementer
  explicitly checked for drift vs the 配置表 and found none; tests run against the existing seed
  state (L2 slots 1–3 + L1 slot 1 boxed, other slots empty).

Gate (`make ci`, full chain re-run after the mint fix):

```
ruff check    — pass
ruff format   — pass
pyright       — pass
pytest        — 387 passed, 1 warning (pre-existing shared-types deprecation) in 21.75s
```

`tests/e2e/test_sample_tube_boxes_bench.py` is unmodified and green (unchanged-behavior pin).
