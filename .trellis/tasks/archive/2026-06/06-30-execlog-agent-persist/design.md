# Design — Agent: step-event passthrough

Rescoped: **no persist.** Two thin additions — a live SSE field + a history proxy endpoint.

## Part A — live: `step_events` on `TaskProgressEvent`

`app/events/bypass_emitted.py` — add a field, leave `apply` writing only what it does today:

```python
class TaskProgressEvent(BypassEventBase):
    kind = "task_progress"
    trial_id: str = ""
    lab_task_id: str = ""
    status: str = ""
    steps: list[dict[str, Any]] = []
    step_events: list[dict[str, Any]] = []   # NEW — ordered timeline; ride-only, NOT persisted
    error_message: str | None = None

    async def apply(self, tx):
        await tx.trials.update_fields(
            trial_id=self.trial_id,
            fields={"status": ..., "steps": ..., "error_message": ...},  # UNCHANGED — no step_events
        )
```

`step_events` is `list[dict]` (not `list[TaskStepEvent]`) to match the existing `steps` field
convention (Rule 8) and because the event is serialized to JSONB in `session_events`. It rides the
payload only: live SSE + durable `session_events` replay on reconnect (AC5 — free).

Populate at BOTH construction sites in `app/session/fast_path_handlers.py`:
- `handle_task_status_transition` (`:457`): alongside `serialized_steps`, add
  `serialized_step_events = [e.model_dump(mode="json") for e in new_payload.step_events]` and pass
  `step_events=serialized_step_events`.
- `emit_terminal_progress` (`:479`/`:500`): it takes `steps: list[dict]` as an arg today. Add a
  `step_events: list[dict]` arg and pass it through. Its two callers in `event_ingress.py`
  (`:177` round-done, `:243` terminal) already build `serialized_steps = [s.model_dump() for s in
  payload.steps]` — add the sibling `serialized_step_events = [e.model_dump(mode="json") for e in
  payload.step_events]` and pass it.

That's every path `task_progress` is emitted. No new event kind (FE reads one new field on an event
it already handles — confirmed with Drake).

## Part B — history proxy endpoint

### B1. LabClient method (`app/infrastructure/lab_client.py`)
Mirror `query_task_status` exactly:
```python
async def query_step_events(self, lab_task_id: str) -> list[TaskStepEvent]:
    try:
        response = await self._client.get(f"/tasks/{lab_task_id}/step-events")
        response.raise_for_status()
        return [TaskStepEvent.model_validate(x) for x in response.json()]
    except httpx.HTTPError as e:
        raise LabClientError(f"query_step_events failed: {e}") from e
```
Add the signature to `LabClientProtocol` (`:72`) too. Import `TaskStepEvent` from
`bic_shared_types.experiment_task.mq.task_status`.

### B2. DI provider (`app/api/dependencies.py`)
```python
def get_lab_client(request: Request) -> LabClientProtocol:
    client = request.app.state.lab_client
    if client is None:
        raise RuntimeError("lab_client not initialized")   # match existing providers' guard tone
    return client
```

### B3. Route — nested in the existing `sessions` router (`app/api/routers/sessions.py`)
`GET /sessions/{session_id}/trials/{trial_id}/step-events` → `response_model=list[TaskStepEvent]`:
1. Resolve `trial_id → lab_task_id` via the session service / trials repo (the snapshot already
   reads `lab_task_id` per trial — reuse that resolver; confirm the exact method at implement time).
2. **trial unknown** → `404` (match existing not-found handling in this router).
3. **trial known but `lab_task_id is None`** (not yet dispatched to Lab) → return `200 []`
   (AC4 decision: an undispatched trial simply has no timeline yet — empty, not an error; mirrors
   the Lab readapi's "known task, no steps → []" semantics). Document this.
4. Else `return await lab_client.query_step_events(lab_task_id)`.

`session_id` in the path is consistent with the router grouping (Drake's choice) though `trial_id`
alone is unique; we do NOT need to cross-check session ownership for MVP (no auth), but a cheap
"trial belongs to session" guard can be added if the resolver already scopes by session — note it,
don't over-build.

## Why no persist is correct here (first-principles)

The FE's durable replay source is `session_events`, not `trials`. `step_events` on
`TaskProgressEvent` is already persisted in `session_events` (the event payload is JSONB). So live
+ reconnect are both covered with **zero** new Agent storage. History beyond the session event
window (e.g. deep-link to an old trial) comes from Lab via the proxy — Lab's EventLog is the
durable store. A `trials.step_events` column would duplicate the EventLog truth for no gain (and
re-introduce the dual-source problem the explore flagged: `trials.steps` vs `trials.result.steps`).

## Compatibility / no-regression
- `steps` snapshot path untouched → workspace step strip unaffected (AC6).
- `TaskProgressEvent.apply` unchanged → no new `trials` write (AC2).
- Additive field on the event → old persisted `session_events` rows (no `step_events`) replay fine
  (defaults to `[]`).

## Spec (Rule 10)
- `.trellis/spec/BIC-agent-service/backend/L2/event-ingress.md` (and/or `contracts.md`): document
  `step_events` on `task_progress` (ride-only, not persisted) + the new proxy endpoint.
- `bypass_emitted.py` `TaskProgressEvent` docstring: note `step_events` is ride-only.

## Out of scope
- FE consumption → fe-timeline.
