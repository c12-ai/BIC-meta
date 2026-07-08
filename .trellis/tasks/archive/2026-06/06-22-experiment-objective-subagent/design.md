# Technical Design — Experiment Objective Subagent

> **Guiding principle (Drake, 2026-06-22):** This is a **Level-1** agent. For the
> Level-1 stage flow it **follows the Plan Agent** (`plan_subgraph`) — propose →
> `FORM_CONFIRM` → stage advance — exactly as Plan does `experiment_objective`'s
> sibling transition. For the ReAct/tool machinery it **follows the CC subagent**.
> So: **Objective Agent = Plan Agent (Level-1 confirm shape) + CC subagent (ReAct tools).**
> No bespoke confirm-event mechanics — mirror what Plan/CC already do.

Grounded in `research/cc-patterns-for-objective.md` (verbatim CC/Plan patterns + file:line).

## 1 · Mental Model & Boundaries

```
Level-1 forward flow (experiment-scoped):
  experiment_objective ──(objective confirmed)──▶ workflow_design ──(plan confirmed)──▶ parameter_design
        ▲ Objective Agent (THIS task)                  ▲ Plan Agent (exists)
```

The Objective Agent is the **sibling of the Plan Agent**:
- both are **experiment-scoped** (no trial / `task_id` / lab dispatch);
- both **propose → emit a confirm form → on `FORM_CONFIRM` advance `Experiment.stage`**;
- both use an experiment-level confirm action with **no `specialist_kind`** (`PlanConfirmAction` is the template, not `CCParamsConfirmAction`).

The CC subagent supplies the **ReAct loop + tool patterns** (Mind-calling tools, `update_*` merge tools, `Command(update=...)`, middleware stack) — because the Objective Agent, unlike Plan, has Mind-wired tools (material-parse, goal-confirm) and a multi-section draft the user co-edits.

## 2 · Stage Gate (the one routing chokepoint)

`route_after_admit.py:59-65` currently sends `execute + no in-flight → plan_subgraph` with **zero stage awareness**. Add the gate here (mirrors how Plan is reached, but stage-gated):

```text
pass + execute + no in-flight task:
    ctx.experiment is None or ctx.experiment.stage == "experiment_objective"  → objective_subgraph
    ctx.experiment.stage == "workflow_design"                                 → plan_subgraph
    ctx.experiment.stage == "parameter_design"                                → specialist_dispatcher  (existing in-flight rules)
```

**The gate predicate is "objective not yet confirmed", and `stage == experiment_objective`
IS that predicate** — because objective confirmation is the ONLY thing that advances
`experiment_objective → workflow_design`. Expected workflow (Drake, 2026-06-22):

1. Execute-intent turn → `route_after_admit`.
2. **No confirmed objective → Objective Subagent.** This holds for the whole pre-confirm period:
   (a) the agent proposed an objective and the user wants to **modify** it → still
   `stage == experiment_objective` (proposal does NOT advance stage) → routes back to objective;
   (b) **every** execute turn keeps looping into the Objective Subagent until the user confirms —
   there is no other exit from `experiment_objective`.
3. **Objective confirmed** (`FORM_CONFIRM(objective)` advanced stage to `workflow_design`) →
   next execute turn auto-routes to the **Plan Agent**; subsequent steps unchanged.

So 2(a)/2(b) need no special handling — they are the default behavior of the stage predicate.
Widen the node's `Literal[...]` goto union to include `"objective_subgraph"`. `ctx.experiment` is
an `ExperimentSnapshot | None` carrying `.stage` (06-18 Phase 1) — already on `GraphState.ctx`.

`route_entry.py` (cross-turn re-entry): add `FORM_CONFIRM(objective) → objective_subgraph`, **mirroring** the existing `FORM_CONFIRM(plan) → plan_subgraph` branch (`route_entry.py:66`).

## 3 · Experiment Creation moves here (S3)

The experiment is created the moment intent = execution and routing first lands on the Objective Agent. The Objective subgraph emits `ExperimentCreatedEvent` (dual-path) when `ctx.experiment is None` — **moving** the creation that lives at `plan_subgraph.py:294-301`.

**Remove** the `ExperimentCreatedEvent` fallback from `plan_subgraph._emit_form_node`. Safe **because** the new stage gate guarantees `plan_subgraph` is only reachable at `stage == workflow_design`, which only exists after an objective was confirmed, which only happens after the experiment was created. Add a routing test proving a no-experiment execute turn reaches objective, never plan.

## 4 · Subgraph Topology (mirror plan_subgraph + cc)

New file `app/runtime/graphs/specialists/objective.py`, `build_objective_subgraph(llm, mind, minio_client)`:

```text
START ─▶ rehydrate ─▶ _pre_route ──(form_confirm_payload present)──▶ emit_confirm ─▶ narrate ─▶ END
                                └──(else / propose turn)───────────▶ react_agent ─▶ _post_route ─┬─▶ emit_form ─▶ narrate ─▶ END
                                                                                                 ├─▶ auto_parse  ─▶ ... (deterministic Mind material-parse when rxn present, recommended missing)
                                                                                                 └─▶ narrate ─▶ END
```

- **`_pre_route`**: `form_confirm_payload is not None → "emit_confirm"` else `"react"` — verbatim Plan pattern (`plan_subgraph.py:120-134`).
- **`react_agent`**: `create_agent(model=llm.chat_model, tools=objective_tools, state_schema=ObjectiveSubgraphState, context_schema=RuntimeContext, middleware=[objective_dynamic_prompt, LLMErrorHandlingMiddleware(), GuardrailMiddleware(), LoopDetectionMiddleware(), ToolErrorHandlingMiddleware(), AfterToolMiddleware()])` — CC middleware stack (order load-bearing), `recursion_limit=25`.
- **`_post_route`**: keys off `last_tool_name` — `request_objective_confirmation` (not refused) → `emit_form`; objective recommendable but `recommended` missing → `auto_parse`/`auto_goal`; else → `narrate`. Mirrors `cc._post_react_route`.
- **`emit_form`**: emits `FormRequestedEvent(confirm_kind="objective", original_action=ObjectiveConfirmAction(...))` built from `objective_draft` — mirrors `plan_subgraph._emit_form_node` + `cc._emit_form_node`.
- **`emit_confirm`**: deterministic stage-advance on `FORM_CONFIRM(objective)` re-entry — mirrors `plan_subgraph` emit_confirm; applies the **same `ExperimentObjectiveConfirmedEvent`** (06-18) so API and agent paths share one stage-advance code path. After advancing to `workflow_design`, the same turn may hand off toward Plan (mirrors Plan's hand-to-dispatcher).
- **`narrate`**: second LLM pass for streaming narration (CC/Plan pattern).

## 5 · State (`ObjectiveSubgraphState`) — experiment-scoped

`SpecialistState` is trial-scoped (`task_id`, `params_confirmed`, `lab_task_id`, dispatch). The Objective Agent diverges; define a parallel state (in `objective.py` or `runtime/types`), keeping the load-bearing reducer fields from CC:

```text
ctx: SessionContext                  # carries ctx.experiment (.stage)
experiment_id: str | None            # None until created this turn
current_phase: ObjectivePhase        # "collecting_objective" | "confirmed" (minimal — Level-1 has no trial phases)
form_confirm_payload: FormConfirmPayload | None
messages: Annotated[list[BaseMessage], add_messages]
objective_draft: Annotated[dict | None, _merge_params_draft]   # reuse the CC section-merge reducer
objective_validated: bool | None
last_tool_name: Annotated[str | None, _last_wins]
last_tool_args: Annotated[dict | None, _last_wins]
last_tool_refused: Annotated[bool | None, _last_wins]
```

No `task_id`, no `lab_task_id`, no `params_confirmed`/`cancel_confirmed`, no submit/dispatch.

## 6 · Tools (`build_objective_tools(mind, minio_client)`)

Mirror CC tool patterns (`@tool`, `InjectedState`, `InjectedToolCallId`, `Command(update=...)`):

| Tool | Mirrors | Behavior |
| --- | --- | --- |
| `update_objective_params(fields, ...)` | `update_cc_params` | Section-merge `from_user` / targets into `objective_draft`; emit a params-set-equivalent event. |
| `parse_reaction(...)` | `recommend_cc_params` (Mind-calling) | Build `ExperimentMaterialParseRequest(rxn=...)` (try/except RxnSmiles → refusal `ToolMessage`), call `mind.parse_experiment_materials`, write `rendered_rxn_url` + materials + baseline hint into draft. |
| `confirm_goal(...)` | `recommend_cc_params` | Build `ExperimentGoalConfirmRequest(...)`, call `mind.confirm_experiment_goal`, write per-material `amount_mg`/`equivalents`/`is_baseline` + `target_weight_mg` into draft. |
| `validate_objective_params(...)` | `validate_cc_params` | Local gate: `objective_params_form_problems`; set `objective_validated`. |
| `request_clarification(question)` | same | Ask chemist; no phase exit. |
| `request_objective_confirmation(...)` | `request_plan_confirmation` / `request_params_confirmation` | Terminal tool; sets `last_tool_name` so `_post_route → emit_form`. |

Mind methods already exist (06-18 in-method stubs): `mind.parse_experiment_materials`, `mind.confirm_experiment_goal`.

**Phase-2 divergence (no set-event):** `update_objective_params` writes only `objective_draft`
state — it emits NO event. The CC analog emits `TaskParamsSetEvent`, but that event is
trial-scoped (`apply` writes `tx.trials.update_fields(trial_id=...)`), and the objective is
experiment-scoped with no trial row — emitting it would corrupt `trials`. This matches the
lenient `handle_objective_draft` precedent (persist draft, no event). **Consequence:**
chat-driven objective edits do NOT live-sync to the FE form via SSE until the objective is
confirmed. If FE live form-sync for agent edits is wanted, that needs a NEW experiment-scoped
`ExperimentObjectiveDraftedEvent` (out of scope here; follow-up for the portal task).

## 7 · Form Payloads (mirror `PlanConfirmAction`, NOT CC)

Add to `app/events/form_payloads.py` (layer-neutral — mirror `ObjectivePayload` shape; do NOT import `app.data`):

- `ObjectiveReactantRow` (layer-neutral mirror of `app.data.objective_schemas.ObjectiveReactantRow`).
- `ObjectiveParamsForm` (from_user + recommended/materials + targets) — the draft shape.
- `ObjectiveConfirmAction(confirm_kind: Literal["objective"] = "objective", experiment_id: str, objective: ObjectiveParamsForm, name: str)` — **no `specialist_kind`** (experiment-level, like `PlanConfirmAction`).
- Register in `OriginalAction` union: add `Annotated[ObjectiveConfirmAction, Tag("objective")]`; extend `_action_discriminator` to short-circuit `confirm_kind == "objective" → "objective"` (mirrors the `"plan"` short-circuit at `form_payloads.py:658`).
- Append `ObjectiveConfirmAction` to `TYPED_ORIGINAL_ACTIONS`.
- Add `"objective"` to `FormRequestedEvent._enforce_typed_action`'s typed-required set (`runtime_emitted.py:427`).
- `build_objective_request()` (strict gate) + `objective_params_form_problems[_from_values]()` — mirror `build_cc_param_request` + `cc_params_form_problems`.

An adapter maps `ObjectiveParamsForm` (wire/form) ↔ `ObjectivePayload` (`app.data`, persisted) — the same split CC uses (`CCParamsForm` vs persisted draft).

## 8 · Confirm Wiring (follow Plan exactly)

`FORM_CONFIRM(objective)` flows **identically to `FORM_CONFIRM(plan)`**:

- `route_entry` → `objective_subgraph` (new branch mirroring the plan branch).
- `_pre_route` sees `form_confirm_payload` → `emit_confirm` (deterministic, no LLM).
- `emit_confirm` applies **`ExperimentObjectiveConfirmedEvent`** (06-18's event) → advances `experiment_objective → workflow_design`. Both the direct API (06-18) and this agent path apply the **same event** = one stage-advance code path (S2 duo-panel reconciliation: both kept).
- `ConfirmKind.OBJECTIVE` + `ConfirmKindLiteral "objective"` already exist (06-18 Phase 1).

If `FORM_CONFIRM(objective)` needs to mint the event at API time like Plan does in `service._build_confirmed_event`: add an `OBJECTIVE` branch there returning `ExperimentObjectiveConfirmedEvent`. Since that event is a `BypassEventBase` (no `turn_id`) while the method is typed `PlanConfirmedEvent | FormConfirmedEvent`, widen the return type / mint path minimally — follow whatever shape keeps it closest to the Plan branch. (Detailed in implement.md; not a new contract, just wiring the existing event into the existing mint switch.)

## 9 · Factory + Dispatch + Prompt

- `factory.py`: `objective_subgraph = build_objective_subgraph(llm, mind, minio_client)`; `builder.add_node("objective_subgraph", project_to_specialist_subgraph(objective_subgraph, node_name="objective_subgraph_node"))` — mirror the CC/RE registration.
- `dynamic_prompts.py`: `_OBJECTIVE_HEADER` + `_OBJECTIVE_PHASE_INSTRUCTIONS` (collecting_objective) + `objective_dynamic_prompt` — mirror `cc_dynamic_prompt`.
- Reception/dispatch projection: project `ctx` + `current_phase` + `form_confirm_payload` + `experiment_id` into `ObjectiveSubgraphState` — mirror the specialist input projection, minus trial fields.

## 10 · Tests

- `tests/unit/test_specialists_objective.py`: `_pre_route` / `_post_route`, `_emit_form_node` builds `ObjectiveConfirmAction`, emit_confirm applies the stage event.
- objective tool tests (in `test_specialists_tools.py` or a sibling): parse/goal Mind calls + draft write-through, bad-rxn refusal, validation problems.
- routing: `route_after_admit` stage gate (no-exp/objective→objective, workflow_design→plan, parameter_design→dispatcher); `route_entry` `FORM_CONFIRM(objective)`; **no-experiment execute turn never reaches plan_subgraph**.
- form payloads: `ObjectiveConfirmAction` discriminator + codec round-trip; `FormRequestedEvent._enforce_typed_action` accepts it.
- creation-move: objective subgraph emits `ExperimentCreatedEvent` when `ctx.experiment is None`; plan_subgraph no longer does.
- e2e: `USER_MESSAGE` (execute) → objective dispatch → `request_objective_confirmation` → `FORM_CONFIRM(objective)` → `stage=workflow_design` → plan reachable.

## 11 · Affected Files

New: `app/runtime/graphs/specialists/objective.py`; `tests/unit/test_specialists_objective.py`.
Modified: `app/events/form_payloads.py` (objective form + action + union), `app/events/runtime_emitted.py` (`_enforce_typed_action` set), `app/runtime/graphs/specialists/tools.py` (`build_objective_tools`), `app/runtime/graphs/nodes/route_after_admit.py` (stage gate), `app/runtime/graphs/nodes/route_entry.py` (FORM_CONFIRM(objective)), `app/runtime/graphs/nodes/plan_subgraph.py` (remove ExperimentCreatedEvent fallback), `app/runtime/graphs/factory.py`, `app/runtime/middleware/dynamic_prompts.py`, `app/session/service.py` (`_build_confirmed_event` OBJECTIVE branch if API-mint needed), reception/dispatch projection, + tests.

## 12 · Risks

| Risk | Mitigation |
| --- | --- |
| Removing plan_subgraph creation FK-fails some path | Stage gate proves plan reachable only at `workflow_design`; add the no-exp→objective routing test BEFORE removing. |
| `ObjectiveSubgraphState` drifts from CC reducers | Reuse `_merge_params_draft` / `_last_wins` verbatim; don't re-invent. |
| Discriminator/typed-action gate misses objective | Mirror the `"plan"` short-circuit + add to `_enforce_typed_action` set + codec test. |
| Two confirm paths diverge | Both apply the SAME `ExperimentObjectiveConfirmedEvent`; assert in tests both reach `workflow_design`. |
| Mind stub vs live | 06-18 stubs stand; swapping to live is localized to the two MindClient methods. |
