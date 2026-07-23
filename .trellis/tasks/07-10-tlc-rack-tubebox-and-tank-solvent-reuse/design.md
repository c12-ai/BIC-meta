# Design — TLC rack tube-box surface + developing-tank solvent reuse

All current-behavior claims below were verified first-hand in this planning session
(file:line cited). Research detail: `research/lab-service.md`, `research/portal.md`,
`research/contract.md`.

## Decisions carried from PRD

- D1 exact match (components AND ratio, order-sensitive, no tolerance)
- D2 tank contents exist in seed data only — no declaration UI
- D3 no robot write-back after 配液
- D4 reuse uses the tank WHERE IT STANDS — zero tank movement ops (Drake, 2026-07-10)
- D5 round-1 shelf carries stay unchanged even when fill is skipped (Drake, 2026-07-10)
- D8 lid read-only in the API, hidden from the maintenance UI (portal #29 ratified,
  Drake 2026-07-11)

## Verified current behavior

Lab-service (`BIC-lab-service`):

- Chemist-facing TLC workspace = `_TLC_WORKSPACE_SHELVES`
  (`app/services/preparation_service.py:138-192`): shelf 1 = tip box (L3) /
  50 ml tube box (L2) / 2 ml tube box (L1); shelf 2 = tank lid (L3,
  `is_maintainable=False`) / developing tank (L2) / silica plate (L1).
- `_TLC_WORKSPACE_AREA_BY_LOCATION_TYPE` (`:196`) feeds the workspace
  maintenance WRITE path (fill/clear by location_id); `_TLC_BENCH_2ML_AREA_SPEC`
  (`:201`) is DERIVED from that map and serves
  `GET /preparations/sample-tube-boxes?source=bench` (`:459-460`).
- Portal never calls `source=bench` (only the type union,
  `BIC-agent-portal/src/lib/lab-service-client.ts:246`); Material Prep uses
  `source=storage` (`MaterialPreparationPanel.tsx:133-135`).
- Planner round shape (`app/tlc/planner.py:376-414`): head resets →
  `_pickup_materials` (`:683`, round 1) / `_dispose_previous` (`:760`, ≥2) →
  `_prepare_solvents` (`:812`) → `_spot_plate` (`:907`) → `_immerse_and_aim`
  (`:1005`) → observe.
- `_prepare_solvents` op seam (`:826-895`): parallel(pipetting AGV →
  `main_station` ‖ [lid off → lid slot, pick tank]) → tank → AGV
  `PLATE_OR_VESSEL` → stage TIP_BOX_1250UL → stage TUBE_BOX_50ML → stage
  WASTE_TIP_BIN → mount single-channel pipette → batch-open 50 ml tubes →
  per-solvent (tip mount → aspirate → tank dispense → eject) → LIFO close.
- `_spot_plate` head teardown (`:933-950`): return single-channel pipette →
  unstage tank → tank home → lid re-fit → tray claims `PLATE_OR_VESSEL` →
  interleaved swaps (stage TIP_BOX_300UL / unstage box50, stage 2 ml box /
  unstage tip1250) → mount 6-channel → spotting. The waste bin STAYS on the
  AGV (END_TLC returns it).
- `_immerse_and_aim` addresses the tank AT ITS OWN table slot
  (`TLC_BEFORE_CC_DEVELOPING_TANK_SLOT[spec.tank_slot]`, `:1005-1046`); observe
  uses `spec.tank_slot` too (`:480`). The tank's AGV ride exists ONLY for
  filling → D4 is safe.
- Binding: `prepare_session_binding` (`app/tlc/service.py:273-313`) allocates
  plate/box50/tank ONCE via `TLCAllocator.allocate_tracked` and PINS
  `tank_slot` (`:304`); rounds reuse it (`:423`, "never drift to round_index").
- Seed tanks: `developing_tank_001` @ `tlc_developing_tank_slot_2`,
  `developing_tank_002` @ slot 3, `properties=None`
  (`app/data/seed.py:433-434`). Lids are NOT seeded (they sit on their tanks).
- `tlc_inventory.properties` is JSONB nullable
  (`app/data/models/tlc_inventory.py:46`); purity precedent writes it at
  insert (`preparation_service.set_sample_tube_cell` → `create(properties=...)`).

Contract (verified in `research/contract.md`):

- `TLCParam` = `solvents: list[Solvent]` + `solvent_ratio: list[PositiveInt]`
  (`bic_shared_types/common/tlc.py:27`); `Solvent` StrEnum = PE / EA / DCM /
  MeOH (`common/enums.py:21-27`). Structured at every hop — no string parsing.
- No shared-types or agent-service change needed: reuse is lab-internal, and no
  step event ever names 配液 (ops are embedded in `StartTLCLabParams.tlc_ops`).

## R1 — trim the chemist-facing workspace surface

The TLC rack (`rack_tlc` in `PREP_AREA_SPECS`, i.e. the supply shelf) is already
the chemist tube-box surface (Production PRD rule 7; Material Prep uses
`source=storage`). The ONLY offending surface is the consumables-page TLC
Workspace section exposing tube boxes / tip box as chemist areas.

Lab-service:

1. `_TLC_WORKSPACE_SHELVES` keeps ONLY the lid/tank/silica shelf (drop shelf 1
   — tip box, 50 ml box, 2 ml box). The GET response then presents exactly the
   three user-controlled areas; the read-only robot block is untouched.
   `TlcWorkspaceResponse.tube_boxes` (`app/data/schemas/preparation.py:326`)
   is populated ONLY from shelf-1 box-grid areas — drop the field and its
   emission loop (`preparation_service.py:775-795`). Rule 10 contract change;
   FE side removed in Phase B.
2. Decouple `_TLC_BENCH_2ML_AREA_SPEC` into a standalone module constant (it
   currently derives from the shelves map and would KeyError). The
   `source=bench` endpoint stays as-is — read-only robot-parking view, no FE
   contract change. (If implementation finds its only consumers are its own
   tests, flag for a follow-up removal; do NOT expand scope here.)
3. Consequence via `_TLC_WORKSPACE_AREA_BY_LOCATION_TYPE`: workspace
   fill/clear writes for tube-box / tip-box slots become rejected — exactly
   the intent (robot territory). Update affected service/route tests.
4. Seed: NO change — bench slots start empty; the robot carries boxes in
   round 1 (PlacementWriter moves rows on success).

Portal (REVISED 2026-07-11 — portal #29 `37dbc69f`, c12-syq, landed first):

5. ALREADY DONE by #29: the `_BOX_GRID_AREA_CODES` / `SampleTubeBoxGrid`
   substitution is deleted; `TlcWorkspaceView` now allowlists
   `tlc_developing_tank` + `tlc_silica_plate` client-side (lid hidden — D8)
   and `sample_tube` areas lost Fill/Clear (read-only). Keep the allowlist as
   harmless defense after the BE trim.
6. Remaining portal work is contract cleanup: remove `tube_boxes` from the
   workspace response type (`src/lib/lab-service-client.ts:164`) and the
   unused `tubeBoxes` prop from `TlcWorkspaceViewProps` + its pass site
   (`ConsumablesPage.tsx:253`) — pairs with the BE field drop (§R1.1).
7. `ConsumablesPage` TLC Rack section: unchanged (already renders rack
   tube boxes read-only via `area_code === 'sample_tube'`). Check FE specs
   asserting workspace areas / `tube_boxes` and update expectations.
8. #29 also added the `workspace-area` Fill/Clear action (slot-by-slot
   `updateWorkspaceAreaSlots` against the virtual workspace areas) — the BE
   trim must keep tank/silica per-slot writes working (Phase A2 covers this).

## R2 — tank contents + planner fill-skip

Properties shape (mirrors `TLCParam`, D1 exact match, order-sensitive):

```json
{"solvents": ["PE", "EA"], "solvent_ratio": [3, 1]}
```

Absent properties / missing keys → unknown tank → never matches (today's
semantics preserved). Seed-only (D2); no write path added.

1. **Seed**: `developing_tank_001` (slot 2) gains contents matching the
   bench-standard recommendation — the med005 stub recommends
   `TLCParam(solvents=[PE, EA], solvent_ratio=[5, 1])`
   (`BIC-agent-service/app/data/med005_fixture.py:77`, verified third-pass
   review); mirror it exactly so the reuse branch is exercisable on the bench.
   The live bench runs REAL ChemEngine, whose recommendation isn't guaranteed
   to match — the E3 bench check pins the confirmed param to PE/EA 5:1 via the
   form (F-E). `developing_tank_002` stays `properties=None`
   (prep branch stays exercisable).
   Mechanism note (python review): the seed tuple schema is
   `(object_id, object_type, location_id, parent_object_id, cell_col,
   cell_row)` — NO properties field (`seed.py:619`); nothing seeds properties
   today. Do NOT widen every tuple with a `None` column: add a small side map
   `_TLC_INVENTORY_PROPERTIES: dict[str, dict]` keyed by `object_id`,
   consulted in the row-build loop. Copy on use (`copy.deepcopy` or a
   per-row literal — the value nests lists) so ORM rows never alias the
   module constant.
2. **Match helper** (lab-service, e.g. `app/tlc/` module-level):
   `tank_matches(properties, param)` → exact list equality on
   `[s.value for s in param.solvents]` and `list(param.solvent_ratio)`;
   None-safe. Order-sensitive by design (D1).
3. **Allocation preference — TIERED (second-pass review, F7)**: once seed
   gives tank_001 contents, the current id-ordered pick would bind a
   physically FULL tank for a non-matching run and dispense into it — a new
   physical bug this task would introduce. Tank allocation therefore ranks:
   - tier 0: tank whose properties exactly match `req.param` (reuse);
   - tier 1: tank with NO recorded contents (presumed empty — prep target);
   - excluded: contents-bearing tank that does not match. If no tier-0/1
     candidate exists, fail loud (same `ValueError` family as the allocator's
     existing no-available error, message naming the reason).
   Order within a tier (D7, Drake 2026-07-10): LEFT TO RIGHT by physical slot
   position — ascending slot index parsed from `location_id` — never by
   object id. Id only as the final stabilizer for impossible same-slot ties.
   Shape: extend `TLCAllocator.allocate_tracked` with an optional
   `rank: Callable[[TlcInventory], int | None] | None = None` — `None` return
   excludes a candidate; pick min `(rank, slot_index, id)`. Single pass,
   deterministic, no exceptions-as-control-flow. (Supersedes the first-pass
   boolean `prefer` shape.)
   Totality rule (third-pass review F-C): the tank rank callable EXCLUDES any
   candidate not bench-placed at a parseable `tlc_developing_tank_slot_N` with
   N within the spec bound — this resolves §F8 in the same place, and every
   admitted candidate then carries a concrete slot index, so the sort key
   never compares `None`. Ranked picks therefore always hit allocate_tracked's
   "already at bench kind" case; the shelf-carry / unplaced cases stay
   rank-less.
   Invariant note (F-D): tier exclusion deliberately breaks
   `available_of_type`'s documented allocator≡readiness shared-predicate claim
   for tanks (readiness may count tanks dispatch will refuse). Amend the
   `available_of_type` / `_first_available` docstrings in the same change and
   record the divergence in the D1 spec update.
   `SessionBinding` gains `tank_id` (so rounds can re-check the bound tank's
   properties); `to_dict`/`from_params` updated with the same direct-indexing
   style as the existing fields (a pre-change in-flight binding raises
   KeyError — acceptable, reset-per-run; no back-compat shim per Drake's
   standing rule).
4. **Per-round decision**: `plan_round_from_binding` loads the bound tank row
   and computes `tank_prefilled = tank_matches(tank.properties, round_param)`
   per round. Retry rounds with a different ratio naturally miss → full prep
   into the bound tank, same as today.
5. **`TLCRoundSpec`** gains `tank_prefilled: bool = False`.
6. **Planner branches** (surgical conditionals; NON-reuse path must stay
   op-identical — the primary regression net already exists:
   `tests/tlc/test_planner_labrun_golden.py::test_strict_full_file_equality`
   locks the FULL round-1 op program by strict file equality against the
   labrun v7 reference (third-pass review F-B; see implement C0)):
   - `_prepare_solvents` with `tank_prefilled`: emit ONLY the pipetting AGV
     move to `main_station` (spotting needs the robot at the bench) and the
     WASTE_TIP_BIN staging (spotting tip ejects need it). Skip: lid off, tank
     pick/place to AGV, tip1250 staging, box50 staging, single-channel mount,
     open/aspirate/dispense/close.
     Shape (python review): an early-return guard block at the TOP of the
     method — emit the two ops, `return` — so the v7 choreography below stays
     textually untouched (zero risk to the op-identical requirement). The AGV
     move is a FLAT `seq.op(...)` in this branch, NOT a single-branch
     `seq.parallel` (no talos branch to pair with).
   - `_spot_plate` head with `tank_prefilled`: skip return-single-channel,
     tank unstage, lid re-fit, box50 unstage, tip1250 unstage (none were
     staged). Still: tray → `PLATE_OR_VESSEL` (free from the start), stage
     TIP_BOX_300UL, stage 2 ml box, mount 6-channel. Tail unchanged.
     Shape: one `if spec.tank_prefilled: ... else: ...` block covering the
     teardown-seam ops only; the spotting body below stays shared.
   - `_pickup_materials` / `_dispose_previous` / `_immerse_and_aim` / observe:
     UNCHANGED (D4, D5). The pre-filled tank sits lid-on at its slot until
     immerse opens it — physically coherent.
   - Reuse rounds still build `spec.solvents` from the binding (unused by the
     emitted ops) — harmless; readiness still requires the solvent group per
     Production PRD rule 10. Keep.
7. **END_TLC**: expected untouched (waste bin return etc.); implementer
   confirms it never references solvent-prep staging.

## Pre-existing edge to verify during C3 (second-pass review, F8)

`tlc_developing_tank` has 4 seeded slots (`seed.py:339`) and the workspace
tank area IS chemist-maintainable (`is_maintainable` defaults True,
`preparation_service.py:123`), so a maintenance-placed tank at slot 4 is
reachable by the allocator — but `TLCRoundSpec.developing_tank_slot` is
`Field(ge=1, le=3)` (`planner.py:178,217`), so binding it would crash at spec
build. Pre-existing (not introduced here), but C3 touches this code: either
confirm why the bound is 3 and exclude out-of-range candidates in the rank
callable, or align the bound — decide from the robot-protocol constraint, do
not widen blindly. Default resolution: exclusion via the rank totality rule
(§R2.3, F-C); widening the bound still needs the robot-protocol confirmation.

## Risk flag — new robot choreography (DOWNGRADED 2026-07-11)

Robot-team agreement (Drake, 2026-07-11): the initial-prep-phase CONCEPT is
agreed — the robot carries all four boxes (confirms D5) and a reusable-tank
check is added; on a match the dispatch sends NO solvent-prep ops. This
branch is the proposal vehicle for golden-standard ops: BIC proposes the op
list, the Robot team verifies feasibility, sequencing, and physical
executability, then approves or rejects.

Still open at the OP level: the exact fill-skipped program (prep↔spot swap
trips lose their return legs; no single-channel pipette phase in the round)
has never been run by the robot. Per the handover practice, the concrete op
list ships in the proposal docs labeled as BIC proposal until the Robot team
confirms it op-by-op (implement D4). The robot mock replays ops generically,
so bench E2E proves sequencing, not physical validity.

## Accepted limitations (by decision)

- Properties describe the SEEDED state. A reused tank still "matches" after
  the run (no write-back, D3); a prep run's tank contents are never recorded.
  Benign under the reset-per-run bench workflow.
- `PE,EA / 3,1` ≠ `EA,PE / 1,3` (order-sensitive exact match) — deliberate D1.
- Round ≥2 may prep into a tank that already holds solvent — identical to
  today's behavior, out of scope.

## Spec / PRD updates (rule 10)

- `.trellis/spec/BIC-lab-service/backend/tlc-placement.md` (+ index if needed):
  workspace chemist-surface scope, tank-properties shape, planner reuse seam,
  and the tank readiness/allocation divergence (F-D: readiness may count tanks
  the tiered allocator refuses).
- Portal frontend spec only if it documents the workspace view (check index).
- `Production-PRD.md` via the `prd` skill: workbench chemist surface =
  tank/lid/silica only; tank-contents rule (seed-only, no write-back, exact
  match) + reuse behavior; acceptance criteria + change log.
- Shared-types / agent-service: NO changes (verified above).

## Rollout / rollback

No schema migration (`properties` column exists), but the tank-contents seed
change ships a PAIRED alembic data migration (third-pass python review F-A,
2026-07-10): repo convention is that every seed change lands with one
(`d5f2a8c41b67_seed_three_sample_tube_boxes`, `9a2f6c8e4d13`, `b2c3d4e5f6a7`…)
— without it a migrated-but-never-reset DB has no tank contents and the reuse
branch silently never fires. Rollback = revert commits +
`POST /admin/reset-to-test-data`. Land order: lab-service → portal (portal
change is contract cleanup after the BE trim — #29 already removed the dead
rendering code).

Base (Drake, 2026-07-11): lab-service work happens in the dedicated worktree
`~/Development/BIC/.worktrees/BIC-lab-service-tlc-following-phase`, branch
`feat/tlc_following_phase` — the TLC_OBSERVATION / TLC_ADDITIONAL_ROUND
dispatch split (`8234bca`) stacked on feat/tlc_adapting (purity, rebased onto
main); neither is merged yet. Portal work stays in the main BIC-agent-portal
checkout.
Branch re-verification (done 2026-07-11 on `feat/tlc_following_phase`):

- Seams intact, lines shifted: `_pickup_materials` :685, `_dispose_previous`
  :762, `_prepare_solvents` :817, `_spot_plate` :913, `_immerse_and_aim`
  :1008. `TLCRoundSpec` :175; `developing_tank_slot` is now
  `int | None = Field(default=None, ge=1, le=3)` with a `tank_slot` property
  falling back to round_index — the F-C rank totality rule (exclude
  unparseable/out-of-bound slots) applies unchanged.
- Round envelopes split: START_TLC (round 1, ends at the camera-aim op; Q7
  observe drop) / TLC_ADDITIONAL_ROUND (retries ≥2, own builder
  `plan_additional_round`, service seam `service.py:468`) / TLC_OBSERVATION
  (agent-interleaved). The `tank_prefilled` decision must feed BOTH round
  builders, not only `plan_round_from_binding`.
- The labrun v7 strict golden (`test_strict_full_file_equality`, ground
  truth `raw_ops.labrun.v7-full.json`) is alive on this branch — C0's
  regression net stands.
