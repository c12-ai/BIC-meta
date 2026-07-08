# Implementation plan — TLC Workspace view

> Order: BE read endpoint → BE slot-PUT extension → FE view → FE wiring → verify (CDP + DB) → spec.
> Read `design.md` for the why. Each step has a validation gate before the next.
> Commit only when Drake asks; stage only this task's files.

## Phase A — Backend read endpoint (R1)

- [ ] A1. Add Pydantic models in `app/data/schemas/preparation.py`:
      `TlcRobotBlockView`, `TlcWorkspaceResponse{ robot_block, shelves: list[RackView],
      tube_boxes: list[SampleTubeBoxView] }`. Reuse existing `RackView`/`RackAreaView`/
      `RackSlotView`/`SampleTubeBoxView`.
- [ ] A2. Add `PreparationService.get_tlc_workspace()` (template: `get_sample_tube_boxes`
      `preparation_service.py:289`). Read the 6 Workspace `LocationType`s via
      `locations.get_by_type`, occupancy via `tlc_inventory.what_at(slot.id)`, box cells via
      `contents(box.id)` for 2mL/50mL. Robot block via `what_at("ws_bic_09_wb_001"/"_002")`.
      English `display_name` per area; `is_maintainable=False` for `tlc_developing_tank_lid`.
      **DB-driven counts only** (`len(get_by_type(...))`).
- [ ] A3. Add thin route `GET /preparations/tlc-workspace` in `app/api/routers/preparations.py`
      (`response_model=TlcWorkspaceResponse`, delegate only).

**Validation A:** `uv run ruff check app/` · `uv run pyright app/` ·
`curl -s localhost:8192/preparations/tlc-workspace | jq` → assert: 2 shelves, floors L1–L3 each,
silica area capacity = 4, tube/tip/tank/lid = 3, tank-lid `is_maintainable=false`, occupancy
reflects seeded rows (2mL/50mL/silica/tank slot 1 occupied; tip empty — expected per design §8).

## Phase B — Backend slot-PUT extension (R3, D1)

- [ ] B1. Extend `TlcMaintenanceBridge` (`app/tlc/maintenance.py`) with `fill_at(slot_id)` /
      `clear_at(slot_id)`: write/delete a `tlc_inventory` row by `location_id` (object_type derived
      from the slot's `LocationType`). Mirror `PlacementWriter`'s `location_id` write convention.
- [ ] B2. In `PreparationService.update_slot` (`preparation_service.py:458`): when `slot_id` is not a
      `RackSlot` but matches a Workspace `LocationType`, route to `fill_at`/`clear_at`. Defensively
      **reject** a write to `tlc_developing_tank_lid_slot` (fail loud, Rule 9). Return
      `AreaMaintenanceResponse{area}` for the affected area (keep FE mutation path identical).
      Existing RackSlot path untouched.

**Validation B:** `uv run pyright app/` · `uv run pytest` ·
manual: capture `tlc_inventory` row count for a Workspace slot →
`curl -X PUT localhost:8192/preparations/slots/tlc_silica_plate_slot_4 -d '{"occupied":true,...}'`
→ confirm row added → clear → confirm row removed (the R4 before/after proof). Confirm a PUT to a
tank-lid slot is rejected.

## Phase C — Frontend view (R2)

- [ ] C1. Add local types in `src/lib/lab-service-client.ts`: `TlcWorkspaceResponse`,
      `TlcRobotBlockView` (cite BE Pydantic in header). Add `fetchTlcWorkspace()` →
      `GET /preparations/tlc-workspace`.
- [ ] C2. Add `tlcWorkspaceQueryOptions()` + `preparationQueryKeys.tlcWorkspace()` in
      `src/lib/lab-service-queries.ts` under the `['lab-preparations']` prefix (so existing
      `invalidatePreparationCaches` covers it).
- [ ] C3. Create `src/components/preparations/TlcWorkspaceView.tsx`: left `RobotWorkspaceBlock`
      (display-only, D4) + right two `RackPlaneView` shelves. `renderAreaBody` keyed on
      `area.area_code` → `SampleTubeBoxGrid` for 2mL/50mL, `null` otherwise (D3). `renderAreaBadge`
      derives `${filled}/${total}` for box areas. No hard-coded counts.

**Validation C:** `pnpm typecheck` (or `tsc --noEmit`) · `pnpm biome check src/` (or repo's biome cmd).

## Phase D — Frontend wiring (R3)

- [ ] D1. In `ConsumablesPage.tsx`: add the workspace query; mount `<TlcWorkspaceView>` in the
      `<main>` `flex flex-col gap-6` block (`:172–228`), passing the page's `maintenanceMode` +
      the existing `MaintenanceAction` mutation (`onSlotSelect`, `renderAreaActions`). Slot fill/clear
      goes through the unchanged `updatePreparationSlot`.

**Validation D:** `pnpm typecheck` · `pnpm biome check src/`.

## Phase E — Verify (R4 + CDP, AC)

> Per `BIC-agent-portal/.claude/rules/rule-1-verify-ui-with-cdp.md`: assert DOM + screenshot,
> then DELETE screenshots. Services run in tmux `bic-services` (lab :8192, portal :5173) —
> do not spawn loose servers.

- [ ] E1. CDP: navigate `/consumables`, assert DOM — left Robot Workspace block present; Shelf 1
      floors (2mL ×3 box-grid, 50mL ×3 box-grid, tip ×3 cards); Shelf 2 (silica ×4, tank ×3,
      tank-lid ×3 cards); tank-lid cards non-clickable (disabled). Screenshot, then delete.
- [ ] E2. CDP: enable maintenance mode, fill then clear one manageable Workspace slot; capture the
      `tlc_inventory` before/after (R4 proof). Screenshot the state change, then delete.
- [ ] E3. Confirm no FE hard-coded counts (counts come from API) and silica reads 4 (not 3).

## Phase F — Spec + finish (Rule 10, Phase 3)

- [ ] F1. Update `.trellis/spec/backend/tlc-placement.md` with §6c: Workspace read endpoint +
      extended slot-PUT (`fill_at`/`clear_at` by `location_id`, tank-lid rejected) + reaffirm §6a
      Rack-vs-Workspace distinction. (Same change set as the code — Rule 10.)
- [ ] F2. Final full-scope `trellis-check`; report results (fail loud on any skip).
- [ ] F3. Commit only when Drake asks; stage only this task's files (NOT the TLC-params files).

## Risky files / rollback points

- `app/services/preparation_service.py` `update_slot` — the riskiest edit (shared with RackSlot path).
  Branch only on Workspace-id match; existing path must stay byte-identical in behaviour. Rollback =
  revert the Workspace branch.
- `ConsumablesPage.tsx` — shared page; additive mount only, reuse existing mutation. Rollback = remove
  the `<TlcWorkspaceView>` mount + query.
- Endpoint + component are additive; no DB migration → clean revert.

## Validation command summary

| Layer | Commands |
|---|---|
| BE | `uv run ruff check app/` · `uv run pyright app/` · `uv run pytest` |
| FE | `pnpm typecheck` (`tsc --noEmit`) · `pnpm biome check src/` |
| E2E | CDP DOM+screenshot on `/consumables` (delete screenshots); `tlc_inventory` before/after |

> Note: confirm exact FE script names (`pnpm typecheck` / biome) from `BIC-agent-portal/package.json`
> at the start of Phase C — do not assume.
