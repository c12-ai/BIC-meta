# Implement — Lab: publish step-event timeline

Repo: `BIC-lab-service`. All commands `uv run`. Logger: `from app.core.logging import logger`.
Depends on contract child (DONE — `bic-shared-types 1.2.0a1` already re-synced into this repo,
`TaskStepEvent` importable). **No code until `task.py start` + Drake review.**

## Access path (verified)
`TaskService.events` → `EventService(self.db)`; `EventService.events` → `EventLogRepository(self.db)`
(same session). Add the new query on the repo + a thin pass-through on `EventService` matching its
existing `get_by_entity`/`get_by_skill` wrappers (`event_service.py:427/440`). DRY (Rule 8).

## Ordered checklist

1. **Repo query** — `app/repositories/event.py`: add
   `get_task_step_events(self, task_id: UUID) -> list[EventLog]` (select where entity_type=TASK,
   entity_id=str(task_id), event_type IN STEP_*, order_by created_at asc; add `, self.model.id`
   tiebreak). Define `STEP_EVENT_TYPES` tuple near it.

2. **EventService pass-through** — `app/services/event_service.py`: add
   `async def get_task_step_events(self, task_id) -> list[EventLog]: return await self.events.get_task_step_events(task_id)`.

3. **Fix P1 (STEP_FAILED)** — `app/services/task_service.py` failure branch (~`:407`, the
   `TASK_FAILED` site in `on_skill_completed`): add a `log_event(event_type=EventType.STEP_FAILED,
   entity_type=TASK, entity_id=str(task.id), new_state={step_index, skill_type, error:
   task.error_message}, skill_id=skill_id, auto_commit=False)` BEFORE the existing TASK_FAILED log.
   Check `_submit_next`'s failure path (~`:679`) too — if a step can fail there, add STEP_FAILED
   there as well (verify whether that path represents a step failure or a submission failure first).

4. **Fix P2 (ordering)** — at each site that does `commit → _publish_status_update →
   log_event(STEP_*)`, reorder to `log_event(STEP_*, auto_commit=False) → commit →
   _publish_status_update`. Affected sites (from grep): WAITING (`:326-345`),
   TLC-park COMPLETED (`:358-368`), and the new STEP_FAILED at the failure branch. STEP_STARTED
   sites (`:233`, `:727`) already log before their downstream publish — verify, leave if correct.
   ⚠️ Be surgical — only move the log/commit/publish lines, touch nothing else (Rule 3).

5. **Builder** — `app/services/task_service.py`: add `_to_step_event(e: EventLog) -> TaskStepEvent`
   per design (event_id=str(e.id), step_index from new_state with -1 sentinel for WAITING,
   skill_type from skill_type|next_skill_type, status=e.event_type.value, occurred_at=e.created_at,
   error_message=new_state.get("error")). Import `TaskStepEvent` from
   `bic_shared_types.experiment_task.mq.task_status`.

6. **Wire into publisher** — `_build_status_message` (`:534`): fetch
   `await self.events.get_task_step_events(task.id)`, add
   `step_events=[self._to_step_event(e) for e in rows]` to `TaskStatusMsgPayload`. Leave `steps`
   and `image_url` exactly as-is.

7. **Spec (Rule 10)** — update `docs/dataflow.md` (task.status now carries `step_events` from
   EventLog STEP_*; STEP_FAILED now emitted) + the relevant `.trellis/spec/BIC-lab-service/backend`
   doc.

## Tests (Rule 7 — encode intent)

- New unit test: run a CC task to completion → assert the published `TaskStatusMsgPayload.step_events`
  is built FROM EventLog (ordered, timestamped) and that mutating `task.steps` does NOT change it
  (proves it's not rebuilt from the snapshot — fails if someone reverts to snapshot source).
- New test: a step failure produces a `STEP_FAILED` entry in `step_events` with `error_message` set
  (guards parent AC3 + P1).
- New test: ordering — `step_events` are chronological by `occurred_at`.
- Regression: existing `steps[]` snapshot still populated; existing task-status / event tests green.
  If any existing test asserts the OLD publish-before-log order, it encoded the P2 bug — update it
  and comment why (Rule 7).

## Validation

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright app/
uv run pytest
```

## Risky points / rollback
- **P2 reorder** is the riskiest — it changes commit/publish sequencing in the hot task-advance
  path. Keep each reorder minimal; run the full task lifecycle tests. Rollback = revert the
  reorder hunks (the new query + builder + STEP_FAILED are independently safe additions).
- The `new_state` shape inconsistency is pre-existing — map defensively, do NOT normalize it
  (out of scope, Rule 3).

## Done = all of:
- [x] New repo query (`event.py:206`) + EventService pass-through (`event_service.py:446`).
- [x] STEP_FAILED emitted on step failure — BOTH sites: `on_skill_completed` (`:416`) AND
      `_submit_next` submission-failure (`:738`, no skill_id — skill never existed) (P1).
- [x] Publish reordered `log→commit→publish` at WAITING / TLC-park / both failure branches (P2).
- [x] `_build_status_message` emits `step_events` from EventLog (`:608`); `steps[]` unchanged.
- [x] 8 tests green (`tests/tlc/test_step_event_timeline.py`).
- [x] `ruff` + `pyright app/` (0 errors) + `pytest` (341 passed) green. Verified under `uv run`.
- [x] Spec (Rule 10): `docs/dataflow.md` updated. No `.trellis/spec/BIC-lab-service/backend`
      contract doc exists — dataflow.md is the authoritative human contract doc.

## Findings carried forward (for agent-persist child)
- `EventType` hydrates as raw `str` from DB (column is `String(50)`, not SQLAlchemy `Enum`) —
  builder coerces defensively. The Agent side reads `status` as the `step_*` string values.
- STEP_STARTED publishes one event behind (lands in step N+1's message) but is NOT dropped
  (verified). Cosmetic only — full-timeline-each-message + event_id dedup self-heals. Left as-is
  (in scope per plan). If the FE ever needs per-message exactness, reorder the 2 STEP_STARTED sites.
