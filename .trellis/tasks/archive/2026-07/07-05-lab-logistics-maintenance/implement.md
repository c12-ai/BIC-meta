# Fix TLC and CC Lab Logistics Maintenance Implementation Plan

## Checklist

1. [x] Create `BIC-agent-portal/docs/project-prd.md` with the TLC/CC Lab Logistics Project PRD.
2. [x] Update frontend lab-service query usage to read dispatchable bench sample-tube boxes.
3. [x] Refactor `MaterialPreparationPanel` TLC branch:
   - fetch `sampleTubeBoxesQueryOptions(undefined, 'bench')`
   - render a maintenance toggle
   - support `updateSampleTubeCell` for dispatchable bench sample-tube cells
   - render only sample-tube maintenance in TLC special-item mode
4. [x] Adjust `TubeSelectorGrid` so empty cells are not selectable in selection mode.
5. [x] Preserve CC flow behavior in the implementation path.
6. [x] Add focused TLC Playwright/component coverage:
   - TLC maintenance toggle and sample-tube cell mutation
   - TLC empty tube cells are not selectable
   - TLC readiness payload carries selected existing tubes
7. [x] Run verification:
   - touched-file Biome check
   - TypeScript typecheck
   - focused Vitest
   - focused Playwright
8. [x] Refactor TLC/CC Lab Logistics page shells through a shared special-item module component:
   - shared right-panel header and maintenance toggle
   - shared selection/maintenance body switch
   - shared pending disabled state
   - experiment-specific selection and maintenance bodies supplied as render content
9. [x] Correct special-item maintenance scope:
   - CC maintenance only exposes sample column/sample cartridge slots
   - TLC maintenance only exposes sample-tube maintenance
   - unrelated consumables/TLC workspace materials are not editable in the special-item module
10. [x] Fix TLC sample-tube selection so maintained sample tubes are visible and selectable in the module.

## Validation Commands

From `BIC-agent-portal`:

```bash
pnpm exec playwright test tests/material-preparation-layout.spec.ts
pnpm typecheck
pnpm lint
```

If Biome formatting/imports change, run:

```bash
pnpm check
```

## Risky Files

- `src/components/workspace/material-preparation/MaterialPreparationPanel.tsx`
- `src/components/workspace/forms/TubeSelectorGrid.tsx`
- `tests/material-preparation-layout.spec.ts`

## Review Gates

- Confirm no RE/FP behavior was expanded.
- Confirm TLC selection and maintenance are separate.
- Confirm no fake client-only persistence path was introduced.
- Confirm TLC and CC use the same special-item module component for maintenance UX orchestration.
- Confirm maintenance mode is scoped to special items only.
- Confirm TLC sample tubes can be selected in the focused workflow.

## Implementation Notes

- Portal Project PRD now lives at `BIC-agent-portal/docs/project-prd.md` and explicitly scopes Lab Logistics to TLC and CC, excluding RE/FP.
- TLC Material Preparation reads dispatchable bench sample tubes from `GET /preparations/sample-tube-boxes?source=bench`.
- TLC sample-tube maintenance persists individual bench box cells through `PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}`, then invalidates preparation caches so selection mode can select the newly maintained tubes.
- TLC special-item maintenance renders only dispatchable bench sample-tube box cells and persists through `updateSampleTubeCell`; TLC silica/tank/tip/workspace areas are not editable in this module.
- CC special-item maintenance renders only the sample-cartridge/manual requirement area.
- Backend contract: selected TLC sample-tube box ids must be dispatchable bench box ids; storage-rack sample-tube boxes are not valid for execution selection.
- `TubeSelectorGrid` no longer mints tube IDs from empty cells; selection mode requires a filled cell with a real `tube_id`.
- Added `tlc-material-preparation` fixture mode and a focused Playwright test for selection/maintenance separation.
- `MaterialPreparationPanel` now routes both CC and TLC through a local `SpecialItemPreparationModule` that owns the shared readiness-list layout, right-panel header, maintenance toggle, pending disabled state, and selection/maintenance body switch.
