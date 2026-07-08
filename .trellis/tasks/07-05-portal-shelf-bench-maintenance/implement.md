# Implementation Plan — portal-shelf-bench-maintenance

Repo: `BIC-agent-portal`. Prerequisite: `07-05-lab-shelf-tube-maintenance` merged or available
locally (generalized cell endpoint + `update_slot` storage branch + `SampleTubeBoxView.slot_id`).

## Ordered checklist

1. [ ] **Client/query layer** (`src/lib/lab-service-client.ts`, `src/lib/lab-service-queries.ts`)
   - Add `slot_id?: string | null` to the `SampleTubeBoxView` client type.
   - In `MaterialPreparationPanel`, for `executor === 'tlc'` additionally query
     `sampleTubeBoxesQueryOptions(undefined, 'storage')`.
   - Verify `invalidatePreparationCaches` invalidates BOTH source query keys (bench + storage) so
     a shelf edit refreshes the consumables page view too.
2. [ ] **`TlcPreparationBody`** (`MaterialPreparationPanel.tsx`)
   - Maintenance groups = bench groups labeled "Bench dispatch box — robot picks from here" +
     storage groups grouped by floor, labeled "Shelf stock — TLC Rack L2" / "… L1", all through
     the existing `SpecialItemMaintenanceGrid` (no new grid component).
   - Present shelf box: cell taps call the same `tube-cell` mutation (generalized endpoint takes
     the storage `box_id`).
   - Empty shelf slot (`present=False`): render an "add box" tile that calls
     `updatePreparationSlot(box.slot_id, { occupied: true })`; a present, ALL-EMPTY shelf box gets
     a remove affordance calling `occupied: false`. Omit `material_key` (the lab guard only checks
     it when provided) unless the lab child's tests establish a required key — read
     `tests/e2e/test_sample_tube_boxes_storage.py` in lab-service first.
   - Selection body unchanged (bench boxes only); add the one-line hint under the selection body:
     shelf boxes are stock, the robot picks only from the bench dispatch box.
3. [ ] **Fixtures + focused Playwright**
   - Extend `tests/fixtures/workspace-state-gating.tsx` with a storage-source sample-tube-boxes
     fixture (two floors, one present box with tubes, one empty slot with `slot_id`).
   - `tests/material-preparation-layout.spec.ts` additions: both labeled groups render in TLC
     maintenance mode; shelf cell toggle issues the PUT cell call with the storage box id; empty
     shelf slot add-box issues PUT `/preparations/slots/{slot_id}`; shelf cells are NOT selectable
     in selection mode; hint text visible. Existing TLC/CC assertions unmodified.
4. [ ] **Spec update** (`.trellis/spec/ui/L3/form.md`): extend the 2026-07-05 special-item module
   entry — TLC maintenance body renders two labeled groups (bench + shelf) through the shared
   grid; shelf is maintainable-not-selectable.
5. [ ] **Gate**: `pnpm typecheck && pnpm lint && pnpm test`, then focused
   `./node_modules/.bin/playwright test tests/material-preparation-layout.spec.ts --project=chromium`.
   Re-run the whole chain after any fix.

## Rollback

Single revertable portal commit; no contract change originates here.
