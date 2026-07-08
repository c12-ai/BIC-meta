# Design — Pending-objective empty states (FE)

Child of `06-30-objective-stall-fix`. Research:
`research/workspace-empty-states-pending-objective.md`.

## Signal

Read **`stage === 'experiment_objective'`** as the primary "objective not yet
confirmed" boolean (`workspaceStore.ts:257`, duo-panel-safe). Both panes subscribe
to one extra primitive boolean — no new store wiring.

```ts
const pendingObjective = useWorkspaceStore((s) => s.stage === 'experiment_objective')
```

Navigation actions already exist (`workspaceStore.ts:637-646`):
```ts
const selectLifecycle = useWorkspaceStore((s) => s.selectLifecycle)
const selectStep = useWorkspaceStore((s) => s.selectStep)
const goToObjective = () => { selectLifecycle('task', true); selectStep('objective', true) }
```

## Shared CTA

A tiny inline CTA block reused by both panes (copy the `result_review` button
anatomy at `ResultConfirmationPane.tsx:49-63`). Keep it inline per pane (two call
sites, Rule 2 — no premature shared component unless a third consumer appears).

Copy:
- Title: **"Confirm the experiment objective"**
- Description: "Confirm the objective to start the workflow. Lab progress and
  results appear here once the experiment is dispatched."
- Button: **"Go to objective"** → `goToObjective()`.

## R1 — MonitorPane (`MonitorPane.tsx:22-35`)

In the `!hasActivity` branch, branch on `pendingObjective`:
- `pendingObjective` → objective CTA empty state (`data-testid="monitor-empty"`
  kept; add `data-testid="monitor-empty-objective"` on the CTA for the test).
- else → existing "No live execution yet" (unchanged).

Order matters: check `pendingObjective` first, since at objective stage
`hasActivity` is already false.

## R2 — ResultConfirmationPane (`ResultConfirmationPane.tsx:36-67`)

In the `results.length === 0` branch, add an `objective` variant **beside** the
existing `isPending` (`result_review`) branch. Precedence: `result_review` and
`experiment_objective` are mutually exclusive in practice (different stages), but
check `pendingObjective` explicitly so copy is unambiguous.

- `pendingObjective` → title "Confirm the experiment objective" + "Go to
  objective" CTA (`data-testid="result-empty-objective"`).
- else if `isPending` (result_review) → unchanged.
- else → "No analysis yet" (unchanged).

## Out of scope

- ParameterDesign empty state — DEFERRED (locked step at objective stage,
  unreachable). Do not touch `ParameterDesignPanel.tsx`.

## Why no duplication (Rule 2)

The objective form already lives in `ExperimentObjectiveStep` and is the
auto-routed destination for a pending objective (`FORM_STEP.objective`,
`workspaceStore.ts:573`). These empty states are **navigation pointers**, not
forms. AC4 asserts no form re-render.

## Test plan

- Fixture/Playwright: hydrate a snapshot at `stage=experiment_objective` (no
  trials) → assert Monitor + Result render the objective CTA; click → asserts
  `activeLifecycle=task`, `activeStep=objective` (AC1, AC2).
- Regression: advance `stage` past objective → CTA gone, normal empty states back
  (AC3).
- AC4: assert the Objective form (`ExperimentObjectiveStep` testid) is NOT
  rendered inside Monitor/Result — only the CTA button.

## Risks

- `pendingForm` holds only the FIRST pending decision; at objective stage that is
  the objective decision, but `stage` is the safer signal and is what we use —
  low risk.
- Copy drift vs the BE confirm surface — keep CTA copy generic ("Go to
  objective"), the actual form labels live in `ExperimentObjectiveStep`.
