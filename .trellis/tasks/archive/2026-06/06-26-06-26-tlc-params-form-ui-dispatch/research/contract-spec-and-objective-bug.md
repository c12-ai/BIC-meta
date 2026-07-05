# Research: contract spec (Q6 detail), objective-block bug (Q7), and the Implementation shape

- **Query**: Which spec governs the contract; is the ExperimentObjectiveStep auto-block real and in-scope; minimal FE edit set.
- **Scope**: mixed
- **Date**: 2026-06-26

## Q6 (detail) — Related spec + shared-types

- **FE wire contract spec:** `BIC-agent-portal/.trellis/spec/ui/L3/form.md` — generic params-confirm HITL flow (stage-agnostic). AC-FORM-8 (duo-panel CTA enables on `activeTrialId`) and AC-FORM-9 (`readOnly = !isLiveTrial(t) || t.paramsConfirmed || t.dispatchedAt != null`; footer renders only when live & unconfirmed & undispatched) are the load-bearing acceptance criteria the TLC form must honor — they are ALREADY satisfied by the shared `PhaseFooter` / `footerShown` logic once TLC is admitted to `hasExecutorForm`.
- **FE workspace spec:** `BIC-agent-portal/.trellis/spec/ui/L3/workspace.md` (stage row, dirty registry).
- **BE contract authorities:** `BIC-agent-service/.trellis/spec/backend/L3/specialist_tools.md`, `.../backend/contracts.md` (§3c user-initiated mint), `.../backend/L3/graphs.md` §2 (TLC S2 mirror).
- **Shared types:** `bic_shared_types/common/tlc.py:TLCParam` (solvents + solvent_ratio); `bic_shared_types/model_service/http/tlc.py:TLCMixcaseRequest` (rxn + target_window, the `0<=lo<hi<=1` validator).
- **BE form types (already exist):** `app/events/form_payloads.py` — `TLCParamsForm`, `TLCFromUserFields`, `TLCLabLogistics`, `TLCParamsConfirmAction`, all registered in `OriginalAction` (`:1000`) and `TYPED_ORIGINAL_ACTIONS` (`:1019`).

**Rule-10 verdict:** Adding the FE TLC form fills an existing, fully-specified-and-emitted contract branch. The FE↔BE params-confirm contract does NOT change — same `FormRequestedEvent(confirm_kind="params")`, same `POST /sessions/{id}/forms/confirm`, BE already routes `tlc` → `tlc_params_form_problems_from_values` (`service.py:340`) and `_submit_l4` already has a TLC arm (`tools.py:543`). No spec edit is mandated. (At most, an optional FE-internal note in `ui/L3/form.md` that TLC params skips the lab-logistics/MaterialPreparation step — a UX detail, not a wire change.)

## Q7 — The ExperimentObjectiveStep "auto-block" bug

The prompt said `ExperimentObjectiveStep.tsx ~:61-70` zod required-gate blocks submit when the agent emits `name:""` / reactant name `null`. Findings:

### The zod schema IS strict (real)

`BIC-agent-portal/src/components/workspace/ExperimentObjectiveStep.tsx:54-72`
```ts
const reactantSchema = z.object({
  name: z.string().trim().min(1, 'Compound name is required.'),
  amountMg: requiredNumeric('Amount'),
  equivalents: requiredNumeric('Equivalents'),
  isReference: z.boolean(),
})
const objectiveSchema = z.object({
  taskName: z.string().trim().min(1, 'Task name is required.'),
  smiles: z.string(),
  reactants: z.array(reactantSchema).min(1, 'Add at least one reactant.')
    .refine((rows) => rows.filter((r) => r.isReference).length === 1, {
      message: 'Exactly one reactant must be the reference compound.' }),
  targetPurityPct: requiredNumeric('Target purity', { max: 100 }),
  targetYieldPct: requiredNumeric('Target yield', { max: 100 }),
})
```
So an agent-drafted objective with an empty `name` or a null reactant name WILL fail this schema. `requiredNumeric` (`:43-52`) also rejects empty / non-positive numbers.

### But the Confirm button is NOT disabled on validity

`ExperimentObjectiveStep.tsx:751-754`
```tsx
        <Button type="submit" disabled={readOnly}>
          Confirm Objective
          <ArrowRight data-icon="inline-end" />
        </Button>
```
The button is `disabled={readOnly}` only — NOT `disabled={!isValid}`. The form's `onSubmit={onConfirm}` (`:294`), and `onConfirm = handleSubmit(async (values) => {...})` (`:270-285`). So clicking Confirm RUNS zod; on failure `handleSubmit` short-circuits and renders inline field errors (`mode: 'onTouched'`, `:175`) — it does NOT silently block a disabled button. The chemist sees the validation errors and can fix them.

### Characterization (nuance vs the prompt)

- The gate is a **client-side validation gate that surfaces errors**, not a silently-disabled-button dead-end. If the agent drafts an objective with `name:""` / `name:null`, the chemist CANNOT confirm until they fill those fields — that is the real friction, and it can block reaching the TLC stage from the UI (objective must confirm → stage advances to workflow_design → plan → parameter_design where TLC lives).
- The wire→form mapping is `mapWireObjective` (referenced at `:446` comment); the store re-seeds via `onObjectiveDrafted`. Whether the agent actually emits `name:null` needs a live-bench trace to confirm the trigger — this research only confirms the GATE exists and is strict.

### In-scope?

**Separate concern, but a real blocker for UI-driven E2E to the TLC stage.** It is NOT part of the TLC params form wire-up. Recommend tracking it as its own task: either (a) loosen the agent draft to never emit null/empty names, or (b) let Save-Draft round-trip partial objectives (it already is lenient — `onSaveDraft` uses `getValues()` with no zod, `:255-268`) and only block Confirm. Do not fix it inside the TLC params task. Located + characterized per the brief; not fixed.

## Implementation shape — minimal FE edits to make TLC mirror CC

The BE is complete. The FE work is to admit TLC to the real-form branch and give it a small bespoke form + a dispatch path that skips MaterialPreparation.

### 1. Types + coercer (new)
- `src/types/specialist-forms.ts` — add a `TLCParamsForm` TS interface mirroring `form_payloads.py:TLCParamsForm` (`from_user:{rxn, target_window, tlc_file_key, tlc_result, product_rf}`, `recommended: TLCParam|null = {solvents, solvent_ratio}`, `lab_logistics: {}`). (Today only CC/RE shapes exist.)
- `src/lib/params-coerce.ts` — add `coerceTlcParamsForm(values: unknown): TLCParamsForm`, mirroring `coerceCcParamsForm`/`coerceReParamsForm`.

### 2. New form component (new)
- `src/components/workspace/forms/TlcParamsForm.tsx` — `forwardRef<DynamicFormHandle, {initial; disabled?}>`, built on `useParamsFormHandle({id:'workspace.params.tlc', ...})`. Fields:
  - `from_user.rxn` — text input.
  - `from_user.target_window` — two number inputs (lo, hi) in [0,1].
  - `recommended.solvents` + `recommended.solvent_ratio` — reuse the Solvent-chip + ratio helpers from `CcParamsForm.tsx`.
  - presence gate (`isValid`): rxn non-empty, target_window both present, recommended solvents+ratio present. (Cross-field `lo<hi` stays BE-only.)
  - `toValues` emits `{from_user:{rxn, target_window:[lo,hi], ...}, recommended:{solvents, solvent_ratio}|null, lab_logistics:{}}`.

### 3. Panel wiring (`ParameterDesignPanel.tsx`)
- `:218` `isPlaceholderStage` — drop `'tlc'` (keep `'fp'`): `activeStage === 'fp'`.
- `:79` `Executor` + `:212-214` `hasExecutorForm` + `:208-211` `stageHasConfirmedRobotJob` — admit `'tlc'` (widen `Executor` to `'cc'|'re'|'tlc'` or branch separately). This flips the body to the real-form branch and renders the footer for TLC.
- `ParamsEditableBody` (`:596-629`) — add a `tlc` branch that mounts `TlcParamsForm` (no `CcEditableBody`-style TLC upload / SpotIdTable / RecommendationBasis — TLC has none).
- Dispatch path: TLC must NOT call `openPreparation` (it returns early at `:177` and there's no TLC MaterialPreparation executor). The TLC Confirm should call `confirm('params', values)` directly (the `submitPreparedDispatch` body without the dialog). Cleanest: in `onConfirm` (`:303`), branch — `tlc` → `confirm('params', values)`; `cc`/`re` → `openPreparation(...)`. Same for the "Lab Logistics" button (hide it for TLC, since there's no logistics).
- `coerceTlcParamsForm` wired in `ParamsEditableBody` alongside `coerceCcParamsForm`/`coerceReParamsForm` (`:609-610`).

### 4. `FORM_IDS` (`ParameterDesignPanel.tsx:81`)
- Add `'workspace.params.tlc'` so the `PhaseFooter` dirty/valid lookup (`:764`) picks up the TLC form's registry entry.

### 5. specialist-stages (`specialist-stages.ts`)
- TLC is already in `SPECIALIST_STAGES` (`:20-21`) and `STAGE_LABEL`. No change needed for the stage to appear; the visibility filter (`ParameterDesignPanel.tsx:104-115`) already surfaces robot TLC steps.

### Decisions needed (TLC genuinely differs from CC) — flag for the implementer
1. **Dispatch path:** confirm the decision to BYPASS `MaterialPreparationPanel` for TLC (TLC `lab_logistics` is empty per `form_payloads.py:294-304`). This research strongly supports bypass — extending `PreparationExecutor`/`buildLabTaskParams` to a no-op TLC arm would be dead scaffolding (Rule 2). **Recommended: TLC Confirm → `confirm('params', values)` directly, no prep dialog, no "Lab Logistics" button.** Needs Drake/owner sign-off only if there's a desired prep UX for TLC.
2. **`target_window` input UX:** two numbers vs a range slider — the BE only needs `[lo, hi]` floats in [0,1] with `lo<hi`. Pick the simplest (two number inputs). The `lo<hi` rule is BE-validated; the FE presence-gate should only require both present (mirror the CC pattern of leaving cross-field rules to a 422).
3. **`rxn` source:** the objective stage already captured a reaction SMILES. Is TLC's `rxn` auto-seeded from the experiment objective, or re-entered? The BE `update_tlc_params` extracts it from chat; the FE form should render whatever `task_params_set` populated (the agent may pre-fill `from_user.rxn`). No new plumbing needed if it just renders the coerced `from_user.rxn` — but confirm whether a chemist is expected to type it or it's pre-filled. (Ambiguous — surface to owner.)
