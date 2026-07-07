# FP Agent — Program Execution Plan

Parent-level checklist. Each child authors its own design.md/implement.md at activation (before its `task.py start`); this file orders the program and holds the cross-child gates.

## Phase 0 — external dependency (done at planning)

- [x] GitHub issue on BIC-lab-service: multi-flask robot capability, max flask count, `collect_config` indexing semantics — https://github.com/c12-ai/BIC-lab-service/issues/81 (raised 2026-07-06 at planning time).

## Phase 1 — `07-06-fp-agent-specialist` (BE, contract owner)

Order of work inside the child:
1. Contract first: add FP DTOs to `form_payloads.py` (per program design.md §2), replace old FpEvidence shape, update MED005 fixture.
2. `fp.py` subgraph (template `re.py`), phases collecting_params → rts → conducting → done; deterministic pre-fill from CC evidence; no MindClient.
3. Routing: `specialist.py` (Kind/executor_to_kind/classify_step_dispatch), `_KIND_TO_SUBGRAPH`, `factory.py`, `__init__.py`; delete stub branch in `specialist_dispatcher.py`.
4. Dispatch: `_submit_l4` fp branch + containers→request mapping (pure fn + unit tests); resolve collect_config indexing (blocking: needs the GitHub-issue answer or a live probe against lab service before first real dispatch).
5. Evidence synthesis on terminal completed + result_review emission.
6. RE dead-field removal (RELabLogistics, update_re_lab_logistics).
7. Spec updates: `.trellis/spec/backend/L3/` (specialist tools/graphs), contracts doc (Rule 10).

Gate: unit + scenario green; manual bench run — robot FP dispatch with 1 flask completes against live lab service + robot mock.

## Phase 2 — `07-06-fp-portal-surfaces` (FE)

1. `FormStage`/`isFormStage`/placeholder retirement/`openPreparation` guard (`ParameterDesignPanel.tsx:89/:235/:242/:192`).
2. FP form: upper panel (upstream CC analysis) + lower panel (container list + rack grid 96-well/custom, click-toggle, live count).
3. `material-preparation-adapter.ts`: PreparationExecutor/TASK_KEY += fraction_preparation; `buildLabTaskParams` fp path. (MaterialPreparationPanel itself: zero structural change, RE-style auto-pick.)
4. FP result card: migrate `FpEvidenceBody` + mappers to the new evidence shape; clean stale comment `workspaceStore.ts:500`.
5. ReForm: remove flasks/collect_config section (R5).

Gate: pnpm typecheck/lint/unit green; manual duo-panel walkthrough of the FP tab.

## Phase 3 — `07-06-fp-e2e-docs`

1. New Playwright spec: full robot chain TLC → CC → FP → RE.
2. Fix stale FP-skip assumptions (`cc-re-chained-flow.spec.ts` — CC→RE jump comment/behavior).
3. Production-PRD: close the FP deferral clause; add FP interaction + result rules; change log entry (use the `prd` skill).

Gate: full FE suite green (LLM specs --workers=1); bench E2E via `bic-e2e-runner` playbook.

## Rollback shape

Each child lands as its own change set on its repo branch; Phase 1 is inert to users until Phase 2 exposes the form (the stub removal only activates when reception meets a robot fp step — plans with manual FP are unaffected). Reverting Phase 1 restores the stub disposition.
