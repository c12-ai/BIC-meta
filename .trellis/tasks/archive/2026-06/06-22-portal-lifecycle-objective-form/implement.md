# Implementation Plan — Portal lifecycle stepper + objective form

> Phased, commit-split execution of `design.md`. Repo: `BIC-agent-portal`. Each phase ends at a
> green gate (`pnpm typecheck` + `pnpm check` + relevant Vitest) and a discrete commit (rollback
> point). Do NOT write backend code — every BE contract this consumes is already shipped
> (06-18 / 06-22).

## ⚠️ Dependency banner (READ FIRST — applies to BOTH this doc and design.md)

This task **depends on the sibling BE task `06-22-l2-lifecycle-plan-confirm`**
(`TrialPhase` enum + `plan-confirm → parameter_design` stage advance + robot-only sparse job
materialization). **Land the BE sibling first.**

- **Phases 1–4 have NO sibling dependency** — they consume only the already-shipped 06-18 / 06-22
  contract (objective draft/confirm endpoints, `ExperimentObjectiveConfirmedEvent`,
  `SnapshotExperiment.stage/name`). Start here.
- **Phase 5** (`plan-confirm → stage='parameter_design'` live advance + robot-only sparse-seq
  verification + parameter-step unlock) **waits on the sibling**. If the sibling slips, ship
  Phases 1–4 and hold Phase 5.

Verify the sibling has landed before Phase 5: confirm a confirmed plan's snapshot shows the owning
experiment at `stage: "parameter_design"` and `trials[].phase` is a real `TrialPhase` value
(`curl .../snapshot | jq '.experiments[].stage, .trials[].phase'`).

## Pre-flight

```bash
cd /Users/drakezhou/Development/BIC/BIC-agent-portal
git checkout main && git pull
git checkout -b feat/portal-lifecycle-objective-form     # do NOT commit on main
pnpm install                                             # ensure deps current
pnpm typecheck && pnpm test                              # baseline green before any change
```

Load specs first: invoke the `BIC-agent-portal:trellis-before-dev` skill for the frontend
state/component/type-safety guidelines before writing code.

Per-phase gate (run before each commit):

```bash
pnpm typecheck                       # tsc -b --noEmit
pnpm exec biome check <touched>      # lint + format (or `pnpm check` to write)
pnpm test <touched test files>       # vitest run, scoped
pnpm build                           # tsc -b && vite build — run at minimum at Phase 1, 4, 5 ends
```

---

## Phase 1 — Client types + objective methods (no sibling dep)

**Goal:** type the wire + add the two objective client methods. No behavior change yet.

Steps:

1. `src/lib/agent-client.ts`:
   - Add `export type ExperimentStage = 'experiment_objective' | 'workflow_design' | 'parameter_design'`.
   - Add `SnapshotExperiment.name: string | null` and `SnapshotExperiment.stage: ExperimentStage`
     (`:343-350`).
   - Add `SnapshotObjective` + `ObjectiveReactantWire` (mirror `ObjectivePayload` /
     `ObjectiveReactantRow`); re-type `SnapshotExperiment.objective` to `SnapshotObjective`.
   - Re-type `SnapshotTrial.phase` from `string` to `TrialPhase` (import from
     `@/lib/derive-routing`) (`:386-400`).
   - Add `ObjectiveDraftRequest/Response`, `ObjectiveConfirmRequest/Response` mirrors (design §3c).
   - Add `saveObjectiveDraft(sessionId, body)` + `confirmObjective(sessionId, body)` mirroring the
     `recognizeTlcPlate` pattern (`headers()` + `jsonOrThrow<T>`, cite the BE route in a comment).
2. Grep consumers of `SnapshotExperiment.objective` (`grep -rn '\.objective' src/`) — confirm the
   re-type from `Record<string,unknown>` to `SnapshotObjective` compiles for every reader
   (the store hydrate is the main one, fixed in Phase 2). `ExperimentCreatedEvent.objective` stays
   `Record<string,unknown>` (event payload, untouched).

Validation:

```bash
pnpm typecheck    # the SnapshotExperiment.objective re-type may surface store-side errors —
                  # expected; the store cast at workspaceStore.ts:708 / :754 is fixed in Phase 2.
                  # If Phase 1 must stay green standalone, keep a local cast at the hydrate site
                  # and remove it in Phase 2.
pnpm exec biome check src/lib/agent-client.ts
```

**Commit:** `feat(client): type SnapshotExperiment.stage/name, SnapshotTrial.phase + objective endpoints`
**Rollback point:** revert this commit — pure additive typing, no runtime path touched.

---

## Phase 2 — Store actions + snapshot hydration (no sibling dep)

**Goal:** back the objective with the endpoints; hydrate objective + stage from the snapshot.

Steps:

1. `src/types/events.ts`:
   - Widen `ConfirmKind` to include `'objective'` (`:139`).
   - Add `ExperimentObjectiveConfirmedEvent` (`kind:'experiment_objective_confirmed'`,
     `experiment_id`, `name?`, `objective`) + add to the `RuntimeEvent` union (`:289-317`).
2. `src/lib/sse-client.ts`: add `'experiment_objective_confirmed'` to `KINDS` (`:30-65`). The
   `_exhaustive` guard (`:70`) now passes with the union widened.
3. `src/lib/event-dispatcher.ts`: add a case
   `case 'experiment_objective_confirmed': workspace.onObjectiveConfirmed(evt); chat.appendSystem(sessionId, 'Confirmed objective.', 'info', evt.event_id); break`.
4. `src/stores/workspaceStore.ts`:
   - Add `stage: ExperimentStage` to state + `INITIAL_DATA` (`'experiment_objective'`).
   - Add `FORM_STEP.objective = { lifecycle: 'task', step: 'objective' }` (`:480`).
   - Replace `saveObjectiveDraft`/`confirmObjective` (`:636-637`) with async actions (design §5b):
     POST via client, set store from the echoed `ObjectivePayload`; `confirmObjective` branches on
     `pendingForm?.formKind === 'objective'` (FORM_CONFIRM via `submitFormConfirm`) vs direct POST.
     Do NOT optimistically flip `stage`.
   - Add `onObjectiveConfirmed(evt)` (design §5c): `stage='workflow_design'`, set `objective`/
     `objectiveConfirmed`, auto-advance to `workflow` when `autoSwitchEnabled`.
   - `hydrateFromSnapshot` (`:648-772`): pick the foreground experiment, set
     `stage = exp?.stage ?? 'experiment_objective'`, `objective = mapWireObjective(exp.objective)`
     with `taskName = exp.name`, `objectiveConfirmed = objective?.confirmed ?? false`. Remove the
     `objective: s.objective` skip (`:752-755`). Remove the `t.phase as TrialPhase` cast (`:708`)
     now that the wire is typed.
   - Add `mapWireObjective` (in store or `src/lib/objective-mapping.ts`): wire `is_baseline →
     isReference`, numbers → draft strings, carry `rendered_rxn_url` + `target_weight_mg` read-only.

Validation:

```bash
pnpm typecheck
pnpm exec biome check src/types/events.ts src/lib/sse-client.ts src/lib/event-dispatcher.ts src/stores/workspaceStore.ts
pnpm test src/lib/event-dispatcher.test.ts src/lib/session-loader.test.ts src/stores/workspaceStore.routing.test.ts
```

**Commit:** `feat(store): backend-backed objective actions + snapshot stage/objective hydration`
**Rollback point:** revert this + Phase 1 to restore the FE-only objective path.

---

## Phase 3 — Stage-driven stepper (no sibling dep for objective→workflow)

**Goal:** `TaskConfigPane` derives Objective/Workflow/Parameter state from `stage`, not
`Boolean(taskId)`.

Steps (`src/components/workspace/TaskConfigPane.tsx`):

1. Replace `:60-62`: read `stage` from the store; drop `taskId`/`objectiveLocked`/`workflowLocked`
   heuristics. Define `objectiveLocked = stage !== 'experiment_objective'`,
   `workflowLocked = planConfirmed`.
2. Rewrite `stepHasData` / `stepStatus` / the `locked` derivation (`:73-122`) per design §6b:
   objective complete when `stage !== 'experiment_objective'`; workflow complete when
   `stage === 'parameter_design'`; parameter unlocks only at `stage === 'parameter_design'`.
3. `handleSelect` guard (`:126`): `if (id === 'parameter' && stage !== 'parameter_design') return`.
4. Re-express `setupSummary` / `setupChip` (`:161-176`) in terms of `stage` (+ `paramsConfirmed`).
5. Pass `readOnly={objectiveLocked}` / `readOnly={workflowLocked}` to the step components (§6c).

Validation:

```bash
pnpm typecheck
pnpm exec biome check src/components/workspace/TaskConfigPane.tsx
pnpm test src/stores/workspaceStore.routing.test.ts   # routing still green
# add a TaskConfigPane render test asserting step state per stage (objective/workflow/parameter)
pnpm test src/components/workspace/TaskConfigPane.test.tsx
```

**Commit:** `feat(stepper): derive Task Config step state from Experiment.stage`
**Rollback point:** revert to restore the heuristic stepper (Phases 1–2 still valid).

---

## Phase 4 — Objective form rework (no sibling dep)

**Goal:** reaction `<img>`, materials rows, remove local target-weight math, async submit + 422 mapping.

Steps (`src/components/workspace/ExperimentObjectiveStep.tsx`):

1. Reaction preview (`:249-263`): render `<img src={renderedRxnUrl}>` when present, SMILES-text
   fallback otherwise (design §7a). Copy action copies `watchedSmiles`.
2. Reactant rows (`:309-317`): render `structure_url` as `<img>` (FlaskConical fallback); seed rows
   from `objective.reactants` (role/smiles/name/amount/equivalents/is_baseline → isReference);
   per-row copy-SMILES (§7b).
3. Remove the local target-weight math (`:127-136`) and re-point the Target weight field (`:498-511`)
   to `objective.targetWeightMg` (`.toFixed(3)`) with a "Calculated on confirm" / "—" empty state.
   Update the label/help text (§7c).
4. Make `onSaveDraft`/`onConfirm` async (`:158-173`): `await saveObjectiveDraft/confirmObjective`;
   on confirm success do NOT call `selectStep('workflow')` locally (the SSE echo advances via the
   store, §7d). Map 422 → field/form errors via `mapObjective422` (§7e).
5. Add `mapObjective422(err)` helper (FastAPI `detail[].loc` → RHF field name; else form-level alert).

Validation:

```bash
pnpm typecheck
pnpm exec biome check src/components/workspace/ExperimentObjectiveStep.tsx src/lib/objective-mapping.ts
pnpm test src/components/workspace/ExperimentObjectiveStep.test.tsx src/lib/objective-mapping.test.ts
pnpm build    # full typecheck + vite build green
```

Tests to add:
- objective form: draft POST called with mapped body; confirm POST (direct) called when no pending
  form; FORM_CONFIRM path called when `pendingForm.formKind === 'objective'`.
- target-weight renders from backend (3 decimals); null → empty state; NO local recompute.
- baseline (reference) switching keeps exactly-one-baseline.
- 422 → field error mapping (mapped loc) and form-level fallback (unmapped).

**Commit:** `feat(objective): backend-backed form — reaction img, Mind materials, 422 mapping`
**Rollback point:** revert to restore the local-math form (Phases 1–3 still valid).

---

## Phase 5 — Live SSE stepper advance + parameter unlock + tests (GATED ON SIBLING BE)

**Goal:** the stepper advances live on objective-confirm → workflow and plan-confirm → parameter;
robot-only sparse jobs verified; full test + verification pass.

> ⛔ Do not start until the sibling BE `06-22-l2-lifecycle-plan-confirm` is landed and verified
> (confirmed-plan snapshot shows `stage: "parameter_design"` + typed `trials[].phase`).

Steps:

1. `src/stores/workspaceStore.ts` `onPlanConfirmed` (`:818-829`): add `stage: 'parameter_design'`
   to the returned patch (alongside the existing `planConfirmed: true` + auto-advance). This makes
   the live plan-confirm move the stepper to Parameter Design, matching the snapshot stage the
   sibling BE now persists.
2. Verify `hydrateFromSnapshot` sparse-seq join (`:667-686`) aligns plan-cards ↔ robot-only jobs
   (it indexes `materializedJobsByPlanId` by `j.seq`, so sparse seqs are already handled). Add a
   routing test with a manual step skipped (gap in `jobs[].seq`).
3. Tests:
   - `event-dispatcher.test.ts`: `experiment_objective_confirmed` → store `stage='workflow_design'`
     + auto-advance to workflow; `plan_confirmed` → `stage='parameter_design'` + advance to parameter.
   - `session-loader.test.ts`: snapshot with `stage` hydrates the stepper; live + replay agree
     (no-drift) for objective-confirm and plan-confirm.
   - `workspaceStore.routing.test.ts`: stage-driven step state; sparse-seq robot-only snapshot.
4. Playwright smoke (`tests/`): Objective → fill → confirm → stepper advances to Workflow Design
   (requires live backend `:8800` + portal `:5173`, `VITE_HIDE_DEVTOOLS=1`).

Validation (full):

```bash
pnpm typecheck
pnpm check                                  # lint + format + organize imports (write)
pnpm test                                   # full vitest suite green
pnpm build                                  # tsc -b && vite build
# Live smoke (backend + portal running):
pnpm exec playwright test tests/<objective-workflow>.spec.ts
```

**Commit:** `feat(lifecycle): live stepper advance on objective/plan confirm + robot-only parameter`
**Rollback point:** revert Phase 5 only — Phases 1–4 (objective vertical) remain shippable without
the sibling.

---

## Review gate

Before requesting review / commit sign-off:

- [ ] `pnpm typecheck` clean.
- [ ] `pnpm check` clean (lint + format + organize imports).
- [ ] `pnpm build` succeeds.
- [ ] `pnpm test` full suite green (added: objective form, objective mapping, stage stepper,
      objective-confirm dispatch, snapshot stage hydration, sparse-seq routing).
- [ ] Playwright objective→workflow smoke green against live backend.
- [ ] Invoke the `BIC-agent-portal:trellis-check` sub-agent for spec-compliance + cross-layer review.
- [ ] FE↔BE contract spec updated if any mirror revealed drift (Rule 10) — else note "no contract
      change, mirrors only".
- [ ] Parent `06-21` `implement.md` cleanup banner updated to mark the portal slice done.

## Completion checklist (maps to PRD Acceptance Criteria)

- [ ] `SnapshotExperiment` typed with `stage` + `name`; `SnapshotTrial.phase` typed `TrialPhase`. (Ph1)
- [ ] Stepper active/locked/complete derives from `stage`, not `Boolean(taskId)`. (Ph3)
- [ ] Objective form POSTs draft/confirm; no local-only persistence. (Ph2/Ph4)
- [ ] `hydrateFromSnapshot` restores the objective; survives hard refresh. (Ph2)
- [ ] Reaction renders from `rendered_rxn_url`; reactant rows from Mind materials; copy SMILES works. (Ph4)
- [ ] Local target-weight math removed; `target_weight_mg` from backend (3 decimals). (Ph4)
- [ ] Live objective-confirm → Workflow Design; live plan-confirm → Parameter Design; no refresh. (Ph5)
- [ ] Robot/manual cards read `plans.params.steps[].type`; manual steps non-dispatchable. (Ph5 verify)
- [ ] No portal code calls Mind directly. (all)
- [ ] Verification commands pass.

## Dependency-slip contingency

If the sibling BE is NOT landed by the time Phases 1–4 are done:

1. Ship Phases 1–4 as a self-contained PR (backend-backed objective + objective stage advance).
   The stepper will advance objective → workflow live (06-18/06-22 contract is enough); it will
   simply not advance workflow → parameter live until the sibling lands.
2. Hold Phase 5 on a follow-up commit/PR gated on the sibling.
3. Flag the split in the parent `06-21` `implement.md` so the lifecycle isn't marked fully done
   prematurely (Rule 9 — fail loud).
