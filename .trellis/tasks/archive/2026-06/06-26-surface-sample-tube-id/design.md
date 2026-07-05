# Design — Sample-tube box→cell grid (dynamic), DB-sourced

## Reframed scope

Drake's mockup = a **nested box → tube-cell grid**, count-agnostic. Supersedes the
original flat-slot tooltip. The synthetic-fallback removal (already done) stays as
independent carried-over work.

Core principle: **DB is the single source of truth; the layout is dynamic.** The FE
renders one box card per box the endpoint returns (flex/grid) — no hard-coded box
count anywhere. Each card is a 4×5 cell grid (dims from the box's real cells).

## Data model (confirmed)

- A box = `tlc_inventory` row, `object_type='tube_box_2ml'`, sitting on
  `tlc_tube_box_2ml_slot_{n}` (slot index = display order).
- A tube = `tlc_inventory` row, `parent_object_id=<box_id>`, `cell_col`=row letter
  (A–D), `cell_row`=col number (1–5), `state` (unused/using/used/disposed).
- Grid dims per box come from the box's cells, NOT a constant (today 4×5=20).

## Backend

### Endpoint (D3)

`GET /preparations/sample-tube-boxes` → typed Pydantic:

```
SampleTubeBoxesResponse:
  boxes: list[SampleTubeBoxView]

SampleTubeBoxView:
  box_id: str
  slot_index: int          # display order (01, 02, …)
  label: str               # e.g. "01"
  rows: list[str]          # distinct cell rows present (A..D), sorted
  cols: list[int]          # distinct cell cols present (1..5), sorted
  filled: int              # count of occupied cells
  total: int               # rows*cols (the box capacity)
  cells: list[SampleTubeCellView]

SampleTubeCellView:
  row: str                 # "A".. (cell_col)
  col: int                 # 1..  (cell_row)
  tube_id: str | None      # real tlc_inventory id when filled, else None
  state: str | None        # tlc_inventory state when filled
  filled: bool
```

- Built in `preparation_service` (reusing `TlcInventoryRepository.contents(box)` +
  the existing box discovery). Boxes discovered dynamically from `tlc_inventory`
  (`object_type='tube_box_2ml'`), ordered by their slot index. Cells emitted for
  the full row×col grid; `filled` from the real tube rows.
- Aggregate page header (filled/total across boxes) = FE sums box.filled / total,
  OR add `total_filled` / `total_cells` to the response. Prefer FE sum (less API
  surface) — boxes already carry per-box filled/total.
- Router: thin controller in `preparations.py`, `display_name` English, follows
  the existing `get_racks` shape.

### Seed (R1, D2)

DB is source of truth → seed real boxes/tubes so the grid is representative:
- Ensure boxes exist for the seeded slots (today only `tube_box_2ml_001`). Add
  `tube_box_2ml_002/003` on slots 2/3 so the dynamic grid shows >1 box.
- Seed a realistic tube spread (Q-fill): e.g. box1 mostly full, box2 partial, box3
  sparse — so filled/total is visibly partial. Keep it real `tube_2ml` rows with
  cell_col/cell_row. (Mirror in `0002`/the TLC seed migration per the sync rule, or
  a new UPDATE/INSERT migration following the `0b3e29d761ed` pattern.)

## Frontend

### Client + query

- `lab-service-client.ts`: `fetchSampleTubeBoxes()` → `SampleTubeBoxesResponse`
  (typed; cite the BE schema path in the header comment).
- `lab-service-queries.ts`: `sampleTubeBoxesQueryOptions()`.

### Component (R3) — dynamic, count-agnostic

`SampleTubeBoxGrid.tsx`:
- Header: title (`Sample Tube` / `样品管盒`) + badge `Σfilled / Σtotal`.
- A flex/grid row of **box cards**, one per `boxes[]` entry (NO fixed count):
  `grid-template-columns: repeat(auto-fit, minmax(...))` or flex-wrap.
- Each card: label (`01`…) + a cell grid `repeat(box.cols.length, …)` × rows, each
  cell green (filled) or dashed (empty). Dims from `box.rows`/`box.cols` (dynamic).
- Filled cell tooltip/aria = real `tube_id` (keeps the "surface the id" intent).
- Pure presentational; data from the query. No hard-coded box/cell counts.

### Wiring (R4)

- Render `SampleTubeBoxGrid` on the consumable / sample-tube view (likely within
  or alongside `ConsumablesPage`, replacing the flat `sample_tube` rendering for
  that area). Keep other racks on the existing `RackPlaneView`.

## Contract / spec impact (Rule 10)

- New endpoint = new FE↔BE contract. Record in
  `.trellis/spec/BIC-lab-service/backend` + the portal lab-service-client header
  citation. No shared-types change (service-local schema).

## Compatibility / rollback

- `/preparations/racks` untouched → consumable page's other racks unaffected.
- New endpoint + component are additive; rollback = remove them + the seed rows.
- Seed change is reset-only (no destructive migration if done as additive INSERT).

## Risks / open

- The `sample_tube` flat RackArea still exists (capacity 20) and currently renders
  in the consumable page via RackPlaneView. Decide: hide that flat area for
  sample_tube and show the new grid instead (avoid double-rendering). — resolve in
  implement.
- Q-fill spread is cosmetic; pick a sensible representative fill.
