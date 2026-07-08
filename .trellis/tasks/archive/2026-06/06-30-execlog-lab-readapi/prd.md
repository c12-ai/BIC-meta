# Lab: GET step-events read endpoint

Parent: `06-30-robot-execution-log`. Depends on `06-30-execlog-shared-contract` (`TaskStepEvent`).
The **history source** in the "live via SSE, history via Lab REST (Agent-proxied)" architecture.

## Goal

Expose a LabService REST endpoint that returns a task's full step-level execution timeline,
read from the `EventLog` STEP_* rows — so the Agent can proxy it to the FE for history/reconnect.

## Context (real code)

- The timeline source + query already exist after the lab-publish child:
  `EventLogRepository.get_task_step_events(task_id)` (ordered STEP_* for entity_type=TASK) and
  `EventService.get_task_step_events(task_id)` pass-through.
- The `_to_step_event(EventLog) -> TaskStepEvent` mapper exists in `task_service.py` (built for
  the MQ publisher). The endpoint should produce the **same `TaskStepEvent` shape** — one wire
  type, MQ and REST identical (Rule 8/DRY).
- `tasks.py` router already has `GET /{task_id}` / `GET /{task_id}/detail` with `response_model`
  and `not_found_error()` on missing task. Mirror that pattern.

## Requirements

- R1. `GET /tasks/{task_id}/step-events` → `200 list[TaskStepEvent]` (chronological, full timeline).
- R2. Response items are the shared-types `TaskStepEvent` (NOT a new Lab-local schema) — same
  shape the MQ message carries. No parallel type (Rule 8).
- R3. Reuse the existing `get_task_step_events` query + `_to_step_event` mapper; do not write a
  second EventLog→event mapping (DRY). If `_to_step_event` is a private method on TaskService,
  promote/relocate it to a shared spot both the publisher and the endpoint use.
- R4. Unknown `task_id` → `404` (match existing `get_task` behavior). A known task with no step
  events yet → `200 []` (empty timeline is valid, not a 404).
- R5. No auth (per Drake — the Agent proxies it, internal call).
- R6. Match Lab conventions: thin router → service, Pydantic response_model, `uv run` tooling.

## Constraints

- C1. Surgical (Rule 3) — add one route + reuse existing query/mapper; touch nothing else.
- C2. The endpoint and the MQ publisher MUST stay shape-consistent — both emit `TaskStepEvent`
  from the same mapper, so the FE sees identical live (SSE) and history (REST) entries.

## Acceptance Criteria

- [ ] AC1. `GET /tasks/{task_id}/step-events` returns the task's STEP_* timeline as
      `list[TaskStepEvent]`, chronological, with `occurred_at` + `error_message` populated.
- [ ] AC2. Matches the MQ `step_events` for the same task (same mapper, same shape) — a test
      asserts REST output == the publisher's `step_events` for a given task.
- [ ] AC3. Unknown task → 404; known task with no steps → `200 []`.
- [ ] AC4. A failed step appears with `status=step_failed` + `error_message` (relies on the
      STEP_FAILED emission added in lab-publish).
- [ ] AC5. `ruff` + `pyright app/` + `pytest` green.
- [ ] AC6. Spec (Rule 10): the new read endpoint documented (`docs/dataflow.md` Lane 1 / the
      events/tasks API doc).

## Out of scope
- Agent proxy + FE consumption → sibling children (agent-passthrough, fe-timeline).

## Notes
- Lightweight-ish but crosses a contract (new HTTP endpoint returning a shared type) → design.md +
  implement.md before `start`.
