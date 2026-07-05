# TLC tubes select from shelf; robot carries boxes with resolved coordinates

Parent: `07-05-lab-logistics-gap-remediation`. Complex — needs `design.md` + `implement.md`
before start. Supersedes part of parent decision D1 (see D4 in the parent PRD).

## Goal

Align the TLC lab-logistics model with the robot protocol's physical story: the chemist prepares
and SELECTS sample tubes in a SHELF box; the robot carries the box (and the other shelf-fetched
materials) from the supply shelf to the bench itself, using coordinates RESOLVED from the actual
inventory placement — never hardcoded defaults.

## Verified ground truth (2026-07-05)

Protocol reference: `mars_doc/projects/tlc_api_flow/protocol/tlc-api-reference.md` (cached at
`~/.cache/tlc-api-reference.md`).

- Stage-1 取料 (first round only): the robot AGV-moves to the supply station (`ws_bic_09_sa_004`)
  and carries FOUR items from the supply shelf to bench slots, two trips of two:
  `tube_box_2ml` (op 4), `tube_box_50ml` (op 5), `tip_box_300ul` (op 10), `tip_box_1250ul`
  (op 11). Silica plate / developing tank / waste bin start on the bench and are NOT fetched
  (doc comment 硅胶板/洗染缸/废料桶一开始就在桌面，不取).
- The doc's shelf coordinates (e.g. 2ml at layer 2/right/col 1) are EXAMPLE values, per Drake
  (2026-07-05): the real contract is user-selects → service resolves coordinates from inventory →
  robot picks that box. Drake confirms arbitrary in-bounds coordinates are executable.
- Current lab-service state (the bug this task fixes): `TLCRoundSpec.supply_*` fields always use
  the fixed `SUPPLY_SHELF_COORDS` defaults (`planner.py:167-179`, no caller overrides), while the
  2ml/50ml boxes are allocated expecting BENCH pre-placement (`_TRACKED_MATERIALS`,
  `allocate_tracked`), and the FE has the chemist select tubes in a bench box. The emulator does
  not verify physical origin, so this passes E2E but breaks on the real bench.

## Requirements

1. **Selection from shelf (portal)**
   - TLC sample-tube SELECTION sources the shelf storage boxes (`source=storage`); the chemist
     selects 2–4 tubes in ONE shelf box, one row, contiguous columns starting at column 1 (the
     shape rule is unchanged — it applies within the carried box).
   - The bench 2ml slots become robot-internal parking: remove the bench group from the popup's
     chemist-facing maintenance (added by `07-05-portal-shelf-bench-maintenance`); bench state may
     remain visible read-only where it already renders (TLC Workspace view).
   - Hint text flips: shelf is where you prepare AND select; the robot fetches the box itself.
2. **Coordinate resolution (lab-service)**
   - `build_round_spec` / round binding derive `supply_2ml_*` from the SELECTED box's actual
     shelf slot, and `supply_50ml_*` / `supply_spot_tip_*` / `supply_pep_tip_*` from the
     ALLOCATED instances' actual shelf slots (slot id → layer/side/column via the shelf geometry
     mapping shared with the seed).
   - Fixed `SUPPLY_SHELF_COORDS` defaults remain only as schema defaults, never as the effective
     source for a dispatched task when inventory placement is known.
3. **Allocation and validation (lab-service)**
   - `_validate_tlc_objects` / task create accepts the sample-tube box at a SHELF slot; the pin
     inverts (a bench-slot box is no longer the required home). Update the dispatch-pin test
     accordingly.
   - `allocate_tracked` for 2ml/50ml boxes accepts shelf pre-placement, with the bench slot as
     DESTINATION (PlacementPolicy next-free-slot), matching the carry ops.
   - 50ml box and tip boxes remain robot auto-pick (allocator-chosen); only the 2ml sample box is
     user-selected.
4. **Seed (delta APPROVED by Drake 2026-07-05, via the codec-unification directive)**
   - The `tlc_rack_box_2ml_*` display-slot family is retired; sample-tube shelf homes become
     `tlc_supply_shelf_l{1,2}_right_c{1..5}` rows (the same `SlotId` codec family the tip boxes
     use). Shelf boxes re-home there; the bench-seeded 2ml box is removed (bench = robot parking,
     starts empty); the 50ml box moves to `tlc_supply_shelf_l1_left_c1`. Exact rows in design §1.
5. **PRD updates**
   - Root Production PRD rule 7 rewords: shelf = chemist maintenance AND selection surface;
     bench = robot parking, not a chemist surface; robot carries shelf→bench with resolved
     coordinates. Rule 9's shape contract is unchanged. Portal project PRD mirrors.
6. **Cross-checks**
   - The prep/carry is first-round-only in the protocol; multi-round tasks must not re-derive or
     re-fetch (rounds ≥2 reuse the bench-parked box — verify existing binding behavior holds).
   - CC flow untouched.

## Constraints

- Builds directly on `07-05-lab-shelf-tube-maintenance` (shelf cell/box maintenance + `slot_id`)
  and `07-05-portal-shelf-bench-maintenance` (shelf groups in the popup) — do not revert them;
  this task re-points selection and removes only the chemist-facing bench maintenance group.
- Shared types: expected to need NO change (`ObjectLocation` carries box_id + cell; coordinates
  are service-resolved). If a shared-types change surfaces, stop and surface it — cross-team.
- Wire contract: `tlc_ops` shapes unchanged; only the VALUES of source coordinates change.

## Acceptance Criteria

- [ ] Portal TLC selection operates on shelf boxes; a dispatched task's `objects[]` reference a
      shelf-located box; bench maintenance group is gone from the chemist popup.
- [ ] Dispatched prep ops pick the 2ml box from the coordinates of the box the chemist selected
      (verified by an e2e asserting the op payload matches the box's seeded slot).
- [ ] 50ml box and tip-box pick coordinates match their allocated instances' inventory slots.
- [ ] A task whose selected box sits at a different shelf slot dispatches with THAT slot's
      coordinates (no fixed-default leakage).
- [ ] Rounds ≥2 do not re-fetch from the shelf.
- [ ] Full `make ci` green; portal gate green; PRDs updated; seed delta (if any) explicitly
      approved by Drake first.
