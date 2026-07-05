# Experiment Objective Subagent

> Split out of `06-18-implement-experiment-objective` on 2026-06-22 (Drake's call).
> 06-18 delivered the backend objective **data + API + event + Mind + snapshot** layer.
> This task builds the **full ReAct Objective specialist subagent** + the routing that sends
> execute-intent turns to it, modeled on the CC specialist.

## Goal

Make the Experiment Objective a first-class ReAct specialist subagent (CC-equivalent) so the
chemist can fill the objective form three ways — **clicking, typing in the form, OR talking to
the agent**. The subagent wraps the two MindClient objective capabilities (already wired in
06-18) as tools, validates inputs, and emits an agent-driven objective confirmation.

## Flow (Drake, 2026-06-22)

1. New session → no experiment / plan / jobs / trials.
2. User types → agent classifies intent: **query vs execution**.
3. Query → query agent replies; nothing created.
4. **Execution determined → route to the Objective Subagent FIRST** (before the Plan Agent).
   The experiment is created at this moment (intent = execution) via `ExperimentCreatedEvent`
   (dual-path: `session_events` + entity projection).
5. The subagent helps the chemist define the objective (reaction, materials, targets), then the
   objective is confirmed → `Experiment.stage` advances `experiment_objective → workflow_design`
   → the Plan Agent takes over.

## Locked Decisions (2026-06-22)

| # | Decision | Choice |
| --- | --- | --- |
| S1 | Subagent shape | **Full ReAct specialist, modeled on CC** (`specialists/cc.py`): tools + Mind-wired recommend/parse + validation + typed form-confirm + dynamic prompt + factory/dispatch. NOT a deterministic stub. |
| S2 | Confirm model | **Agent-emitted form-confirm**, like CC's `request_params_confirmation` → `FormRequestedEvent(confirm_kind="objective")` → `FORM_CONFIRM(objective)`. **This SUPERSEDES 06-18's direct-API confirm (D6).** Reconcile (keep direct API as a duo-panel deterministic path, or replace it) in this task's design. |
| S3 | Experiment creation point | The **Objective Subagent** creates the experiment at intent=execution (via `ExperimentCreatedEvent`). 06-18 already changed the objective API to *resolve, not create*. **This task REMOVES the `ExperimentCreatedEvent` creation fallback from `plan_subgraph`** (Drake: move creation, remove plan fallback) — creation lives only in the objective subagent. |
| S4 | Mind capabilities | Reuse the two MindClient methods 06-18 added (in-method stubs): `parse_experiment_materials` (rxn → rendered_rxn_url + materials[] + baseline hint) and `confirm_experiment_goal` (baseline + feed + purity + yield → per-material amount/equivalents + target_weight_mg). |

## The two Mind capabilities the subagent tools wrap (Drake's description)

1. **Material parse:** extract `RxnSmiles` from user input → `MindClient.parse_experiment_materials` →
   returns how the rxn renders to an image URL (FE display) + the materials in the rxn + which is
   most likely the baseline (main material).
2. **Goal confirm:** given amount + equivalents per material + target purity + target weight/amount and
   which material is the baseline → `MindClient.confirm_experiment_goal` → calculates and returns the
   required amount for each material + `target_weight_mg`.

## Scope — the 9 areas to mirror from the CC specialist

Reconnaissance (this session, `Explore` over `specialists/cc.py` et al.) found the CC specialist
spans ~2500 lines across 9 areas. The objective subagent mirrors each:

1. **Subgraph builder** — new `app/runtime/graphs/specialists/objective.py` (mirror `cc.py`): `rehydrate` →
   `_pre_react_route` → `{react_agent | auto_submit}` → `_post_react_route` → emit + `narrate`. `create_agent`
   with model + objective tools + `SpecialistState` + middleware stack (order is load-bearing).
2. **Tools** — `build_objective_tools()` in `specialists/tools.py`: `update_objective_params`, `parse_reaction`
   (→ Mind material-parse), `recommend_objective` / `confirm_goal` (→ Mind goal-confirm), `validate_objective_params`,
   `request_objective_confirmation` (terminal → form), `request_clarification`. Each draft mutation emits the
   params-set-equivalent event.
3. **State schema** — extend `SpecialistState` (`runtime/types/specialist.py`) with an `objective_draft` (section-wise
   merge reducer) + `objective_validated` / `objective_confirmed` mirrors; add the objective `specialist_kind` /
   phase values if distinct.
4. **Forms + validation** — `form_payloads.py`: `ObjectiveParamsForm` (from_user / recommended / lab_logistics
   shape), `ObjectiveParamsConfirmAction` typed `OriginalAction` arm + `TYPED_ORIGINAL_ACTIONS`,
   `build_objective_request()` strict gate, `objective_params_form_problems[_from_values]()`.
5. **Emit-form node** — `_emit_form_node` builds `ObjectiveParamsConfirmAction` from `objective_draft` and emits
   `FormRequestedEvent(confirm_kind="objective", original_action=...)`.
6. **Mind wiring** — tools call `mind.parse_experiment_materials` / `mind.confirm_experiment_goal`; write the
   rendered url / materials / target_weight_mg back into the draft.
7. **Factory + dispatch** — register the objective subgraph in `factory.py`; route execute-intent + no-confirmed-
   objective turns to it via `route_after_admit` (stage gate: `experiment is None or stage == experiment_objective`
   → objective; `workflow_design` → plan); route `FORM_CONFIRM(objective)` via `route_entry`; add the objective
   target to the `Literal[...]` goto unions.
8. **System prompt** — `dynamic_prompts.py`: `_OBJECTIVE_HEADER` + `_OBJECTIVE_PHASE_INSTRUCTIONS` +
   `objective_dynamic_prompt`.
9. **Tests** — `test_specialists_objective.py`, objective tool tests in `test_specialists_tools.py`, routing tests
   (`route_after_admit` / `route_entry`), an e2e `USER_MESSAGE → objective dispatch → form` integration test.

## Cross-task reconciliation (must resolve in design)

* **S2 confirm model vs 06-18 direct API** — 06-18 ships `POST /sessions/{id}/objective/{draft,confirm}` +
  `ExperimentObjectiveConfirmedEvent` (bypass event). This task adds the agent-emitted `FORM_CONFIRM(objective)`
  path. Decide: does `FORM_CONFIRM(objective)` apply the SAME `ExperimentObjectiveConfirmedEvent` (reuse the
  stage-advance apply), and is the direct API kept as a duo-panel deterministic confirm or removed? `ConfirmKind.OBJECTIVE`
  + the `ConfirmKindLiteral` mirror already exist (06-18 Phase 1).
* **S3 plan_subgraph fallback removal** — removing the `ExperimentCreatedEvent` fallback from `plan_subgraph._emit_form_node`
  requires proving every path into `plan_subgraph` has an experiment first (the objective subagent guarantees it). Add a
  test that an execute turn with no experiment routes to objective, not plan.
* **Parent 06-21** — this task and 06-18 both touch the L1 stage machine; keep `06-21`'s `implement.md` consuming, not
  rebuilding (see 06-18 D5 cleanup flag).

## Out of Scope

* The portal objective form rework (06-18 Phase 6 / a portal task) — except the FE contract for `FORM_CONFIRM(objective)`.
* Real Mind routes (the 06-18 in-method stubs stand until Mind confirms live).
* `Trial.phase` enum + plan-confirm transition (parent 06-21).

## Acceptance Criteria (high-level; expand in design)

* [ ] `specialists/objective.py` subgraph registered in the factory and reachable.
* [ ] Execute-intent + no-confirmed-objective turn routes to the objective subagent, not `plan_subgraph`.
* [ ] Objective subagent creates the experiment via `ExperimentCreatedEvent` at intent=execution.
* [ ] `plan_subgraph` no longer creates experiments (fallback removed); a no-experiment execute turn cannot reach plan.
* [ ] Objective tools wrap `parse_experiment_materials` / `confirm_experiment_goal` and fill the draft.
* [ ] `request_objective_confirmation` emits `FormRequestedEvent(confirm_kind="objective")`; `FORM_CONFIRM(objective)`
  advances `experiment_objective → workflow_design` (reusing or reconciled with `ExperimentObjectiveConfirmedEvent`).
* [ ] Confirm-model reconciliation with 06-18's direct API is decided and documented.
* [ ] Full backend test suite + targeted objective tests pass (ruff / pyright / pytest green).

## Status of the prerequisite (06-18)

Done and committed on branch `feat/shared-types-v1-1-6a1-cc-re-migration`:
`name`/`stage` columns + `ExperimentStage` + `ConfirmKind.OBJECTIVE`; `ExperimentObjectiveConfirmedEvent`;
`MindClient.parse_experiment_materials` / `confirm_experiment_goal` (stubs) + fixtures; objective draft/confirm
endpoints + L2 service (resolve-not-create); snapshot `name`/`stage`. This task builds on that.
