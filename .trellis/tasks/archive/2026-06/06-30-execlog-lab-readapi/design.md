# Design — Lab: GET step-events read endpoint

## Everything needed already exists (this is a thin assembly)

From the lab-publish child, in `BIC-lab-service`:
- `EventLogRepository.get_task_step_events(task_id)` — ordered STEP_* rows (`event.py:206`).
- `EventService.get_task_step_events(task_id)` — pass-through (`event_service.py:446`).
- `TaskService._to_step_event(e: EventLog) -> TaskStepEvent` — **already a `@staticmethod`**
  (`task_service.py:558`). Reusable as-is; no relocation needed (resolves PRD R3).
- `TaskService.get_task(task_id) -> Task` (`task_service.py:489`) — for the 404 check.

So the endpoint = new service method + new route. No new query, no new mapper, no new type.

## Service method

`TaskService.list_task_step_events(self, task_id: UUID) -> list[TaskStepEvent]`:

```python
async def list_task_step_events(self, task_id: UUID) -> list[TaskStepEvent]:
    task = await self.tasks.get(task_id)
    if task is None:
        return []            # router maps the 404; see note below
    rows = await self.events.get_task_step_events(task_id)
    return [self._to_step_event(e) for e in rows]
```

404 handling: mirror the existing `get_task` route. The router already does the
"`not_found_error()` if task missing" pattern — so either the service raises (matching
`get_task`) or the router checks existence first. **Decision: router-level existence check**
to match `tasks.py:108 get_task` exactly (it calls `service.get_task` which raises
`not_found_error` on miss). Reuse that: the route first resolves the task (404 if absent),
then returns the timeline (`200 []` if the task exists but has no STEP_* rows yet — R4).

## Route

`app/api/routers/tasks.py`, mirroring `GET /{task_id}/detail` (`:96`):

```python
@router.get("/{task_id}/step-events", response_model=list[TaskStepEvent], summary="Get task step-event timeline")
async def get_task_step_events(task_id: UUID, service: TaskServiceDep) -> list[TaskStepEvent]:
    await service.get_task(task_id)              # raises not_found_error → 404 if missing
    return await service.list_task_step_events(task_id)
```

Import `TaskStepEvent` from `bic_shared_types.experiment_task.mq.task_status` (R2 — same wire
type as the MQ message; NO new Lab-local schema).

> Note: `TaskStepEvent` currently lives under `experiment_task/mq/`. It's now ALSO an HTTP
> response body. That's fine — it stays one type, imported from its current path; we do NOT
> duplicate it into `http/`. Mention in the spec that this MQ type doubles as the read-endpoint
> response (one contract, two transports). It is NOT added to the JSON-schema REGISTRY unless the
> repo convention requires HTTP response bodies there — CHECK `export_json_schema.py` REGISTRY:
> the existing `GET /tasks/{id}` response `TaskRead` IS registered (`create-task`/`task-read`
> entries), so HTTP boundary bodies ARE registered. **If we want strict parity**, the step-events
> response is a `list[TaskStepEvent]` (a list, not a single boundary model) — registry entries are
> single models. Likely no registry entry needed (it's `list[...]`, and the item type isn't an
> endpoint body on its own). Confirm during implement; do not force a malformed entry.

## Shape consistency (the core invariant — PRD C2/AC2)

REST output and MQ `step_events` are produced by the **same `_to_step_event` mapper** over the
**same `get_task_step_events` query**. So for any task, `GET /tasks/{id}/step-events` ==
the `step_events` field of that task's status message. A test asserts this equality.

## Compatibility
- Purely additive: one new GET route, one new service method. No existing route/model touched.
- No DB change.

## Spec (Rule 10)
- `docs/dataflow.md` Lane 1: add `GET /tasks/{task_id}/step-events` (history read of the EventLog
  STEP_* timeline; returns `list[TaskStepEvent]`, the same shape as MQ `step_events`).

## Out of scope
- Agent proxy (`GET /api/trials/{trial_id}/step-events`) + FE → sibling children.
