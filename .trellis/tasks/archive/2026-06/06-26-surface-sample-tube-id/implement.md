# Implement — Sample-tube box→cell grid (dynamic), DB-sourced

Backend contract first, then seed, then FE. Dynamic box count throughout — no
hard-coded constants.

## Carried-over (already done, keep)

- `_tube_ids` synthetic-fallback removal + `test_service.py` /
  `test_task_dispatch.py` seed fixes + new `_tube_ids` test. Independent of the
  grid; verified green.

## Step 1 — BE schema + service (lab-service)

- [ ] `app/data/schemas/preparation.py`: add `SampleTubeCellView`,
      `SampleTubeBoxView`, `SampleTubeBoxesResponse` (shapes in design.md).
- [ ] `app/services/preparation_service.py`: `get_sample_tube_boxes()` —
      discover `tube_box_2ml` boxes from `tlc_inventory` ordered by slot index;
      for each, read `contents(box_id)`, build the full row×col cell grid, mark
      filled cells with the real `tube_id`/`state`. Dynamic dims from real cells.
- [ ] Reuse `TlcInventoryRepository`; no new magic numbers (grid dims derived).

Validate: `uv run ruff check … && uv run pyright app/`

## Step 2 — BE endpoint (lab-service)

- [ ] `app/api/routers/preparations.py`: `GET /sample-tube-boxes` thin controller
      → `preparation_service.get_sample_tube_boxes()`. English `display_name`.
- [ ] Add a service test: 2 boxes with differing fills → response has 2 boxes,
      correct filled/total, real tube ids on filled cells, None on empty.

Validate: `uv run pytest tests/…  -q`

## Step 3 — Seed representative boxes/tubes (lab-service, DB = source of truth)

- [ ] `app/data/seed.py`: add `tube_box_2ml_002/003` on slots 2/3; seed a real
      partial tube spread across the 3 boxes (Q-fill — e.g. box1 full row A+B,
      box2 a few, box3 empty) so the grid shows partial fill.
- [ ] Keep seed ↔ migration in sync per project rule (additive migration following
      `0b3e29d761ed`, or update the canonical seed migration as the rule dictates).
- [ ] Reset + curl `GET /preparations/sample-tube-boxes` → 3 boxes, real ids,
      partial fill.

Validate: reset API + curl; `uv run pytest` full.

## Step 4 — FE client + query (portal)

- [ ] `src/lib/lab-service-client.ts`: `fetchSampleTubeBoxes()` + typed
      `SampleTubeBoxesResponse` (cite BE schema path).
- [ ] `src/lib/lab-service-queries.ts`: `sampleTubeBoxesQueryOptions()`.

## Step 5 — FE dynamic grid component (portal)

- [ ] `SampleTubeBoxGrid.tsx`: header (title + Σfilled/Σtotal badge) + a
      flex/grid of box cards, **one per box returned** (auto-fit/wrap, no fixed
      count). Each card: label + cell grid sized from `box.rows`/`box.cols`;
      filled=green, empty=dashed; filled cell `title`/aria = real `tube_id`.
- [ ] Match the mockup styling (green fill, dashed empties, rounded cards, header
      badge). Pure presentational; data from the query.

Validate: `pnpm typecheck && pnpm exec biome check <files>`

## Step 6 — Wire into the page (portal)

- [ ] Render `SampleTubeBoxGrid` on the consumable / sample-tube view; ensure the
      flat `sample_tube` RackArea isn't ALSO rendered for the same data (avoid
      double display — hide/replace that area in the consumable rack list).

## Step 7 — Verify live + finish

- [ ] Load the page: dynamic box count matches DB (seed 3 → 3 cards; change seed →
      count changes); cells reflect real fill; filled cell shows real tube id.
- [ ] Spec update (Rule 10): record the new endpoint contract.
- [ ] No commit unless Drake asks.

## Risky files

- `preparation_service.py` (new query), `seed.py` (+ migration sync), the new FE
  component + page wiring.

## Rollback

- Endpoint + component + seed rows are additive — remove to revert. `/racks`
  untouched.

## Phase 2.2 check — PASS (trellis-check, behavior + gates)

- BE gates: ruff ✅ · pyright 0 errors ✅ · 46 prep/tlc tests ✅ (227 broad). The pre-existing
  parity failures are now GREEN — the lab-service commit `b36273f` shipped migration
  `c4e1a7f2b9d3` (sample_tube capacity reconcile) + a demo-fixture fix.
- FE gates: typecheck ✅ · biome ✅ · vitest ✅.
- Behavioral criterion (Drake): every consumable area EXCEPT sample_cartridge / tube_rack /
  sample_tube is `is_maintainable=true` and reaches a working PUT; the 3 exclusions are
  non-clickable on the page (sample_tube replaced by the box grid). VERIFIED.
- DB-change proof: a fill→clear round-trip on `rack_1_l3_fraction_collection_waste_drum_01`
  created then removed an `inventory_items` row in the lab Postgres (before/after captured) —
  maintenance writes persist to the Lab Service DB.
- Flagged (out of scope, pre-existing): the lab single-slot PUT accepts `sample_cartridge`
  (HTTP 200) via the EM-prep carve-out (`_is_sample_cartridge_area`, commit 9b49712); it does
  NOT make sample_cartridge clickable on the consumables page. Separate ticket if undesired.
- Spec updated (Rule 10): `tlc-placement.md` §6a (box-grid endpoint) + §6b (no synthetic fallback).

Git: lab-service committed (`b36273f`, by Drake/parallel process); portal changes remain
uncommitted (per "don't commit unless asked").
