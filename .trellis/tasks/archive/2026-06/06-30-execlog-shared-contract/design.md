# Design — Shared-types: step-event contract

## Decisions (locked with Drake, 2026-06-30)

- **D1. Transport: enrich `TaskStatusMsgPayload`.** Add `step_events: list[TaskStepEvent] = []`.
  No new `ApexMessageType`, no new Agent consumer branch, no new routing key. The Agent
  already receives this payload on every status transition (`event_ingress.handle_task_status`)
  and already `model_dump()`s `steps` into SSE — `step_events` rides the same path.
- **D2. Payload mode: full timeline each message.** Every status message carries all
  step-events so far. Self-healing against dropped MQ messages; the Agent dedups on
  `event_id`. Step counts are tiny (~4–8/task) so size is a non-issue. (This is a contract
  *expectation* documented in the spec; the actual "send full" behavior is implemented in the
  Lab child, but the contract doc must state it so the Agent child builds idempotent ingest.)
- **D3. `event_id` = LabService `EventLog.id` (UUID, stringified).** Free stable key — every
  `EventLog` row already has a UUID PK. Used downstream for dedup (Agent) and React keys (FE).

## The contract

`bic_shared_types/experiment_task/mq/task_status.py` — add one new model, one new field:

```python
class TaskStepEvent(BaseModel):
    """One entry in a task's step-level execution timeline.

    Sourced from a LabService ``EventLog`` STEP_* row; ``event_id`` is that row's
    UUID (stringified) and is stable across re-publishes for idempotent ingest.
    """
    event_id: str
    step_index: int
    skill_type: str
    status: str            # step lifecycle: step_started|step_completed|step_failed|step_waiting
    occurred_at: datetime  # EventLog.created_at
    error_message: str | None = None


class TaskStatusMsgPayload(BaseModel):
    task_id: str
    agent_side_task_id: str | None = None
    status: TaskStatus
    steps: list[TaskStatusStepPayload]        # UNCHANGED — current snapshot
    step_events: list[TaskStepEvent] = []     # NEW — ordered, full timeline so far
    error_message: str | None = None
    image_url: FileUrl | None = None
```

Add `TaskStepEvent` to `__all__`. `datetime` import: `from datetime import datetime`
(precedent already in `experiment_task/http/responses.py`).

### Field rationale (first-principles)

| Field | Required by which truth | Note |
|---|---|---|
| `event_id` | D2 idempotency needs a stable key | = EventLog UUID, no new id machinery |
| `step_index` | FE groups events under their step | already on snapshot |
| `skill_type` | FE shows a human label per step | already on snapshot |
| `status` | the lifecycle transition this event marks | the STEP_* event mapped to a string |
| `occurred_at` | this is *the* new info vs. snapshot — "when" | = EventLog.created_at |
| `error_message` | failed-step display | already on snapshot |

`old_state/new_state` JSONB from EventLog is **deliberately excluded** — parent PRD put entity
state snapshots out of MVP. `status: str` (not a new enum): the four STEP_* values are a
LabService-internal vocabulary; encoding them as a free string keeps the contract additive and
avoids a cross-repo enum (constraint C3, and avoids a `ts/enums.ts` regen). Documented as the
known value set in the spec.

## Why this is low-risk

- **MQ payloads are NOT in the JSON-schema REGISTRY** (`scripts/export_json_schema.py:46` —
  HTTP-boundary-only; comment at line 42 confirms). So adding `TaskStepEvent` needs **no**
  schema file, **no** example, **no** contract-inventory endpoint row. Verified by grep:
  `task_status` does not appear in the registry.
- **Additive only** — existing `TaskStatusStepPayload` and `.steps` are untouched; `step_events`
  defaults to `[]`, so an old Lab publisher (not yet emitting it) still validates. Satisfies
  the deprecate-don't-delete policy and the historic v1.1.4a1-collapse lesson.
- No enum touched ⇒ `export_ts_enums.py --check` stays green without regen.

## Compatibility & migration

- **Forward**: Agent/FE can read `step_events` once present; absent ⇒ `[]` ⇒ no timeline (graceful).
- **Backward**: old consumers ignore the unknown field (Pydantic default ignore). No break.
- **Version bump**: `1.1.9a1 → 1.2.0a1` (minor feature line — new contract surface).
  [Confirmed Drake, 2026-06-30]. Bump `pyproject.toml` `version` **and** run `uv lock`;
  consumers re-pin to `1.2.0a1`.

## 3-repo consume verification (the real risk gate)

After the type lands and consumers re-pin:
- `BIC-lab-service`: `uv run pytest --collect-only` green.
- `BIC-agent-service`: `uv run pytest --collect-only` green.
- Both still `from bic_shared_types.experiment_task.mq.task_status import TaskStatusMsgPayload`
  without error. (This is the check the v1.1.4a1 incident would have failed.)

## Spec update (Rule 10)

Update the `.trellis/spec/` doc that describes the Lab↔Agent `TaskStatusMsgPayload` contract
(BIC-shared-types backend spec + the agent-service MQ-ingress spec reference) to document
`step_events`, the `TaskStepEvent` shape, the four `status` string values, and the
"full-timeline-each-message + dedup-on-event_id" contract expectation (so the Lab and Agent
children implement against a written contract, not this task doc).

## Out of scope (pushed to sibling children)

- *Producing* `step_events` from EventLog → `06-30-execlog-lab-publish`.
- *Persisting* + idempotent ingest + SSE/REST exposure → `06-30-execlog-agent-persist`.
- *Rendering* → `06-30-execlog-fe-timeline`.
