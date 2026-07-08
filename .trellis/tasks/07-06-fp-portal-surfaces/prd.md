# FP parameter design and result surfaces in portal

Parent: `07-06-fp-agent-program` (requirements R1–R4 and DTOs in parent prd.md / design.md — this child consumes the contract owned by `07-06-fp-agent-specialist`).

## Goal

Give FP a real Parameter Design tab (upper: upstream CC analysis; lower: container config with a tube-rack grid), enable FP in material preparation, and migrate the FP result card to the new evidence shape. Remove ReForm's dead flask fields.

## Requirements

- Tab enablement (chokepoints verified 2026-07-06): `ParameterDesignPanel.tsx` — `FormStage` += `'fp'` (:89), `isFormStage` (:235), retire the `isPlaceholderStage` branch (:242), `openPreparation` guard passes fp (:192).
- FP form layout (parent R3): upper panel read-only upstream CC analysis (`FPUpstreamContext`); lower panel container list (default 烧瓶1 + 废液瓶, add-flask, name ≤5 chars) + tube-rack grid (96-well/custom from `rack_cols`/`rack_rows`), click a well to toggle membership in the selected container, live selected-tube list + total count.
- Single-flask operating convention (parent R1): multi-flask UI is allowed by the model; no hard cap coded. Drake configures one flask manually until the lab-service GitHub issue answers.
- Material prep: `material-preparation-adapter.ts` `PreparationExecutor`/`TASK_KEY` += `fraction_preparation`; `buildLabTaskParams` fp path; `MaterialPreparationPanel` unchanged (RE-style pure auto-pick — fraction waste drums 2/2).
- Result card (parent R4): migrate `FpEvidenceBody`, `mapFpEvidence`, and adapters to the new `FpEvidence` shape (mapping rows with classification, volume math, totals, solvent system); clean the stale comment at `workspaceStore.ts:500`.
- ReForm cleanup (parent R5): remove the flasks/collect_config section mirrored from `RELabLogistics`.
- TS mirrors of the FP DTOs in `specialist-forms.ts` / `result-stage-model.ts` per parent design.md §2.

## Acceptance Criteria

- [ ] FP tab renders upper/lower panels; grid click-toggle works; count and list update live; container names capped at 5 chars.
- [ ] The selection/maintenance right-panel consistency rule (Production-PRD, UI Interaction Requirements) holds for FP surfaces.
- [ ] FP can open the material-prep dialog; auto-pick drums show n/2 and gate confirm at zero stock.
- [ ] FP result card renders mapping + volumes + solvent system from a live `FpEvidence`; no `PoolMappingRow`/`FpSummaryRow` references remain.
- [ ] ReForm shows no flask/collect fields; typecheck/lint/unit green.

## Notes

- Author design.md (+ implement.md if needed) at activation; portal frontend spec index: `.trellis/spec/BIC-agent-portal/frontend/index.md`.
