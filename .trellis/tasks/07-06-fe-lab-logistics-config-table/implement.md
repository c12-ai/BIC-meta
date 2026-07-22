# Implementation Plan — fe-lab-logistics-config-table

Repo: `BIC-agent-portal`. EXECUTION HELD — do not run `task.py start` or edit code until Drake
releases the plan (loop directive 2026-07-06).

## Ordered checklist

1. [ ] **Pre-flight**: `git status` — confirm no overlap with the 07-02 session's in-flight files
   beyond this task's set (`MaterialPreparationPanel.tsx`, new config module,
   `tests/material-preparation-layout.spec.ts`); run the focused Playwright suite once BEFORE any
   change and keep the output as the baseline.
2. [ ] **Types + config skeleton** (`lab-logistics-config.tsx`): `ExperimentLabLogisticsConfig`
   (incl. `taskLabel`, `manualSelection.write` — design §8), `ManualSelection` union,
   `LayoutData`, closed `LabLogisticsExecutor` key type (design §9), empty `tlc`/`cc` entries
   typed against the interface.
2a. [ ] **Prop generalization** (design §7): replace the panel's
   `onSampleCartridgeLocationChange`/`onSampleTubesChange` props with one
   `onManualSelectionChange(sel: ManualSelection)`; update `ParameterDesignPanel.tsx` (lines
   ~362-363, ~397-427) to map the union to `applySampleCartridgeLocation`/`applySampleTubes`.
3. [ ] **CC entry**: move the cc-side of each branch (design table lines 120/172/185/190-194/
   231-235/248/258/339-344/369/430/519) into the entry — selection via rack view wiring,
   maintenance groups from `maintenanceGroupFromRackArea`, slot-click allowance, copy, blocker
   text, `buildTaskParams`.
4. [ ] **TLC entry**: fold `TlcPreparationBody`'s experiment-specific content into the entry —
   storage-box selection grid, per-floor shelf maintenance groups + add-box tiles, hint
   (`tlc-shelf-bench-hint`), 2–4 shape gate (`tubeSelectionProblem`), tube-list summaries,
   `buildTaskParams`.
5. [ ] **Shrink the shared body**: single `LAB_LOGISTICS_CONFIG[executor]` lookup; both queries
   with `enabled` flags; generic ready/loading/error composition; readiness snapshot lifecycle,
   maintenance-mode state, and mutation dispatch unchanged; delete dead per-experiment helpers.
6. [ ] **Structural guard test** (vitest): panel source contains zero `executor === '`
   occurrences; `LAB_LOGISTICS_CONFIG` has exactly the `tlc` and `cc` keys.
7. [ ] **Gate**: `pnpm typecheck && pnpm lint && pnpm test`, then focused
   `./node_modules/.bin/playwright test tests/material-preparation-layout.spec.ts
   --project=chromium`. The 7 Playwright cases must pass with ZERO assertion edits (design §6 —
   an assertion edit means behavior drifted; stop and re-review). Re-run the whole chain after
   any fix.

## Validation commands

```bash
rg "executor === '" src/components/workspace/material-preparation/MaterialPreparationPanel.tsx  # → no matches
pnpm typecheck && pnpm lint && pnpm test
./node_modules/.bin/playwright test tests/material-preparation-layout.spec.ts --project=chromium
```

## Rollback

Single revertable portal commit; no contract/network change — pure relocation.
