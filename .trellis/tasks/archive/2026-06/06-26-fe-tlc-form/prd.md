# portal: TLC params form + 2–4 sample-tube selector → UI-to-lab dispatch

> Child 4 (final) of parent `06-26-06-26-tlc-params-form-ui-dispatch`.
> **Depends on child 3** (agent-BE) — the TLC form's `lab_logistics.sample_tubes`
> field is the wire contract this form fills. Also consumes child 2's box-grid
> read API. See parent `design.md` §2d and
> `research/cc-params-dispatch-pattern.md` (the CC path to mirror) +
> `research/contract-spec-and-objective-bug.md` (the FE edit list).

## Goal

Replace the TLC stage's static `PlaceholderParamForm` with a real params form so a
chemist can, from the portal UI: see the recommended TLC params, **select the 2–4
sample tubes they physically placed**, and Confirm — dispatching the TLC task
through agent-BE → lab. This closes the FE gap that blocked TLC E2E (lab tasks
created from UI today: 0).

## Requirements

Mirror the CC params-confirm→dispatch path (`research/cc-params-dispatch-pattern.md`):

- **Un-placeholder TLC** — `ParameterDesignPanel.tsx`:
  - `:218` drop `'tlc'` from `isPlaceholderStage` (keep `'fp'`).
  - admit `'tlc'` to `Executor` (`:79`), `hasExecutorForm` (`:212-214`),
    `stageHasConfirmedRobotJob` (`:208-211`) so the real-form branch + footer render.
  - `FORM_IDS` (`:81`) — add `'workspace.params.tlc'`.
  - `ParamsEditableBody` (`:596-629`) — add a `tlc` branch mounting the new form.
- **New form** `src/components/workspace/forms/TlcParamsForm.tsx`
  (`forwardRef<DynamicFormHandle>` via `useParamsFormHandle({id:'workspace.params.tlc'})`):
  - `from_user.rxn` — text input, **rendered from BE pre-fill** (editable).
  - `from_user.target_window` — **two number inputs** (lo, hi) in [0,1]; presence
    gate requires both present; `lo<hi` is BE-validated (no FE cross-field rule).
  - `recommended.solvents` + `recommended.solvent_ratio` — reuse CC's Solvent-chip
    + ratio helpers.
  - **Sample-tube selector** — the new piece: fetch `GET /api/preparations/sample-tube-boxes`
    (TanStack Query), render each box slot's grid (`SampleTubeBoxesResponse`:
    `boxes[].{box_id, present, slot_index, label, rows, cols, cells[]}`,
    cell `{row, col, tube_id, state, filled}`). Chemist picks **2–4 filled cells**;
    each pick → `ObjectLocation {tube_id, box_id, cell:{row, col}}` written to
    `lab_logistics.sample_tubes`. Presence gate: 2–4 tubes selected.
- **Coercer** `src/lib/params-coerce.ts` — `coerceTlcParamsForm` mirroring
  `coerceCcParamsForm`/`coerceReParamsForm`; nests back to
  `{from_user, recommended, lab_logistics:{sample_tubes}}`.
- **Dispatch path** — TLC has no MaterialPreparation dialog; `onConfirm` branches:
  `tlc` → `confirm('params', values)` directly (the tube selector lives IN the
  form); `cc`/`re` → `openPreparation(...)` as today. Hide the "Lab Logistics"
  button for TLC.
- **Types** — add a `TLCParamsForm` TS interface + `ObjectLocation`/tube-cell
  shape under `src/types/` mirroring the BE `form_payloads.py` `TLCLabLogistics.sample_tubes`.
- **Spec (Rule 10)** — `.trellis/spec/ui/L3/form.md`: note TLC params has a
  tube-selector + skips MaterialPreparation (FE-internal UX, the wire contract is
  unchanged from the generic params-confirm flow).

## Constraints

- Portal conventions (CLAUDE.md): no BFF; SSE→event-dispatcher→stores; type-only
  imports; `pnpm check` before done; `VITE_HIDE_DEVTOOLS=1` for Playwright.
- The form-field NAMES must match child 3's BE payload (`lab_logistics.sample_tubes`,
  each `{tube_id, box_id, cell:{row, col}}`).

## Acceptance Criteria

- [ ] TLC stage renders `TlcParamsForm` (not the placeholder); footer + Confirm present.
- [ ] rxn pre-fills from BE draft; target_window = two number inputs; solvents/ratio editable.
- [ ] Tube selector loads boxes from `/preparations/sample-tube-boxes`, lets the
      chemist pick 2–4 filled tubes, and blocks Confirm outside [2,4].
- [ ] Confirm POSTs `/sessions/{id}/forms/confirm` with `form_values.lab_logistics.sample_tubes`
      carrying the 2–4 `ObjectLocation`s (verified via network assertion).
- [ ] `pnpm check` + `pnpm typecheck` green; a Playwright spec drives chat →
      Confirm Plan → TLC form → select tubes → Confirm and asserts the confirm POST shape.
- [ ] `ui/L3/form.md` updated.

## Out of scope

- shared-types / lab / agent-BE (children 1–3, done).
- The objective-form zod gate friction (separate task) — only relevant if it
  blocks *reaching* the TLC stage during the E2E test; note but don't fix.
- ChemEngine recognition (separate sub-leg).
