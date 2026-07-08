# Fix TLC round-2 resolver IndexError (multi-round submit)

## Goal

The R7 multi-round-TLC-in-one-task path (feat/hands-off-ready) must survive a round-≥2
submit. Today it has NEVER worked: every append round dies lab-side with an unguarded
`IndexError`, and every multi-round TLC bench flow is blocked.

## Evidence (bench run 4b, 2026-07-02, agent session 40235a4a…)

1. Round 1 healthy: dispatched, mock completed (173 ops, 1 plate image), recognition ran
   (Rf 0.25 OUT of pinned window) → deterministic append: `rounds: [[5,1],[4,2]]`, round-2
   trial created + dispatched.
2. Lab step-1 submit died in 127ms: "Step 1 (start_thin_layer_chromatography) failed to
   submit: list index out of range" (`task_service.py:866`; lab task `127d4507…` → `failed`).
3. Mechanism: round 1's op replay moved the 50ml solvent tubes OUT of the bound box —
   `tlc_inventory` shows `tube_50ml_001/002` parentless at `tlc_cap_station_slot`,
   `tube_box_50ml_001` empty but state `using`. Round-2 resolve calls
   `_tube_ids(binding.box50_id, count=2)` (`app/tlc/service.py:315`, helper `:390` — its own
   docstring admits a short box "returns fewer ids") then indexes `solvent_tube_ids[i]`
   unguarded in `plan_round_from_binding` (`service.py:317-319`). Empty list → IndexError.
4. The exception is swallowed at `task_service.py:781-786` with no traceback — the error
   message is a bare "failed to submit".
5. Round 1 resolved fine (tubes still in box at resolve time); the box emptied when round 1's
   DONE result replayed. So the bug fires deterministically on every round ≥2.

Full chain: task 07-02 run-4b report; logs `/tmp/bic-e2e-form-edit-sync/run4b.log`.

## Requirements

- R1: Round-≥2 resolve must succeed when the bound box's tubes were moved out by a prior
  round — re-address the task's solvent tubes at their CURRENT inventory location (they are
  known tubes, just relocated), or an equivalent minimal correction consistent with the R7
  round-program design.
- R2: A genuinely short/missing tube set must fail LOUD: descriptive error naming the box,
  expected vs found counts — never a bare IndexError; the submit-failure log must carry the
  traceback (today `task_service.py:781-786` swallows it).
- R3: Regression test: a two-round task (round 1 completes and relocates tubes, round 2
  submits) passes resolve; a short-box case produces the descriptive error.

## Acceptance Criteria

- [x] Two-round TLC task submits round 2 successfully in lab-service tests.
- [x] Short-box failure yields a descriptive error + logged traceback.
- [x] Bench validation: round-2 submit 200, both rounds completed (live AC 2026-07-02).

## Verification (2026-07-03, sonnet research-agent pass)

RESOLVED by BIC-lab-service commit `1668d76` on `feat/hands-off-ready` (pushed to origin).
R1: `SessionBinding.solvent_tube_ids` captured at prep (`app/tlc/service.py:125,284,291`),
`plan_round_from_binding` reads the binding (`service.py:337`) — live `_tube_ids()` re-read gone.
R2: short-box raises descriptive `ValueError` (`service.py:338-342`); `task_service.py:789`
uses `logger.exception` (traceback logged). R3: regression tests in `tests/tlc/test_round_loop.py`
(two-round) + `tests/tlc/test_service.py` (short-box). Spec updated in same commit
(`tlc-placement.md` §6b). NOTE: `feat/hands-off-ready` not yet merged to lab main — branch-level
concern (multi-fix branch), not this task's residual.
