# Design — FE lab-logistics config table

Portal-only. Implements portal project PRD contract 4b. Execution HELD pending Drake's release;
this document is refined by the standing loop until stable.

## Current state (branch inventory, verified 2026-07-06)

`MaterialPreparationPanel.tsx` holds 18 `executor === / !==` sites (post-shelf-cutover):

| Lines | Concern |
|---|---|
| 120, 126 | query enablement: rack layout (non-tlc) vs storage sample-tube boxes (tlc) |
| 172, 175 | manual-selection value extraction (cc slot location vs tlc tube list) |
| 182, 185 | selection shape problem + satisfaction gate |
| 190, 192, 194 | layout data ready / loading / error composition |
| 231, 235 | manual assigned text + dispatch summary formatting |
| 248, 258 | slot-click behavior (cc maintenance allowance; cc-only selection via rack slots) |
| 339, 344 | requirement-card copy (unassigned hint / assigned formatting) |
| 369 | right-panel body switch (TlcPreparationBody vs CC module composition) |
| 430 | validate-button title / blocker source |
| 519 | `readinessBlockerText` per-experiment message branch |

Single consumer: `ParameterDesignPanel.tsx` (the lab logistic button for every experiment).
Left-list CONTENT already comes from lab-service `GET /preparations/requirements`
(`material_rules.py` authority) — this refactor moves only its per-experiment presentation
wiring into the config.

## Target shape

New module `src/components/workspace/material-preparation/lab-logistics-config.tsx`:

```ts
export interface ExperimentLabLogisticsConfig {
  taskKey: string                                     // requirements/readiness task key
  dataSources: { rackLayout?: true; sampleTubeBoxes?: SampleTubeBoxesSource }
  taskLabel: string                                   // absorbs taskLabelForExecutor
  manualSelection: {
    unassignedHint: string
    /** Extract the manual selection from form values (opaque to the shared body). */
    read(values: FormValues): ManualSelection          // discriminated: slot | tubes
    /** Write a changed selection back into form values (absorbs withSampleTubes /
     *  withSampleCartridgeLocation from material-preparation-adapter.ts). */
    write(values: FormValues, sel: ManualSelection): FormValues
    isSatisfied(sel: ManualSelection): boolean
    problem(sel: ManualSelection): string | null       // shape-rule message or null
    blockerText(ctx: BlockerCtx): string               // feeds button title + status line
    assignedText(sel: ManualSelection): string | null  // requirement card
    dispatchSummary(sel: ManualSelection, layout: LayoutData): string | null
  }
  selection: { title: string; description: string; render(ctx: SelectionBodyCtx): ReactNode }
  maintenance: {
    title: string
    description: string
    groups(data: LayoutData, ctx: MaintenanceCtx): SpecialItemMaintenanceGroup[]
    /** cc: rack-slot editability allowance; tlc: none (grid cells carry their own actions) */
    slotClickAction?(slot: RackSlotView, area: RackAreaView): MaintenanceAction | null
  }
  hint?: { testId: string; text: string }
  buildTaskParams(taskId: string, values: FormValues): LabTaskParams
}

export const LAB_LOGISTICS_CONFIG: Record<'tlc' | 'cc', ExperimentLabLogisticsConfig>
```

`MaterialPreparationPanel` becomes: one `const config = LAB_LOGISTICS_CONFIG[executor]` lookup,
then generic orchestration (queries with `enabled: !!config.dataSources.x`, readiness snapshot
lifecycle, maintenance-mode state, dialog chrome) reading config fields. `TlcPreparationBody`'s
experiment-specific content moves into the TLC entry; the generic module chrome stays in
`SpecialItemPreparationModule`.

## Key decisions

1. **Hooks via enabled-flags, not per-config hooks.** The shared body declares BOTH queries
   unconditionally and drives them with `enabled: !!config.dataSources.rackLayout` /
   `config.dataSources.sampleTubeBoxes`. No rules-of-hooks hazard, no `key={executor}` remount
   trick, and a future entry needing both sources (RE?) works for free. `LayoutData` is a small
   union the config adapters receive (`{ rackLayout?, sampleTubeBoxes? }`), with
   ready/loading/error composed generically from the ENABLED queries only (kills lines 190–194).
2. **`ManualSelection` as a discriminated union** (`{kind:'slot', locationId} |
   {kind:'tubes', tubes: ObjectLocation[]}`): the shared body never inspects the variant — only
   config functions do. This removes lines 172–185/231–235/339–344/430/519 in one stroke.
3. **Config entries may render JSX** (`selection.render`, `maintenance.groups`) but only by
   composing the existing shared primitives (`TubeSelectorGrid`, `RackAreaView` slots adapter,
   `SpecialItemMaintenanceGrid` group shape). The reuse contract from
   `.trellis/spec/ui/L3/form.md` (2026-07-05) is unchanged — this refactor relocates wiring, not
   grid components. The `SelectionBodyCtx` contract (pinned in loop review #3) is
   `{ layout: LayoutData, manualSelection: ManualSelection,
   onManualSelectionChange(sel: ManualSelection): void }` — experiment-specific toggle semantics
   (e.g. TLC's rolling-FIFO `toggleTubeSelection`) are wired INSIDE the entry's `render`, so the
   shared body's `handleTubeToggle`/cc-selection handlers dissolve into generic
   "selection changed → write → sync → clear snapshot" plumbing.
4. **Mutation mapping stays in the shared body; configs return ACTION DESCRIPTORS**
   (`MaintenanceAction` union already exists: `slot | tube-cell | shelf-slot`). Config code never
   calls mutations directly — keeps cache-invalidation and pending-state handling in one place.
5. **Structural guard is a test, not a lint rule**: a vitest case reads the panel source and
   asserts no `executor === '` occurrences (same rg-check pattern used in prior check.md
   records), so regression is CI-visible without a custom eslint/biome plugin (YAGNI).
6. **Zero behavior change** is the loud invariant: the focused Playwright 7 must pass with NO
   assertion edits. Any needed assertion edit means the refactor changed behavior — stop and
   re-review, don't adapt the test.
7. **The panel's OWN props are also de-branched** (found in loop review #2): today the shared
   component exposes two experiment-specific sync callbacks
   (`onSampleCartridgeLocationChange` / `onSampleTubesChange`, panel lines 73-76), which
   `ParameterDesignPanel` wires per experiment (lines 362-363 → `applySampleCartridgeLocation` /
   `applySampleTubes`). They generalize to ONE
   `onManualSelectionChange(sel: ManualSelection)` prop; the PARENT maps the union to the right
   form-draft apply function. The parent legitimately branches — it owns the per-experiment
   forms; contract 4b governs the shared module's internals. This adds
   `ParameterDesignPanel.tsx` to the touched file set (small, mechanical).
8. **`material-preparation-adapter.ts` is absorbed ONLY where the panel is the sole consumer**
   (corrected in loop review #3): `taskKeyForExecutor`, `taskLabelForExecutor`, and
   `buildLabTaskParams`'s executor switch move into config entries. The value-writers
   `withSampleTubes` / `withSampleCartridgeLocation` STAY in the adapter as shared utilities —
   `ParameterDesignPanel` also uses them (lines 212/224) to apply the `ManualSelection` union to
   the form draft (design §7), and the config entries' `manualSelection.write` references the
   same helpers. One implementation, two referencing sites — no duplication, no breakage.
9. **Config key is a closed subset type** (`LabLogisticsExecutor = 'tlc' | 'cc'`) and the panel
   prop narrows to it — unconfigured executors are a compile error, not a runtime fallback
   (ParameterDesignPanel only opens the dialog for these two today; RE/FP widen the type when
   their entries land).

## Risks / mitigations

- `readinessBlockerText` currently mixes experiment-specific and generic causes (layout/
  requirements loading, missing task). Split: generic causes stay in the shared body; only the
  manual-selection cause delegates to `config.manualSelection.blockerText` (avoids duplicating
  generic strings per entry).
- `handleSlotSelect` (lines 248–258) mixes maintenance allowance and cc-only selection. The
  config's `slotClickAction` covers maintenance; cc selection becomes part of the cc entry's
  `selection.render` wiring (the rack view's onSlotSelect prop comes from the entry).
- The 07-02 session touches sibling test files; this task's file set is disjoint by constraint
  (prd Constraints) — re-verify `git status` overlap at implementation start.

## Rejected alternatives

- **Per-experiment child components with a common interface** (a `TlcBody`/`CcBody` pair): keeps
  the branch, just renames it; left-list presentation and right panel could still diverge —
  fails contract 4b's "one entry defines both sides".
- **Server-driven UI config (lab-service ships the wiring)**: over-engineering; presentation
  wiring is FE-owned by decision (contract 4b authority split), and lab-service already owns the
  data-level config (material_rules).
