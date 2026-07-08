# Implement — Lab: GET step-events read endpoint

Repo: `BIC-lab-service`. `uv run` tooling. Depends on lab-publish (DONE — query + mapper exist).
**No code until `task.py start` + Drake review.**

## Ordered checklist

1. **Service method** — `app/services/task_service.py`: add
   `async def list_task_step_events(self, task_id: UUID) -> list[TaskStepEvent]` that fetches
   `await self.events.get_task_step_events(task_id)` and maps via the existing
   `self._to_step_event`. (No task-existence check here — the route does the 404, matching
   `get_task`.)

2. **Route** — `app/api/routers/tasks.py`: add
   `GET /{task_id}/step-events` → `response_model=list[TaskStepEvent]`, mirroring the
   `GET /{task_id}/detail` route. Body: `await service.get_task(task_id)` (raises
   `not_found_error` → 404 on missing), then `return await service.list_task_step_events(task_id)`.
   Import `TaskStepEvent` from `bic_shared_types.experiment_task.mq.task_status`.
   ⚠️ Route ORDER: register `/{task_id}/step-events` so it doesn't get shadowed by `/{task_id}`
   — FastAPI matches by registration order; place it beside `/{task_id}/detail` (both are
   more-specific than `/{task_id}`), which already coexists fine.

3. **Spec (Rule 10)** — `docs/dataflow.md` Lane 1: document the new endpoint (history read of the
   EventLog STEP_* timeline, returns `list[TaskStepEvent]` — same shape as MQ `step_events`).

## Tests (Rule 7)

- `GET /tasks/{task_id}/step-events` for a task with STEP_* rows → 200, ordered `list[TaskStepEvent]`
  with `occurred_at`/`error_message` populated (AC1).
- **Shape-parity test (AC2)**: for the same task, the REST response equals the publisher's
  `step_events` (build the status message via `_build_status_message` and compare). This is the
  invariant that guarantees FE sees identical live vs. history entries.
- Unknown task_id → 404 (AC3).
- Known task, no step events yet → `200 []` (AC3).
- Failed step → entry with `status="step_failed"` + `error_message` (AC4).

## Validation
```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright app/
uv run pytest
```

## Risky points
- **Route shadowing** — verify `/{task_id}/step-events` resolves and isn't swallowed by
  `/{task_id}`. Test hitting the real path guards this.
- **Registry parity** — response is `list[TaskStepEvent]` (not a single boundary model), so it
  likely needs NO `export_json_schema.py` REGISTRY entry. Do NOT force a malformed list entry;
  if unsure, leave it out (the type is already exported from shared-types).

## Done = all of:
- [x] `list_task_step_events` service method (`task_service.py:501`) — reuses query + `_to_step_event`.
- [x] `GET /{task_id}/step-events` route (`tasks.py:109`), `list[TaskStepEvent]`, 404 unknown, `[]` empty.
      Route registered before `/{task_id}` → not shadowed (verified static + runtime).
- [x] Shape-parity test (REST == MQ `step_events`) green, non-vacuous (guards against empty==empty).
- [x] `ruff` + `pyright app/` (0 errors) + `pytest` (346 passed, 5 new) green. Verified under `uv run`.
- [x] `docs/dataflow.md` Lane 1 updated.

## Finding carried to lab-publish (NOT readapi's bug)
`_submit_next` logs `STEP_STARTED` with `auto_commit=False` AFTER its last commit
(`task_service.py:~809`), so a separate reader session sees `[]` after a bare round-1 dispatch
until `on_skill_completed` commits. Same B1 pattern flagged in lab-publish for STEP_STARTED.
**Live/history parity still holds** (live MQ `step_events` is also empty at that instant). Logged
on lab-publish for a possible follow-up reorder; the read endpoint itself is correct.