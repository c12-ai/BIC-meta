# Design — Lab: publish step-event timeline

## What I verified in the real code (premise check)

- The feature premise holds: `task_service.py` DOES write step events via
  `self.events.log_event(entity_type=EntityType.TASK, entity_id=str(task.id), event_type=...)`:
  - `STEP_STARTED` — append-round (`:236`) and `_submit_next` (`:730`)
  - `STEP_COMPLETED` — normal completion (`:291`) and TLC-park (`:366`)
  - `STEP_WAITING` — delay-before-next (`:337`)
- Egress is `_build_status_message` (`:534`) → `_publish_status_update` (`:589`) →
  `mq_producer.publish_task_status`, built from the in-memory `Task` snapshot today.
- `EventLogRepository` has NO "STEP_* for task X ordered" query — `get_by_entity` is
  `desc()` + `limit=100`. There IS a composite index `(entity_type, entity_id, created_at)`.

## Two real problems found (both resolved with Drake, 2026-06-30)

### P1 — failed steps are invisible to a STEP_*-only timeline
A failed step logs **`TASK_FAILED`** (`:410`, `:682`), never `STEP_FAILED` (enum value exists
but is written nowhere). A STEP_*-only timeline would miss failures → breaks parent **AC3**.
**Decision (D1):** add a real `STEP_FAILED` `log_event` at the failure site, beside the existing
`TASK_FAILED`, carrying `new_state={step_index, skill_type, error}` + `skill_id`. Makes the dead
enum value live; the timeline query then handles failure uniformly.

### P2 — publish reads the timeline one event behind
At the COMPLETED/FAILED/WAITING sites the order is `commit → _publish_status_update →
log_event(STEP_*, auto_commit=False)`. The current transition's event is committed only on the
**next** commit, so a publish-time EventLog query would always lag by one.
**Decision (D2):** reorder each affected site to
`log_event(STEP_*, auto_commit=False) → commit → _publish_status_update`. Same events, made
durable before the publish reads them. Matches the lab's existing "stage event before final
commit" lesson (`CLAUDE.local.md` B1 bug).

## The timeline query (new repo method)

`EventLogRepository.get_task_step_events(task_id: UUID) -> list[EventLog]`:

```python
STEP_EVENT_TYPES = (
    EventType.STEP_STARTED, EventType.STEP_COMPLETED,
    EventType.STEP_FAILED, EventType.STEP_WAITING,
)

async def get_task_step_events(self, task_id: UUID) -> list[EventLog]:
    query = (
        select(self.model)
        .where(
            self.model.entity_type == EntityType.TASK,
            self.model.entity_id == str(task_id),
            self.model.event_type.in_(STEP_EVENT_TYPES),
        )
        .order_by(self.model.created_at)  # asc — chronological
    )
    result = await self.session.execute(query)
    return list(result.scalars().all())
```

Uses the existing `(entity_type, entity_id, created_at)` composite index. No `limit` — a task's
step count is tiny (~4–8). Ordering: `created_at` asc; ties broken by insertion order (the query
is stable enough at this scale; if needed, add `, self.model.id` as a deterministic tiebreak).

## Mapping EventLog → TaskStepEvent

`new_state` JSON shape is **inconsistent** across sites (a pre-existing wart — do NOT refactor it,
Rule 3; just map defensively):

| event_type | new_state keys present | maps to TaskStepEvent |
|---|---|---|
| STEP_STARTED | step_index, skill_type, (status) | status=`step_started` |
| STEP_COMPLETED | step_index, skill_type | status=`step_completed` |
| STEP_FAILED (new) | step_index, skill_type, error | status=`step_failed`, error_message=error |
| STEP_WAITING | status, delay_seconds, next_skill_type (NO step_index) | status=`step_waiting` |

Builder (in task_service, beside `_build_status_message`):

```python
def _to_step_event(e: EventLog) -> TaskStepEvent:
    ns = e.new_state or {}
    return TaskStepEvent(
        event_id=str(e.id),                       # stable dedup key (D3 of contract child)
        step_index=int(ns.get("step_index", -1)), # WAITING has none → -1 sentinel
        skill_type=str(ns.get("skill_type") or ns.get("next_skill_type") or ""),
        status=e.event_type.value,                # step_started|completed|failed|waiting
        occurred_at=e.created_at,
        error_message=ns.get("error"),
    )
```

`step_index=-1` sentinel for WAITING is acceptable for MVP (the FE groups by step_index; a
waiting marker without a step is a transient row). Documented, not silently dropped (Rule 9).

## Wiring into the publisher (full-timeline-each-message — locked in contract child)

In `_build_status_message`, after building `steps`, add:
```python
step_event_rows = await self.events_repo.get_task_step_events(task.id)
payload = TaskStatusMsgPayload(
    ...,
    steps=[...],                                  # UNCHANGED
    step_events=[_to_step_event(e) for e in step_event_rows],  # NEW — full timeline so far
    ...
)
```
Every status message carries the full timeline → self-healing against dropped MQ; the Agent
dedups on `event_id`. (Resolves parent **R2/Q1**: forwarded from EventLog, not snapshot.)

`_build_status_message` needs read access to an `EventLogRepository` bound to the same session —
confirm how it's injected (TaskService already holds `self.events` = EventService; check whether
that exposes the repo or whether a sibling `EventLogRepository(self.session)` is the pattern).

## Compatibility / no-regression

- `steps[]` snapshot still populated identically → existing consumers unaffected (parent R6/AC4).
- Old behavior if `step_events` empty (e.g. event query returns nothing) → `[]` → graceful.
- Reorder (D2) preserves the set of events and their `new_state`; only the commit/publish
  sequence changes. Existing event-ordering tests must stay green; if any asserts the OLD
  publish-before-log order, that assertion encoded the bug — update it (Rule 7) and note why.

## Spec update (Rule 10)

Update the lab-service dataflow spec (the Lab↔Agent `agent.exchange` / `task.status` description
in `docs/dataflow.md` is the human doc; the `.trellis/spec/BIC-lab-service/backend` index for the
task/event layer) to document that `task.status` now carries `step_events` sourced from the
`EventLog` STEP_* rows, and that `STEP_FAILED` is now emitted on step failure.

## Out of scope
- Persisting / SSE / FE → sibling children. This child ends at "MQ message carries the timeline."
