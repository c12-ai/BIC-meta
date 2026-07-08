# TLC popup maintains shelf stock and bench dispatch box

Parent: `07-05-lab-logistics-gap-remediation` (decisions D1–D3 recorded there). Medium — PRD plus
`implement.md`; design is bounded by the existing shared-module contract in
`.trellis/spec/ui/L3/form.md`.

## Goal

The TLC Material Preparation popup becomes the single maintenance surface for ALL TLC sample-tube
inventory (shelf stock + bench dispatch box), and explains the shelf-vs-bench split so a chemist
understands why selection is bench-only.

## Requirements

1. **Maintenance mode** renders two labeled groups inside the shared
   `SpecialItemMaintenanceGrid`:
   - "Shelf stock — TLC Rack L1/L2" (from `GET /preparations/sample-tube-boxes?source=storage`),
     cells editable via the generalized cell endpoint;
   - "Bench dispatch box — robot picks from here" (`source=bench`), behavior unchanged.
   No new page-specific maintenance component — this stays within the shared-module reuse
   contract (both groups flow through the same grid shape).
2. **Selection mode is unchanged**: bench boxes only, 2–4 tubes, one box, one row, contiguous from
   column 1, filled cells only. Shelf cells must never be selectable.
3. **Honest hint text**: one line in the popup explaining that shelf boxes are stock and the robot
   dispatches only from the bench box (this answers the observed confusion: "two layers on the
   consumables page, one row here").
4. **Consumables page untouched**: shelf tube boxes remain read-only there
   (`SampleTubeBoxGrid` stays display-only).
5. Query invalidation covers both sources after any maintenance mutation (a shelf edit must
   refresh the consumables-page view too).

## Constraints

- Depends on `07-05-lab-shelf-tube-maintenance` (generalized cell endpoint) — do not start
  implementation before that child's endpoint behavior is merged or available on a branch the
  portal can develop against.
- Match the existing `SpecialItemPreparationModule` composition; no module chrome duplication
  (spec: `.trellis/spec/ui/L3/form.md` 2026-07-05 entry).
- CC behavior untouched.

## Acceptance Criteria

- [ ] TLC maintenance mode shows both groups with distinct labels; editing a shelf cell persists
      and re-renders (focused Playwright).
- [ ] Shelf cells are not selectable in selection mode; the 2–4/contiguous/col-1 gate and blocker
      text behave exactly as before (existing focused tests unmodified and green).
- [ ] The shelf-vs-bench hint text is visible in the popup (asserted in the focused test).
- [ ] Consumables page still renders tube boxes read-only; its view refreshes after a popup shelf
      edit.
- [ ] `pnpm typecheck`, `pnpm lint`, `pnpm test` green; focused
      `tests/material-preparation-layout.spec.ts` runs green.
