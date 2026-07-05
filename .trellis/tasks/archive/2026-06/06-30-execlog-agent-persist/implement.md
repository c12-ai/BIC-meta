# Implement — Agent: step-event passthrough

Repo: `BIC-agent-service`. `uv run` tooling. Depends on lab-readapi (DONE — Lab endpoint live) +
shared-contract (DONE — `step_events`/`TaskStepEvent` synced). **No code until `start` + review.**

## Ordered checklist

### Part A — live SSE field
1. `app/events/bypass_emitted.py`: add `step_events: list[dict[str, Any]] = []` to
   `TaskProgressEvent`. Update its docstring: `step_events` is ride-only (NOT persisted). Leave
   `apply()` UNCHANGED (it must not write `step_events` to `trials`).
2. `app/session/fast_path_handlers.py`:
   - `handle_task_status_transition` (~`:439-461`): add
     `serialized_step_events = [e.model_dump(mode="json") for e in new_payload.step_events]` and
     pass `step_events=serialized_step_events` into the `TaskProgressEvent(...)`.
   - `emit_terminal_progress` (~`:479-504`): add a `step_events: list[dict[str, Any]] = []`
     parameter; pass it into the `TaskProgressEvent(...)`.
3. `app/session/event_ingress.py`: at BOTH `emit_terminal_progress` call sites (`:177`, `:243`),
   build `serialized_step_events = [e.model_dump(mode="json") for e in payload.step_events]` and
   pass `step_events=serialized_step_events`.

### Part B — history proxy
4. `app/infrastructure/lab_client.py`: add `query_step_events(self, lab_task_id) ->
   list[TaskStepEvent]` mirroring `query_task_status` (`:134`). Add the same signature to
   `LabClientProtocol` (`:72`). Import `TaskStepEvent` from
   `bic_shared_types.experiment_task.mq.task_status`.
5. `app/api/dependencies.py`: add `get_lab_client(request) -> LabClientProtocol` mirroring the
   existing `get_*` providers (`:35`) incl. the None guard.
6. `app/api/routers/sessions.py`: add route
   `GET /{session_id}/trials/{trial_id}/step-events` → `response_model=list[TaskStepEvent]`.
   - Resolve `trial_id → lab_task_id` via the existing session-service/trials resolver (the
     snapshot path reads `lab_task_id` per trial — find + reuse that method; do NOT add a new
     repo query if one exists).
   - trial unknown → 404. trial known, `lab_task_id is None` → `200 []`. Else
     `return await lab_client.query_step_events(lab_task_id)`.
7. Spec (Rule 10): update `.trellis/spec/BIC-agent-service/backend/L2/event-ingress.md` (and/or
   `contracts.md`) — `step_events` on `task_progress` (ride-only) + the proxy endpoint.

## Tests (Rule 7)
- Non-terminal + terminal `task_progress` events carry `step_events` mirroring `payload.step_events`
  (AC1).
- `apply()` does NOT write `step_events` to trials — assert the `update_fields` call args contain
  only status/steps/error_message (AC2). This guards the no-persist invariant.
- Proxy route: mock `lab_client.query_step_events` → assert the route forwards by resolved
  `lab_task_id` and returns its result (AC3).
- Unknown trial → 404; trial with `lab_task_id=None` → `200 []` (AC4).
- Reconnect/replay: a persisted `task_progress` `session_events` row replays with `step_events`
  intact (AC5) — or assert the field is in the serialized payload.
- Regression: existing fast-path / event-ingress / snapshot tests green (AC6).

## Validation
```bash
uv run ruff check .
uv run pyright app/
uv run pytest
```
(Confirm the repo's exact lint/format cmds from its CLAUDE.md before reporting done.)

## Risky points
- `emit_terminal_progress` signature change ripples to 2 callers — update both (`:177`, `:243`),
  miss one → that path ships empty `step_events`. The tests for terminal + round-done cover this.
- Do NOT touch `apply()` — accidentally adding `step_events` to `update_fields` would (a) try to
  write a non-existent column and (b) violate the no-persist decision. The AC2 test guards it.

## Done = all of:
- [x] `TaskProgressEvent.step_events` field (`bypass_emitted.py:66`); `apply()` does NOT write it.
- [x] Populated at all 3 emit paths: non-terminal (`fast_path:465`), terminal (`:514`),
      event_ingress round-done (`:185`) + terminal (`:255`).
- [x] `LabClient.query_step_events` + `LabClientProtocol` entry; `get_lab_client` DI provider.
- [x] Proxy route (`sessions.py:710`) → `list[TaskStepEvent]`; 404 unknown; `200 []` when
      `lab_task_id is None`. Resolver `service.resolve_trial_lab_task_id` reuses `TrialsRepo.get`.
- [x] AC2 no-persist guard test: `test_task_progress_apply_does_not_persist_step_events`
      (fails the moment someone adds step_events to the apply write). + proxy/lab_client tests.
- [x] `ruff` + `pyright app/` (0 errors) + `pytest` (**951 passed**, +18) green. Verified under `uv`.
- [x] Spec (Rule 10): `event-ingress.md` + `L1/http-routes.md` + `L4/events.md` updated.

## Note: sub-agent connection dropped mid-run (85 tool calls in)
The dispatch returned "Connection closed", no report. Main session independently verified ALL
acceptance criteria from the working tree + full gate — work was complete and in-scope. Out-of-scope
dirty files (orchestrator.py, session_events_repo.py, plan_dynamic_prompt.py) confirmed PRE-EXISTING
WIP (no step_event code from this agent), NOT touched by this task.