# Research: CC params-confirm + lab-dispatch flow in the FRONTEND (the pattern TLC must mirror)

- **Query**: How does the CC (column_chromatography) params-confirm + lab-dispatch flow work in the FE, so we can mirror it for TLC?
- **Scope**: mixed (FE-primary, BE traced for the contract)
- **Date**: 2026-06-26

## Q1 — CC params form rendering

### Which component renders the CC form, and how the panel routes to it

`ParameterDesignPanel.tsx` is the stage router. The body is chosen by three branches:

`BIC-agent-portal/src/components/workspace/ParameterDesignPanel.tsx:247-292`
```tsx
  let body: React.ReactNode
  if (isPlaceholderStage) {                         // tlc | fp  -> dead-end
    body = <PlaceholderParamForm stage={activeStage} />
  } else if (hasExecutorForm) {                     // cc | re   -> real form
    const executor: Executor = activeStage          // Executor = 'cc' | 're'
    ...
    body = (
      <StageFormCard stage={executor}>
        ...
        <ParamsEditableBody
          executor={executor}
          params={shownTrial?.params}
          taskId={shownTrial?.trialId}
          formRef={formRef}
          readOnly={readOnly}
          ccConsumesRobotTlc={ccConsumesRobotTlc}
        />
      </StageFormCard>
    )
  } else {
    body = <NoBackendDataStageBody stage={activeStage} />
  }
```

`ParamsEditableBody` (`:596-629`) splits on executor: `cc` → `CcEditableBody` → `CcParamsForm`; `re` → `ReParamsForm`. Both are wired to a shared `formRef: DynamicFormHandle`.

The CC form itself is `forms/CcParamsForm.tsx` (`CcParamsForm`, `:253-454`). Its field set is the AUTHORITY-cited mirror of the BE `CCParamsForm`:

`BIC-agent-portal/src/components/workspace/forms/CcParamsForm.tsx:1-9` (header comment)
```
// CC unified params form. Authority for the field set:
//   form_payloads.py:CCParamsConfirmAction.params = CCParamsForm
//   = { from_user: CCFromUserFields, recommended: CCParam | None,
//       lab_logistics: CCLabLogistics }
```

Visible fields (`CcParamsForm.tsx`):
- `from_user` block ("Fields Auto-filled From Above, Editable", `:318-377`): Product Rf (`cc-product-rf`), Eluent System (`cc-eluent-system`, the `solvents` chips), Eluent Ratio (`cc-eluent-ratio`, `solvent_ratio`), Sample Amount (`cc-sample-quantity`, `sample_quantity`).
- `recommended` block ("Execution Parameters", `:384-451`): Column Specification (`cc-column-type`, read-only derived), Silica Gel Amount (read-only derived), Eluent System (`cc-recommended-eluent-system`, `solvent_system`), Sample Cartridge Location (`cc-sample-cartridge-location`, this is `lab_logistics.sample_cartridge_location`), plus a Gradient Settings table (`solvent_gradient`).

The local flat `Draft` ↔ wire shape mapping is `toDraft` (`:70-85`) and `toValues` (`:87-117`). `toValues` re-nests the flat draft back into `{from_user, recommended, lab_logistics}`.

### Where the payload comes from (store + event-dispatcher path)

The BE writes the draft via `TaskParamsSetEvent` (full `{from_user, recommended, lab_logistics}` dict). The dispatcher is the only fan-out:

`BIC-agent-portal/src/lib/event-dispatcher.ts:168-174`
```ts
    case 'task_params_set':
      // Full unified form dict ({from_user, recommended, lab_logistics}) —
      // the store REPLACES `params`. Fires from every draft-mutating agent
      // tool, so chat-driven edits reach the live form before any
      // form_requested.
      workspace.onTaskParamsSet(evt)
      break
```

The form mount reads `shownTrial.params` (per-trial, see `selectTrialForStage`), coerces it with `coerceCcParamsForm` (`ParameterDesignPanel.tsx:609`, defined in `lib/params-coerce.ts:89-127`), and feeds it as `initial` into the form. `useParamsFormHandle` (`forms/useParamsFormHandle.ts`) re-syncs the draft on every new `initial` (`:47` `useEffect(() => reset(), [reset])`), so an agent proposal always overwrites the local draft.

The separate `form_requested` event only mints the `pendingForm` (decision_id) — it does NOT carry the field values; values flow via `task_params_set`:

`event-dispatcher.ts:130-138`
```ts
    case 'form_requested':
      workspace.onFormRequested({
        decisionId: evt.decision_id,
        formKind: evt.confirm_kind,
        originalAction: evt.original_action,
      })
```

The BE `original_action` for CC params is `CCParamsConfirmAction` (`form_payloads.py:634-649`): `{confirm_kind:"params", task_id, specialist_kind:"cc", params: CCParamsForm}`.

## Q2 — CC confirm footer + button, traced to the network call

### The footer + button

The footer is `PhaseFooter` (`ParameterDesignPanel.tsx:756-841`), rendered only when `footerShown` (`:215-216`, see Q3). The Confirm button:

`ParameterDesignPanel.tsx:828-837`
```tsx
        <Button
          onClick={() => onConfirm(formRef.current?.getValues() ?? {})}
          disabled={ctaDisabled}
          ...
          data-testid="params-confirm"
        >
          Confirm
          <ArrowRight data-icon="inline-end" />
        </Button>
```
Testids in the footer: `params-actions` (footer), `params-confirm` (Confirm), `params-setup-logistics` (Lab Logistics), `params-reset` (Reset), `params-footer-status`, `params-dirty-chip`.

`ctaDisabled = !ready || !isValid` (`:777`). `ready = Boolean(pendingDecisionId) || taskReady` (`:776`); `taskReady = isShownLive` (passed at `:305`). `isValid` is the form's presence gate read from the dirty registry (`:772`).

### Handler chain (CC routes through a material-prep dialog FIRST, then dispatch)

`onConfirm` → `openPreparation(values, {showMissingManualNotice:true})` (`:303`).

`openPreparation` (`:173-184`) is **gated to cc/re** and opens the `MaterialPreparationDialog`:
```tsx
  const openPreparation = (values, options = {}) => {
    if (activeStage !== 'cc' && activeStage !== 're') return   // <-- TLC blocked here
    setPreparationRequest({ executor: activeStage, taskId: shownTrial?.trialId, values, ... })
  }
```

The dialog hosts `MaterialPreparationPanel` (lab-logistics gate: pick sample cartridge slot for CC / flasks for RE). On its "Confirm Dispatch" button (`MaterialPreparationPanel.tsx:334-343`, testid `confirm-dispatch`) it calls `onDispatch(draftValues)` → `submitPreparedDispatch` (`ParameterDesignPanel.tsx:186-189`):
```tsx
  const submitPreparedDispatch = async (values) => {
    const submitted = await confirm('params', values)
    if (submitted) setPreparationRequest(null)
  }
```

`confirm` comes from `useSubmitForm(pendingDecisionId)` (`:170`).

### The network call (`use-submit-form.ts` → `agent-client.ts`)

`lib/use-submit-form.ts:40-104` — `confirm(confirmKind, formValues)` POSTs via `submitFormConfirm`:
```ts
        const { event_id } = await submitFormConfirm(sessionId, {
          decision_id: decisionId,
          task_id: decisionId ? undefined : taskId,   // duo-panel: BE mints from task_id
          confirm_kind: confirmKind,
          form_values: formValues,
        })
```

`lib/agent-client.ts:112-131` — endpoint + body:
```ts
export async function submitFormConfirm(sessionId, payload: {
    decision_id?: string
    task_id?: string
    confirm_kind: ConfirmKind
    form_values: Record<string, unknown>
  }): Promise<SubmitFormConfirmResponse> {
  const res = await fetch(`${env.API_BASE_URL}/sessions/${sessionId}/forms/confirm`, {
    method: 'POST', headers: headers(), body: JSON.stringify(payload),
  })
  ...
}
```

**Exact endpoint:** `POST /sessions/{sessionId}/forms/confirm`
**Body:** `{ decision_id?: string, task_id?: string, confirm_kind: "params", form_values: <the full {from_user, recommended, lab_logistics} dict from toValues> }`
(one of `decision_id` / `task_id` is sent: `decision_id` when the agent fired `form_requested`, else `task_id` for the duo-panel user-initiated path.)

A 422 `form_validation_failed` is caught (`use-submit-form.ts:90-98`) and surfaced as `paramsValidationErrors` (the in-panel `params-validation-alert`, `ParameterDesignPanel.tsx:268`).

### What that triggers on the BE (confirmed it reaches dispatch)

`BIC-agent-service/app/api/routers/sessions.py:149-160` — `POST /{session_id}/forms/confirm` → `service.submit_form_confirm`.

`app/session/service.py:306-350` — `_validate_params_form_values` resolves the specialist kind from the trial→job→executor and picks the matching `*_params_form_problems_from_values`. **TLC is already wired** (`service.py:337-341`):
```python
        problems_fn_by_kind = {
            "cc": cc_params_form_problems_from_values,
            "re": re_params_form_problems_from_values,
            "tlc": tlc_params_form_problems_from_values,   # <-- TLC supported
        }
```

The confirm enqueues a `FormConfirmPayload(confirm_kind=PARAMS)` next-turn input. The TLC subgraph treats a params-confirm re-entry as the explicit dispatch (`specialists/tlc.py:313-334` `_is_params_confirm_dispatch` / `_pre_react_route` → `auto_submit`), which runs the SAME `_submit_l4` body CC/RE use (`specialists/tools.py:543-559`, TLC arm builds `CreateTLCTaskRequest` and POSTs `lab.submit_task`). **So the BE confirm→dispatch leg for TLC is complete; the FE is the only gap.**

## Q3 — Every `activeStage` / `isPlaceholderStage` gate in ParameterDesignPanel.tsx

All in `ParameterDesignPanel.tsx`. `Executor = 'cc' | 're'` (`:79`).

| Line | Condition | Controls |
|---|---|---|
| `:177` | `if (activeStage !== 'cc' && activeStage !== 're') return` (inside `openPreparation`) | Hard-blocks the prepare/dispatch dialog for tlc/fp. **TLC must either be added here, or bypass this and call `confirm('params', values)` directly (TLC has no lab-logistics).** |
| `:208-211` | `stageHasConfirmedRobotJob = planConfirmed && visibleStages.includes(activeStage) && (activeStage === 'cc' \|\| activeStage === 're')` | Lets a confirmed robot CC/RE stage own the real form surface before `task_params_set`. TLC absent. |
| `:212-214` | `hasExecutorForm = (shownTrial != null \|\| stageHasConfirmedRobotJob) && (activeStage === 'cc' \|\| activeStage === 're')` | The master gate that selects the real-form body branch (`:253`). **This is the central gate to extend for TLC.** |
| `:215-216` | `footerShown = hasExecutorForm && (shownTrial == null \|\| isShownLive) && !paramsConfirmed && !dispatched` | Whether the Confirm footer renders. Inherits the cc/re gate via `hasExecutorForm`. |
| `:218` | `isPlaceholderStage = activeStage === 'tlc' \|\| activeStage === 'fp'` | Routes tlc/fp to `PlaceholderParamForm` (`:248-252`). **Remove `'tlc'` from here when TLC gets a real form.** |
| `:463-464` | `isExecutorStage = stage === 'cc' \|\| stage === 're'` (in `NoBackendDataStageBody`) | Only the empty-state copy; cosmetic. |
| `:524-526` | `stage === 'tlc' ? ... : ...` (in `PlaceholderParamForm`) | The placeholder copy strings. |
| `:536-540` | `stage === 'tlc' ? 'TLC Monitoring Form' : ...` (in `StageFormCard`) | Card title (already TLC-aware). |
| `:571-583` | `stageDescription` switch incl. a `'tlc'` case | Card subtitle (already TLC-aware). |

Sibling gates outside this file:
- `lib/material-preparation-adapter.ts:4` `export type PreparationExecutor = 'cc' | 're'` and `buildLabTaskParams`/`taskKeyForExecutor` switch on `cc`/`re` only — TLC is NOT a material-prep executor (it has no lab-logistics). This is why the TLC Confirm should bypass `MaterialPreparationPanel`.

## Q6 — FE↔BE contract spec (Rule 10)

The governing FE spec is `BIC-agent-portal/.trellis/spec/ui/L3/form.md` (the form-confirm HITL flow + AC-FORM-8 duo-panel + AC-FORM-9 lock-on-confirmed/dispatched). It is **stage-agnostic** — it describes the `params` confirm contract generically (`FormRequestedEvent(form_kind='param')` → render from payload → POST `FORM_CONFIRM`), with no per-specialist field list. Adding a TLC params form **does NOT change this contract** — TLC params-confirm uses the identical `FormRequestedEvent(confirm_kind="params")` / `POST /forms/confirm` machinery. The new form just fills the already-defined `params` branch for `specialist_kind="tlc"`.

The BE-side contract authorities are:
- `BIC-agent-service/.trellis/spec/backend/L3/specialist_tools.md` (CC tool table; TLC mirrors).
- `BIC-agent-service/.trellis/spec/backend/contracts.md` §3c (user-initiated decision minting).
- `BIC-agent-service/app/events/form_payloads.py` — the `TLCParamsConfirmAction` / `TLCParamsForm` / `TLCFromUserFields` types ALREADY EXIST and are registered in the `OriginalAction` union (`form_payloads.py:1000`, `:662-670`). So the wire contract for TLC params is already defined and emitted by the BE — there is nothing to add to the contract, only an FE consumer to write.

**Conclusion (Rule 10):** adding the FE TLC form fills an existing-but-unimplemented branch of an already-specified contract. No spec change is required to the FE↔BE params contract. If the implementer adds anything new to `ui/L3/form.md`, it would be at most a note that TLC params has no lab-logistics step (so it skips `MaterialPreparationPanel`), which is an FE-internal UX detail, not a wire-contract change.
