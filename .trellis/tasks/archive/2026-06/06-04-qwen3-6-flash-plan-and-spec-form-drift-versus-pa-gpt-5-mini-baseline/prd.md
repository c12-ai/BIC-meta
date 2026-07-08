# Complete the SessionContext loader (`_load_session_context` full assembly)

## Status

**Planning** — re-scoped 2026-06-04 from the original "Qwen3.6-flash
plan-and-spec form drift" framing. The model swap (parent task
`06-03-provider-swap-to-qwen-via-chatdeepseek-and-surface-reasoning-to-sse`)
unmasked a pre-existing architectural gap: the per-turn `SessionContext`
loader has been shipping a half-populated `ctx` since ticket-1, and the
L3 specialist subgraphs depend on fields that are never written.

## Goal

`app/session/orchestrator.py:_load_session_context` (line 419) must
return a **complete** `SessionContext` matching the shape defined in
`app/core/context.py:SessionContext` (lines 114-138) and the spec at
`.trellis/spec/backend/L2/orchestrator.md` § `SessionContext` Loader.

Today the loader populates 4 of 7 fields. After this task `SessionContext`
has 6 fields (one deleted) and the loader populates all of them except
`loaded_at` (default_factory). No more selective projection; no more
"L3 only needs X today" — that pattern is exactly how we ended up here.

## Why now (motivation)

Three E2E failures from parent task v4 run + one manual-test symptom
(see `research/be-log-evidence-2026-06-04.md`) traced to the gap:

- `cc-re-chained-flow.spec.ts:124` — CC specialist produces zero tool
  calls post-plan-confirm; just narrates text. Spec form never renders.
- `task-progress-stream.spec.ts:70` — same shape as above.
- Drake's manual test — clicks Confirm Plan, watches CC text-narrate for
  3.5 minutes without a form, types `Draft a CC Spec for me` to work
  around it, and then hits the M4 admittance-reject mechanism.

Root cause (verified by reading
`app/runtime/graphs/specialists/rehydrate.py:35-75` + log inspection):
`rehydrate_specialist_state` iterates `state.ctx.conversation_history`
to rebuild the SubAgent's `messages` channel, but the field is the
dataclass default `tuple()`. The CC react agent receives only
`[cc_system_prompt, phase_snapshot_SystemMessage]` — no `HumanMessage`
echoing the user's original request. `pa/gpt-5-mini` was smart enough
to follow the cc system prompt's instruction ladder cold; `qwen3.6-flash`
defaults to chat.

The model swap is the **trigger** that surfaced the gap. The fix surface
is the loader, not the model.

## Scope — populate the 2 missing fields with real consumers; delete the unused one

`SessionContext` has 7 fields. Loader currently writes 4. Of the 3 missing:

| Field | Decision | Why |
|---|---|---|
| `conversation_history` | **Populate** via `session_events.read_recent` → `decode_history` projection | Real consumer: `rehydrate_specialist_state` / `plan/rehydrate.py` rebuild `messages` from this; current emptiness is the root cause of M3/M5 |
| `decisions` | **Populate** via `decisions.get_pending_by_session` | Real consumers: `form_confirm_gate`, fast-path decision-bridging, decision-expiry replay. Repo + `DecisionSnapshot` model already exist (`decisions_repo.py:28, 111`) |
| `current_focus` | **Delete** from `SessionContext` + remove `CurrentFocus` dataclass + update spec | No consumers in `app/`. Wrong shape for the actual dispatchers (`reception_node` needs `(kind, task_id, phase)`; `CurrentFocus` carries `(plan_id, task_id)`). Spec `L4/domain-types.md:184` says it's for "routing USER_MESSAGE turns" but routing is done by `route_entry` (turn-kind dispatch) and `reception_node` (phase/plan-cursor projection) — neither needs it. Rule 2 (Simplicity): delete dead field. |

After this change, `SessionContext` has 6 fields. Loader writes all of them
except `loaded_at` (default_factory).

## Tertiary refactor — slim down `rehydrate_specialist_state`

Today rehydrate does two things (`specialists/rehydrate.py:78-104`):
1. Project `ctx.conversation_history` → `messages` field
2. Inject a `[harness-injected phase snapshot]` SystemMessage with
   `current_phase` + 5 flag mirrors + `last_input_kind`

Step 2 is **duplicative**: `reception_node` already projects the same
flags into `SpecialistDispatchInputs` (see `reception_node.py:362-372`)
and the dynamic-prompt middleware (`cc_dynamic_prompt` /
`re_dynamic_prompt`) composes the per-phase system prompt at every
invoke. The harness SystemMessage is a third copy of state the LLM
already sees.

Refactor: keep step 1, drop step 2. After the refactor, rehydrate is
a ~10-line function that builds `messages` from `ctx.conversation_history`
and that's it. The phase snapshot disappears from the LLM's input —
phase info is already in the system prompt composed by the dynamic
prompt middleware.

Why bundle with this task: the cc/re LLM input changes anyway when
`ctx.conversation_history` starts being populated (the original bug fix).
Slim-down rides on the same E2E verification — testing both changes
together is no harder than testing each alone, and the unified PR is
cleaner than two near-back-to-back changes to the same node.

## Secondary refactor — merge in-flight task predicate + picker

`_has_in_flight_task` (route_after_admit.py:44-54) returns `bool`.
`_pick_in_flight_specialist` (reception_node.py:138-153) returns
`tuple[SpecialistKind | None, str | None, SpecialistPhase]`.
Both walk `ctx.tasks` looking for the first non-terminal task — identical
search, different return shapes. Merge into a single helper that returns
the full tuple; callers needing just the boolean use `result[0] is not None`.

New home: `app/runtime/graphs/in_flight.py` (small new module) or co-located
with `reception_node.py` since reception_node holds the dispatch picker
trio. Decide in jsonl curation.

## Out of Scope

- M2 — Planner re-call loop tightening (separate task; see
  research file). Real bug, different fix surface (planner prompt /
  model upgrade). Does not block the 2 of 3 E2E failures this task
  addresses.
- M4 — Qwen admittance-judge false-rejection (separate task). First
  step there is instrumentation: add `logger.info` in
  `user_admittance.py:113-122` to capture `verdict.reason` /
  `user_facing_message`. Then collect evidence. Then decide on a fix.
<!-- rehydrate slim-down moved IN SCOPE — see Scope § below -->
- Loosening FE test matchers — ruled out in brainstorm. The matchers
  (`#column-type`, `Sample amount`, `Confirm spec`, `Reject ... re-plan`)
  are canonical UI surfaces, not brittle assertions.
- Re-introducing `pa/gpt-5-mini` — parent task locked DashScope/Qwen
  as the provider. The loader fix is provider-agnostic.
- Bumping the FE `PLAN_PROPOSE_TIMEOUT_MS` — addresses M2 only, doesn't
  touch the loader.

## What I already know

- Loader: `app/session/orchestrator.py:_load_session_context` (line 419,
  called from `:325`). Single function, one transaction block.
- Repo for events: `app/repositories/session_events_repo.py:read_recent`
  exists (line 139). Used today only by SSE replay.
- Repo for decisions: needs to be located/verified — see Open Questions.
- Projection function: `decode_history(events) → tuple[ConversationMessage, ...]`
  does NOT exist yet. Needs to be written. Per the dataclass docstring
  at `context.py:91-95`, the consumer side (loader) owns decoding; the
  module owns only the shape.
- Spec for full assembly: `.trellis/spec/backend/L2/orchestrator.md`
  § `SessionContext` Loader — 5 parallel repo fetches, D13 history
  decode, D17 current_focus inference.
- Consumer side is already wired: `rehydrate_specialist_state`
  (`specialists/rehydrate.py:35-75`) and `plan/rehydrate.py` already
  iterate `ctx.conversation_history` and project to LangChain messages
  with `rehydrated-<sha1>` ids. No L3 changes required.

## Hypotheses already validated in brainstorm

- ~~H1 (schema drift)~~ — ruled out by logs (no `pydantic.ValidationError`
  on test day).
- ~~H2 (recursion_limit on cc/re)~~ — ruled out by grep (cap is
  planner-only).
- ~~H3 (model tier capacity)~~ — partially true (qwen3.6-flash is weaker)
  but not the root cause; the cc input shape is missing user context
  entirely, so no model could deterministically follow the ladder.
- ✅ **M5 (loader gap)** — confirmed by reading
  `orchestrator.py:443-444` + `:468-473` directly. The loader's
  `SessionContext(...)` constructor does not pass
  `conversation_history`, `decisions`, or `current_focus`.

## Resolved from auto-context (spec authority + repo inspection)

- **Q1 — pending_decisions repo**: ✅ exists. `app/repositories/decisions_repo.py:111`
  `get_pending_by_session(session_id) -> list[DecisionSnapshot]`. `DecisionSnapshot`
  pydantic model at `decisions_repo.py:28`. No new types to write.
- **Q2 — current_focus**: **delete the field**. Grep shows zero
  non-definition consumers in `app/`. Spec (`L4/domain-types.md:184`)
  claims it's for "routing USER_MESSAGE turns" but routing is actually
  split between `route_entry` (turn-kind dispatch) and `reception_node`
  (phase + plan-cursor projection); neither needs a struct of
  `(plan_id, task_id)`. The actual in-flight task picker
  (`reception_node._pick_in_flight_specialist`) returns
  `(kind, task_id, phase)` and walks `ctx.tasks` directly. Per Rule 2,
  delete dead field rather than ship dead data.
- **Q3 — read_recent limit**: `n=50` per `orchestrator.md:232`. Same
  default the repo already uses for SSE replay.
- **Q4 — event kinds for decode_history**: at minimum `text_done`
  (assistant) per spec; plus `user_message_submitted` (user) since the
  event already carries `text: str` verbatim
  (`app/events/orch_emitted.py:43-58`). The spec's "user-side D13 gap"
  noted at `orchestrator.md:245` is closeable today — the event exists.
  Other event kinds (`form_requested` / `form_confirmed` /
  `decision_resolved`) are out-of-band structured state, not
  conversational. Exclude.
- **Q5 — ordering**: by `session_seq` (BIGSERIAL, monotonic). The
  `read_recent` repo already orders by seq; the projection just iterates.
  `text_done` is already assembled — no streaming-fragment dedupe needed.
- **Q6 — loader concurrency**: spec at `orchestrator.md:226-232` shows
  parallel `asyncio.gather` for the 4 entity fetches + serial
  `read_recent` after. Current loader is fully serial. Convert to spec
  shape.

## Concrete fix shape

```python
async def _load_session_context(
    self, session_id: str, turn_input: TurnInput,
) -> SessionContext:
    async with self._persistence.transaction() as tx:
        session, plans, task_rows, decisions = await asyncio.gather(
            tx.sessions.get_by_id(session_id),
            tx.agent_plans.get_by_session(session_id),
            tx.agent_tasks.get_by_session(session_id),
            tx.decisions.get_pending_by_session(session_id),
        )
        if session is None:
            raise SessionNotFoundError(session_id)
        recent_events = await tx.session_events.read_recent(session_id, limit=50)
    return SessionContext(
        session_id=session_id,
        user_id=session.user_id,
        plan=_pick_active_plan(plans),
        tasks={row.task_id: row for row in task_rows},
        decisions={d.decision_id: d for d in decisions},
        conversation_history=decode_history(recent_events),
        # current_focus deleted (see Scope §); loaded_at defaults.
    )
```

(Spec diverges from this: spec at `orchestrator.md:220-243` still
includes `current_focus`. The spec update is part of this task — see
Spec edits below.)

## New code surface

1. **`decode_history`** lives **inline in `orchestrator.py`** as a
   public top-level function (no new file). Signature:
   `decode_history(events: list[SerializedEvent]) -> tuple[ConversationMessage, ...]`.
   Filters to `kind in {"user_message_submitted", "text_done"}`;
   parses `payload_json` with `json.loads`; maps to
   `ConversationMessage(role, content, emitted_at)` with
   `role = "user"` for `user_message_submitted` and
   `role = "assistant"` for `text_done` (regardless of source —
   planner / cc / re / query_agent all collapse to `"assistant"`;
   `rehydrate.py:71` only branches on `entry.role == "user"`, so a
   single non-user role is sufficient). **Reverses** the repo's DESC
   ordering to chronological before returning. Rationale for inline
   placement: only one caller today (`_load_session_context`); no
   need for a new module. If a second consumer (decision-history /
   audit replay / etc.) appears later, split then per Rule 2 (YAGNI).

2. **Merged in-flight picker** `_pick_in_flight_task(state) ->
   tuple[SpecialistKind, str, SpecialistPhase] | None` — combines
   current `_pick_in_flight_specialist` (reception_node.py:138-153) and
   `_has_in_flight_task` (route_after_admit.py:44-54). Single walk of
   `ctx.tasks`; returns `None` on miss instead of the current
   `(None, None, _INITIAL_PHASE)` sentinel (the `_INITIAL_PHASE`
   fallback was misleading — it's a "default phase for new tasks,"
   not a real phase of "no task exists"). Boolean callers use
   `result is not None`; tuple callers unpack with a guard
   (reception_node already uses this idiom at line 331). Home: keep
   in `reception_node.py` alongside the dispatch-picker trio
   (`_pick_terminal_task_specialist`, `_pick_next_planned_step`) for
   cohesion; `route_after_admit.py` imports it. Avoids a new module
   for one helper (Rule 2).

3. **`orchestrator.py:_load_session_context`** — rewritten: parallel
   `asyncio.gather` of 4 entity fetches + serial `read_recent` after;
   populates 5 of 6 remaining fields (`loaded_at` defaults). Removes
   `needs_plan` conditional at lines 446-459 (plans load on every turn,
   matching tasks/decisions parity). `TODO(loader-v2)` markers removed
   from module docstring (lines 11-13) and function docstring
   (line 443).

4. **Delete `CurrentFocus`** (hard delete — no deprecation shim, per
   global CLAUDE.md "no backward-compat code unless specified" + zero
   `app/` consumers): remove the dataclass from
   `app/core/context.py:64-73`, remove `"CurrentFocus"` from `__all__`
   (line 33), remove `current_focus` field from `SessionContext`
   (line 127). No imports to clean — grep showed zero non-definition
   references.

5. **Slim down `rehydrate_specialist_state`**
   (`app/runtime/graphs/specialists/rehydrate.py:78-104`): keep the
   messages-rebuild step; delete the `[harness-injected phase snapshot]`
   SystemMessage block (the 5 flag_snapshot_lines + the
   `last_input_kind` discriminator + the `phase_reminder` SystemMessage).
   Same edit applies symmetrically to `app/runtime/graphs/plan/rehydrate.py`
   if it carries the same snapshot block (verify during impl).
   Function returns `{"messages": history_messages}` only after the
   refactor.

## Spec edits (Rule 10 — code + spec same change set)

- `.trellis/spec/backend/L2/orchestrator.md:236, 246` — remove
  `current_focus=infer_current_focus(...)` from the loader code block;
  remove the D17-derived bullet.
- `.trellis/spec/backend/L4/domain-types.md:149, 167-168, 184` — remove
  `CurrentFocus` row from the type table; remove the `current_focus`
  field from the `SessionContext` example; remove the "used only for
  routing USER_MESSAGE turns" sentence.
- `.trellis/spec/backend/contracts.md:403` — mark D17 row as rescinded
  (or strip — pick during impl).
- `.trellis/spec/backend/L3/graphs.md` — update `rehydrate_specialist_state`
  description (search for "harness-injected phase snapshot" / "flag snapshot
  SystemMessage" / "trimmed flag-snapshot"); the snapshot SystemMessage no
  longer exists post-refactor.
- `.trellis/spec/backend/L3/state.md` — same (I-S-E and related sections
  reference the snapshot SystemMessage; verify and prune).

## Acceptance Criteria

- [ ] `SessionContext` has 6 fields (`CurrentFocus` dataclass removed)
- [ ] `_load_session_context` populates 5 of 6 fields (`loaded_at`
  defaults); no `default_factory` fall-through for `tasks` / `decisions`
  / `conversation_history`
- [ ] `decode_history` is a public top-level function in
  `app/session/orchestrator.py`; projects `user_message_submitted` +
  `text_done` events to chronological `ConversationMessage` tuple;
  unit tested
- [ ] `_pick_in_flight_task` is the single in-flight picker;
  `route_after_admit._has_in_flight_task` deleted;
  `reception_node._pick_in_flight_specialist` replaced
- [ ] `rehydrate_specialist_state` returns only the rebuilt
  `messages`; the `[harness-injected phase snapshot]` SystemMessage
  block is removed. Same for `plan/rehydrate.py` if it carries an
  equivalent block.
- [ ] `cc-re-chained-flow.spec.ts:124` passes
- [ ] `task-progress-stream.spec.ts:70` passes
- [ ] Parent task AC1 (`reasoning-streaming.spec.ts`) still passes
- [ ] No regression on currently-passing E2E specs
- [ ] Spec docs (`L2/orchestrator.md`, `L4/domain-types.md`,
  `contracts.md`) reflect shipped behavior — no `CurrentFocus` /
  `current_focus` / D17 references remain (Rule 10)

## Definition of Done

- Full FE Playwright suite passes (modulo `persist-bubbles-hard-refresh:111`
  which is M2, and `tlc-upload-chain:129` T2 which is the ChemEngine env flake)
- `TODO(loader-v2)` markers removed from `orchestrator.py`
- Unit tests for `decode_history`: empty events, single user message,
  user/assistant interleaving, DESC→chronological reversal,
  non-conversational event-kind filtering. **Fixture construction**
  uses the real event constructors (`UserMessageSubmittedEvent(...)`,
  `TextDoneEvent(...)`) + `.to_wire_payload()` to produce JSON exactly
  as the writer does, then wraps in `SerializedEvent(seq, kind,
  json.dumps(...).encode())`. Rationale (Rule 7): tests verify that
  the loader reads what the writer writes; hand-rolled JSON would
  silently pass through a payload-schema drift.
- Unit tests for merged `_pick_in_flight_task`: empty tasks dict, all
  terminal, one in-flight, multiple in-flight (deterministic pick
  order), non-cc/re task_type
- `pnpm exec playwright test` green (modulo known-out-of-scope failures
  above)
- `pytest` green on backend
- Backend lint / typecheck pass

## Technical Notes

- Authority for spec: `.trellis/spec/backend/L2/orchestrator.md` §
  `SessionContext` Loader (D13 + D17)
- Authority for downstream contract:
  `.trellis/spec/backend/L3/state.md` I-S-E, `L3/graphs.md` §2.2 (both
  already documented as if `ctx.n` / `ctx.conversation_history` is
  populated — the spec has been ahead of the code)
- The `rehydrated-<sha1>` id scheme in `specialists/rehydrate.py:60-75`
  is load-bearing for LangGraph's StreamMessagesHandler dedupe — do not
  touch it
- Read-only invariant on `ctx` (frozen dataclass) is preserved; this
  task only changes what gets written at load time
- `SessionEventsRepo.read_recent` returns `ORDER BY seq DESC` per
  `session_events_repo.py:142-143` ("caller decides whether to reverse
  for chronological consumption"). `decode_history` MUST reverse before
  emitting — `ConversationMessage` order must be oldest→newest so the
  SubAgent reads a coherent conversation.
- `SerializedEvent.payload_json` is raw UTF-8 bytes. `decode_history`
  parses locally with `json.loads(payload_json)` then reads `text` and
  `emitted_at` keys. Same pattern as
  `app/api/routers/sessions.py:306`.
- Cross-team contract note (Rule 10): this task changes the L2 ↔ L3
  contract surface in the "more populated" direction (ctx fields go
  from default `tuple()` / `{}` / `None` to actually-populated). The L3
  consumer side (`specialists/rehydrate.py`, `plan/rehydrate.py`) was
  designed for the populated shape. No L3 spec change required; L2
  spec at `orchestrator.md:220-243` is already accurate — code catches
  up to spec.

## Research References

- `research/be-log-evidence-2026-06-04.md` — full root-cause analysis
  with per-spec mechanism classification (M1–M5), session timelines,
  and supporting log line numbers. Read this first if revisiting scope.
