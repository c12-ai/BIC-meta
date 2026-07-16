# Current user Turn cancellation evidence

Evidence date: 2026-07-15. Read-only audit of Agent Service `origin/main` and Portal `origin/main`.

## Portal baseline

- `src/pages/chat/Composer.tsx` accepts `streaming`, `sending`, and `onSend`, but no Stop callback. Streaming disables the composer.
- `src/pages/chat/Composer.test.tsx` and `tests/chat-redesign.spec.ts` explicitly assert that no fake Stop action appears while streaming.
- `src/pages/chat/ChatPage.tsx` uses `AbortController` for route/session hydration and tears down the local live stream on navigation. This does not call a backend cancellation operation.
- `src/lib/sse-client.ts` closes/reconnects browser reception only; it has no authority over the server worker.
- `src/lib/agent-client.ts` posts a message without returning `turn_id`; the response shape is only `{accepted, event_id}`.
- `src/types/events.ts` and `src/lib/event-dispatcher.ts` recognize `turn_started`, `turn_completed`, and `turn_failed`, but no cancellation terminal.

## Agent Service baseline

- `app/api/routers/sessions.py` exposes message admission but no Turn cancel/status endpoint; its response omits `turn_id`.
- `app/data/turn_schemas.py` creates `TurnInput.turn_id`, but the identifier belongs to the in-process work object under current main.
- `app/data/models.py` has no durable Turn lifecycle aggregate keyed by `turn_id`; the existing trace metadata is not lifecycle authority.
- `app/session/orchestrator.py` cancels worker tasks during shutdown. `CancelledError` can escape without a persisted terminal event; this is operational shutdown, not a user cancellation contract.
- `app/api/routers/sse.py` treats SSE connection lifetime independently from worker execution.
- `app/runtime/graphs/specialists/tools.py` contains a Lab-job cancellation concept, but it is unsupported and refers to a physical Lab task rather than an Agent Turn.

## Shared-contract baseline

- BIC-shared-types currently contains a Lab Task cancellation route, not an Agent Session/Turn cancellation contract.
- Portal manually mirrors Agent Session event types today, so the minimum Turn-cancellation slice does not require BIC-shared-types unless event-contract ownership is separately centralized.

## Design implications

1. A real Stop action requires additive Agent Service API and Portal work; current local abort/SSE behavior cannot be reused as cancellation authority.
2. Message admission must expose the stable server `turn_id` so cancellation never races through a session-level `current` alias.
3. Cancellation must be durable and must serialize with Proposal acceptance and unique Turn terminal closure.
4. A committed Proposal/Outbox Command remains independent; stopping the Agent Turn is not undo and is not Lab Task cancellation.
5. A non-error Portal projection is needed; exact event naming and payload remain a compatibility decision.

## Terminal-event compatibility detail

- `src/lib/sse-client.ts` registers a closed compile-time list of named SSE kinds. Browser `EventSource` does not deliver an unregistered named channel to the generic handler, so an old Portal drops a new `turn_cancelled` event completely.
- `src/lib/event-dispatcher.ts::turnRunningSignal` clears the shared chat lock only for `turn_completed` and `turn_failed`. An old page that misses a new cancellation event can retain `turnRunning=true` until authoritative rehydration.
- Reusing `turn_failed` is not semantically neutral. Its dispatcher creates a failed assistant bubble and calls `workspace.onAnalysisFailed()`, which may mark an awaiting-analysis trial as failed.
- A distinct cancellation event therefore requires coordinated Portal support in the RuntimeEvent union, named SSE registration, turn-running signal, assistant finalization, thinking-timeline convergence, replay/snapshot equivalence, and tests.
- A safe staged release can deploy hidden Portal support first, then deploy the Agent Service cancellation endpoint/event, then enable the Stop control. Mixed-version tabs remain an explicit compatibility case to resolve rather than a reason to misclassify cancellation as failure.

## Collaborative-session authorization baseline

- Agent Service defines `owner`, `collaborator`, `observer`, and `former` Session roles. `CHAT` belongs to owner, collaborator, and observer; `EXECUTE` belongs only to owner and collaborator; `MANAGE_MEMBERS` belongs only to owner (`app/core/enums.py`, `app/session/registry.py`).
- `POST /sessions/{session_id}/messages` authenticates `current_user_id` and requires `Capability.CHAT`, so an observer may initiate a user-message Turn (`app/api/routers/sessions.py`, `app/session/service.py`).
- Portal's collaboration interlock makes `turnRunning` the only chat-lock term and applies it to every member. Focus ownership controls editable/confirmation surfaces, not the ability to cancel a currently locking Turn (`src/lib/capabilities.ts`).
- Current `UserMessageSubmittedEvent` and `TurnInput` correlate the message and Turn but do not persist the initiating `user_id`. An authorization rule that distinguishes "own Turn" from "another member's Turn" therefore requires the target durable admission/Turn model to retain a trusted initiator principal reference.
- Authorization options have different consequences: initiator-only can strand collaborators when the initiator disconnects; any `CHAT` member lets observers interrupt another user's work; initiator-or-`EXECUTE` preserves self-cancellation while giving owner/collaborator a shared-workspace recovery control.

## Turn-source eligibility baseline

- Current Turn kinds are `USER_MESSAGE`, `FORM_CONFIRM`, `DECISION_RESPONSE`, `DECISION_EXPIRED`, and `TASK_TERMINAL`; sources are `USER`, `MQ`, `SCHEDULER`, and `RECONCILIATION` (`app/core/enums.py`).
- User message, form confirm, and genuine decision response paths use `source=USER`; task ingress uses MQ and reconciler continuations use RECONCILIATION.
- Current decision-expiry production behavior has documented drift: scheduler expiry may be materialized as `DECISION_RESPONSE` with `source=USER` instead of the declared `DECISION_EXPIRED/SCHEDULER`. Eligibility cannot trust that drift as intentional user origin.
- User cancellation is therefore gated by trusted L2 admission provenance and the reviewed user-triggered kinds. A client-provided source/kind cannot authorize cancellation.
- Form/decision admission may already have changed durable facts before its Agent Turn runs. Cancelling that Turn stops only the continuation and must not be presented as undoing the admitted confirmation or decision.

## Partial-output durability baseline

- Agent Service classifies `text_delta`, `reasoning_delta`, node transitions, and tool-call deltas as emit-only. They are broadcast with `session_seq=None` and are not appended to `session_events` (`app/session/orchestrator.py`).
- Completed `text_done` and `reasoning_done` events are persisted and are the durable twins used by conversation/history reconstruction and Portal replay.
- Portal appends live text deltas directly to the active assistant bubble, while history/reconnect can reconstruct text only from persisted completion events (`src/lib/event-dispatcher.ts`, `src/stores/chatStore.ts`).
- If cancellation arrives before the active text/reasoning segment emits its done event, current durable state cannot reconstruct the live partial fragment after refresh.
- Keeping an emit-only fragment only in the current tab would make cancelled output differ across live, replay, reconnect, and multi-tab views. Preserving every partial fragment durably instead would require a new L2-owned output-draft/accumulator contract, cross-process flush semantics, and write-volume policy; Foundation itself cannot own that persistence.

## Admission and cancellation HTTP baseline

- Current `POST /sessions/{session_id}/messages`, `/forms/confirm`, and `/decisions` all return HTTP 202 with `accepted` and `event_id`, but no `turn_id` (`app/api/routers/sessions.py`).
- Portal consumes only `event_id` from all three responses for optimistic projection (`src/pages/chat/useChatSend.ts`, `src/lib/use-submit-form.ts`, `src/lib/agent-client.ts`).
- The target cancellation contract must therefore add the server-assigned `turn_id` to every eligible admission receipt, not only user-message submission, if queued cancellation is to address an exact Turn.
- Because accepted user cancellation immediately commits terminal closure, a successful cancel operation is no longer merely asynchronous acceptance. HTTP 200 can truthfully report the committed disposition, while the persisted terminal event remains authoritative for live/replay projection.
- An already-terminal result must not be reported as a new cancellation: cancellation racing normal completion should preserve the existing terminal and let Portal observe/refetch that terminal rather than render a false Stop outcome.
