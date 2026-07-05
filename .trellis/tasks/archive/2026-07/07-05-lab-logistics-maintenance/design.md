# Fix TLC and CC Lab Logistics Maintenance Design

## Scope

Implement portal-owned behavior for TLC and CC Lab Logistics:

- Persist the portal Project PRD.
- Keep CC behavior intact.
- Extend TLC Lab Logistics to show dispatchable bench sample-tube boxes, support maintenance mode, and separate selection from maintenance.

RE and FP are not part of this task.

## Existing Boundaries

- Portal owns UI flow, selection state, readiness gating, and cache invalidation.
- Lab Service owns material state and persistence.
- Existing Lab Service APIs are sufficient:
  - `GET /preparations/sample-tube-boxes?source=bench`
  - `PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}`
  - `PUT /preparations/slots/{slot_id}`
  - `POST /preparations/validate`

No database schema change is required. The sample-tube cell maintenance endpoint is required because storage-rack tube boxes are not robot-dispatchable.

## Data Flow

### CC

1. Dialog opens from Parameter Design.
2. Portal fetches rack layout and task requirements.
3. Selection mode: clicking an allowed sample-cartridge slot writes `lab_logistics.sample_cartridge_location`.
4. Maintenance mode: only sample-cartridge/sample-column slots are editable. It must not expose every maintainable rack area from the global consumables layout.
5. Validation uses `validatePreparation` with the selected location.

### TLC

1. Dialog opens from Parameter Design.
2. Portal fetches dispatchable bench 2 mL sample-tube boxes plus task requirements.
3. Selection mode:
   - Render bench 2 mL tube boxes from `GET /preparations/sample-tube-boxes?source=bench`.
   - Only filled cells in present 2 mL boxes are selectable.
   - Selection writes `lab_logistics.sample_tubes`.
4. Maintenance mode:
   - Render only the TLC sample-tube maintenance surface.
   - Fill/clear bench sample-tube cells through `PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}`.
   - Do not expose TLC silica plate, developing tank, tank lid, tip boxes, or generic consumables as editable in this special-item module.
   - TLC selection mode must have maintained sample tubes available to click; otherwise the module has not fulfilled the sample-tube special-item workflow.
5. Any successful maintenance mutation clears readiness snapshot and invalidates preparation caches.
6. Validation uses existing `validatePreparation`; final task submission remains responsible for full TLC object validation.

## UI Shape

Use existing portal vocabulary:

- Existing utility app shell.
- Tailwind-only styling.
- Existing `RackPlaneView` and `TubeSelectorGrid` patterns.
- No decorative redesign.

TLC should gain the same upper-right module-level maintenance toggle semantics as CC. The body can show:

- Left: readiness requirement list.
- Right: TLC workspace/tube selection surface.
- In selection mode, focus copy and interactivity on sample tube selection.
- In maintenance mode, focus interactivity only on the current experiment's special item slots.

## Shared Component Shape

The special-item maintenance/selection module should be implemented as a reusable component, not as separate CC/TLC page shells. The shared component owns:

- the left readiness requirement list;
- the right-panel header and maintenance toggle;
- maintenance-mode state and disabled/pending button behavior;
- slot maintenance action dispatch and stale-readiness invalidation hooks;
- selection-mode versus maintenance-mode body switching.

Experiment-specific code supplies only the data and render surfaces:

- CC supplies rack setup selection/maintenance rendering.
- TLC supplies sample-tube maintenance rendering and sample-tube selection rendering.
- RE/FP remain out of scope and should not be wired in until their execution params are clarified.

## Key Decisions

- Do not touch RE/FP.
- Do not mint sample-tube ids from empty-cell selection anymore.
- Do not show non-special TLC materials (silica/tank/tips) as maintainable in the special-item module.
- Do not add a frontend-only persistence illusion for sample-tube maintenance.
- Preserve readiness gating and dispatch confirmation path.
- Prefer a single special-item module component over page-specific duplicate maintenance wrappers.

## Risk and Mitigation

- Risk: removing empty-cell declaration may leave fresh reset TLC with no selectable sample tubes if the bench dispatch box is empty.
  - Mitigation: this is correct under the new product rule; the user must first maintain/insert physical items. If backend cell-level tube maintenance is missing, expose that as a remaining backend gap rather than faking it in portal.
- Risk: TLC bench sample-tube cells need persistent maintenance while remaining dispatchable for task execution.
  - Mitigation: use the Lab Service cell-level maintenance endpoint on dispatchable bench boxes and keep storage-rack sample-tube boxes out of TLC execution selection.

## Rollback

Revert portal UI/test/PRD changes. No data migration is introduced.
