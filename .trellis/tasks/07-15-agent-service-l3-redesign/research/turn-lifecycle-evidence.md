# Turn lifecycle evidence

Evidence baseline: BIC Agent Service live `main` at `12a84f3238a952f00eb95b24c1943f8303041350`.

## Current Turn model

- `TurnInput` is an immutable, identified queue envelope consumed serially by an L2 per-session worker.
- Inputs may come from users or systems. Current kinds are user message, form confirmation, decision response, decision expiry, and task-terminal callback.
- `turn_id` is created by the `TurnInput` default factory before submission. Queue admission and Turn execution are therefore distinct boundaries.
- The current 900-second timeout begins inside `_run_turn` after dequeue. Queue waiting is outside it.
- `turn_started` is persisted only after context loading, so a dequeued Turn may fail without ever receiving a started marker.

Primary code:

- `app/data/turn_schemas.py`
- `app/core/enums.py`
- `app/session/orchestrator.py`
- `app/api/routers/sessions.py`

## Current terminal semantics

The persisted lifecycle markers are:

- `turn_started`
- `turn_completed`
- `turn_failed`

`turn_completed` means that the L3 async iterator exhausted normally after its yielded durable events were applied and appended. It does not mean that a Lab/Nexus Task completed.

`turn_failed` is written in an independent transaction for an escaped exception. A timeout is represented as `turn_failed` with `failure_kind=turn_timeout`; there is no distinct cancellation terminal. Events already committed earlier in the Turn are not rolled back by a later failure.

Primary code:

- `app/events/orch_emitted.py`
- `app/session/orchestrator.py`
- `app/runtime/runtime.py`

## Exactly-one is not a current guarantee

`session_events` has no uniqueness rule enforcing one terminal per `(session_id, turn_id)`, and append is an unconditional insert. Current failure cases include:

- shutdown directly cancels the session worker; `CancelledError` escapes `_run_turn` and may leave a started Turn without a terminal;
- process crash or OOM may leave zero terminals;
- failure to persist `turn_failed` is only logged and leaves zero terminals;
- duplicate enqueue or replay of the same `TurnInput` can produce duplicate lifecycle markers;
- a queued but never-dequeued input has neither start nor terminal lifecycle records.

Therefore “each Turn has exactly one durable terminal” is a target invariant requiring a durable Turn lifecycle model, idempotent terminal transition, recovery/watchdog behavior, and database enforcement. It must not be described as a property of the current event-only implementation.

Primary code:

- `app/data/models.py`
- `app/repositories/session_events_repo.py`
- `app/session/orchestrator.py`

## Deadline and cancellation gaps

- The only general deadline is an L2 relative `asyncio.timeout(900)` around context loading, L3 stream consumption, per-event persistence/broadcast, and terminal emission.
- There is no absolute deadline carried by `TurnInput` or propagated as a remaining budget to model and tool calls.
- There is no independent watchdog that can close a Turn when the execution coroutine is stuck or killed.
- Current shutdown performs immediate task cancellation. The documented draining model is not implemented.
- Foundation currently returns an `AsyncIterator[RuntimeEvent]`; L2 infers completion from normal exhaustion and failure from exceptions. There is no typed execution-closure result.

## Additional contract drift

- The schema comment says exactly one payload must match `TurnInput.kind`, but no Pydantic validator enforces this.
- `DECISION_EXPIRED` exists in the contract, while the current scheduler path constructs a `DECISION_RESPONSE` with user source.

These are migration-baseline defects to classify explicitly rather than silently preserve as intended compatibility behavior.
