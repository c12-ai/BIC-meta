# Implementation Plan — Experiment Objective Subagent

> Read `prd.md` → `design.md` → `research/cc-patterns-for-objective.md` first.
> **Template rule:** Level-1 confirm flow follows the **Plan Agent**; ReAct/tools follow the **CC subagent**.
> One task, commits split by phase. No git commit until Drake asks.

## Review Gate Before Start

- [ ] `design.md` accepted (esp. §2 stage gate, §3 creation-move, §7 PlanConfirmAction-style form, §8 shared event).
- [ ] 06-18 prerequisite landed (stage column, `ExperimentObjectiveConfirmedEvent`, Mind stubs, draft/confirm API).
- [ ] Confirmed: both confirm paths (direct API + agent FORM_CONFIRM) share `ExperimentObjectiveConfirmedEvent`.

## Phase 1 — Form Payloads + Typed Action (layer-neutral)

Mirror `PlanConfirmAction`, not CC.

1. `app/events/form_payloads.py`: add `ObjectiveReactantRow`, `ObjectiveParamsForm` (from_user + materials + targets), `ObjectiveConfirmAction(confirm_kind: Literal["objective"], experiment_id, objective, name)` — no `specialist_kind`.
2. Register: `OriginalAction` union `+ Annotated[ObjectiveConfirmAction, Tag("objective")]`; `_action_discriminator` short-circuit `confirm_kind=="objective" → "objective"`; append to `TYPED_ORIGINAL_ACTIONS`.
3. `app/events/runtime_emitted.py`: add `"objective"` to `FormRequestedEvent._enforce_typed_action` typed-required set.
4. `build_objective_request()` + `objective_params_form_problems[_from_values]()` mirror `build_cc_param_request` + `cc_params_form_problems`.
5. Tests: `test_events_codec.py` round-trip for `FormRequestedEvent(confirm_kind="objective")`; discriminator accepts the objective arm; `_enforce_typed_action` accepts it.

Validate: `uv run pytest tests/unit/test_events_codec.py tests/unit/test_import_hygiene.py && uv run ruff check app tests && uv run pyright app`.
Commit: `feat(events): ObjectiveConfirmAction typed form payload`.

## Phase 2 — Objective Tools

`build_objective_tools(mind, minio_client)` in `specialists/tools.py`, mirroring the CC tool patterns.

1. `update_objective_params` (section-merge → `objective_draft`, `Command(update=...)`), `parse_reaction` (Mind material-parse, RxnSmiles try/except → refusal), `confirm_goal` (Mind goal-confirm → target_weight_mg), `validate_objective_params` (local gate), `request_clarification`, `request_objective_confirmation` (terminal).
2. Reuse `_merge_params_draft` / `_last_wins` reducers.
3. Tests: each tool's draft write-through; bad-rxn refusal; validation problems; Mind stub responses land.

Validate: `uv run pytest tests/unit/test_specialists_tools.py -q && uv run ruff check app tests && uv run pyright app`.
Commit: `feat(specialists): objective tools (Mind parse/goal + draft merge)`.

## Phase 3 — Objective Subgraph + State

1. `ObjectiveSubgraphState` (experiment-scoped; §5) — in `objective.py` or `runtime/types`.
2. `app/runtime/graphs/specialists/objective.py` `build_objective_subgraph(llm, mind, minio_client)`: `rehydrate → _pre_route → {emit_confirm | react_agent} → _post_route → {emit_form | auto_* | narrate}` — mirror `plan_subgraph` (confirm shape) + `cc` (react/post-route).
3. `emit_form` builds `ObjectiveConfirmAction`; `emit_confirm` applies `ExperimentObjectiveConfirmedEvent` (deterministic re-entry, like Plan).
4. `dynamic_prompts.py`: `_OBJECTIVE_HEADER` + `_OBJECTIVE_PHASE_INSTRUCTIONS` + `objective_dynamic_prompt`.
5. Emit `ExperimentCreatedEvent` when `ctx.experiment is None` (creation moves here).
6. Tests: `test_specialists_objective.py` — `_pre_route`/`_post_route`, emit_form action, emit_confirm stage advance, creation-on-empty.

Validate: `uv run pytest tests/unit/test_specialists_objective.py -q && uv run ruff check app tests && uv run pyright app`.
Commit: `feat(specialists): experiment objective subgraph`.

## Phase 4 — Routing + Factory + Creation-Move

1. `route_after_admit.py`: stage gate (§2) + widen `Literal[...]` goto union with `"objective_subgraph"`.
2. `route_entry.py`: `FORM_CONFIRM(objective) → objective_subgraph` (mirror plan branch).
3. `factory.py`: register the objective subgraph node.
4. Reception/dispatch projection: project objective inputs into `ObjectiveSubgraphState`.
5. **`plan_subgraph.py`: REMOVE the `ExperimentCreatedEvent` fallback** (`:294-301`).
6. `service.py` `_build_confirmed_event`: add OBJECTIVE branch if API-time mint of the event is required (widen return type minimally).
7. Tests: stage-gate routing; `FORM_CONFIRM(objective)` route; **no-experiment execute turn → objective, never plan**; plan_subgraph no longer creates experiments.

Validate: `uv run pytest tests/unit/test_runtime_emitted_apply.py tests/integration/test_l1_l2_wireup.py <routing tests> -q && uv run ruff check app tests && uv run pyright app`.
Commit: `feat(runtime): stage-gated objective routing; move experiment creation to objective`.

## Phase 5 — E2E + Verification

1. e2e (mirror `test_specialist_smoke_e2e.py` / `test_l3_reception_node_split_e2e.py`): `USER_MESSAGE`(execute) → objective dispatch → `request_objective_confirmation` → `FORM_CONFIRM(objective)` → `stage=workflow_design` → plan reachable.
2. Full gate:
```bash
uv run ruff check app tests && uv run ruff format --check app tests
uv run pyright app && uv run alembic check
uv run pytest -q
```
3. Spec update (Rule 10): `L3/graphs.md` (objective subgraph topology + stage gate), `L3/specialist_tools.md` (objective tools), `L1/http-routes.md`/`L4/events.md` if the confirm-path note needs amending (06-18 flagged the supersession).
4. Update parent `06-21` implement.md cleanup banner if anything shifts.
5. Commit preamble + present plan; commit per phase after Drake's go-ahead.

## Completion Checklist

- [ ] `ObjectiveConfirmAction` typed + registered + codec-tested.
- [ ] Objective tools wrap `parse_experiment_materials` / `confirm_experiment_goal`.
- [ ] `objective_subgraph` built, registered, reachable.
- [ ] Stage gate: no-exp/objective→objective, workflow_design→plan, parameter_design→dispatcher.
- [ ] `FORM_CONFIRM(objective)` advances `experiment_objective → workflow_design` via the shared `ExperimentObjectiveConfirmedEvent`.
- [ ] Experiment creation moved to objective; plan_subgraph fallback removed; no-exp turn never reaches plan.
- [ ] Both confirm paths (API + agent) reach `workflow_design`.
- [ ] ruff / format / pyright / alembic / full pytest green.
- [ ] Specs updated.
