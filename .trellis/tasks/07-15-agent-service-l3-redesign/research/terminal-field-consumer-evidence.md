# Terminal-field consumer evidence

Audited baselines:

- Agent Service `origin/main`: `12a84f3238a952f00eb95b24c1943f8303041350`
- Agent Portal `origin/main`: `d02aaea3049d4681425ba28bbdf3e6954f105936`
- BIC Shared Types `origin/main`: `f8e6e3277179b728eab41afe58cfa90264e5a998`

## Current producer versus declared matrix

Agent Service declares nine `FailureKind` values and seven `ErrorStage` values. The live classifier can produce only six pairs:

| Produced pair | Trigger |
|---|---|
| `turn_timeout / timeout` | `TimeoutError` |
| `llm_error / runtime_invoke` | `LLMClientError` |
| `tool_error / runtime_invoke` | material, Lab, or Mind error |
| `persistence_error / loading_ctx` | any `PersistenceUnavailableError` |
| `runtime_error / runtime_invoke` | `RecursionError` |
| `unknown / runtime_invoke` | every other exception |

Declared but unproduced failure kinds include post-processor, broadcast, and drain timeout. Declared but unproduced stages include apply, append, emit, and drain.

The classifier receives only the exception, not a tracked phase. Therefore a persistence exception is labelled loading-context even when it could arise during event append; apply and append share one transaction without phase tracking; broadcast exceptions are swallowed/logged; shutdown cancellation bypasses the failure classifier.

Primary code:

- `app/core/enums.py:91-114`
- `app/session/orchestrator.py:350-403`
- `app/session/orchestrator.py:467-509`
- `app/session/orchestrator.py:726-759`
- `app/session/broadcaster.py:277-325`

## Persistence and wire behavior

- `failure_kind`, `error_stage`, and `error_message` are unconstrained strings inside opaque Session Event JSON.
- They have no dedicated columns, indexes, or durable terminal model.
- live SSE, replay, and history forward the event JSON unchanged.
- tests primarily prove preservation and selected classification pairs, not the declared matrix semantics.

Primary code:

- `app/events/orch_emitted.py:243-268`
- `app/events/_base.py:44-79`
- `app/repositories/session_events_repo.py:77-107`
- `app/data/models.py:140-164`
- `app/session/broadcaster.py:240-303`
- `app/api/routers/sse.py:138-152`
- `app/api/routers/sessions.py:840-864`

## Portal and shared-contract consumers

- Portal's local `TurnFailedEvent` type contains only `error_message`; it omits `failure_kind`, `error_stage`, and backend `display`.
- Portal treats all `turn_failed` events as the same terminal class, renders generic/user-safe error text, and never branches on kind or stage.
- its workflow reaction is based only on event kind and guesses an unanalyzed trial; stage would not supply the missing subject correlation.
- Portal has no BIC Shared Types dependency for Agent lifecycle events, and Shared Types does not define the Agent Turn failure payload.

Primary code:

- `BIC-agent-portal/src/types/events.ts:62-67`
- `BIC-agent-portal/src/lib/event-dispatcher.ts:58-75`
- `BIC-agent-portal/src/lib/event-dispatcher.ts:127-143`
- `BIC-agent-portal/src/stores/chatStore.ts:641-672`
- `BIC-agent-portal/src/stores/workspaceStore.ts:1831-1858`
- `BIC-agent-portal/src/pages/chat/Message.tsx:209-221`

## Operations, retry, and recovery consumers

- no live metrics or alert path consumes failure kind/stage;
- LLM retry uses exception classes before terminal creation;
- startup recovery scans authoritative workflow/decision state, not terminal event fields;
- the worker does not retry based on terminal classification;
- the developer CLI prints kind/stage, which is diagnostic rather than workflow authority.

## Evidence-backed disposition

- `failure_stage` is not accepted into the new durable terminal schema.
- component, operation, exception class, and effect-committed information remain structured telemetry and may evolve with implementation topology.
- legacy `turn_failed.error_stage` remains a best-effort compatibility projection until removal is independently reviewed.
- a future persisted semantic reason or stage requires a named consumer, action, and stability contract.
