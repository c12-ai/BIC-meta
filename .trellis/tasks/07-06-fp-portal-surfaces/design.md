# FP portal surfaces — child design

Authoritative product design: parent `../07-06-fp-agent-program/design.md` (§2 DTOs — FE mirrors; §6 data flow). BE contract is IMPLEMENTED and verified on BIC-agent-service `feat/fp_agent` (child A complete): params-form family snake_case on the wire, evidence family camelCase.

## Repo

`BIC-agent-portal` (work on the current checkout; NO commits by agents).

## Wire contract to mirror (from implemented BE)

- `FPParamsForm` (snake_case): `{ upstream: { rack_cols, rack: RackTube[], fractions: FractionRow[] }, from_user: { containers: FPContainer[] | null } }`; `FPContainer = { id, type: 'flask'|'waste', name (≤5 chars), volume: FlaskVolume|null, tubes: string[] }`. RackTube/FractionRow already exist on FE (CC result types) — REUSE, do not redeclare.
- `FpEvidence` (camelCase off-wire): `{ kind: 'fp', mapping: FpMappingRow[], collectedVolumeMl, discardedVolumeMl, solventSystem: string|null }`; `FpMappingRow = { containerName, containerType, tubes, tubeCount, classification: 'product'|'suspect'|'waste'|'mixed', volumeMl }`. REPLACES the old `{ mapping: PoolMappingRow[], summary }` shape everywhere (result-stage-model.ts:117, mappers, FpEvidenceBody, adapters, i18n summary lines).
- Confirm actions: `specialist_kind: 'fp'` with `confirm_kind: 'params' | 'result_review'` — same envelope as cc/re.

## Stage boundaries

- **B1 plumbing (mechanical)**: TS type mirrors; `ParameterDesignPanel.tsx` — `FormStage` += 'fp' (:89), `isFormStage` (:235), retire `isPlaceholderStage` branch (:242), `openPreparation` guard passes fp (:192); `material-preparation-adapter.ts` — `PreparationExecutor`/`PreparationTaskKey` += `fraction_preparation`, `TASK_KEY`/`TASK_LABEL`, `buildLabTaskParams` fp path (flasks + collect_config from confirmed form — mirror how re/cc build theirs); ReForm: remove the dead flasks/collect_config section (BE removed RELabLogistics); clean stale comment `workspaceStore.ts:500`. A temporary minimal FpForm (read-only upstream dump + confirm footer) keeps the tab functional until B2.
- **B2 FP form UI**: upper panel = upstream CC analysis (fraction rows table + read-only rack map, reuse CC result-card rendering pieces); lower panel = container list (default 烧瓶1+废液瓶, add-flask ≤5-char names, active-container selection) + interactive rack grid (rack_cols wide, click well toggles membership in active container, color by container/status, live selected list + count). Single-flask operating convention: UI allows multi-flask (no hard cap), per parent R1.
- **B3 result card + i18n + tests**: migrate `FpEvidenceBody`/`mapFpEvidence`/`result-stage-adapters` to the new evidence shape (volume totals + solvent system + classification column); update zh/en i18n keys (fp summary lines, form labels); unit tests for form state logic + evidence mapping; verify duo-panel (confirm works without agent turn).

## Gate

Portal repo chain (discover exact scripts in package.json): typecheck + lint + unit tests green; `pnpm build` if that's the repo's standard gate. Playwright E2E belongs to child D, NOT here.

## Non-goals

Lab Logistics panel beyond material-prep auto-pick (parent decision: FP has no separate logistics surface); multi-flask live dispatch; PRD updates (child D).
