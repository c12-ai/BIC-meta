# Agent: step-event passthrough (NOT persist)

> ⚠️ Rescoped 2026-06-30. Architecture pivoted to **"live via SSE, history via Lab REST
> (Agent-proxied); the Agent persists NOTHING."** The original "persist to a trials table"
> plan is VOID. Dir name stays `agent-persist` (renaming breaks Trellis links); the work is
> passthrough. Parent task map calls this `agent-passthrough`.

Parent: `06-30-robot-execution-log`. Depends on `06-30-execlog-shared-contract` (type) and
`06-30-execlog-lab-readapi` (the Lab read endpoint the proxy forwards to).

## Goal

Two thin things, no DB writes:
1. **Live**: carry `step_events` on the existing `TaskProgressEvent` so the live timeline rides
   the current SSE + `session_events` rail to the FE.
2. **History proxy**: expose `GET /api/sessions/{session_id}/trials/{trial_id}/step-events` that
   translates `trial_id → lab_task_id` and forwards to LabService
   `GET /tasks/{lab_task_id}/step-events`, returning `list[TaskStepEvent]`.

## Context (real code)

- `TaskProgressEvent` (`app/events/bypass_emitted.py:27`) carries `steps: list[dict]`, `apply()`
  writes `trials.status/steps/error_message`. Built at 2 sites in `fast_path_handlers.py`:
  `handle_task_status_transition` (`:457`, non-terminal) and `emit_terminal_progress` (`:500`,
  terminal — called from `event_ingress.py:177` and `:243`).
- The MQ payload now has `payload.step_events: list[TaskStepEvent]` (shared-types 1.2.0a1, synced).
- `LabClient` (`app/infrastructure/lab_client.py:99`) + `LabClientProtocol` (`:72`) exist on
  `app.state.lab_client` (`lifespan.py:124`); `query_task_status(lab_task_id)` (`:134`) is the
  exact template for a new `query_step_events`. `trust_env=False` already set.
- DI pattern: `get_X(request) -> request.app.state.X` (`app/api/dependencies.py:35`).
- `trials.lab_task_id` mapping exists (`trials_repo.py`); the session snapshot already exposes
  `lab_task_id` per trial (`sessions.py:677`). `lab_task_id` is many-to-one over attempt-trials.

## Requirements

- R1. Add `step_events: list[dict] = []` to `TaskProgressEvent`; populate it at BOTH construction
  sites from `payload.step_events` (`[e.model_dump(mode="json") for e in payload.step_events]`).
- R2. `TaskProgressEvent.apply` must **NOT** write `step_events` to `trials` (no persist). It only
  rides the event payload (→ `session_events` durable replay + live SSE). `steps` write unchanged.
- R3. New `LabClient.query_step_events(lab_task_id) -> list[TaskStepEvent]` mirroring
  `query_task_status`; add to `LabClientProtocol` too.
- R4. New route `GET /sessions/{session_id}/trials/{trial_id}/step-events` →
  `list[TaskStepEvent]`: resolve `trial_id → lab_task_id` (404 if trial unknown; sensible error if
  the trial has no `lab_task_id` yet — not dispatched), then `lab_client.query_step_events(...)`.
- R5. Add a `get_lab_client` DI provider (mirror existing providers).
- R6. No regression to the existing `task_progress` path (the `steps` snapshot the workspace strip
  already depends on must keep flowing).

## Constraints

- C1. **No DB writes for the timeline** — this is the whole point of the pivot. No new column,
  no migration, no `trials` write of `step_events`.
- C2. Type-first (Rule 11): `TaskStepEvent` on the boundary; the event payload uses `list[dict]`
  only because `TaskProgressEvent.steps` already does (match the existing field, Rule 8).
- C3. Surgical (Rule 3): extend the 2 emit sites + add 1 route + 1 client method + 1 DI provider.

## Acceptance Criteria

- [ ] AC1. A non-terminal and a terminal `task_progress` SSE event both carry `step_events`
      mirroring the MQ `payload.step_events`.
- [ ] AC2. `step_events` is NOT written to `trials` (assert no DB column/write touched).
- [ ] AC3. `GET /sessions/{session_id}/trials/{trial_id}/step-events` returns
      `list[TaskStepEvent]` forwarded from Lab; matches what Lab's endpoint returns.
- [ ] AC4. Unknown trial → 404; trial with no `lab_task_id` (not yet dispatched) → a clear error
      (404 or empty — decide in design), not a 500.
- [ ] AC5. Reconnect: replaying `session_events` re-delivers `task_progress` events WITH
      `step_events` (free — they're in the persisted payload).
- [ ] AC6. Existing `steps` snapshot path unchanged; existing fast-path/ingress tests green.
- [ ] AC7. `uv run pytest` + type-check + lint green.
- [ ] AC8. Spec (Rule 10): event-ingress / contracts spec notes `step_events` on `task_progress`;
      the new proxy endpoint documented.

## Out of scope
- FE rendering → fe-timeline. Lab read endpoint → lab-readapi (DONE).

## Notes
- Complex-ish (event contract + cross-service proxy) → design.md + implement.md before `start`.
