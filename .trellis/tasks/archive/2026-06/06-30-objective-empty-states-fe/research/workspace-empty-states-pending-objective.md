# Research: Workspace empty states + pending-objective CTA opportunity

- **Query**: At "objective recommended" (no plans/jobs/trials, but a pending objective decision), Monitor / Result / Parameter Design show generic empty states. Where would a smarter "confirm the objective" empty state go, and does the store already carry the pending objective decision cheaply?
- **Scope**: internal
- **Date**: 2026-06-30
- **Repo**: `/Users/drakezhou/Development/BIC/BIC-agent-portal`

## TL;DR for the caller

1. **The pending objective decision IS already in the store, cheaply.** Snapshot `pending_decisions[]` → the FIRST `status==='pending'` row lands in `workspaceStore.pendingForm` (a single slot), and `objective` is a valid `ConfirmKind`. Any empty-state component can read `useWorkspaceStore((s) => s.pendingForm?.formKind === 'objective')` — one boolean subscription, no new wiring. There is also `s.stage === 'experiment_objective'` (the L1 lifecycle stage) which is the more robust signal of "objective not yet confirmed" (covers the duo-panel case where the user can confirm without an agent decision).
2. **The objective confirmation already has a first-class home**: the **Task tab → Objective step** (`ExperimentObjectiveStep.tsx`) renders the full objective form + a `Confirm Objective` CTA, and `onFormRequested`/hydrate auto-route a pending `objective` form to `{ lifecycle: 'task', step: 'objective' }`. So a redesign should **point users back to the Task/Objective step**, NOT duplicate the objective form into Monitor/Result/ParamDesign (Rule 2).
3. The three generic empty states are dumb because each gates on trial/job data that does not exist yet. The cheap win is: when `pendingForm?.formKind === 'objective'` (or `stage === 'experiment_objective'`), swap the generic copy + add a CTA that calls `selectLifecycle('task', true)` + `selectStep('objective', true)` to jump the user to the existing confirm surface.

## Findings

### Files Found

| File Path | Role |
|---|---|
| `src/components/workspace/WorkspacePanel.tsx` | Tab shell — wires Task / Monitor / Result tabs |
| `src/components/workspace/TaskConfigPane.tsx` | Task tab body; hosts Objective / Workflow / ParameterDesign steps |
| `src/components/workspace/ExperimentObjectiveStep.tsx` | Objective form + `Confirm Objective` CTA (the existing pending-objective surface) |
| `src/components/workspace/MonitorPane.tsx` | Monitor tab; "No live execution yet" empty state |
| `src/components/workspace/ExperimentProgressPanel.tsx` | Rendered inside MonitorPane once activity exists; returns `null` pre-dispatch |
| `src/components/workspace/ParameterDesignPanel.tsx` | Parameter Design body; `No backend data` / `Stage locked` empty states |
| `src/components/workspace/ResultConfirmationPane.tsx` | Result tab; "No analysis yet" / "Result review pending" empty state |
| `src/components/workspace/task-config-steps.ts` | `isObjectiveLocked`, `canSelectStep` — Objective step is selectable while `stage==='experiment_objective'` |
| `src/stores/workspaceStore.ts` | Store: `pendingForm`, `stage`, `hydrateFromSnapshot` |
| `src/stores/workspaceStore.selectors.ts` | `selectActiveTrial`, `selectTrialForStage`, `trialsForStage`, `isLiveTrial` |
| `src/lib/agent-client.ts` | `SnapshotDecision` / `SessionSnapshot.pending_decisions` shape |
| `src/types/events.ts` | `ConfirmKind = 'plan' | 'params' | 'result_review' | 'objective'` (`:139`) |

> Note on the "ConfirmationPane" the brief mentioned: there is **no** component literally named `ConfirmationPane`. `WorkspacePanel.tsx:5,71` imports/renders `ResultConfirmationPane` (the Result tab). The objective confirmation lives in `ExperimentObjectiveStep.tsx`, not a separate pane. (grep over `src/` confirms only `ResultConfirmationPane`.)

### Empty-state gating (current, with file:line)

**MonitorPane** — `MonitorPane.tsx:17-36`
```ts
const hasActivity = useWorkspaceStore((s) => {
  const t = selectActiveTrial(s)
  return (t?.progress ?? null) !== null || t?.labTaskId != null
})
if (!hasActivity) { /* <Empty> "No live execution yet" — MonitorPane.tsx:22-35 */ }
```
At objective stage there is no active trial → `hasActivity=false` → generic empty. `ExperimentProgressPanel` itself returns `null` when both `progress` and `labTaskId` are absent (`ExperimentProgressPanel.tsx:289-291`), so MonitorPane owns this empty copy.

**ResultConfirmationPane** — `ResultConfirmationPane.tsx:20-67`
```ts
const results = useWorkspaceStore((s) => s.results)
const pendingForm = useWorkspaceStore((s) => s.pendingForm)
const isPending = pendingForm?.formKind === 'result_review'   // :29
if (results.length === 0) {
  // <Empty> title: isPending ? 'Result review pending' : 'No analysis yet'  (:43)
  // when isPending → renders Accept/Rework buttons inline (:49-63)
}
```
Note this pane ALREADY has a pattern of "pending decision → smarter empty state + inline CTA" — but only for `result_review`, not `objective`. At objective stage `isPending=false` → "No analysis yet".

**ParameterDesignPanel** — `ParameterDesignPanel.tsx`
- `robotStageSig` derived from `jobs[]` filtered to `type==='robot'` (`:114-119`). With `jobs=[]` (objective stage) the panel keeps the full peer row and falls into the no-trial branch.
- Body branch decision (`:254-299`): `hasExecutorForm` (`:221`) = `(shownTrial != null || stageHasConfirmedRobotJob) && isFormStage`. At objective stage `shownTrial` is undefined (`selectTrialForStage` → undefined, `selectors:56-64`) and `planConfirmed=false` so `stageHasConfirmedRobotJob=false` → `hasExecutorForm=false` → `body = <NoBackendDataStageBody stage={activeStage} />` (`:298`).
- `NoBackendDataStageBody` empty copy: `:480-503` ("No backend data" + "... after the backend creates a trial and sends task_params_set ...").
- Note: ParameterDesignPanel is reached via the Task tab → Parameter step, AND the Parameter step is **locked** at objective stage anyway (`canSelectStep`/`isWorkflowLocked` chain; `task-config-steps.ts:97-116`). So at the exact "objective recommended" moment the user is on the **Objective** step, not the Parameter step — the ParamDesign empty state is the lowest-priority of the three to fix.

**WorkspacePanel** — `WorkspacePanel.tsx:26-77`. All three lifecycle tabs are always rendered (`:29-32`, `availableTabs = LIFECYCLE_TABS`); each pane owns its own empty state. No tab-level gating to change.

### Store data-flow for pending decisions (cite file:line)

1. **Snapshot shape** — `agent-client.ts:506-526`: `SessionSnapshot.pending_decisions: SnapshotDecision[]`, each `{ decision_id, kind: ConfirmKind | null, original_action, status }`.
2. **Landing in the store** — `workspaceStore.ts:931-938` (inside `hydrateFromSnapshot`):
   ```ts
   const pending = snapshot.pending_decisions.find((d) => d.status === 'pending')
   const pendingForm: PendingForm | null = pending?.kind
     ? { decisionId: pending.decision_id, formKind: pending.kind, originalAction: pending.original_action }
     : null
   ```
   **Only the FIRST pending row becomes `pendingForm`** — it is a single slot, not a list (`pendingForm: PendingForm | null`, type at `workspaceStore.ts:133-140, 249`). For the objective-recommended state that single pending row IS the objective decision, so `pendingForm.formKind === 'objective'`.
3. **Live path** — `onFormRequested` (`workspaceStore.ts:665-674`) sets the same single `pendingForm` and auto-routes via `FORM_STEP` (`:571-579`): `objective → { lifecycle: 'task', step: 'objective' }`. Hydrate replays the same routing (`:968-973`).
4. **L1 stage** — `stage: ExperimentStage` (`workspaceStore.ts:257`), hydrated from the foreground experiment (`:888, :956`), starts at `'experiment_objective'` (`INITIAL_DATA :607`), advanced to `workflow_design` by `onObjectiveConfirmed` (`:805-813`). `stage === 'experiment_objective'` is the **most reliable** "objective not yet confirmed" signal because it is true even in the duo-panel case where the user can confirm with no agent-minted decision (so `pendingForm` may be null but `stage` is still objective).

**selectActiveTrial / selectTrialForStage** (selectors):
- `selectActiveTrial(s)` = `s.activeTrialId ? s.trialsById[s.activeTrialId] : undefined` (`selectors:36-38`). undefined at objective stage.
- `selectTrialForStage(s, stage)` = pinned attempt ?? latest `trialsForStage` ?? undefined (`selectors:56-64`).
- Neither reads `pendingForm`; the existing selectors are trial-centric. A new helper (e.g. `selectPendingObjective(s)` or just reading `s.pendingForm` / `s.stage` inline) is what an empty-state needs.

**Can an empty-state cheaply read "is there a pending objective decision?"** — YES. Two cheap primitive subscriptions, no new store wiring:
- `useWorkspaceStore((s) => s.pendingForm?.formKind === 'objective')` (agent-decision present), and/or
- `useWorkspaceStore((s) => s.stage === 'experiment_objective')` (objective not yet confirmed — duo-panel-safe).
Plus the navigation actions already exist: `selectLifecycle(tab, byUser)` (`workspaceStore.ts:637-641`) and `selectStep(step, byUser)` (`:642-646`).

### Related Specs

- `.trellis/spec/ui/L3/workspace.md`
  - `:128-130` — tab-visibility contract: Monitor visible only on `waiting|in_progress`; Result visible on pending `result_review` / evidence / done trial. (Objective stage shows none of these → all three are empty, by design.)
  - `:147` — "E2E fixture: workspace fixture must assert ... pending result-review empty-state actions" — precedent that pending-decision empty states ARE a spec'd surface (only `result_review` today).
  - `:266, :278` — Result append model + "If the gate arrives before typed evidence, the `No analysis yet` empty state still renders the same Accept/Rework actions so the user is not blocked by card timing." This is the EXACT pattern to mirror for objective.
  - `:60-68` — StepIndicator / `Task setup` card; Objective step is FE-resident; `FORM_STEP` routes objective → Objective step.
  - `:297` — `No backend data` empty-state contract for ParameterDesign (`testid="no-backend-data"`).
- `.trellis/spec/frontend/state-management.md`, `component-guidelines.md` — (not yet read in depth; relevant if adding a selector — prefer a pure derivation in `workspaceStore.selectors.ts` per the existing pattern, keep component subscriptions primitive/boolean).

## Concrete proposal: where a smarter empty state goes per tab

The existing confirm surface is `ExperimentObjectiveStep` (Task tab → Objective step). The improved empty states should be **pointers/CTAs to that surface**, not new objective forms.

| Tab | File:line to edit | What to read | Suggested behavior |
|---|---|---|---|
| **Monitor** | `MonitorPane.tsx:22-35` (the `!hasActivity` `<Empty>` block) | add `const pendingObjective = useWorkspaceStore((s) => s.pendingForm?.formKind === 'objective' || s.stage === 'experiment_objective')` | When `pendingObjective`: title/desc like "Confirm the experiment objective first" + a CTA button `onClick={() => { selectLifecycle('task', true); selectStep('objective', true) }}`. Else keep "No live execution yet". |
| **Result** | `ResultConfirmationPane.tsx:36-67` (the `results.length === 0` `<Empty>`) | already reads `pendingForm`; add the `formKind === 'objective'` (or `stage`) branch alongside the existing `isPending` (`result_review`) branch at `:29`/`:43` | Add a third empty-state variant: when objective is pending, title "Confirm the experiment objective" + same Task/Objective CTA. Mirrors the existing `result_review` inline-CTA pattern (`:49-63`). |
| **Parameter Design** | `ParameterDesignPanel.tsx:298` → inside `NoBackendDataStageBody` (`:480-503`), OR branch earlier in the body decision (`:254`) | `s.stage === 'experiment_objective'` (cheapest) | LOWEST priority: at objective stage the Parameter step is locked and the user is on the Objective step, so they rarely see this. If addressed, route the empty copy through the same Task/Objective CTA. |

### Avoiding redundancy (Rule 2)

- **DO NOT** duplicate the objective form. It already lives in `ExperimentObjectiveStep.tsx` and is the auto-routed destination for a pending objective decision (`FORM_STEP.objective`, `workspaceStore.ts:573`).
- The right scope is a **navigation CTA** ("go confirm the objective") + better copy, reading the boolean already in the store. No new event handling, no new snapshot field.
- The cleanest single point would arguably be Monitor + Result only (the two tabs a user might click while waiting). Parameter Design is gated behind a locked step at this stage, so its empty state is mostly unreachable at "objective recommended" — consider deferring it.

## Caveats / Not Found

- I did NOT find an existing component that surfaces the pending **objective** as a workspace-level CTA outside the Objective form itself — so there is genuinely nothing to reuse beyond `ExperimentObjectiveStep` + the `selectLifecycle`/`selectStep` actions. (The `result_review` empty-state CTA in `ResultConfirmationPane.tsx:49-63` is the closest design precedent.)
- `pendingForm` holds only the FIRST pending decision (`workspaceStore.ts:931`). At "objective recommended" that is the objective decision, so this is fine — but if multiple pending decisions ever coexist, `pendingForm` may not be the objective one; `s.stage === 'experiment_objective'` is the safer signal in that edge case.
- I did not read `.trellis/spec/frontend/state-management.md` / `component-guidelines.md` line-by-line — flag for the implementer to confirm the selector-placement convention before adding `selectPendingObjective`.
- No code was modified; this is research only.
