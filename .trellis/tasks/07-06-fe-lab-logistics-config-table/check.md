# Check Results — fe-lab-logistics-config-table

## 2026-07-06

Implemented by `config-impl` subagent (sonnet) in an isolated git worktree
(`~/.cache/bic-worktrees/fe-lab-logistics-config`, branch
`feat/fe-lab-logistics-config-table`), reviewed and gate-verified in the main session. Uncommitted
pending Drake's go-ahead. Isolated from the concurrent 07-02 portal session by worktree + a
dedicated dev server on :5175.

### Outcome

`MaterialPreparationPanel.tsx` reduced from ~700 to ~130 lines: one
`LAB_LOGISTICS_CONFIG[executor]` lookup, then generic orchestration. All 18 `executor ===/!==`
branch sites removed (`rg "executor === '"` → 0). New `lab-logistics-config.tsx` holds the
`ExperimentLabLogisticsConfig` interface and `tlc`/`cc`/`re` entries; the two panel sync props
collapsed to one `onManualSelectionChange(ManualSelection)` (parent maps the union). Adapter
executor branches (`taskKeyForExecutor`/`taskLabelForExecutor`/`buildLabTaskParams`) absorbed into
entries; `withSampleTubes`/`withSampleCartridgeLocation` kept shared (also used by
ParameterDesignPanel).

### Main-session review — two regressions caught and fixed

1. **RE render dropped (behavior change).** The agent first added an `isLabLogisticsExecutor`
   guard that made RE render nothing in the prep dialog. Verified pre-change RE DOES reach the
   dialog (`isFormStage` includes `'re'` → "Set Up Lab Logistics" → `openPreparation('re')`) and
   showed both empty-requirement notices. Fix: widen the key type to `'tlc' | 'cc' | 're'`, delete
   the guard, add an `re` config entry reproducing the empty state exactly (no data sources, no
   manual requirement, RE's original `buildTaskParams`). The `re` entry's `missingAlert*` strings
   are dead code — `manualRequirement == null` short-circuits `hasRequiredManualSelection` to true,
   so the alert never renders for RE, matching pre-change.
2. **CC assigned-text regression (broke 2 of the original 7 tests).** The agent's CC `assignedText`
   returned `Selected · ${locationId}`, dropping the resolved slot label; the pre-change string was
   `Selected {area.display_name} · Slot {display_label} · {locationId}`. Playwright `:5` and `:348`
   failed on my own run despite the agent reporting green. Fix: thread `layout` into `assignedText`
   and restore the byte-exact string.

Both fixes verified by re-running the gate in the main session (not trusting the agent's report).

### Coverage added

New RE Playwright case (`material-preparation-layout.spec.ts:378`) asserts both empty-requirement
notices render for an RE prep dialog — the gap that let regression #1 pass unnoticed. Structural
vitest guard asserts zero `executor === '` in the panel and exactly the configured keys.

### Gate (main-session run)

- `pnpm typecheck` — clean
- `pnpm lint` — 15 pre-existing warnings, 0 new
- `pnpm test` — 76/76 (12 files, incl. structural guard)
- `playwright material-preparation-layout.spec.ts --project=chromium` — **8/8** (original 7 with
  zero assertion edits + new RE case)
- `rg "executor === '" MaterialPreparationPanel.tsx` — 0 matches

### Outstanding

- Commit pending Drake (branch `feat/fe-lab-logistics-config-table` in the worktree).
- Worktree cleanup after commit/merge (`git worktree remove`).
