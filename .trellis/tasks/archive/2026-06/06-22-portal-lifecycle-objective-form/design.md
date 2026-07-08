# Technical Design — Portal lifecycle stepper + objective form

> Grounds the PRD (R1–R6) against the live portal (`BIC-agent-portal@main`) and the
> backend contract (`BIC-agent-service`). Every field name below is quoted verbatim from
> the BE DTOs (`app/data/objective_schemas.py`, `app/api/routers/sessions.py`,
> `app/events/bypass_emitted.py`, `app/events/form_payloads.py`). Mirrors the 06-18
> `design.md` structure.

## 0 · Dependency banner (UPDATED 2026-06-22 — sibling BE LANDED)

✅ **The sibling BE task `06-22-l2-lifecycle-plan-confirm` is DONE and archived** (TrialPhase enum
end-to-end, `plan-confirm → parameter_design` stage advance, robot-only sparse job materialization,
sparse-seq cursor). **Phase 5 is NO LONGER gated** — this task can run start-to-finish.

✅ **`ExperimentObjectiveDrafted` also landed** (task `06-22-objective-draft-live-sync`,
`kind="experiment_objective_drafted"`, a `RuntimeEmittedEvent`): the objective subagent's tools
emit it as the agent edits the draft; `apply` persists to `experiments.objective`. **This task must
also consume it** — add `experiment_objective_drafted` to `KINDS` + a dispatcher case that live-syncs
the agent's draft edits into the objective form (see §4c, §5c). Without it the form only updates at
confirm; with it, agent chat-driven edits appear live.

What was already shipped by 06-18 / 06-22 BE (all consumable now):

- `SnapshotExperiment.stage` + `.name` are on the wire (`SnapshotExperimentItem`,
  `sessions.py:457-466`).
- `POST /sessions/{id}/objective/draft` + `/objective/confirm` are live
  (`sessions.py:344-399`).
- `ExperimentObjectiveConfirmedEvent` (`kind="experiment_objective_confirmed"`) + both confirm
  paths (direct POST and FORM_CONFIRM(objective)) exist (`bypass_emitted.py:101`,
  `service.py:416`, `form_payloads.py:763`).

Also now shipped (no longer a wait): `SnapshotTrial.phase` is a real `TrialPhase` value; plan
confirm advances `stage → parameter_design` and materializes **robot-only sparse** jobs.

Phasing (see `implement.md`): Phases 1–4 are the objective + objective-stage vertical; Phase 5 is
the `stage → parameter_design` live advance + robot-card verification + the `experiment_objective_drafted`
live-sync. With the sibling landed, Phase 5 runs without a gate.

## 1 · Scope & Boundaries

This task owns the **portal lifecycle vertical**: typing `SnapshotExperiment.stage/name` +
`SnapshotTrial.phase`, rewriting `TaskConfigPane` to derive step state from backend `stage` (not
`Boolean(taskId)` heuristics), backing the objective form with the real draft/confirm endpoints,
hydrating the objective from the snapshot, advancing the stepper live on the objective-confirm /
plan-confirm SSE events, and rendering reaction/materials from Mind data (removing the local
target-weight math).

It deliberately stops at the BE lifecycle (sibling task), the 5-status FE header projection
(separate FE task Drake owns), OCR/image reaction recognition, and a client-side molecule drawing
library (PRD Out of Scope).

Event flow stays inside the established invariants: `sse-client.ts → event-dispatcher.ts →
zustand stores → components` (invariant **I-UI-1**: no component subscribes to SSE directly;
new event surfaces add a `dispatchEvent` case + a store mutation + a `KINDS` registration).

## 1a · Experiment Objective field contract (Drake, 2026-06-22) — backend-Agent recognition

Drake's field spec for the FE `ExperimentObjective` form (the agent reads by field **semantics**,
not UI position):

```ts
interface ExperimentObjective {
  taskName: string            // Experiment name — required; the agent's task identifier
  smiles?: string             // Rxn source (Reaction SMILES) — optional; drives the rendered image
  reactants: ObjectiveReactant[]  // Compound matrix — from Mind/Rxn parse or user-added
  targetYieldPct: string      // required; string-stored, validated 0–100 at confirm
  targetPurityPct: string     // required; string-stored, validated 0–100 at confirm
}
interface ObjectiveReactant {
  name: string                // Compound name
  amountMg: string            // Feed mg
  equivalents: string         // Eq.
  isReference: boolean        // Primary — exactly one true per experiment (basis for eq. + target weight)
}
```

**Two reconciliations with the BE contract (Drake decisions 2026-06-22):**

1. **Target weight is the BACKEND/Mind value, NOT the local formula.** The spec's
   `Target weight = primary.amountMg × targetYieldPct / 100` is **legacy/fallback documentation
   only**. Phase 4 removed that local math; the form renders `ObjectivePayload.target_weight_mg`
   (Mind goal-confirm, MW/stoichiometry-correct, read-only, 3 decimals). Mind is authoritative.
   `Target product` is still parsed from the `>>` product side of `smiles` for display; a future
   structured `targetProduct` field can supersede that.
2. **Required-at-confirm, lenient-at-draft.** `taskName` / `reactants[].name` / `amountMg` /
   `equivalents` / both target pcts are required + positive/in-range **at confirm** (the BE
   `confirm` endpoint is the validation authority → 422 `form_validation_failed`). At **draft**,
   parsed reactants may carry `name=null` and non-baseline `equivalents` empty (Mind fills them on
   recalculation); the **baseline** row's `equivalents` is fixed `1.00`. The draft endpoint is
   lenient; the FE zod gate is a fast-UX mirror, not the authority.

Recognition rules (unchanged from the spec): `reactants` (input compounds + feed) and the target
metrics (`targetYieldPct`/`targetPurityPct`) are distinct data classes; the `isReference:true`
compound is the basis for eq. + target-mass calculation; the agent parses the target product from
the `smiles` product side until a structured field exists.

This field contract is **consistent with the Phase-4 form as built** — no code change; recorded here
as the authoritative recognition contract for the backend Agent.

## 2 · Backend Contract (consume, no change)

All shapes are **already on the wire** — the portal only types + consumes them. Hand-mirror to TS
(shared-types does not export these to TS; the established portal pattern is to mirror in
`agent-client.ts` / `events.ts` and cite the BE file).

### 2a · Objective draft/confirm DTOs (`sessions.py`, `objective_schemas.py`)

```text
POST /sessions/{id}/objective/draft   (lenient)
  req  ObjectiveDraftRequest:    name?, reaction_smiles?, reactants[], target_purity_pct?,
                                 target_yield_pct?
  resp ObjectiveDraftResponse:   experiment_id, name?, objective:ObjectivePayload

POST /sessions/{id}/objective/confirm (strict — BE is the validation authority)
  req  ObjectiveConfirmRequest:  name(min_len 1), reaction_smiles(min_len 1), reactants[],
                                 feed_amount_mg(gt 0), target_purity_pct, target_yield_pct,
                                 basis_material_hint?
  resp ObjectiveConfirmResponse: experiment_id, name, objective:ObjectivePayload,
                                 stage("workflow_design"), event_id

ObjectiveReactantInput / ObjectiveReactantRow:
  role, smiles, name?, structure_url?, amount_mg?, equivalents?, is_baseline(=false)

ObjectivePayload (persisted `experiments.objective` JSONB, echoed on both responses):
  reaction_smiles?, rendered_rxn_url?, reactants[ObjectiveReactantRow],
  target_purity_pct?, target_yield_pct?, target_weight_mg?(Mind-calculated), confirmed(bool)
```

Key contract facts the portal must honor:

- `target_weight_mg` is **Mind-calculated** and lives on `ObjectivePayload` — null until goal-confirm
  runs. The portal renders it (3 decimals) and **removes** the local
  `refAmount * yield / 100` math (`ExperimentObjectiveStep.tsx:127-136`).
- `rendered_rxn_url` is a **server-rendered** reaction image URL (`<img src>`); `structure_url` per
  reactant row is the per-molecule image. No client molecule lib (confirmed: package.json has
  **zero** ketcher/rdkit/smiles/openchemlib deps).
- `confirm` returns `event_id` for optimistic reconciliation with the SSE echo (same id-idempotent
  pattern as `submitFormConfirm` / `submitDecision`).
- BE is the validation authority — `confirm` 422s on bad SMILES / out-of-range targets / baseline
  rules with `error_code: "form_validation_failed"` (see §7).

### 2b · `ExperimentObjectiveConfirmedEvent` (bypass; `bypass_emitted.py:101`)

```text
kind = "experiment_objective_confirmed"   # BYPASS → no turn_id
  experiment_id, name?, objective:dict
apply: persist objective(+name); advance stage experiment_objective → workflow_design (idempotent)
```

Both confirm paths (direct POST and FORM_CONFIRM(objective)) emit this **same** event → one
stage-advance code path. The portal dispatcher must recognize it and advance the stepper to
Workflow Design (R1/R4).

### 2c · Snapshot DTOs (already typed BE-side; portal mirror is stale)

```text
SnapshotExperimentItem (sessions.py:457):  experiment_id, kind, name(str|null),
                                           objective(dict), status, stage(ExperimentStage), started_at
SnapshotTrialItem      (sessions.py:500):  ... phase(str → TrialPhase value), ...
SnapshotPlanItem.params.steps[]:           {title, executor, type}  ← robot/manual ownership
```

`ExperimentStage` wire values: `experiment_objective | workflow_design | parameter_design`.
`TrialPhase` wire values: `collecting_params | rts | conducting | done`.

### 2d · FORM_CONFIRM(objective) vs direct POST (R4 reconciliation — resolved)

The BE supports BOTH and they converge on `ExperimentObjectiveConfirmedEvent`:

| Path | Portal call | BE handler | Use when |
| --- | --- | --- | --- |
| **Direct POST** | new `confirmObjective(sessionId, body)` → `POST /objective/confirm` | `service.confirm_objective` → mints bypass event + runs Mind goal-confirm for `target_weight_mg` | **Pure form-driven confirm** (duo-panel: chemist fills + confirms the form with no agent-minted decision). PREFERRED default for this form. |
| **FORM_CONFIRM(objective)** | existing `submitFormConfirm(sessionId, {decision_id, confirm_kind:'objective', form_values})` | `route_entry.py:72` → `service` `_build_objective_confirmed_event` (`service.py:416`) → same bypass event | An **agent-proposed** objective: when a `FormRequestedEvent(confirm_kind="objective")` is pending (`pendingForm.formKind === 'objective'`), confirm via the decision so the agent's HITL gate resolves. |

**Decision (Rule 5):** the objective form uses the **direct POST** as its primary confirm action
(duo-panel — the chemist proceeds without the agent), and **routes through `submitFormConfirm`
only when there is a pending objective decision** (`pendingForm.formKind === 'objective'`). The
selector is identical to the params-confirm pattern already in the codebase
(`submitFormConfirm` omits `decision_id` for user-initiated params). The store's confirm action
encapsulates this branch; the component stays path-agnostic. Either way the stepper advance is
driven by the resulting `ExperimentObjectiveConfirmedEvent`, never by an optimistic local flip
alone (so live + replay agree).

`form_values` for the FORM_CONFIRM path is the `ObjectiveConfirmAction` echo:
`{experiment_id, name, objective}` (`form_payloads.py:763-779`); the BE falls back to the active
experiment when omitted.

## 3 · Type changes (`agent-client.ts`)

### 3a · `SnapshotExperiment` — add `stage` + `name` (`agent-client.ts:343-350`)

```ts
/** Wire values: experiment_objective | workflow_design | parameter_design.
 *  Mirrors BIC-agent-service app/core/enums.py::ExperimentStage. */
export type ExperimentStage = 'experiment_objective' | 'workflow_design' | 'parameter_design'

export interface SnapshotExperiment {
  experiment_id: string
  kind: string
  name: string | null            // NEW — SnapshotExperimentItem.name
  objective: SnapshotObjective    // was Record<string, unknown>; now the typed ObjectivePayload mirror
  status: string
  stage: ExperimentStage          // NEW — SnapshotExperimentItem.stage
  started_at: string | null
}
```

`objective` is re-typed from `Record<string, unknown>` to a `SnapshotObjective` mirror of
`ObjectivePayload` (§3c) so hydration is type-safe.

### 3b · `SnapshotTrial.phase` — type as `TrialPhase` (`agent-client.ts:386-400`)

The portal already defines `TrialPhase` (`derive-routing.ts:18`, exact 4 values). Re-type
`SnapshotTrial.phase` from `string` to `TrialPhase` and import it. (The store already casts
`t.phase as TrialPhase` at `workspaceStore.ts:708`; this removes the cast.)

### 3c · `SnapshotObjective` + objective request/response mirrors (new, in `agent-client.ts`)

```ts
export interface ObjectiveReactantWire {
  role: string
  smiles: string
  name: string | null
  structure_url: string | null
  amount_mg: number | null
  equivalents: number | null
  is_baseline: boolean
}
export interface SnapshotObjective {     // mirror of ObjectivePayload
  reaction_smiles: string | null
  rendered_rxn_url: string | null
  reactants: ObjectiveReactantWire[]
  target_purity_pct: number | null
  target_yield_pct: number | null
  target_weight_mg: number | null
  confirmed: boolean
}
export interface ObjectiveDraftRequest { name?: string; reaction_smiles?: string;
  reactants: ObjectiveReactantWire[]; target_purity_pct?: number; target_yield_pct?: number }
export interface ObjectiveDraftResponse { experiment_id: string; name: string | null; objective: SnapshotObjective }
export interface ObjectiveConfirmRequest { name: string; reaction_smiles: string;
  reactants: ObjectiveReactantWire[]; feed_amount_mg: number; target_purity_pct: number;
  target_yield_pct: number; basis_material_hint?: string }
export interface ObjectiveConfirmResponse { experiment_id: string; name: string;
  objective: SnapshotObjective; stage: ExperimentStage; event_id: string }
```

### 3d · Client methods (mirror the existing `recognizeTlcPlate` / `submitFormConfirm` pattern)

```ts
export async function saveObjectiveDraft(sessionId: string, body: ObjectiveDraftRequest):
  Promise<ObjectiveDraftResponse> { /* POST /objective/draft via jsonOrThrow */ }
export async function confirmObjective(sessionId: string, body: ObjectiveConfirmRequest):
  Promise<ObjectiveConfirmResponse> { /* POST /objective/confirm via jsonOrThrow */ }
```

Both use `headers()` + `jsonOrThrow<T>` so a 422 surfaces as `ApiError` with
`errorCode = "form_validation_failed"` (consumed in §7).

## 4 · Event-type changes (`events.ts`, `sse-client.ts`, `event-dispatcher.ts`)

### 4a · `ConfirmKind` gains `'objective'` (`events.ts:139`)

```ts
export type ConfirmKind = 'plan' | 'params' | 'result_review' | 'objective'
```

This widens `FormRequestedEvent.confirm_kind` so a pending agent-proposed objective form is typed,
and `FORM_STEP` (store, §5d) can route `objective → workflow` lifecycle/step.

### 4b · `ExperimentObjectiveConfirmedEvent` (new) + union + KINDS

```ts
/** Bypass — chemist confirmed the Experiment Objective (06-18). No turn_id.
 *  apply advances Experiment.stage experiment_objective → workflow_design.
 *  See BIC-agent-service app/events/bypass_emitted.py::ExperimentObjectiveConfirmedEvent. */
export interface ExperimentObjectiveConfirmedEvent extends BaseEvent {
  kind: 'experiment_objective_confirmed'
  experiment_id: string
  name?: string | null
  objective: Record<string, unknown>
}
```

- Add to the `RuntimeEvent` union (`events.ts:289-317`).
- Add `'experiment_objective_confirmed'` to `KINDS` (`sse-client.ts:30-65`) — **REQUIRED**: the
  `_MissingKind`/`_exhaustive` guard (`sse-client.ts:70-72`) fails the build if a union kind is not
  registered, AND a named SSE channel is dropped before any listener runs if the kind is missing
  from `KINDS`.
- Add a dispatcher case (`event-dispatcher.ts`) calling a new
  `workspace.onObjectiveConfirmed(evt)` store action (§5c). Optionally append a system bubble
  (`chat.appendSystem(... 'Confirmed objective.' ...)`) for parity with `plan_confirmed` —
  but the bypass event has no `event_id`-minted optimistic bubble path, so the system bubble is
  dispatcher-only (mirror `decision_resolved`'s id from `evt.event_id`).

> Note: `FormRequestedEvent(confirm_kind="objective")` rides the existing `form_requested` case —
> already dispatched to `workspace.onFormRequested` — so no new case is needed for the
> agent-proposed gate; only `ConfirmKind` widening (§4a) and the `FORM_STEP` map entry (§5d).

## 5 · Store changes (`workspaceStore.ts`)

### 5a · Level-1 stage state (new)

Add an explicit `stage: ExperimentStage` field to the store (init `'experiment_objective'`),
replacing the implicit `Boolean(taskId)`/`planConfirmed` heuristics as the stepper authority.
Source of truth precedence:

- **Hydrate**: `stage` from the foreground experiment's `snapshot.experiments[].stage` (§5e).
- **Live**: `onObjectiveConfirmed` sets `stage = 'workflow_design'`; `onPlanConfirmed` sets
  `stage = 'parameter_design'` (sibling BE advances the persisted stage; the live store mirror is
  set here so the stepper moves without refresh — Phase 5).

`planConfirmed` stays (it gates the workflow→parameter handoff and the confirm-frozen plan form),
but the **stepper status** reads `stage`, not `Boolean(taskId)`.

### 5b · Objective form state — re-typed + backend-backed

- Keep `ObjectiveDraft` (the FE form draft, string-typed numeric fields) but extend it to carry
  the Mind-derived, read-only fields the form now renders from the backend rather than computes:
  `renderedRxnUrl?: string | null`, `targetWeightMg?: number | null`, and per-reactant
  `smiles` / `structureUrl` / `role` / `isBaseline` (map `is_baseline` ↔ the form's reference row).
  The local `equivalents`/`amountMg`/`name` stay editable strings.
- `saveObjectiveDraft` / `confirmObjective` (`workspaceStore.ts:636-637`) change from
  `set(...)`-only to **async actions** that POST via the §3d client, then set the store from the
  echoed `ObjectivePayload` (authoritative `target_weight_mg`, `rendered_rxn_url`, `confirmed`).
  Signature becomes `Promise<void>` (the component awaits + maps errors).
- `confirmObjective` branches on `pendingForm?.formKind === 'objective'`:
  - pending objective decision → `submitFormConfirm(sessionId, {decision_id, confirm_kind:'objective',
    form_values:{experiment_id, name, objective}})`;
  - else → `confirmObjective` direct POST (§2d).
  In both cases the **stage advance is applied by the SSE `experiment_objective_confirmed` echo**
  (§5c), so the action does NOT optimistically flip `stage` (avoids live/replay drift). It MAY set
  a local `objective.confirmed = true` for immediate form chrome, reconciled by the echo.

### 5c · `onObjectiveConfirmed(evt)` (new store action)

```text
onObjectiveConfirmed(evt):
  stage = 'workflow_design'
  objective = mapWireObjective(evt.objective)  // confirmed payload of record
  objectiveConfirmed = true
  if autoSwitchEnabled: activeLifecycle='task', activeStep='workflow'
```

Mirrors `onPlanConfirmed`'s `autoSwitchEnabled`-respecting auto-advance.

### 5d · `FORM_STEP` map gains `objective` (`workspaceStore.ts:480`)

```ts
const FORM_STEP: Record<ConfirmKind, { lifecycle: LifecycleTab; step?: ConfigStep }> = {
  objective: { lifecycle: 'task', step: 'objective' },   // NEW — a pending objective form steers to the objective step
  plan: ...,
  params: ...,
  result_review: ...,
}
```

This keeps the exhaustive `Record<ConfirmKind, ...>` total after widening `ConfirmKind` (§4a).

### 5e · `hydrateFromSnapshot` reads the objective + stage (`workspaceStore.ts:648-772`)

Replace the deliberate skip (`:752-755` — `objective: s.objective`) with snapshot hydration:

```text
foregroundExperiment = pick active experiment (latest / by active plan's experiment_id)
stage = foregroundExperiment?.stage ?? 'experiment_objective'
objective = foregroundExperiment ? mapWireObjective(foregroundExperiment.objective) : null
            with taskName = foregroundExperiment.name
objectiveConfirmed = objective?.confirmed ?? false
```

`mapWireObjective(SnapshotObjective)` is a small adapter (new): wire `reactants[].is_baseline` →
form `isReference`, `amount_mg`/`equivalents` numbers → draft strings, carries `rendered_rxn_url`
+ `target_weight_mg` through read-only. Lives next to the store or in a `objective-mapping.ts`
helper (tested in isolation).

The `TrialPhase` cast at `:708` becomes a typed read once §3b lands.

## 6 · Stage-driven stepper (`TaskConfigPane.tsx`) — R1

Replace the local heuristics (`TaskConfigPane.tsx:61-122`) with `stage`-derived state.

### 6a · Read `stage` + `planConfirmed` from the store (replace `:60-62`)

```ts
const stage = useWorkspaceStore((s) => s.stage)              // NEW authority
const planConfirmed = useWorkspaceStore((s) => s.planConfirmed)
// DROP: const taskId = ...activeTrialId; objectiveLocked = Boolean(taskId);
//       workflowLocked = planConfirmed || Boolean(taskId)
```

### 6b · Derive per-step state from `stage` (replace `stepHasData` / `stepStatus` / `locked`)

| Step | `completed` | `active`/`pending` | `locked` |
| --- | --- | --- | --- |
| **objective** | `stage !== 'experiment_objective'` (objective confirmed → past it) | active when `activeStep==='objective'` | locked (read-only) once `stage !== 'experiment_objective'`; still selectable to review |
| **workflow** | `stage === 'parameter_design'` (plan confirmed → past it) | active/pending at `stage === 'workflow_design'` | locked before `stage` reaches `workflow_design`; read-only (`workflowLocked`) once `planConfirmed` |
| **parameter** | (no "complete" until result phase — leave `pending`/`active`) | unlocks **only** at `stage === 'parameter_design'` | locked + 'Waiting' badge while `stage !== 'parameter_design'` |

- Replace `objectiveLocked = Boolean(taskId)` → `objectiveLocked = stage !== 'experiment_objective'`.
- Replace `workflowLocked = planConfirmed || Boolean(taskId)` → `workflowLocked = planConfirmed`
  (the workflow form is read-only once the plan is frozen; pre-confirm it is editable).
- Parameter unlocks at `stage === 'parameter_design'` (was `!planConfirmed`); equivalent end-to-end
  once the sibling BE advances `stage` on plan confirm, but `stage` is the single authority.
- `handleSelect` guard (`:126`) becomes `if (id === 'parameter' && stage !== 'parameter_design') return`.
- `setupSummary` / `setupChip` (`:161-176`) re-expressed in terms of `stage` (+ `paramsConfirmed`
  for the parameter sub-state) rather than `objective || jobs || taskId`.

### 6c · Pass `readOnly` from `stage` to the step components

- `<ExperimentObjectiveStep readOnly={objectiveLocked} />` — now `stage !== 'experiment_objective'`.
- `<WorkflowDesignStep readOnly={workflowLocked} />` — now `planConfirmed`.

Behavioral equivalence note (Rule 5): the old `Boolean(taskId)` proxy locked the objective the
moment any trial existed; `stage`-driven locking is stricter and correct — the objective is locked
exactly when the experiment has advanced past `experiment_objective`. This is the intended R1
change, not a regression.

## 7 · Objective form rework (`ExperimentObjectiveStep.tsx`) — R3/R6

### 7a · Reaction render from `rendered_rxn_url` (replace the SMILES-text preview `:249-263`)

```tsx
{renderedRxnUrl ? (
  <img src={renderedRxnUrl} alt={`Reaction structure: ${watchedSmiles}`} className="..." />
) : watchedSmiles ? (
  <code>{watchedSmiles}</code>   // server hasn't rendered yet (draft typed, pre-parse) → SMILES fallback
) : (
  <span>Structure preview — enter a reaction SMILES above.</span>
)}
```

Copy action copies the reaction SMILES (`watchedSmiles`); "edit" degrades to editing the SMILES
text input (no molecule editor — documented gap, PRD R3).

### 7b · Reactant rows from Mind materials (replace the placeholder structure tile `:309-317`)

Render each reactant's `structure_url` as an `<img>` (fallback to the `FlaskConical` placeholder
when null). Rows are seeded from the hydrated/echoed `objective.reactants` (role, smiles, name,
amount_mg, equivalents, is_baseline) rather than empty defaults. `is_baseline` maps to the existing
`isReference` radio (the 1.00 eq basis). Copy-SMILES per row from `reactants[i].smiles`.

### 7c · Remove local target-weight math (`:127-136`, `:498-511`) — R3

Delete the `refAmount * yieldNum / 100` block and the `watchedReactants`/`watchedYield`-derived
`targetWeightMg`. Render `objective.targetWeightMg` from the backend, **3 decimals**
(`.toFixed(3)`), with an explicit loading/unavailable state when null
("Calculated on confirm" / "—"). Update the field label + help text (no longer "Reference amount ×
target yield").

### 7d · Submit handlers are async + map errors (`:158-173`)

- `onSaveDraft` → `await saveObjectiveDraft(values)` (lenient; surface a non-blocking toast on
  failure). Re-seed the form from the echoed payload (esp. `rendered_rxn_url` after parse).
- `onConfirm` → `await confirmObjective(values)`; on resolve, the SSE echo advances the stepper
  (do NOT also call `selectStep('workflow')` locally — the store's `onObjectiveConfirmed` owns the
  advance, matching the no-drift guarantee). On reject, map the error (§7e).

### 7e · 422 → field errors (R6)

`ApiError` from `jsonOrThrow` carries `status=422` + `errorCode="form_validation_failed"`. The BE
422 body is FastAPI's `{detail: [{loc, msg, type}, ...]}` (request-validation) or the domain
`{error_code}` envelope. Map:

- If `detail[]` carries field `loc` paths (e.g. `["body","target_purity_pct"]`), call
  `setError('targetPurityPct', { message })` on the matching RHF field.
- Else (form-level / unmapped) → a form-level alert (`role="alert"`) above the action bar.
- A loose adapter `mapObjective422(err): {field?: keyof ObjectiveDraft; message: string}[]` keeps
  the loc→RHF-name mapping in one place (tested).

Required-field copy stays `"<Field> is required."`; range copy includes the configured max
(existing zod messages already do this — keep them for the client-side gate; the BE 422 is the
authority on confirm).

## 8 · Robot/manual cards + parameter visibility (R5) — mostly already in place

Research finding: the portal **already** reads `plans.params.steps[].type` (not `jobs.type`) for
robot/manual ownership:

- `WorkflowDesignStep.tsx` renders `jobs[]` (each `{title, executor, type}` sourced from
  `plans.params.steps` via `hydrateFromSnapshot`'s `planStepsByPlanId`,
  `workspaceStore.ts:654-686`); the per-step toggle flips `type` pre-confirm (`toggleStepType`).
- `ParameterDesignPanel.tsx:104-114` filters the specialist row to `jobs[].type === 'robot'`
  stages, so manual steps already do not surface a dispatchable Parameter panel.

So R5's portal work is **confirmation + typing**, not a rewrite:

- Type `SnapshotTrial.phase` as `TrialPhase` (§3b) — consumed by `deriveRouting` / per-trial state.
- Once the sibling BE materializes **robot-only sparse** jobs and advances `stage`, verify the
  existing `materializedJobsByPlanId` sparse-seq join (`workspaceStore.ts:667-677`, indexed by
  `j.seq`) still aligns plan-cards ↔ jobs (it indexes by `seq`, so sparse seqs are already handled).
  Add a routing test covering a sparse-seq snapshot (manual step skipped → gap in `jobs[].seq`).
- No new robot/manual rendering code is expected; if a gap surfaces against the real sibling
  contract, scope it as a follow-up and flag (Rule 9).

## 9 · Live SSE stepper advance (R1) — Phase 5

- `experiment_objective_confirmed` → `onObjectiveConfirmed` → `stage='workflow_design'` + auto-advance
  to Workflow Design (§5c). Works for BOTH confirm paths (same event).
- `plan_confirmed` → `onPlanConfirmed` sets `stage='parameter_design'` (NEW line) in addition to the
  existing `planConfirmed=true` + auto-advance to Parameter Design (`workspaceStore.ts:818-829`).
  This depends on the sibling BE persisting the same stage advance so live + hydrate agree.
- No refresh required; snapshot hydration (§5e) restores the same `stage` so live + replay match
  (the no-drift guarantee, mirrors the 06-18 §7 contract).

## 10 · Affected Files

Portal (`BIC-agent-portal`):

- `src/lib/agent-client.ts` — `ExperimentStage` type; `SnapshotExperiment.stage/name`;
  `SnapshotTrial.phase: TrialPhase`; `SnapshotObjective` + objective request/response mirrors;
  `saveObjectiveDraft` / `confirmObjective` client methods.
- `src/types/events.ts` — `ConfirmKind` += `'objective'`; `ExperimentObjectiveConfirmedEvent` + union.
- `src/lib/sse-client.ts` — `KINDS` += `'experiment_objective_confirmed'`.
- `src/lib/event-dispatcher.ts` — `experiment_objective_confirmed` case → `onObjectiveConfirmed`.
- `src/stores/workspaceStore.ts` — `stage` state; `FORM_STEP.objective`; async
  `saveObjectiveDraft`/`confirmObjective`; `onObjectiveConfirmed`; `onPlanConfirmed` stage line;
  `hydrateFromSnapshot` objective+stage read; `mapWireObjective` helper (or `objective-mapping.ts`).
- `src/components/workspace/TaskConfigPane.tsx` — stage-driven step status/locked/select.
- `src/components/workspace/ExperimentObjectiveStep.tsx` — reaction `<img>`, materials rows,
  remove target-weight math, async submit, 422 mapping.
- `src/lib/objective-mapping.ts` (new, optional) + `mapObjective422` adapter.
- Tests: `src/lib/event-dispatcher.test.ts`, `src/lib/session-loader.test.ts`,
  `src/stores/workspaceStore.routing.test.ts` (+ new `workspaceStore.objective.test.ts`,
  `ExperimentObjectiveStep.test.tsx`, `objective-mapping.test.ts`); Playwright objective→workflow smoke.

No backend files change. If any portal mirror reveals a real contract gap, the BE spec is updated
in the sibling task (Rule 10) — flag, do not silently fork.

## 11 · Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| **Sibling BE not landed** → plan confirm doesn't advance `stage`, parameter step never unlocks live | Phase 5 is gated on the sibling; Phases 1–4 (objective vertical) ship independently. Stepper reads `stage`; until BE advances it, the live stepper simply won't move past workflow — no crash, just incomplete. Flag in `implement.md`. |
| `KINDS` not updated → SSE drops the objective-confirm named channel silently | The `_exhaustive` guard (`sse-client.ts:70`) fails the build if the union kind isn't in `KINDS` — a compile-time gate, not a runtime surprise. |
| Confirm-flow double-advance (optimistic flip + SSE echo) drifts live vs replay | The store action does NOT optimistically flip `stage`; only `onObjectiveConfirmed` (SSE) advances it. Same no-drift pattern as 06-18 §7. |
| `target_weight_mg` null on a draft that never ran goal-confirm | Render an explicit "Calculated on confirm" / "—" state; the value is authoritative only post-confirm. Never recompute locally. |
| 422 shape mismatch (FastAPI `detail[]` vs domain `error_code` envelope) | `mapObjective422` handles both; unmapped → form-level alert (Rule 9, fail loud, never swallow). |
| FORM_CONFIRM(objective) vs direct POST chosen wrongly | The store branches on `pendingForm.formKind === 'objective'` (a pending agent decision) — identical selector logic to the existing params path; tested both ways. |
| Sparse `jobs[].seq` (robot-only) breaks plan-card↔job join | The hydrate join already indexes `materializedJobsByPlanId` by `j.seq` — sparse-safe; add a routing test to lock it. |
| Re-typing `SnapshotExperiment.objective` from `Record<string,unknown>` breaks an existing consumer | grep consumers of `.objective` before re-typing; `ExperimentCreatedEvent.objective` stays `Record<string,unknown>` (event payload, not snapshot). |

## 12 · Rollout / Rollback

- Pure portal change; no migration, no new external service. The objective endpoints + event are
  already shipped BE-side.
- Rollback: revert the portal commits. The BE endpoints/event are harmless if unconsumed (the old
  FE-only objective path would return, but the snapshot already carries `stage` — the previous FE
  ignored it).
- Phase boundaries are independent commits (see `implement.md`), so a partial rollback (e.g. keep
  Phases 1–3, revert Phase 4 form rework) is clean.
- The Phase 5 `stage='parameter_design'` line is the only piece coupled to the sibling BE — if the
  sibling slips, hold Phase 5; Phases 1–4 still ship value (backend-backed objective + objective
  stage advance).
