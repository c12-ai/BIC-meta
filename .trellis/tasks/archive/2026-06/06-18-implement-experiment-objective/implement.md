# Implementation Plan — Implement Experiment Objective

> One task, **commits split by phase** (PRD D7). Each phase is independently reviewable with its own rollback point.
> Read `prd.md` then `design.md` first. Contract field names are in `design.md §2` (verbatim from shared-types `v1.1.6a1`).

## Review Gate Before Start

Confirm before `task.py start`:

- [ ] `prd.md` decisions D1–D8 accepted.
- [ ] `design.md` contract accepted (esp. §2 stub toggle, §7 dual-path event, §8 direct-API-not-FORM_CONFIRM routing simplification).
- [ ] Mind runs on **stub data** for this task (D4); live wiring is a config flip later.
- [ ] Parent `06-21` objective slice is superseded by this task (D5) — will update its `implement.md` in the finish step.
- [ ] No shared-types change, no `Trial.phase` enum, no FE 5-status header in this task.

## Phase 1 — Schema, Enums, Repos (backend)

Goal: `experiments.name` + `experiments.stage` land cleanly with `ExperimentStage` typing, no behavior change yet.

1. `app/core/enums.py`: add `ExperimentStage` enum; add `ConfirmKind.OBJECTIVE = "objective"`.
2. `app/events/form_payloads.py:59`: add `"objective"` to `ConfirmKindLiteral` (byte-identical to the enum value).
3. Alembic migration `<rev>_experiments_name_stage.py`: add `name VARCHAR(255)` nullable + `stage VARCHAR(32) NOT NULL DEFAULT 'experiment_objective'`; downgrade drops both.
4. `app/data/models.py`: add `Experiment.name` (`str | None`) + `Experiment.stage` (`str`, persists enum value). Do not touch `Trial.phase`.
5. `app/repositories/experiments_repo.py`: add `name`, `stage` to `ExperimentSnapshot` + `_row_to_snapshot` + updatable-fields. Default insert stage = `experiment_objective`.
6. Tests: extend `tests/unit/test_persistence_repo_experiments.py` (name/stage round-trip, stage update, default), `tests/unit/test_import_hygiene.py` + `tests/unit/test_events_codec.py` (ConfirmKind.OBJECTIVE + literal mirror parity).

Validate:
```bash
cd BIC-agent-service
alembic check
uv run pytest tests/unit/test_persistence_repo_experiments.py tests/unit/test_import_hygiene.py tests/unit/test_events_codec.py
uv run ruff check app tests && uv run pyright app
```
Rollback point: revert migration + model + enum if repo tests fail, before touching runtime.
Commit: `feat(experiments): add name + stage columns and ExperimentStage enum`.

## Phase 2 — Objective-Confirm Event + Stage Transition (backend)

Goal: `ExperimentObjectiveConfirmedEvent` applies through the dual-path tx and advances stage idempotently.

1. New event in `app/events/` (layer-neutral, string literals): `ExperimentObjectiveConfirmedEvent(experiment_id, objective, name, confirm_kind="objective")`.
2. `apply()`: update `experiments.objective` (+ `name`); `update_fields(stage="workflow_design")`; no-op if already `workflow_design`/`parameter_design`.
3. Register in event codec / runtime unions where exhaustiveness tests require.
4. Tests: `tests/unit/test_runtime_emitted_apply.py` — confirm advances `experiment_objective -> workflow_design`; replay is no-op; never backward; `tests/unit/test_events_codec.py` — event round-trips.

Validate:
```bash
uv run pytest tests/unit/test_runtime_emitted_apply.py tests/unit/test_events_codec.py
uv run ruff check app tests && uv run pyright app
```
Rollback point: revert the event + apply if stage movement destabilizes; keep Phase 1.
Commit: `feat(events): ExperimentObjectiveConfirmedEvent advances experiment stage`.

## Phase 3 — Mind Wiring (stub port) + Objective Service + Endpoints (backend)

Goal: objective draft/confirm endpoints persist + (stub) Mind-parse/goal-confirm + confirm emits the event.

1. `app/infrastructure/`: add `ObjectiveMaterialPort` interface + `StubObjectiveMaterialAdapter` (deterministic, contract-typed responses) + real `MindClient`-backed adapter; default = stub, toggle by config (follow existing client-injection convention). Map `RxnSmiles` validator `ValueError` → field error.
2. `app/session/service.py` (L2 Facade): `save_objective_draft(...)` (lenient persist, optional parse to fill materials) + `confirm_objective(...)` (validate name uniqueness-in-session + ranges + baseline rules; goal-confirm for `target_weight_mg`; emit event via three-piece tx).
3. `app/api/routers/sessions.py` (L1): `POST /sessions/{sid}/objective/draft` + `POST /sessions/{sid}/objective/confirm` with request/response DTOs + the parse/goal-confirm adapter (§2 asymmetry). 422 field-mapped on validation failure.
4. Tests: objective endpoint test (draft lenient, confirm strict, 422 mapping, duplicate-name rejection), Mind-stub adapter test (deterministic contract-valid output).

Validate:
```bash
uv run pytest tests/unit/<objective_endpoint_test> tests/unit/<mind_stub_test>
uv run ruff check app tests && uv run pyright app
```
Rollback point: revert endpoints + service + port; Phases 1–2 stand.
Commit: `feat(objective): draft/confirm endpoints with stubbed Mind material/goal wiring`.

## Phase 4 — Objective Subagent + Routing — SPLIT OUT (2026-06-22)

**Decision (Drake, 2026-06-22):** The objective subagent is a FULL ReAct specialist
(CC-equivalent: tools + Mind-wired recommend/parse, validation, typed form-confirm
action, dynamic prompt, factory/dispatch, ~2500 lines / 9 areas — see
`research/cc-subagent-architecture-map` reconnaissance). That is far larger than a
phase and is moved to a new task **`06-22-experiment-objective-subagent`**.

**Confirm-model decision (Drake, 2026-06-22):** the subagent will use **agent-emitted
form-confirm** (`request_objective_confirmation` → `FormRequestedEvent(confirm_kind=
"objective")` → `FORM_CONFIRM(objective)`), like CC's `request_params_confirmation`.
This SUPERSEDES this task's Phase-3 direct-API confirm (D6) — but Phases 1–3 are NOT
ripped out here: they are a working, tested boundary, and the new task owns the
reconciliation (it may keep the API as a duo-panel deterministic path or replace it).
Flagged loudly (Rule 9): 06-18 ships with direct-API confirm; 06-22 changes the model.

**What stays in 06-18 (minimal, so the lifecycle does not crash):**

1. `route_after_admit.py`: stage-gated routing for the EXECUTE + no-in-flight path —
   `ctx.experiment is None or stage == experiment_objective` → (for now) keep routing to
   `plan_subgraph` UNCHANGED, because the objective subgraph node does not exist yet in
   06-18. **Do NOT add a dangling goto to a non-existent node.** The stage gate + objective
   node land together in 06-22.
2. Therefore Phase 4 in THIS task is effectively a NO-OP on the graph — routing is left as-is
   and the objective subagent + its routing edge are wholly owned by 06-22.

Net: **skip graph changes in 06-18.** Proceed to Phase 5 (snapshot) + Phase 7 (finish), and
create `06-22-experiment-objective-subagent`.

## Phase 5 — Snapshot DTO (backend)

1. `app/api/routers/sessions.py`: `SnapshotExperimentItem` adds `name: str | None`, `stage: ExperimentStage`; `objective` now carries real data.
2. Tests: `tests/unit/test_persistence_repo_snapshot.py` + session-route snapshot test — name/stage/objective present.

Validate:
```bash
uv run pytest tests/unit/test_persistence_repo_snapshot.py
uv run ruff check app tests && uv run pyright app && alembic check
```
Commit: `feat(snapshot): expose experiment name + stage`.

## Phase 6 — Portal: client, store, hydration, form

1. `src/lib/agent-client.ts`: `ExperimentStage` const-union; `SnapshotExperiment.name/.stage`; `saveObjectiveDraft` / `confirmObjective` client methods + hand-mirrored objective DTOs.
2. `src/stores/workspaceStore.ts`: async draft/confirm actions; `hydrateFromSnapshot` reads `experiments[].objective` + `name` + `stage` (stop skipping); live `ExperimentObjectiveConfirmedEvent` → set stage `workflow_design`.
3. `src/components/workspace/ExperimentObjectiveStep.tsx`: remove local target-weight math; render `target_weight_mg` (3 dp) + reaction image (`rendered_rxn_url`/`structure_url`); reactant table → goal-confirm `materials[]`; baseline `1.00` fixed; copy SMILES; edit → existing molecule editor or documented SMILES-text degrade; 422 → field errors.
4. `src/components/workspace/TaskConfigPane.tsx`: objective step status from `stage`/objective state (objective step only — do not touch workflow/parameter logic).
5. Tests: validation, baseline switching, error mapping, draft/confirm flow, snapshot hydration, live objective-confirm stage advance.

Validate:
```bash
cd BIC-agent-portal
pnpm test -- src/stores/workspaceStore.routing.test.ts src/lib/session-loader.test.ts <objective form test>
pnpm typecheck
pnpm exec biome check src/lib/agent-client.ts src/stores/workspaceStore.ts src/components/workspace/ExperimentObjectiveStep.tsx src/components/workspace/TaskConfigPane.tsx
pnpm build
```
Rollback point: revert portal changes; backend contract stays dormant behind the new endpoints.
Commit: `feat(portal): backend-backed objective form with snapshot hydration`.

## Phase 7 — Verification & Finish

1. Full targeted backend suite:
```bash
cd BIC-agent-service
uv run pytest tests/unit/test_persistence_repo_experiments.py tests/unit/test_runtime_emitted_apply.py tests/unit/test_events_codec.py tests/unit/test_import_hygiene.py tests/unit/test_persistence_repo_snapshot.py tests/integration/test_l1_l2_wireup.py <objective endpoint/routing/stub tests>
uv run ruff check app tests && uv run ruff format --check app && uv run pyright app && alembic check
```
2. Full targeted portal suite (Phase 6 commands).
3. Optional E2E smoke: objective draft → confirm → Workflow Design (dispatch `bic-e2e-runner` per CLAUDE.local.md if a live bench is warranted).
4. Compare against `prd.md` Acceptance Criteria; re-read `design.md §12` risks; confirm mitigations landed.
5. **D5 cleanup:** update parent `.trellis/tasks/06-21-align-l1-l2-experiment-workflow-lifecycle/implement.md` so its Phase 0/2 objective slice **consumes** the stage/event/subagent built here instead of rebuilding. Surface the change to Drake.
6. Update `.trellis/spec/` if the objective endpoint pattern / objective-confirm event is a reusable convention (Rule 10: contract change → spec update).
7. Present the commit plan; commit per phase only after Drake's go-ahead (CLAUDE.md: never commit without being asked).

## Completion Checklist

- [ ] Migration adds `name` + `stage`; `alembic check` clean; downgrade drops both.
- [ ] `ExperimentStage` enum + `ConfirmKind.OBJECTIVE` (enum + literal mirror parity).
- [ ] `ExperimentObjectiveConfirmedEvent` applies via dual-path tx; idempotent; no-backward.
- [ ] Objective draft/confirm endpoints persist + (stub) Mind parse/goal-confirm; 422 field-mapped.
- [ ] No-objective execute turns route to objective subagent; post-confirm reaches plan path.
- [ ] Snapshot exposes `name` + `stage` + real `objective`.
- [ ] Portal: backend-backed draft/confirm, snapshot hydration, live stage advance, no direct Mind calls, local target-weight math removed.
- [ ] Mind behind stub toggle; live flip needs no contract change.
- [ ] Backend + portal targeted tests, lint, types, build all green.
- [ ] Parent `06-21` implement.md updated to consume (D5).
