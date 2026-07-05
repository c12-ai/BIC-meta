# Surface sample tubes (box → tube-cell grid) in the portal

## Goal

Render the **Sample Tube** inventory in the portal as a **nested box → tube grid**
matching Drake's mockup: the `样品管盒` area shows **3 boxes** (slots 01–03), each
box a **4×5 = 20-tube grid**, every individual tube cell filled (green) or empty
(dashed) from **real `tlc_inventory` data**. Header shows filled/total (x/60).

**Source of truth = the database.** If the data is wrong, fix the seed/DB — never
hard-code box/tube layout on the front end.

## Mockup (Drake-provided)

- Title `样品管盒` + aggregate badge `filled/total` (e.g. `18/100` in the mock; real
  total here = 3 boxes × 20 = **60**).
- N box cards labelled `01..0N`; each card = a 4-row × 5-col grid of tube cells.
- Filled tube = solid green; empty = dashed outline. Per-tube granularity.

## Confirmed facts (code inspection)

- **Box grid dims**: `domain.py:86` — `tube_box_2ml` = rows (A,B,C,D) × cols
  (1,2,3,4,5) = **20 cells**.
- **Box slot count**: `tlc_tube_box_2ml` has **3** slots (`seed.py`), matching
  Drake's "3 box slots". (Decision: 3 boxes, not the mockup's illustrative 5.)
- **Seed gap**: only **1 box** is seeded (`tube_box_2ml_001` in slot 1) with **5
  tubes** (row A, cols 1–5). Boxes 002/003 and most cells are absent.
- **Nesting model**: a tube is a `tlc_inventory` row with `parent_object_id` =
  box id, `cell_col` = row letter, `cell_row` = col number, `state`
  (unused/using/used/disposed).
- **Current API gap**: `/preparations/racks` is flat (box-slot occupancy only); it
  does NOT expose per-box tube cells. The `sample_tube` RackArea spreads
  `available_of_type('tube_2ml')` positionally across flat slots — wrong shape for
  the grid.

## Decisions

- D1: **Dynamic box count — never hard-coded.** The component renders exactly as
  many boxes as the DB/endpoint returns (flex/grid auto-layout): 5 rows → 5 cards,
  3 rows → 3 cards. No magic number in BE or FE. (Drake — supersedes "3 boxes".)
- D2: **DB is source of truth** — seed real boxes + tubes; no FE hard-coding. (Drake.)
- D3: **New dedicated endpoint** `GET /preparations/sample-tube-boxes` returns the
  boxes × cells; `/preparations/racks` stays flat/unchanged. (Drake.)

## Requirements

- R1 (seed/DB): seed 3 real `tube_box_2ml` boxes (slots 1–3) with realistic
  per-cell `tube_2ml` tubes so the grid + header reflect real partial fill.
- R2 (BE endpoint): `GET /preparations/sample-tube-boxes` →
  `[{box_id, slot_index, cells:[{row, col, tube_id, state, filled}]}]`, sourced
  from `tlc_inventory` box→children. Typed Pydantic response.
- R3 (FE component): a **dynamic** nested box-grid component (flex/grid) that
  renders one card per box the endpoint returns — count-agnostic — each card a 4×5
  cell grid with filled/empty styling + header filled/total, fed by R2.
- R4: wire it into the consumable / sample-tube view.

## Acceptance Criteria

- [ ] `GET /preparations/sample-tube-boxes` returns 3 boxes × 20 cells from real
      `tlc_inventory` rows; filled cells map to real `tube_2ml` ids.
- [ ] Page renders the box→tube grid matching the mockup (one card per DB box,
      4×5 cells, header filled/total); box count comes from the data, not a
      constant; fill state reflects DB; no hard-coded layout.
- [ ] Changing tube state/fill in the DB changes the page after reset (DB is
      source of truth, verified live).
- [ ] BE: ruff + `uv run pyright app/` + `uv run pytest` green. FE: typecheck +
      biome green.

## Out of scope

- The earlier flat-slot tooltip (superseded by the grid).
- Chemist tube *selection*/assignment interaction (display only for now).
- Changing the box count away from 3.

## Carried-over (already done under this task, still valid)

- `_tube_ids` synthetic-fallback removal + test fixes (solvent path) — independent
  of the grid; keep. See git working tree.

## Open questions

- Q-fill: what realistic fill should the seed encode (e.g. box1 full, box2 partial,
  box3 empty) to make the grid representative? — minor, pick a sensible spread.
