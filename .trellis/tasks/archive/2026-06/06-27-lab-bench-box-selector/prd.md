# lab: TLC tube selector surfaces BENCH boxes (dispatchable), not storage

> Child 5 of parent `06-26-06-26-tlc-params-form-ui-dispatch`. Fixes the
> slot-taxonomy bug the live E2E found. Grounded in
> `research/slot-taxonomy-mismatch.md` + `research/robot-pick-physical-model.md`.
> Confirmed with owner: the robot picks from the BENCH box; no storage→bench move
> exists. Fix (a).

## Problem

A chemist selects sample tubes in the FE TubeSelectorGrid (fed by
`GET /preparations/sample-tube-boxes`), but dispatch fails at the lab with
`unrecognized TLC slot id: 'tlc_rack_box_2ml_l1_slot_1'`. Root cause: the selector
endpoint surfaces **STORAGE-rack** boxes (`TLC_RACK_BOX_2ML_SLOT`,
`preparation_service.py:419`), but the TLC planner/dispatch only accepts **BENCH**
boxes (`TLC_TUBE_BOX_2ML_SLOT`, `SlotId.parse` in `domain.py`). The storage rack
has **no protocol address** — the robot can't reach it, and there is **no
storage→bench move op**. So every selectable tube lands on a slot dispatch rejects.
The two halves shipped in the same commit `b36273f` and never shared a taxonomy.

## Goal

The FE TLC tube selector surfaces the **bench** 2mL boxes the robot actually picks
from (`tlc_tube_box_2ml_slot_{1..3}`), so a chemist's selection dispatches
successfully. The consumables/maintenance page keeps its **storage** view unchanged.

## Decisions (locked)

- **Fix (a)** — surface bench boxes to the selector. (Not (c): no storage→bench
  move op exists; not (d)/(b): band-aids that don't fix dispatch.)
- **Do NOT repurpose `get_sample_tube_boxes`** — the consumables/maintenance page
  legitimately needs the STORAGE view (boxes live in storage for refill). The FE
  *selector* needs a separate BENCH data source. Reuse the existing
  `_workspace_box_views` (`preparation_service.py:558-617`) which already reads
  `TLC_TUBE_BOX_2ML_SLOT`.

## Requirements

- **A bench-box data source for the FE selector.** Either a new endpoint
  (e.g. `GET /preparations/sample-tube-boxes?source=bench` or a dedicated
  workspace-boxes selector route) or wire the FE selector to the existing
  Workspace box-grid path. The returned boxes MUST sit on `TLC_TUBE_BOX_2ML_SLOT`
  ids that `SlotId.parse` accepts. Reuse `_workspace_box_views`
  (`preparation_service.py:558-617`) — bench-box grid logic already exists.
- **FE selector consumes the bench source** — `TubeSelectorGrid` / `TlcParamsForm`
  in BIC-agent-portal must fetch the bench boxes, so selected
  `{tube_id, box_id, cell}` carry a bench `box_id` whose `location_id` is a
  parseable bench slot. (This is the FE half of fix (a) — small: point the query
  at the bench source.)
- **Harden the dead clean-400 guard** — `command_validator._validate_tlc_objects`
  (`command_validator.py:509-511`) intends a clean 400 ("not on a known rack-slot")
  but `where_is`/`SlotId.parse` *raises* for an unparseable id, so the guard is
  dead and the raw `ValueError` propagates. Catch the raise → clean 400 (so any
  stray bad box_id returns a typed 400, not a 500). Defensive; the primary fix
  removes storage ids from the selector.
- **Seed sanity** — confirm at least one bench box (`tube_box_2ml_001` on
  `tlc_tube_box_2ml_slot_1`, `seed.py:435`) with seeded tubes is surfaced by the
  bench source so the E2E has selectable, dispatchable tubes. If the demo needs
  multiple bench boxes, decide whether to seed bench boxes on slots 1-3 (NOT
  storage) — but keep the storage demo boxes for the maintenance page. Flag if a
  seed change is needed vs the single existing bench box being enough.
- **Spec (Rule 10)** — update the lab TLC spec: the selector reads bench boxes;
  storage rack is maintenance-only and not dispatchable.

## Constraints

- Lab conventions (`uv run`, services commit, validate at API boundary). This is a
  cross-repo fix (lab endpoint + portal selector query) — both halves in this task.
- Do NOT add a storage→bench move op (that's fix c, net-new, not the chosen path).
- Don't disturb the consumables/maintenance storage view.

## Acceptance Criteria

- [ ] The FE TLC tube selector loads boxes whose `box_id` sits on a bench slot
      (`tlc_tube_box_2ml_slot_*`); selecting tubes from it dispatches without the
      `unrecognized TLC slot id` error.
- [ ] The consumables/maintenance page still shows the STORAGE boxes (unchanged).
- [ ] An unparseable/storage box_id at dispatch returns a clean 400 (guard hardened),
      not a raw 500.
- [ ] Lab gate green (`ruff`, `pyright app/`, `pytest`); portal gate green
      (`pnpm check`, `pnpm typecheck`).
- [ ] Lab TLC spec updated.
- [ ] Re-run live E2E: chemist selects 2–4 bench tubes in the UI → lab task created
      → `tlc_ops` spotting addresses the chosen cells → task completed.

## Out of scope

- Storage→bench move op (fix c).
- The `_pickup_materials` generic-box-from-shelf-L3/C1 issue (it fetches a generic
  box, not the chemist's specific box — noted in research, self-consistent on the
  seed happy path; separate follow-up).
- Other children (1–4, done).
