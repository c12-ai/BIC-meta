# lab-service: honor chemist sample tubes + declared-placement write

> Child 2 of parent `06-26-06-26-tlc-params-form-ui-dispatch`.
> **Depends on child 1** (shared-types `ObjectLocation`), rev
> `72f4882dca1e581bfcedc87cc62c0f3dd15388a9` on `feat/tlc-skill-protocol`.
> Re-pin to that rev before coding. See parent `design.md` §1 + §2b and
> `research/objectlocation-shape.md` Q2/Q3/Q5 for seams.

## Goal

When a TLC task arrives with the chemist's `objects: list[ObjectLocation]` (2–4
sample tubes), the lab WRITES the declared tube→box+cell placements into
`tlc_inventory`, then plans + dispatches a `tlc_ops` program that addresses the
chemist's chosen tubes — replacing today's `_first_available` / `_tube_ids`
auto-pick.

## Requirements

- **Re-pin** `pyproject.toml` `bic-shared-types` to rev `72f4882…` (current
  pin is the `feat/tlc-skill-protocol` branch — confirm it resolves the new
  `ObjectLocation` + `CreateTLCTaskRequest.objects`). `uv sync`.
- **Declared-placement write (NEW path — none exists today; only robot-`place`
  drives `placement.py:103-140`)**: before planning, for each `ObjectLocation`,
  write tube→box (`parent_object_id`) + cell (`cell_col`=row letter,
  `cell_row`=col number — note the axis swap, parent design §1) into
  `tlc_inventory`. Reuse `TubeBox.insert` / `persist_box` / `_set_placement`
  (`inventory.py:119-152`). Idempotent (re-declaring updates in place).
  Transactional with planning — validation failure rolls back, no partial persist.
- **Use chemist tubes in planning** (`service.py:159-211 plan_from_request`):
  - `sample_tube_ids = [o.tube_id for o in req.objects]`, ordered by `cell.col`.
  - derive the 2ml sample box from the chosen tubes' shared `box_id` (NOT
    `_first_available(TUBE_BOX_2ML)`).
  - 50ml solvent box, silica plate, tip boxes stay auto-allocated.
  - `_tube_ids` stays for the SOLVENT path only (`count=n_solvents`, line 174).
- **Validation at the API boundary → clean 400** (no persist):
  - count 2–4 (the Field bound gives 422 at parse; also assert in-service for the
    derived-box path).
  - all `objects` share one `box_id` AND form one contiguous row (same `cell.row`,
    consecutive `cell.col`) — the planner assumes one row at cols 1..n.
  - `box_id` resolves to a real tube box on a known rack-slot.
- **Planner unchanged** (`planner.py:636-685`) — row-contiguity is validated
  upstream so the existing "one row, cols 1..n in list order" holds. Align the
  `SpottingSpec.sample_tube_ids` doc/bound note to 2–4 where it's misleading; no
  logic rewrite.
- **Spec update (Rule 10)**: lab TLC backend spec — request `objects`, the
  placement-write, and the validation rules.

## Constraints

- Lab conventions (CLAUDE.local.md): `uv run` only; `from app.core.logging import
  logger`; services commit, repos don't; validate at API boundary not service
  layer; EntityUpdateService is the sole MQ entity-state writer (this write is a
  REQUEST-path placement, distinct from the MQ log path — keep that boundary).
- Keep the old auto-pick path alive until the new path's tests are green, then
  delete the dead sample-tube auto-pick (parent `implement.md` rollback note).

## Acceptance Criteria

- [ ] Re-pinned to `72f4882…`; `uv sync`; `ObjectLocation` importable.
- [ ] A TLC task with 2–4 `objects` writes the declared placements into
      `tlc_inventory` (idempotent, transactional) before planning.
- [ ] Dispatched `tlc_ops` spotting addresses the chemist's chosen tubes' cells,
      ordered by `cell.col`; the sample box is the chosen `box_id`, not
      `_first_available`.
- [ ] Invalid input (count≠2–4, non-contiguous row, mixed/unknown box) → clean
      400, no partial persist (new tests assert each).
- [ ] Gate green: `ruff check`, `uv run pyright app/`, `uv run pytest` (incl. new
      placement + validation + dispatch tests).
- [ ] Lab TLC spec updated.

## Out of scope

- shared-types changes (child 1, done).
- agent-BE forwarding (child 3) / FE form (child 4).
- Planner per-tube cell addressing for scattered tubes (deferred — validation
  enforces one row instead).
