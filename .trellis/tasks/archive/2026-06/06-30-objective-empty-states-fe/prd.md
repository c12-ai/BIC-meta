# PRD — Pending-objective workspace empty states (FE)

Child of `06-30-objective-stall-fix`. Research:
`research/workspace-empty-states-pending-objective.md`.

## Goal

When a session sits at `stage = experiment_objective` (objective not yet
confirmed), the Monitor and Result tabs render a **"confirm the objective"**
empty state with a CTA that routes the chemist to the existing Task → Objective
step — instead of generic "nothing here yet" copy that dead-ends.

## Requirements

### R1 — Monitor empty state
At `stage === 'experiment_objective'` (or `pendingForm?.formKind === 'objective'`),
`MonitorPane` shows "Confirm the experiment objective first" + a CTA button that
calls `selectLifecycle('task', true)` then `selectStep('objective', true)`.
Otherwise keep the existing "No live execution yet".
- Chokepoint: `MonitorPane.tsx:22-35` (the `!hasActivity` `<Empty>` block).

### R2 — Result empty state
`ResultConfirmationPane` already has the pending-decision → smarter-empty pattern
for `result_review` (`:29,:43,:49-63`). Add an `objective` branch beside it: when
objective is pending, title "Confirm the experiment objective" + the same
Task/Objective CTA.
- Chokepoint: `ResultConfirmationPane.tsx:36-67`.

### Signal to read
`stage === 'experiment_objective'` is the primary signal (duo-panel-safe — true
even when no agent decision exists). `pendingForm?.formKind === 'objective'` is the
secondary. Both are already in `workspaceStore` — **no new wiring, no new snapshot
field, no duplicated objective form** (the form lives in `ExperimentObjectiveStep`
and is the auto-routed destination already).

## Out of scope

- **Parameter Design empty state — DEFERRED.** At objective stage the Parameter
  step is locked and the user is on the Objective step, so its empty state is
  effectively unreachable. Research flagged it lowest-priority; skip unless Drake
  asks. (Rule 2 — don't build unreachable UI.)

## Acceptance Criteria

- [ ] AC1: At `stage=experiment_objective`, Monitor shows the objective CTA empty
  state; clicking it lands on Task → Objective step. Playwright/fixture test.
- [ ] AC2: At `stage=experiment_objective`, Result shows the objective CTA empty
  state (not "No analysis yet").
- [ ] AC3: Once `stage` advances past objective, both tabs revert to their normal
  empty/active states (no stale objective CTA). Regression guard.
- [ ] AC4: No objective form is duplicated — the CTA navigates to the existing
  `ExperimentObjectiveStep`, it does not re-render the form.

## Constraints

- Surgical (Rule 3): edit only `MonitorPane.tsx` and `ResultConfirmationPane.tsx`
  (+ a pure selector if the convention calls for one). Keep component
  subscriptions primitive/boolean.
- Match the existing `result_review` empty-state CTA anatomy (Rule 8) — copy that
  pattern, don't invent a new one.

## Consistency (Drake — maintain BE↔FE)

- **Copy the CC sibling, do not invent.** Authority:
  `../06-30-objective-stall-fix/research/cc-consistency-pattern.md` §(c) — mirror
  `ResultConfirmationPane.tsx:43-63` (the live `result_review` pending→CTA empty
  state) exactly. Same `Empty` primitive + `Button` anatomy (Rule 8).
- **Consume the existing contract only.** Read the pending objective from the
  EXISTING snapshot `pending_decisions[]` / `stage` (parent PRD "Shared contract"
  table). No new snapshot field, no BE change, no duplicated objective form — the
  CTA navigates to `ExperimentObjectiveStep`, it does not POST a confirm.
- **This child is built AGAINST merged BE** — the BE child lands and freezes the
  contract first (parent PRD Ordering). Verify against the BE `events.md` §3.6
  `ObjectiveConfirmAction` shape (pulled into this task's `implement.jsonl` by
  absolute path) before wiring the CTA.
- **Pre-dev verify** (research caveat): confirm `kind==='objective'` hydrates into
  `workspaceStore.pendingForm`; if it is filtered to `params`/`result_review`,
  key the CTA off `stage === 'experiment_objective'` (already in the store).

## Research

- `research/workspace-empty-states-pending-objective.md` — store data-flow,
  per-tab file:line, the `result_review` precedent to mirror.
- `../06-30-objective-stall-fix/research/cc-consistency-pattern.md` — the CC
  consistency authority shared with the BE child.
