# Research: Fix seams for plateless-park loud path

- **Query**: How to fix plateless awaiting_confirmation park + failed-trial narration — code seams, test harness, blast radius
- **Scope**: internal
- **Date**: 2026-07-03

---

## Q1 — WARN + PROGRESS SEAM (plateless park)

### Where the silent return lives

`fast_path_handlers.py:450-451`:

```python
async with self._persistence.transaction() as tx:
    derived_key = await tx.trials.try_record_transition_announcement(
        new_payload.task_id,
        new_status,
    )
    if derived_key is None:
        return          # ← silent return; no warn, no event
    ...
    progress_event = TaskProgressEvent(...)
    session_seq = await tx.session_events.append(progress_event)
```

`_derive_transition_key` (`trials_repo.py:52-88`) returns `None` for
`new_status == "awaiting_confirmation"` (falls to the catch-all `return None`
at line 88). Nothing after that fires.

The warning in `try_record_transition_announcement` (`trials_repo.py:667-675`)
fires ONLY when `current_status in _TERMINAL_DB_STATUSES`. Plateless park is
`non-terminal`, so it stays fully silent.

### Cleanest fix location

**Option A (preferred, minimal blast radius)**: Add an explicit guard in
`EventIngress.handle_task_status` at `event_ingress.py:119-123`, BEFORE the
`NON_TERMINAL_STATUSES` dispatch. When
`status_value == AWAITING_CONFIRMATION and payload.image_url is None`:

1. `logger.warning(...)` — structured log (same pattern as
   `metric.task_status_regression_*` elsewhere).
2. `await self._fast_path.emit_terminal_progress(...)` or
   `await self._fast_path.handle_task_status_transition(...)` for a
   `TaskProgressEvent` (see below), then `return`.

This is a 6-8 line addition in `event_ingress.py` with NO change to
`fast_path_handlers`, `trials_repo._derive_transition_key`, or the FE contract.

**Option B**: Add `awaiting_confirmation` to `_derive_transition_key` so it
returns a key. BUT this causes `handle_task_status_transition` to call
`try_record_transition_announcement` which does a `SELECT ... FOR UPDATE` and
a conditional UPDATE — that machinery was designed for the `pending/waiting/
in_progress` state machine. Adding a novel key would require audit of
every caller. This is more invasive and option A is simpler.

### How TaskProgressEvent is constructed (the exact pattern to reuse)

In `fast_path_handlers.py:461-468`:

```python
progress_event = TaskProgressEvent(
    session_id=session_id,
    trial_id=new_payload.task_id,
    status=new_status,
    steps=serialized_steps,
    step_events=serialized_step_events,
)
session_seq = await tx.session_events.append(progress_event)
```

Fields (`bypass_emitted.py:27-66`):
- `kind = "task_progress"` (wire constant, locked by FE contract)
- `trial_id: str`
- `status: str`
- `steps: list[dict]`
- `step_events: list[dict]` (ride-only, not persisted)
- `error_message: str | None`

The emit path is `tx.session_events.append(event)` inside the transaction,
then `broadcaster.emit(session_id, event, session_seq=session_seq)` post-commit.

The existing `emit_terminal_progress` helper at `fast_path_handlers.py:484-532`
already does the append+broadcast without needing a derived_key. For the
plateless park, calling this helper from `event_ingress` with
`terminal_status=TaskStatus.AWAITING_CONFIRMATION.value` is the cleanest
reuse — it's the exact same call `_handle_round_done` makes at
`event_ingress.py:180-186`.

### Does this require FE contract change or shared-types change?

**No.** `TaskProgressEvent` with `kind="task_progress"` is already an
established wire shape. The FE already renders it. Emitting it with
`status="awaiting_confirmation"` and `image_url=None` (note: `TaskProgressEvent`
has no `image_url` field — it is purely from the MQ payload, not on the event)
is purely additive. No shared-types change, no FE contract change.

Spec anchor: `contracts.md` §1 "session_events is the authoritative event log";
§ I1 append-before-emit. The new emit follows the same pattern as all other
bypass events.

---

## Q2 — CHAT-VISIBLE SEAM (plateless park)

### How the terminal path submits a turn → chat message

`event_ingress._handle_terminal` (`event_ingress.py:197-268`):
1. Commits `trials` row to terminal via `apply_terminal_from_lab`.
2. Calls `fast_path.emit_terminal_progress(...)` → `TaskProgressEvent` appended.
3. Builds a `TurnInput(kind=TurnKind.TASK_TERMINAL, ...)` and calls
   `orchestrator.submit_turn(session_id, turn)`.

The TASK_TERMINAL turn drives the L3 subgraph: `reception_node` routes to the
TLC specialist → `rehydrate_specialist_state` → `react_agent_node` →
`_post_react_route` → `narrate`. The LLM narration emits a `TextDoneEvent`
which renders in the chat thread.

### Could plateless park submit a TASK_TERMINAL turn the same way?

Yes, but with complications:

- **With `terminal_status=None`**: This is exactly what `_handle_round_done`
  does. On a TASK_TERMINAL with `terminal_status=None` and a `conducting` trial
  whose `status == "awaiting_confirmation"` but `image_url` was NOT persisted,
  the `_post_react_route` gate at `tlc.py:403-410` would check
  `trial.status.lower() == _TLC_ROUND_DONE_STATUS` (=="awaiting_confirmation")
  → TRUE → routes to `evaluate_tlc_result`. But `evaluate_tlc_result` at
  `tlc.py:709+` calls `from_user.tlc_round_image_url or mock://...` — it would
  silently use the mock URL, which is wrong.

- **With `terminal_status=TerminalStatus.FAILED`**: Would require writing the
  trial to `failed` via `apply_terminal_from_lab` first (like `_handle_terminal`
  does for a lab-failed task). Then the TASK_TERMINAL turn would arrive with a
  `failed` terminal status. The L3 TLC graph's `_post_react_route` check gates
  on `trial.status == "awaiting_confirmation"` for the Rf-loop, so a `failed`
  trial would fall through to `narrate`, which gives the chemist a LLM response.
  But the narrate prompt would be `_NARRATE_PROMPT_TEXT_REPLY` (generic) unless
  we add a special-case.

### Assessment: turn-submission vs progress-event-only

| Option | Effort | Risk | Chat visible | Recovery path |
|---|---|---|---|---|
| warn + `TaskProgressEvent` only | XS (6-8 lines in event_ingress) | Very low | No (workspace strip only) | None — trial stays frozen, manual retry needed |
| warn + `TaskProgressEvent` + TASK_TERMINAL(failed) | S (15-20 lines, write trial to failed first) | Low-medium (requires `apply_terminal_from_lab` call in the plateless branch) | Yes — narrate runs | Chemist sees failure, can restart |
| warn + `TaskProgressEvent` + TASK_TERMINAL(None) + new narrate branch | M (requires new `_build_narrate_prompt` branch in tlc.py, image_url guard in evaluate_tlc_result) | Medium | Yes | Chemist prompt for re-photo (HITL) |

**Recommendation (subject to Drake's R2 decision)**: The simplest complete fix
is the middle option — write the trial to `failed` (mirroring a genuine lab
failure), emit the progress event, and submit a `TASK_TERMINAL(failed)` turn.
The LLM narrates with the generic prompt (or a new specific prompt — see Q3).
This requires no new turn-kind, no changes to `_post_react_route`, and no
FE contract changes.

---

## Q3 — FAILED-NARRATION SEAM (post-dispatch lab failure)

### Current routing for a conducting trial that is `failed`

`tlc.py:351-411` `_post_react_route`:

```python
if state.current_phase == "conducting":
    trial = state.ctx.find_trial(state.task_id)
    if (
        trial is not None
        and trial.status.lower() == _TLC_ROUND_DONE_STATUS  # "awaiting_confirmation"
        and not trial.analysis_completed
    ):
        return "evaluate_tlc_result"
return "narrate"   # ← failed trial falls here
```

A `failed` trial at `conducting` does NOT match `_TLC_ROUND_DONE_STATUS`
("awaiting_confirmation"), so it falls through to `narrate`. That is correct
routing; the problem is the narrate prompt selected.

### Prompt selection at `_build_narrate_prompt` (tlc.py:552-561)

```python
def _build_narrate_prompt(state: SpecialistState) -> str:
    tool_name = state.last_tool_name or ""
    if tool_name == TOOL_NAME_SUBMIT_L4 and _submit_failed(state):
        return _NARRATE_PROMPT_SUBMIT_FAILED
    return _NARRATE_PROMPT_BY_TOOL.get(tool_name, _NARRATE_PROMPT_TEXT_REPLY)
```

For a `TASK_TERMINAL` turn driven by a lab-side MQ `failed`:
- `last_tool_name` is `None` (the turn is a system MQ delivery, no LLM tool
  ran in THIS turn).
- `_submit_failed(state)` checks `_last_tool_content(state)` for the regex
  `r"^submit_l4_execution FAILED:"` — which only appears in the ToolMessage from
  the dispatch tool run (a prior turn). For a NEW `TASK_TERMINAL` turn, the
  message history contains that prior tool message, but `_last_tool_content`
  returns the LAST ToolMessage in `state.messages` — and in a TASK_TERMINAL
  turn the messages are rebuilt from `ctx.conversation_history` (rehydrate).
  The last ToolMessage could be the prior dispatch's ToolMessage if it's still
  in history — this is uncertain and unreliable.
- Therefore `_build_narrate_prompt` falls to `_NARRATE_PROMPT_TEXT_REPLY`
  (generic "answer the chemist directly"). The LLM reads the conversation history
  which says the task is running → produces "standing by" responses.

### What state IS available at narrate time for a post-dispatch failure?

At `_narrate_node` entry (`tlc.py:593-612`), the graph state contains:
- `state.ctx` (frozen `SessionContext`): the trial row IS reloaded by the
  orchestrator before the turn runs. At this point
  `state.ctx.find_trial(state.task_id).status == "failed"` and
  `state.ctx.find_trial(state.task_id).error_message` contains the lab's error
  string (persisted by `apply_terminal_from_lab` at `event_ingress.py:224`).
- `state.current_phase == "conducting"` (set by reception_node from
  `trial.phase`, which is still `conducting` — phase does not advance on failure).
- `state.task_id` — the trial UUID.
- `state.messages` — rebuilt from conversation history (rehydrate).

### Fix for failed-narration prompt

Add a new branch to `_build_narrate_prompt`:

```python
def _build_narrate_prompt(state: SpecialistState) -> str:
    tool_name = state.last_tool_name or ""
    if tool_name == TOOL_NAME_SUBMIT_L4 and _submit_failed(state):
        return _NARRATE_PROMPT_SUBMIT_FAILED
    # Post-dispatch MQ failure: trial reached "failed" while conducting.
    # last_tool_name is None (MQ delivery, no tool ran this turn).
    if tool_name == "" and state.current_phase == "conducting":
        trial = state.ctx.find_trial(state.task_id)
        if trial is not None and trial.status == "failed":
            return _NARRATE_PROMPT_LAB_TASK_FAILED   # new constant
    return _NARRATE_PROMPT_BY_TOOL.get(tool_name, _NARRATE_PROMPT_TEXT_REPLY)
```

New prompt template (mirrors `_NARRATE_PROMPT_SUBMIT_FAILED` style):

```python
_NARRATE_PROMPT_LAB_TASK_FAILED = (
    "The lab reported that the TLC task FAILED while it was running "
    "(status=failed from the robot/instrument). The trial's error_message "
    "in the conversation context carries the lab diagnostic. In 1-2 "
    "chemist-facing sentences: (a) acknowledge that the running TLC task "
    "failed, (b) cite the error diagnostic if available, and "
    "(c) suggest the chemist may edit the params form and ask to retry. "
    "Do NOT promise an automatic retry. Do not call any tools -- reply "
    "with text only."
)
```

The LLM gets the conversation history which includes the `TaskProgressEvent`
error message context — but actually, the LLM does NOT see raw DB fields; it
sees `state.messages`. The error_message from the MQ payload IS carried in
the `TaskProgressEvent` wire payload (`error_message` field on `TaskProgressEvent`
schema at `bypass_emitted.py:66`), but whether that event's content reaches the
`messages` channel depends on the dispatcher/rebuild — it's a session_event, not
a chat message. The LLM may not directly see the error text.

**Practical approach**: The prompt can instruct the LLM to acknowledge the failure
without citing a specific error. The specific error is surfaced to the chemist via
the FE workspace (which renders `TaskProgressEvent.error_message`) — the chat
narration just needs to break the "standing by" illusion.

---

## Q4 — TEST HARNESS

### How fast_path_handlers is tested today

- `tests/unit/test_fast_path_handlers_system.py` — runs against a REAL test DB
  (`db_session: AsyncSession` pytest fixture). Uses `Persistence` wired to the
  test engine. Orchestrator and Broadcaster are `AsyncMock` fakes. No mocking
  of `TrialsRepo` or `SessionEventsRepo`.
- `tests/unit/test_event_ingress.py` — also runs against a real test DB. Seeds
  full hierarchy (sessions→experiments→plans→jobs→trials) via `_seed_trial`.
  The FAST PATH (`fast_path`) is a `MagicMock` with `AsyncMock` methods. The
  orchestrator is `AsyncMock`. EventIngress is real.

### Current gap (test_event_ingress.py:236)

`test_round_awaiting_confirm_without_image_is_progress_only` at line 236 asserts:

```python
fast_path.handle_task_status_transition.assert_awaited_once_with(
    session_id="sess-1",
    new_payload=payload,
)
orchestrator.submit_turn.assert_not_awaited()
```

It confirms the routing (delegates to fast_path mock) but because `fast_path`
is a MagicMock, the REAL `handle_task_status_transition` never runs. The silent
return at `fast_path_handlers.py:450-451` is invisible to this test.

### Non-mocked regression test shape

**Pattern**: Mirror `test_non_terminal_delegates_to_fast_path` but use the REAL
`FastPathHandlers` wired to the test DB (like `test_fast_path_handlers_system.py`
does). The fix should emit a `TaskProgressEvent`; the test asserts the event
was appended to `session_events`.

```python
async def test_plateless_park_emits_warn_and_progress(
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """plateless awaiting_confirmation MUST emit a warn log + TaskProgressEvent.

    WHY (Rule 7): the silent return (fast_path_handlers.py:450-451) left the
    trial frozen with zero events — the chemist and FE saw "in progress" forever.
    After the fix, the warn is observable in logs and the event is durable in
    session_events so the FE workspace step strip reflects the anomaly.
    """
    await _seed_trial(db_session)
    # Wire REAL FastPathHandlers (not a mock) so the silent return is observable.
    from app.session.fast_path_handlers import FastPathHandlers
    from app.session.broadcaster import Broadcaster  # or AsyncMock
    real_fast_path = FastPathHandlers(
        persistence=_persistence_from_session(db_session),
        broadcaster=AsyncMock(),
        orchestrator=AsyncMock(is_accepting=MagicMock(return_value=True)),
        mind=AsyncMock(),
        minio_client=AsyncMock(),
    )
    orchestrator = MagicMock()
    orchestrator.submit_turn = AsyncMock()
    ingress = EventIngress(
        persistence=_persistence_from_session(db_session),
        fast_path=real_fast_path,
        orchestrator=orchestrator,
    )
    payload = _payload("trial-1", TaskStatus.AWAITING_CONFIRMATION, image_url=None)

    import logging
    with caplog.at_level(logging.WARNING, logger="app.session.event_ingress"):
        await ingress.handle_task_status(payload)

    # MUST: warn log emitted (not silent).
    assert any("plateless" in r.message.lower() or "awaiting_confirmation" in r.message for r in caplog.records)
    # MUST: at least one session_event row appended (TaskProgressEvent).
    from app.repositories.session_events_repo import SessionEventsRepo
    events = await SessionEventsRepo(db_session).list_by_session("sess-1")
    assert any(e.get("kind") == "task_progress" for e in events)
    # MUST NOT: submit_turn fired (no TASK_TERMINAL turn for the simple warn path).
    orchestrator.submit_turn.assert_not_awaited()
```

Note: if the fix writes the trial to `failed` and submits a TASK_TERMINAL turn
(middle option from Q2), then `orchestrator.submit_turn.assert_awaited_once()`
would be the correct assertion instead.

### Failed-trial narration regression test shape

This is an L3 graph test. Ideal fixture: a session with a TLC trial in
`conducting` phase and `status="failed"`, turn kind `TASK_TERMINAL`. Assert
the narration prompt selected is NOT `_NARRATE_PROMPT_TEXT_REPLY`.

In practice the simplest approach is a unit test on `_build_narrate_prompt`
directly, since it's a pure function of `SpecialistState`:

```python
def test_build_narrate_prompt_failed_conducting_trial():
    """Post-dispatch MQ failure selects the lab-failed narrate prompt, not the
    generic text-reply prompt.

    WHY (Rule 7): the generic prompt made the LLM say "standing by" even when
    the trial.status was "failed" — chemist got zero signal of the failure.
    """
    # Build a minimal SpecialistState with conducting phase + failed trial.
    # ctx.find_trial returns a trial with status="failed".
    ...
    prompt = _build_narrate_prompt(state)
    assert prompt is _NARRATE_PROMPT_LAB_TASK_FAILED
    assert _NARRATE_PROMPT_TEXT_REPLY not in prompt
```

---

## Q5 — BLAST RADIUS

### Who calls `_derive_transition_key` / relies on None-return for `awaiting_confirmation`

`_derive_transition_key` is a **private** function in `trials_repo.py`. It is
called ONLY from `try_record_transition_announcement` (`trials_repo.py:660-664`).

`try_record_transition_announcement` is called ONLY from:
- `fast_path_handlers.py:446` inside `handle_task_status_transition`.

`handle_task_status_transition` is called ONLY from:
- `event_ingress.py:120-123` for `status_value in NON_TERMINAL_STATUSES`.

The `NON_TERMINAL_STATUSES` set (`event_ingress.py:42-49`) INCLUDES
`TaskStatus.AWAITING_CONFIRMATION.value`, so any plateless `awaiting_confirmation`
goes through this path today. If we add a guard BEFORE the
`NON_TERMINAL_STATUSES` branch (Option A from Q1), the with-image path is
completely unaffected — that path is already short-circuited at
`event_ingress.py:115` and goes to `_handle_round_done`.

### Would adding an `awaiting_confirmation` transition key to `_derive_transition_key` cause double-emit?

If we were to add `awaiting_confirmation` to `_derive_transition_key` (Option B):
- The with-image path never reaches `_derive_transition_key` (it's caught at
  line 115 and returns after `_handle_round_done`). So NO double-emit for
  the with-image path.
- The plateless path would then emit a `TaskProgressEvent` via
  `handle_task_status_transition` (the existing machinery). But `_derive_transition_key`
  would also write to `announced_transitions`, which for an `awaiting_confirmation`
  status has no defined semantics in the existing state machine. This is a state
  machine hygiene concern but not a functional double-emit.

**Conclusion**: Option A (guard in `event_ingress.py`) has ZERO blast radius on
`_derive_transition_key` callers, transition key semantics, or the with-image path.

### Side note: `list_inprogress_with_lab_task_id` (reconciler gap-1 path B)

At `trials_repo.py:583-600`, the reconciler scans `_NON_TERMINAL_DB_STATUSES`
which is `(pending, waiting, in_progress)`. It explicitly excludes
`awaiting_confirmation`. A plateless-parked trial would NOT be recovered by
gap-1 path B (it's not in the scan set). This is another reason the fix must
make the plateless park loud immediately, not rely on reconciler recovery.

---

## Summary of Seams

| Seam | Location | Effort | Notes |
|---|---|---|---|
| Plateless park warn log | `event_ingress.py` new branch before line 119 | XS | `logger.warning(...)` — 1 line |
| Plateless park `TaskProgressEvent` | `event_ingress.py` → call `fast_path.emit_terminal_progress(...)` | XS | Exact same call as `_handle_round_done` line 180 |
| Plateless park TASK_TERMINAL(failed) turn | `event_ingress.py` → `apply_terminal_from_lab` + `submit_turn` | S | Requires deciding to fail the trial |
| Failed-trial narrate prompt | `tlc.py:552-561` `_build_narrate_prompt` + new prompt constant | S | Read `trial.status + current_phase` off state |
| Regression test (plateless park) | New test in `test_event_ingress.py` using REAL FastPathHandlers | S | Needs `_seed_trial` + `SessionEventsRepo` assertion |
| Regression test (failed narration) | Unit test on `_build_narrate_prompt` in tlc tests | XS | Pure-function test of the prompt selector |

---

## Recommended Option Set for R2 (Drake's decision)

### Option 1: Progress-event-only (minimal, no chat message)
- Emit `warn` log + `TaskProgressEvent(status="awaiting_confirmation")` in
  `event_ingress.py`. Trial stays `awaiting_confirmation` (non-terminal, not
  failed).
- FE workspace strip shows the anomaly state; no chat message to the chemist.
- Chemist must notice the workspace strip and ask the agent what happened.
- **Effort**: XS (6-8 lines). **Risk**: Very low. **Chat visible**: No.
- Reconciler gap-1 path B does NOT cover this (scan excludes awaiting_confirmation);
  if the service restarts with the trial in this state it would be stuck. Needs
  reconciler extension or a timeout to eventually fail it.

### Option 2: Progress-event + fail the trial + TASK_TERMINAL turn (recommended)
- Write the trial to `failed` via `apply_terminal_from_lab` (same as real terminal
  path). Emit `TaskProgressEvent(status="failed")`. Submit `TASK_TERMINAL(failed)`.
- TLC graph gets the TASK_TERMINAL turn; `_post_react_route` routes to `narrate`
  (trial is `failed`, not `awaiting_confirmation` → does NOT enter Rf-retry loop).
- With Q3's `_build_narrate_prompt` fix, the chemist gets a specific "TLC task
  failed" chat message.
- Reconciler gap-1 path A (list_terminal_unanalyzed) would catch this if the
  TASK_TERMINAL turn was never processed.
- **Effort**: S (20 lines across event_ingress.py + tlc.py). **Risk**: Low.
  **Chat visible**: Yes, with specific failure message.

### Option 3: Progress-event + TASK_TERMINAL(None) + new HITL prompt for retry-photo
- Treat the plateless park as a re-photo request: submit `TASK_TERMINAL(None)`
  (same as `_handle_round_done` for a with-image park), add a guard in
  `_evaluate_tlc_result_node` when `image_url` is absent to branch to a new
  `emit_retry_photo_request` node, show the chemist a HITL form to upload the
  plate photo manually.
- **Effort**: L (multiple new nodes/routes in tlc.py, possibly new form type).
  **Risk**: Medium. **Chat visible**: Yes, HITL form.

**Bottom line for the implement agent**: Drake decides between Option 1/2/3 (R2).
Options 1 and 2 can be implemented independently; Option 2 subsumes Option 1.
The failed-narration fix (Q3) applies in Option 2 and 3 only.

## Caveats / Not Found

- `SessionEventsRepo.list_by_session` was referenced in the test proposal but not
  confirmed to exist by name — verify the actual helper method name before
  writing the test.
- The `TaskProgressEvent.error_message` field IS on the schema
  (`bypass_emitted.py:66`) but whether the FE renders it in the workspace step
  strip needs FE-side verification.
- Option 3 (HITL re-photo) was not researched in depth; the implement agent
  should do its own design before choosing it.
