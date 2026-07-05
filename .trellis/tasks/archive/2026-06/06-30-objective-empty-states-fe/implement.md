# Implement — Pending-objective empty states (FE)

Child of `06-30-objective-stall-fix`. Read `design.md` first.

## Pre-dev

- [ ] `BIC-agent-portal:trellis-before-dev` for the frontend package.
- [ ] Read the `result_review` empty-state CTA pattern end-to-end:
  `ResultConfirmationPane.tsx:36-67` (the anatomy to copy).
- [ ] Confirm `stage` + `selectLifecycle`/`selectStep` are exported from the
  store as research states (`workspaceStore.ts:257, 637-646`).

## Step 1 — MonitorPane objective empty state

- [ ] `MonitorPane.tsx`: add `pendingObjective` boolean sub +
  `goToObjective` handler.
- [ ] In the `!hasActivity` branch, render the objective CTA empty state when
  `pendingObjective`, else the existing "No live execution yet".
- [ ] Add `data-testid="monitor-empty-objective"` to the CTA button.

## Step 2 — ResultConfirmationPane objective empty state

- [ ] `ResultConfirmationPane.tsx`: add the same `pendingObjective` sub +
  handler.
- [ ] In the `results.length === 0` branch, add the `objective` variant before
  the `result_review` (`isPending`) variant.
- [ ] Add `data-testid="result-empty-objective"`.

## Step 3 — Validate

- [ ] Typecheck + lint (`pnpm` per portal scripts).
- [ ] Playwright fixture spec: snapshot at `stage=experiment_objective`, no
  trials → Monitor + Result show objective CTA (AC1, AC2); click → lands on
  Task/Objective (assert `activeLifecycle/activeStep`).
- [ ] Regression: stage past objective → CTA gone (AC3).
- [ ] AC4: assert `ExperimentObjectiveStep` form NOT rendered inside Monitor/
  Result.
- [ ] `BIC-agent-portal:trellis-check`.

## Notes

- Do NOT touch `ParameterDesignPanel.tsx` (out of scope — deferred).
- Keep the CTA inline in each pane (two call sites; no shared component yet —
  Rule 2). Extract only if a third consumer appears.
- Playwright runs on port **5173** (config is authoritative); LLM specs
  `--workers=1`. Bypass the localhost proxy (`--noproxy` / unset) before runs.

## Validation commands

```bash
cd BIC-agent-portal
pnpm typecheck && pnpm lint
pnpm playwright test tests/<objective-empty-states>.spec.ts
```
