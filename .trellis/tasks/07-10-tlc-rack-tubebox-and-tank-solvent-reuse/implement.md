# Implementation Plan — TLC rack tube-box surface + developing-tank solvent reuse

Land order: lab-service (A, C) → portal (B) → specs/PRD (D) → full gates (E).
A and C are both lab-service but independent; do A first (small, de-risks the
workspace test churn before the planner work).

Read first (per implement.jsonl): research/*.md, design.md,
`.trellis/spec/BIC-lab-service/backend/index.md` + `tlc-placement.md`,
`.trellis/spec/BIC-agent-portal/frontend/index.md`.

## Phase A — lab-service: workspace surface trim (R1)

- [ ] A1 `app/services/preparation_service.py`: drop the tube-box/tip-box shelf
      from `_TLC_WORKSPACE_SHELVES` (keep lid/tank/silica only); make
      `_TLC_BENCH_2ML_AREA_SPEC` a standalone constant (no longer derived from
      the shelves map). `source=bench` endpoint behavior unchanged.
      Also drop `tube_boxes` from `TlcWorkspaceResponse`
      (`app/data/schemas/preparation.py:326`) and its emission loop
      (`preparation_service.py:775-795`) — populated only from shelf-1
      box-grid areas (rule 10 contract change; FE side in B1).
- [ ] A2 Confirm the workspace maintenance write path now rejects tube-box /
      tip-box slot fills (via the shrunken `_TLC_WORKSPACE_AREA_BY_LOCATION_TYPE`)
      and that tank / silica fills still work. Lid stays `is_maintainable=False`.
- [ ] A3 Update lab-service tests that assert the old workspace shelves /
      workspace fills of tube-box slots. If `source=bench` turns out to have
      only self-tests as consumers, note it in the task journal for a follow-up
      — do NOT remove it in this task. Include #100's cases in
      `tests/e2e/test_preparation_api.py` in the sweep (rack-side tip-box
      mapping — should be unaffected, but verify).
- [ ] A4 Gate: `cd BIC-lab-service && make ci` (full chain, re-run whole chain
      after any fix).

Rollback point: Phase A is a self-contained commit candidate.

## Phase B — portal: contract cleanup after #29 (R1)

Portal #29 (`37dbc69f`, 2026-07-11) already landed the workspace hiding
(tube boxes / tip box / lid / robot zones) + sample_tube read-only — B is
contract cleanup only.

- [ ] B1 Remove `tube_boxes` from the workspace response type
      (`src/lib/lab-service-client.ts:164`), and the unused `tubeBoxes` prop
      from `TlcWorkspaceViewProps` + its pass site (`ConsumablesPage.tsx:253`).
      Keep the `VISIBLE_TLC_WORKSPACE_AREA_CODES` allowlist (harmless defense).
- [ ] B2 Sweep FE specs asserting workspace areas / `tube_boxes` (consumables
      specs under `tests/`) and update expectations to the trimmed response.
- [ ] B3 Gate: `cd BIC-agent-portal && pnpm typecheck && pnpm lint && pnpm test`.
- [ ] B4 Against live services (tmux `bic-services`, reset both DBs first):
      verify the Consumables page shows tube boxes ONLY under TLC Rack, and the
      TLC Workspace section shows tank + silica areas (lid hidden per D8).

## Phase C — lab-service: tank contents + fill-skip (R2)

- [ ] C0 Regression net (slimmed, review F-B): the existing labrun golden
      `tests/tlc/test_planner_labrun_golden.py::test_strict_full_file_equality`
      already locks the FULL round-1 op program (strict file equality vs the
      v7 reference) — rely on it; do NOT build a parallel fixture mechanism.
      Inspect the retry-round tests (`test_retry_round_skips_talos_shelf_trips`,
      `test_head_triple_is_uniform`) and add ONE round-2 full-program fixture
      only if they prove shape-only.
- [ ] C1 Seed (`app/data/seed.py`): `developing_tank_001` gets
      `properties={"solvents": ["PE", "EA"], "solvent_ratio": [5, 1]}` —
      mirrors the med005 stub recommendation
      (`BIC-agent-service/app/data/med005_fixture.py:77`, review F-E), the
      value the mock path recommends on the bench. `developing_tank_002` stays
      `properties=None`.
      Mechanism: the seed tuple has NO properties field (`seed.py:619`) — add a
      `_TLC_INVENTORY_PROPERTIES: dict[str, dict]` side map keyed by object_id,
      consulted in the row-build loop; do not widen every tuple. Deep-copy the
      value per row (it nests lists) so ORM rows never alias the constant.
- [ ] C1b Paired alembic data migration (review F-A; repo convention — every
      seed change ships one, e.g. `d5f2a8c41b67_seed_three_sample_tube_boxes`):
      UPDATE `developing_tank_001`'s properties to the same value; downgrade
      sets it back to NULL. Without it a migrated-but-never-reset DB has no
      tank contents and the reuse branch silently never fires.
- [ ] C2 Match helper `tank_matches(properties: dict | None, param: TLCParam)`
      — exact, order-sensitive list equality per design; None-safe and
      wrong-type-safe (a non-list value like `"solvents": "PE"` → no match,
      never a crash); unit-tested (match / ratio-miss / order-miss / None /
      missing-key / wrong-type-value cases).
- [ ] C3 `prepare_session_binding` (`app/tlc/service.py:273`): TIERED tank
      allocation per design §R2.3 — tier 0 exact match (reuse), tier 1 no
      recorded contents (prep MUST target an empty tank), contents-bearing
      non-match EXCLUDED, fail loud when no candidate (existing `ValueError`
      family, clear message). Within a tier: LEFT TO RIGHT by slot index
      parsed from `location_id` (D7), never by object id.
      Shape: `TLCAllocator.allocate_tracked` gains optional
      `rank: Callable[[TlcInventory], int | None] | None = None` (`None` =
      excluded; pick min `(rank, slot_index, id)`).
      Totality (review F-C): the rank callable excludes any tank not
      bench-placed at a parseable `tlc_developing_tank_slot_N` with N within
      the spec bound — admitted candidates always carry a concrete slot index,
      so the sort key never compares `None`. This also resolves design §F8
      (4 seeded slots vs spec `le=3`) — don't widen the bound without the
      robot-protocol confirmation.
      Docstrings (review F-D): `available_of_type` / `_first_available`
      document an allocator≡readiness shared predicate; amend both to note the
      tank-tier divergence (readiness may count tanks dispatch will refuse).
      `SessionBinding` gains `tank_id` (+ `to_dict`/`from_params`, direct
      indexing like existing fields); no back-compat shim.
- [ ] C4 Per-round decision: load the bound tank row and set
      `tank_prefilled = tank_matches(...)` on the spec — in BOTH round
      builders on this branch: the START_TLC path (`plan_round_from_binding`,
      `service.py:319`) and the TLC_ADDITIONAL_ROUND path (`service.py:468`
      → `plan_additional_round`).
- [ ] C5 `TLCRoundSpec` gains `tank_prefilled: bool = False`; planner branches
      per design §R2.6: `_prepare_solvents` via an early-return guard at the
      TOP (flat `seq.op` AGV move + waste-bin staging, then `return` — the v7
      choreography below stays textually untouched); `_spot_plate` head via a
      single if/else over the teardown-seam ops (skip single-channel return /
      tank unstage / lid re-fit / box50+tip1250 unstage). `_pickup_materials`,
      `_dispose_previous`, `_immerse_and_aim`, observe: untouched.
- [ ] C6 Confirm END_TLC planning never references solvent-prep staging (no
      change expected; if it does, STOP and re-plan — design assumption broken).
- [ ] C7 Tests:
      - reuse-branch op-sequence test (matching tank → no lid/tank/pipette/
        aspirate/dispense ops; AGV move + waste bin present; immerse addresses
        the matched slot);
      - regression: non-matching / properties-less tank → op sequence
        unchanged — covered by the existing labrun strict golden (round 1)
        plus the round-2 fixture if C0 added one;
      - `tank_matches` parametrized table: match / ratio-miss / order-miss /
        component-miss / `None` / missing-key / empty-lists / wrong-type-value;
      - allocation tier tests: matching tank wins over everything; no match →
        contents-less tank wins (never the full one); only contents-bearing
        non-matching tanks → loud failure; two empty tanks → the LEFTMOST
        (lowest slot index) is picked even when the other has a smaller id;
      - retry-round test (round 2 different ratio → full prep in same binding);
      - binding round-trip with `tank_id`.
- [ ] C8 Gate: `cd BIC-lab-service && make ci` (re-run full chain after fixes).

Rollback point: Phase C is a self-contained commit candidate; reverting it
leaves A/B intact.

Note: the reuse-branch op program is a NEW robot choreography (never
labrun-validated — see design.md risk flag). Bench E2E via the robot mock
proves sequencing only; raise the Robot-team confirmation externally after
landing (non-blocking).

## Phase D — specs + Production PRD (rule 10)

- [ ] D1 `.trellis/spec/BIC-lab-service/backend/tlc-placement.md`: workspace
      chemist-surface scope, tank-properties shape, planner reuse seam, match
      rule. Check `index.md` linkage.
- [ ] D2 Check `.trellis/spec/BIC-agent-portal/frontend/index.md` for a
      workspace-view doc; update only if one exists.
- [ ] D3 `Production-PRD.md` via the `prd` skill: workbench chemist surface =
      lid/tank/silica only; tank-contents rule (seed-only, no write-back,
      exact match) + planner reuse behavior; acceptance criteria; change log
      entry dated 2026-07-10.
- [ ] D4 Proposal docs (branch vehicle): add the fill-skipped round-1 op list
      to `docs/proposals/tlc-following-phases/` (proposed_ops JSON generated
      from the planner + a HANDOVER.md/.en.md section), labeled as BIC
      proposal pending the Robot team's op-level verification. The 2026-07-11
      agreement covers the concept (four-box carry + reuse check + no
      solvent-prep ops); the concrete ops still go through their
      feasibility/sequencing review.

## Phase E — full verification

- [ ] E1 Lab-service: `make ci` green (final full run).
- [ ] E2 Portal: `pnpm typecheck && pnpm lint && pnpm test && pnpm build`.
- [ ] E3 Live bench sanity (services via tmux `bic-services`, reset both DBs):
      one TLC dispatch whose param matches the seeded tank → confirm the
      START_TLC ops contain no fill sequence; one with a different ratio →
      full prep ops present. (Inspect dispatched ops via lab-service logs or
      the robot mock.) The bench runs REAL ChemEngine, so don't trust the live
      recommendation to equal the seed — EDIT/confirm the TLC param to
      PE/EA 5:1 in the form to force the match deterministically (review F-E).
- [ ] E4 FE E2E: run the TLC-related playwright specs (`--workers=1` for LLM
      specs per project memory); full-suite run only if the TLC specs churned.

## Non-goals (guard rails)

- No declaration UI, no write-back, no staleness model (D2/D3).
- No shared-types or agent-service changes.
- No removal of the `source=bench` endpoint in this task.
- No planner refactor beyond the two conditional seams; non-reuse op output
  must remain identical.
