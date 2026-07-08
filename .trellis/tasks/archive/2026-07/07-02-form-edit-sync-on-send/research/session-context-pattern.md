# Research: SessionContext pattern — end-to-end path to the LLM prompt

- **Query**: Where SessionContext is defined/assembled and exactly how it reaches the LLM prompt, so a new field (e.g. `chemist_form_draft`) can thread the same way.
- **Scope**: internal (BIC-agent-service)
- **Date**: 2026-07-02

**Summary**: `SessionContext` is a frozen dataclass (`app/core/context.py:119`) loaded once per turn by the orchestrator (`app/session/orchestrator.py:487-553`), packed into `GraphState(ctx=...)` (`app/runtime/runtime.py:137`), projected into `SpecialistState.ctx` via the reception-node bundle (`app/runtime/types/dispatch.py:27`), and finally read by the `@dynamic_prompt` middleware which renders ctx-derived blocks (the "PRIOR STEP CONTEXT" block) into the per-turn system prompt (`app/runtime/middleware/dynamic_prompts.py:582-593`). A new ctx field needs exactly 3 touch points: dataclass field, loader query, prompt-render block (plus tests). There is ALSO a second, already-working channel into the LLM's `params_draft` state: reception_node re-seeds `params_draft` from persisted `trials.params` on every re-entry (`reception_node.py:437-438`) — anything persisted there before the turn is visible to the specialist tools automatically.

## Findings

### Files Found

| File Path | Description |
|---|---|
| `BIC-agent-service/app/core/context.py` | `SessionContext` definition (frozen dataclass) |
| `BIC-agent-service/app/session/orchestrator.py` | Per-turn loader `_load_session_context` |
| `BIC-agent-service/app/runtime/runtime.py` | `GraphState(ctx=ctx, turn=turn)` packing |
| `BIC-agent-service/app/runtime/types/state.py` | `GraphState.ctx` (line 53) |
| `BIC-agent-service/app/runtime/types/dispatch.py` | `SpecialistDispatchInputs` projection bundle |
| `BIC-agent-service/app/runtime/types/specialist.py` | `SpecialistState.ctx` + `params_draft` reducer |
| `BIC-agent-service/app/runtime/graphs/nodes/reception_node.py` | Bundle builder + draft re-seeding |
| `BIC-agent-service/app/runtime/middleware/dynamic_prompts.py` | System-prompt composition, ctx-block render |
| `BIC-agent-service/app/runtime/graphs/_rehydrate.py` | conversation_history → LangChain messages |

### 1. Definition — `app/core/context.py`

- `SessionContext` frozen dataclass: `context.py:119`. Fields (`:140-154`): `session_id`, `user_id`, `experiment: ExperimentSnapshot|None`, `plan: PlanSnapshot|None`, `jobs: tuple[JobSnapshot,...]`, `trials: Mapping[JobId, tuple[TrialSnapshot,...]]`, `conversation_history: tuple[ConversationMessage,...]`, `decisions: Mapping[DecisionId, DecisionSnapshot]`, `loaded_at`.
- `ConversationMessage` (`:93-103`): `{role, content, emitted_at}` — decoded from `session_events` payloads.
- Derived helpers: `current_job` (`:161`), `next_job` (`:179`), `latest_trial` (`:214`), `find_trial` (`:226`).
- Docstring (`:1-23`): all types frozen; NO DB-loading factories live here — the ctx-loader layer owns loading. Spec authority: `.trellis/spec/backend/L4/domain-types.md § app/core/context.py`.

### 2. Per-turn assembly — `app/session/orchestrator.py`

- Called from `_run_turn`: `orchestrator.py:336` (`ctx = await self._load_session_context(session_id, turn_input)`).
- `_load_session_context` (`:487-553`), single tx, serial queries:
  1. `tx.sessions.get_by_id` (`:523`)
  2. `tx.experiments.list_by_session` (`:526`)
  3. `tx.decisions.get_pending_by_session` (`:527`)
  4. `tx.session_events.read_recent_conversation(session_id, limit=50)` (`:528`) — **this is the "recent conversation" read around line 528**
  5. active plan → `tx.jobs.list_by_plan` → per-job `tx.trials.list_by_job` (`:534-542`)
  - Returns `SessionContext(...)` at `:544-553`; `conversation_history=decode_history(recent_events)` at `:552`.
- `decode_history` (`:570-599`): filters to `CONVERSATION_EVENT_KINDS = {"user_message_submitted", "text_done"}` (`app/repositories/session_events_repo.py:47-49`), reads `payload["text"]` only, maps `user_message_submitted → role="user"`. **Any extra field added to `UserMessageSubmittedEvent`'s payload is silently ignored by this decode unless deliberately surfaced.**
- **Threading a new field**: add the field to `SessionContext`, load it here (`:487-553`) inside the same tx. `del turn_input` at `:521` — all turn kinds get the same loader shape.

### 3. Into the graph — `Runtime` and `GraphState`

- `app/runtime/runtime.py:137`: `state = GraphState(ctx=ctx, turn=turn)`.
- `GraphState.ctx: SessionContext` — `app/runtime/types/state.py:53` (frozen per D40; `arbitrary_types_allowed`).

### 4. Specialist projection — reception_node → `SpecialistDispatchInputs` → `SpecialistState`

- `SpecialistDispatchInputs` TypedDict (`app/runtime/types/dispatch.py:27-64`): required `ctx / task_id / specialist_kind / current_phase / form_confirm_payload`; optional `params_draft / params_validated / params_confirmed / cancel_confirmed / last_form_snapshot / lab_task_id / prior_is_robot_tlc`.
- Draft seeding in `reception_node.py`:
  - FORM_CONFIRM(params): validate `form_values` against `CCParamsForm/REParamsForm/TLCParamsForm` and seed `params_draft` (`reception_node.py:366-385`, write at `:381`).
  - Cross-turn re-entry: `_extract_trial_flags_for_dispatch` (`:393-440`) re-seeds `params_draft` from **persisted `trials.params` as the whole blob** (`:437-438`). This is the second channel: anything written to `trials.params` before the turn reaches `SpecialistState.params_draft` at entry.
  - TLC→CC carry-forward: `bundle["params_draft"] = {"from_user": carried}` (`:698`); `prior_is_robot_tlc` (`:705-706`).
- `SpecialistState` (`app/runtime/types/specialist.py:199`): `ctx` at `:210` ("the same frozen ctx as the top-level GraphState"); `params_draft` with section-wise `_merge_params_draft` reducer (`:32-61`, field at `:258`).
- `ObjectiveSubgraphState` analog: `app/runtime/types/objective_subgraph_state.py:45` (ctx `:58`, `objective_draft` `:95`). Objective projection is thinner — `factory.py:282-297` seeds only `{ctx, experiment_id, form_confirm_payload}` (NO draft seed; see objective-draft-precedent.md caveat).

### 5. Prompt assembly — `app/runtime/middleware/dynamic_prompts.py`

- Four `@dynamic_prompt` middlewares: `cc_dynamic_prompt` (`:596-612`), `re_dynamic_prompt` (`:615-621`), `tlc_dynamic_prompt` (`:624-630`), `objective_dynamic_prompt` (`:633-647`). Each composes `{header}\n\n{phase_instructions}` from `request.state`.
- State readers (dict-or-typed defensive): `_resolve_phase` (`:448-457`), `_resolve_prior_is_robot_tlc` (`:460-471`), `_resolve_ctx_and_task_id` (`:489-504`) — **this pulls the frozen `SessionContext` and `task_id` straight off request state**.
- **The exact precedent to clone for a chemist-draft block**: `_extract_prior_step_params` (`:542-579`) walks `ctx.find_trial(task_id) → ctx.jobs → prior job's latest trial's params["from_user"]` and `_render_from_user` (`:520-539`) renders it as short `key: value` lines; `_maybe_prior_step_block` (`:582-593`) appends `"PRIOR STEP CONTEXT:\n{prior}\n{_REUSE_RULE}"` ONLY in `collecting_params` phase, shared by cc/re/tlc so wording can't desync.
- Structured-blob hygiene: `_PROSE_EXCLUDED_FROM_USER_KEYS = {"tlc_result", "tlc_file_key"}` (`:517`) — structured fields NEVER stringified into prompt; they flow via the code carry-forward instead. A chemist-draft prompt block must follow the same rule.
- The docstring at `:12-14`: this middleware is the "sole authority for per-turn phase / flag context" — rehydrate appends no SystemMessage.
- Relevant behavioral rule already in the prompts: RE-RECOMMEND RULE ("when the chemist changes ANY from_user field after a recommendation exists → update then recommend again") at `:197-199` (CC), `:268-270` (TLC), `:350-353` (RE) — this is what the LLM is instructed to do once it *knows* about chemist edits.

### 6. Conversation-history channel (messages, not system prompt)

- `app/runtime/graphs/_rehydrate.py:21` `rebuild_messages_from_history` — `ctx.conversation_history` → `HumanMessage`/`AIMessage` list with deterministic `rehydrated-<sha1>` ids; used by `rehydrate_objective.py:28-40` and the cc/re/tlc + plan rehydrate nodes. If the draft were to travel as chat context instead of a system-prompt block, this is the projection that would need to render it — but note `decode_history` only reads `payload["text"]` (§2).

## Recommended threading path for `chemist_form_draft` (same-pattern)

1. `app/core/context.py` — add field to `SessionContext` (frozen dataclass).
2. `app/session/orchestrator.py:487-553` — load it in `_load_session_context` (same tx).
3. `app/runtime/middleware/dynamic_prompts.py` — a `_maybe_chemist_draft_block(request, phase)` clone of `_maybe_prior_step_block`, appended by all three specialist prompts (single shared helper, cc/re/tlc symmetric).
   - OR/AND: persist the draft into `trials.params` pre-turn and let the existing `reception_node.py:437` whole-blob re-seed carry it into `params_draft` (zero prompt work, but changes what "draft" means to the tools' merge; see overwrite-policy-surface.md).

## Caveats / Not Found

- `SpecialistState` boolean flags (`params_confirmed` etc.) are read via `getattr` on `TrialSnapshot` because the columns don't exist yet (`reception_node.py:409-423`, GAP-R7-02) — mirrors, not authority.
- `GraphState`/`SpecialistState` field rosters are spec-bound: `.trellis/spec/BIC-agent-service/backend/L3/state.md` §1/§2 (esp. `:241-246` documenting the seeding order) must be updated with any new field (Rule 10).
