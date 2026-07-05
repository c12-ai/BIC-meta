# TLC Workspace view on the Consumable Maintenance page

## Handover (start here — fresh session)

Build a new **TLC Workspace** view on the Consumable Maintenance page
(`BIC-agent-portal` `/consumables`, portal `:5173`; backend `BIC-lab-service`
`:8192`). The TLC Rack sample-tube box grid is already done + committed
(lab-service `901e849`, portal `92ee9e1`); this is the next surface.

This is a complex cross-layer task: **enter Trellis planning** (this prd → design →
implement) before building. First planning step is the robot-update verification
(R5 below).

> **Planning status (2026-06-27):** R5 verified (see `research/r5-robot-completion-trace.md`),
> contracts mapped (`research/be-box-grid-contract.md`, `research/fe-view-contract.md`),
> four design decisions locked (see "Decisions" below). `design.md` + `implement.md` written.

## Goal & user value

Surface the TLC Workspace (the robot's working bench) on the maintenance page so a
chemist can see and (mostly) manage what is staged there. The Workspace is shared
with the robot — handled procedurally for now (see Conflict handling).

## Required layout (Drake's spec; left→right, lower→upper floors)

- **Left panel:** "Robot Workspace" — one manageable block (backed by
  `ws_bic_09_wb_001` 操作台 + `ws_bic_09_wb_002` 废弃区).
- **Right, Shelf 1:** L1 = 3× 2mL tube box · L2 = 3× 50mL tube box · L3 = 3× tip box.
- **Right, Shelf 2:** L1 = 4× silica plate · L2 = 3× developing tank · L3 = 3× tank lid.
- **Manageability:** everything manageable **except developing-tank-lid** (read-only).

## Confirmed data model (verified against live DB — counts are real)

In `app/data/seed.py`, the Workspace slots are robot `locations` (NOT yet exposed via
any `RackArea` or API):

| Slot type | Count | Robot bound |
|---|---|---|
| `tlc_tube_box_2ml_slot` | 3 | dispatch `le=3` |
| `tlc_tube_box_50ml_slot` | 3 | dispatch |
| `tlc_tip_box_slot` | 3 | dispatch |
| `tlc_silica_plate_slot` | **4** | dispatch `le=4` — KEEP at 4, do NOT change to 3 |
| `tlc_developing_tank_slot` | 3 | dispatch |
| `tlc_developing_tank_lid_slot` | 3 | dispatch |

These are robot dispatch addresses (`SlotId` codec, planner `Field(le=…)`,
`TLCRoundSpec`) — do NOT change their bounds or ids. Occupancy is in `tlc_inventory`
(`location_id` = slot id). Decided: silica plate **stays 4** (Drake's "3" was the
mismatch; the robot was built for 4).

## Requirements

- R1 (BE): new endpoint (e.g. `GET /preparations/tlc-workspace`) reading the 6
  Workspace slot types + `tlc_inventory` occupancy, shaped into: a robot block +
  Shelf 1 (3 floors) + Shelf 2 (3 floors). Typed Pydantic; thin router →
  `PreparationService`. DB-driven counts (no hard-coding).
- R2 (FE): new `TlcWorkspaceView` component — left robot block + right 2 shelves × 3
  floor-rows of slot cards. 2mL/50mL box areas may reuse the box→cell grid pattern
  (`SampleTubeBoxGrid`); tank-lid read-only.
- R3 (FE): maintenance wiring (fill/clear) for all but tank-lid — reuse the existing
  `updatePreparationSlot` / fill / clear PUT flow; gate tank-lid as non-clickable.
- R4 (verify): writes persist to the Lab Service DB (same proof bar as before:
  before/after on a real row).
- R5 (verify, FIRST planning step): confirm the lab service already updates these
  Workspace slots on robot completion — trace `app/services/handlers/log_handler.py`
  (`EntityUpdateService`, the `#.log` writer) + `tlc_inventory` updates. The deep
  pre-dispatch "is something really there" check is DEFERRED.

## Decisions (locked during planning 2026-06-27)

- **D1 — Write path:** Extend the existing `update_slot` / `TlcMaintenanceBridge` flow
  to recognize Workspace slot ids and write `tlc_inventory` directly. FE
  `updatePreparationSlot` client stays unchanged. (Smallest surface; mirrors how
  robot-completion already writes `tlc_inventory`.)
- **D2 — Occupancy model:** Occupied / free only (a `tlc_inventory` row exists at the
  slot, or not). No `used`/`disposed` distinction — the DB does not author `state` on
  Workspace slots (deferred, see R5 nuance).
- **D3 — Slot shape:** 2mL/50mL tube boxes render as box→cell grid (reuse
  `SampleTubeBoxGrid` via `renderAreaBody`). Tip box, silica plate, developing tank,
  tank lid render as plain occupied/empty slot cards (no internal grid — they are
  single-occupancy addresses).
- **D4 — Robot block:** Left "Robot Workspace" block (`ws_bic_09_wb_001` 操作台 +
  `ws_bic_09_wb_002` 废弃区) is **display-only** this task — shows occupancy, no
  fill/clear wiring. R1–R4 acceptance centers on the 6 shelf slot types.

### R5 verification result (DONE)

Robot-completion **already writes** all 6 Workspace slot occupancies. The PRD's R5 hint
(`log_handler.py` / `EntityUpdateService`) is the **wrong** path — that writer is for
CC/RE and never touches `tlc_inventory`. Actual path: the TLC robot does NOT report
placement; LabService self-authors it on `#.result`:
`ResultHandlerService.process_result` (`result_handler.py:172`) →
`_infer_tlc_placement` → `PlacementWriter.infer_and_write` (`placement.py:83`) →
per succeeded `place` op `set_location`/`persist_box` writes
`tlc_inventory.location_id = <workspace slot id>` (`inventory.py:150`/`:119`).
Only `location_id` is authored (occupied/free is real; `state` is not) — this is why D2
is occupied/free only. **Nothing to rebuild; this view is a read layer over existing writes.**

## Conflict handling (decided by Drake — procedural, not technical)

Workspace state is shared with the robot. For this task:
- The chemist stages materials and does NOT touch the Workspace during a run
  (client education / regulation, not code-enforced).
- The lab service updates slots when the robot finishes (verify R5; do not rebuild).
- NO locking / pre-dispatch verification in this task (deferred).

## Acceptance criteria

- [ ] Endpoint returns the robot block + 2 shelves × 3 floors with real DB counts
      (3/3/3 · 4/3/3) and live occupancy.
- [ ] Page renders the layout matching the spec; tank-lid is read-only, all else
      manageable; CDP-verified (DOM + screenshot, screenshots deleted after).
- [ ] A fill/clear on a manageable Workspace slot changes the Lab Service DB
      (before/after captured).
- [ ] R5 documented: where/how the robot-completion update writes these slots.
- [ ] BE: ruff + `uv run pyright app/` + `uv run pytest` green. FE: typecheck + biome.

## Out of scope

- Changing any robot slot bound / id (esp. silica plate stays 4).
- Pre-dispatch "is it really there" verification + any locking (deferred).
- The parallel TLC-params work (`TlcParamsForm.tsx`, `TubeSelectorGrid.tsx`, …) —
  do not touch or commit those.

## Rules / conventions

- **Verify every UI change with Chrome DevTools (CDP)** per
  `BIC-agent-portal/.claude/rules/rule-1-verify-ui-with-cdp.md` — assert DOM +
  screenshot, then DELETE screenshots.
- DB is source of truth; no FE hard-coded counts. Match codebase conventions
  (English `display_name`, `RackPlaneView` styling, the `renderAreaBody` override
  pattern used for the sample-tube grid).
- Commit only when Drake asks; stage only this task's files.
- Reference: `.trellis/spec/backend/tlc-placement.md` §6 (TLC Rack vs Workspace,
  the box-grid endpoint) — the prior task's contract.
