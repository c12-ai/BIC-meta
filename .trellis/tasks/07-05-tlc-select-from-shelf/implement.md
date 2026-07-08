# Implementation Plan — tlc-select-from-shelf

Order matters: lab-service steps 1–6 are sequential; portal step 7 needs step 4's contract only;
PRDs (step 8) can land any time after design sign-off. Seed delta (step 1) is Drake-approved
(2026-07-05, codec-unification directive).

## Lab-service (`BIC-lab-service`, everything via `uv run` / `make ci`)

1. [ ] **Shelf regions** (`app/tlc/domain.py`): add `SUPPLY_SHELF_REGIONS` per design §2 (verify
   tip regions + D7 extras against the 配置表 and the D7 comment; keep D7 behavior on conflict).
2. [ ] **Seed** (`app/data/seed.py` + canonical migration copy + seed-coverage drift-guard test):
   design §1 exactly — 9 new shelf rows, 10 rack rows removed, 4 shelf boxes re-homed, bench 2ml
   box + tubes removed, 50ml box moved to `l1_left_c1`. `POST /admin/reset-to-test-data` must
   round-trip.
3. [ ] **Storage views + maintenance gates** (`preparation_service.py`): design §3 — region-scoped
   storage view via `SlotId.parse`, delete `_rack_box_slot_meta`, update cell/slot maintenance
   gates, remove the `tlc_rack_box_2ml_slot` LocationType member and all references.
4. [ ] **Validation + binding** (`command_validator.py`, `service.py`): design §4 — shelf-region
   origin required for the sample box; destination slot allocator-picked at round 1; rounds ≥2
   path unchanged; INVERT the dispatch pin test (bench-located box now 400s, shelf box passes).
5. [ ] **Allocation origins** (`app/tlc/allocate.py`): design §5 — `Allocation.origin`, shelf→bench
   split in `allocate_tracked`, origin exposure in `allocate_tip_box`.
6. [ ] **Spec population** (`service.py` build/round paths): design §6 — all four `supply_*` sets
   from allocation origins at round 1; `SessionBinding` carries box50 origin.
7. [ ] **Tests** (extend `tests/e2e/test_sample_tube_boxes_storage.py`, TLC create/plan e2e):
   - storage view lists the shelf-region slots with codec `slot_id`s;
   - round-1 plan: op-4/5/10/11 source coords equal the SELECTED box's / allocated instances'
     seeded slots (assert exact layer/side/col, e.g. box at `l1_right_c1` → `layer 1/right/col 1`);
   - a box at a DIFFERENT shelf slot yields THAT slot's coords (no fixed-default leakage);
   - bench-located sample box at task create → 400 (inverted pin);
   - round ≥2 plan emits NO pickup ops;
   - cell + box maintenance still work on the new slot family; bench cell endpoint unchanged.
8. [ ] **Gate**: `make ci` — full chain re-run after any fix.

## Portal (`BIC-agent-portal`)

9. [ ] Selection grid → `source=storage`; remove the bench maintenance group; hint text per
   design §7; labels stay floor-based (`L{layer}`).
10. [ ] Fixtures → `tlc_supply_shelf_*` slot ids; focused Playwright: selection from shelf box,
    dispatch payload carries the shelf `box_id`, bench group absent, shelf maintenance intact.
11. [ ] **Gate**: `pnpm typecheck && pnpm lint && pnpm test` + focused
    `playwright test tests/material-preparation-layout.spec.ts --project=chromium` (+ the
    tube-selector spec if it asserts sources). Whole chain re-run after any fix.

## Docs

12. [ ] Root Production PRD rule 7 reword + change log; portal project PRD TLC flow/acceptance
    mirror + change log; `.trellis/spec/ui/L3/form.md` selection-source update; lab-service spec
    note via trellis-update-spec if a matching page exists.

## Rollback

One commit per repo; seed change reversible by reverting seed.py + migration copy together. No
wire-shape change (coordinate VALUES only), so no cross-team rollback coordination.
