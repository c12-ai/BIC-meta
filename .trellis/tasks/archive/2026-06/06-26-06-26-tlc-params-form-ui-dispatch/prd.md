# TLC: chemist selects sample tubes → UI-to-lab dispatch (ObjectLocation)

> Parent task. Owns the cross-layer `ObjectLocation` contract and the end-to-end
> acceptance. Implementation happens in four independently-verifiable children
> (shared-types → lab → agent-BE → FE). See `design.md` for the contract and
> `implement.md` for the child map + ordering.

## Problem

A TLC experiment cannot be driven end-to-end from the portal UI. Two gaps:

1. **FE dead-end** — the TLC parameter-design stage renders a static
   `PlaceholderParamForm` with no confirm/dispatch wire
   (`ParameterDesignPanel.tsx:218`, `:516-530`). The BE reaches the
   params-confirm gate (`form_requested(confirm_kind=params)`) but the UI has
   nothing to confirm with, so `lab.submit_task` is never called. Lab tasks
   created from a UI flow today: **0**.

2. **No sample-tube selection** — even when dispatched, the lab auto-picks the
   sample tube via `TLCAllocator._first_available(TUBE_BOX_2ML)` +
   `_tube_ids(box, count=1)` (`BIC-lab-service/app/tlc/service.py:159-246`).
   The chemist's real, physically-placed 2ml sample tubes are never
   communicated. The wire contract has no field for them — `CreateTLCTaskRequest`
   carries only `{solvents, solvent_ratio}`; the `objects: list[ObjectLocation]`
   slot is a commented-out stub (`bic_shared_types/experiment_task/http/tlc.py:19-20`,
   "暂不实现").

## Goal

A chemist drives a TLC experiment from the portal UI: enters params, **selects
the 2–4 sample tubes they physically placed**, confirms, and the task dispatches
through agent-BE → lab → mock robot → completion, with the robot picking the
chemist's chosen tubes.

## Decisions (locked with owner — do not re-litigate)

- **Placement model: B — declare placement.** The chemist's selection *is* a
  placement assertion. The lab writes the tube→box+cell placement into
  `tlc_inventory` before planning. (Model A "select pre-placed" rejected: it only
  works against seeded tubes; a real sample tube has no cell on record.)
- **`ObjectLocation` (per tube): `{ tube_id, box_id, cell: (col, row) }`.** The
  lab derives `rack_slot` from `box_id` (where the box sits). Chemist supplies
  tube_id + box_id + cell.
- **`objects: list[ObjectLocation]`, length 2–4** (`min_length=2, max_length=4`).
- **TLC only.** Do NOT touch the CC/RE `ObjectLocation` stubs — separate tasks.
- **Row-contiguity: chemist guarantees one row; the lab validates** (clean 400 if
  the chosen tubes are not one contiguous row of one box). The planner
  (`planner.py` `_spot_plate`, "all tubes one row, cols 1..n in list order")
  stays unchanged.
- **shared-types: edit directly** on branch `feat/tlc-skill-protocol`, commit
  there; re-pin both services to that rev. (No main rebase — main reverted the
  TLC op protocol this branch depends on; reconciliation is a separate team
  decision.)
- **FE TLC form fields**: `rxn` (rendered from BE pre-fill), `target_window`
  (two number inputs lo/hi in [0,1], `lo<hi` BE-validated), editable
  `recommended.solvents` + `solvent_ratio`, and a **2–4 sample-tube selector**
  (tube_id + box_id + cell). Dispatch via the existing `confirm('params', …)`
  path; CC/RE-only gates extended to include `tlc`.
- **Docstring fix**: `CreateTLCTaskRequest` doc "由 Apex 拆解为 SkillCommand 后下发"
  is misleading — the lab (Nexus) decomposes the task into skill commands, not
  the requester. Correct it to name the actual component.

## Acceptance Criteria (cross-layer; verified by the parent)

- [ ] **AC1 — contract**: `CreateTLCTaskRequest` carries `objects: list[ObjectLocation]`
      (len 2–4); `ObjectLocation = {tube_id, box_id, cell}`; shared-types builds
      and both services import it from the shared package (no local widen left for
      TLC dispatch).
- [ ] **AC2 — lab honors selection**: a TLC task with chemist `objects` dispatches
      a `tlc_ops` program whose spotting ops address the **chosen tubes' cells**,
      not `_first_available`. The lab writes the declared placement into
      `tlc_inventory` before planning.
- [ ] **AC3 — lab validation**: non-contiguous / wrong-count (`<2` or `>4`) /
      unknown-box selections return a clean 400, no partial persist.
- [ ] **AC4 — BE passes through**: the TLC specialist's params-confirm dispatch
      (`_submit_l4` TLC arm) forwards the chemist `objects` into
      `CreateTLCTaskRequest`; the TLC form payload carries the tube selections.
- [ ] **AC5 — FE drives it**: from the portal UI a chemist reaches the TLC params
      form, selects 2–4 tubes, clicks Confirm, and the task dispatches. The TLC
      stage is no longer a placeholder.
- [ ] **AC6 — E2E**: a UI-driven TLC run creates a lab task that reaches
      `completed` via the mock robot, with the dispatched skill's `tlc_ops`
      referencing the chemist-selected tubes. (The exact assertion the prior E2E
      run could not make.)

## Out of scope

- CC/RE `ObjectLocation` adoption.
- The objective-form zod required-gate friction (`ExperimentObjectiveStep.tsx`,
  agent emits `name:""`/null) — separate task; only noted because it can block
  *reaching* the TLC stage from the UI.
- ChemEngine recognition reachability (remote MCP_HOST vs local MinIO) — a
  separate, pre-existing env blocker on a different TLC sub-leg.
- main-branch reconciliation / the #52 TLC-op-protocol revert.

## Source research

- `research/cc-params-dispatch-pattern.md` — the CC params-confirm→dispatch path TLC mirrors.
- `research/tlc-params-gap.md` — BE TLC params payload + CC↔TLC field diff.
- `research/objectlocation-shape.md` — derivation of the `ObjectLocation` field set + downstream seams.
- `research/tlc-sample-tube-location.md` — proof the lab has no tube-location field today (Verdict B chosen).
- `research/contract-spec-and-objective-bug.md` — Rule-10 contract spec map + objective-bug characterization.
