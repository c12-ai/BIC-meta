# Lab: publish step-event timeline

Parent: `06-30-robot-execution-log`. Depends on `06-30-execlog-shared-contract`
(needs the `TaskStepEvent` type + transport decision).

## Goal

Make LabService **forward its existing step-level events** to AgentService over MQ, so
the Agent receives an ordered, timestamped step timeline — not just the latest task
status snapshot it gets today.

## Context (real code)

- The detail **already exists**: `EventService` writes `EventLog` rows
  (`STEP_STARTED / STEP_COMPLETED / STEP_FAILED / STEP_WAITING`) with `created_at`,
  cross-referenced by `skill_id`, persisted in the same txn as the entity update
  (`app/services/event_service.py`, `app/data/models/event.py`).
- The egress is `TaskService._publish_status_update` → `MQProducer.publish_task_status`
  (`app/services/task_service.py:589`, `app/infrastructure/mq_producer.py:132`), invoked
  on every status transition (task_service.py lines 328/360/380/404/451).
- The payload is built by `_build_status_message` (`task_service.py:534`) **from the
  in-memory `Task` model** — current status + flat `TaskStep[]` snapshot, **not** from
  `EventLog`. This is exactly where the timeline is dropped.

## Requirements

- R1. When publishing task status, include the step-event timeline in the new contract
  shape from the shared-contract child (field on `TaskStatusMsgPayload` or new message,
  per that child's R2 decision).
- R2. Timeline entries are **derived from the authoritative source** — the `EventLog`
  STEP_* rows for this task (carrying real `created_at` timestamps) — not re-synthesized
  from the `Task.steps` snapshot. (Resolves parent R2: "forwarded, not reconstructed".)
- R3. Ordering is stable and chronological (by `created_at`, tie-broken deterministically).
- R4. No new robot-side protocol — robot messages are unchanged; this is purely Lab egress.
- R5. Match LabService conventions: services commit / repos don't; query `EventLog` via the
  existing `EventLogRepository`; `loguru` logger; `uv run` tooling; Pydantic at boundaries.

## Constraints

- C1. **Surgical** (Rule 3) — extend the publish path; do not refactor the status path or
  the result-handler two-phase transaction model.
- C2. Don't regress the existing `steps[]` snapshot consumers — both old snapshot and new
  timeline ship together until/unless the Agent side fully migrates.
- C3. Watch the publish-on-every-transition frequency: forwarding the full timeline on each
  status message is acceptable for MVP (step counts are small), but the design must state
  whether we send full-timeline-each-time or only-new-events, and justify it.

## Acceptance Criteria

- [ ] AC1. A CC task run publishes task-status MQ messages whose payload contains the
      ordered step-event timeline sourced from `EventLog`, with timestamps.
- [ ] AC2. Timeline order matches `EventLog.created_at` order for that task's STEP_* events.
- [ ] AC3. A failed step's event carries its `error_message` and `STEP_FAILED`.
- [ ] AC4. Existing `TaskStatusMsgPayload.steps[]` snapshot is still populated (no regression);
      existing Lab→Agent tests stay green.
- [ ] AC5. New/updated unit tests assert the timeline is built from `EventLog` (Rule 7 —
      a test that fails if someone rebuilds it from `Task.steps`).
- [ ] AC6. `.trellis/spec/` Lab↔Agent dataflow / contract doc updated (Rule 10).
- [ ] AC7. `ruff check`, `uv run pyright app/`, `uv run pytest` green.

## Resolved (see design.md)

- **Full-timeline-per-message** (locked in contract child) — Agent dedups on `event_id`.
- **No existing query** — add `EventLogRepository.get_task_step_events(task_id)` (STEP_* for
  entity_type=TASK / entity_id=task.id, ordered by created_at). Uses the existing
  `(entity_type, entity_id, created_at)` composite index.
- **P1 (failed steps invisible)**: a failed step logs `TASK_FAILED`, not `STEP_FAILED`
  (dead enum). → add a real `STEP_FAILED` log at the failure site. [Drake, 2026-06-30]
- **P2 (publish lags one event)**: sites do `commit → publish → log_event(STEP_*)`. → reorder
  to `log_event → commit → publish` so the current transition is in the timeline. [Drake, 2026-06-30]
- **new_state shape is inconsistent** across STEP_* sites (pre-existing wart) → map defensively,
  `step_index=-1` sentinel for WAITING; do NOT normalize (Rule 3).

## Notes

- Complex task: design.md + implement.md before `start`.
