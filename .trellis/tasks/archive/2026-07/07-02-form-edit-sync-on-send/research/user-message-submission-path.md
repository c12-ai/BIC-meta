# Research: User message submission path (FE → BE → turn)

- **Query**: The FE→BE flow for sending a chat message; where an optional form-draft attachment could ride the same request; whether the DTO is shared via BIC-shared-types.
- **Scope**: internal (BIC-agent-portal + BIC-agent-service)
- **Date**: 2026-07-02

**Summary**: Composer → `ChatPanel.handleSend` → `sendLiveUserMessage` → `submitUserMessage` POST `/sessions/{id}/messages` `{text}` → route mints `TurnInput(USER_MESSAGE)` → `SessionService.submit_user_message` persists `UserMessageSubmittedEvent` synchronously then enqueues the turn. The request DTO is **local to `sessions.py` (NOT in BIC-shared-types)**; the FE mirrors it by hand in `agent-client.ts`. Every model on the path is `extra="forbid"` / frozen, so an optional draft field must be added explicitly at each hop. Critical FE gap: `handleSend` has no access to the params-form values — the dirty registry tracks `isDirty/isValid/reset` but exposes **no `getValues`**; values live behind `formRef` inside `ParameterDesignPanel`.

## Findings

### FE path (BIC-agent-portal)

| File:Line | Role |
|---|---|
| `src/pages/chat/ChatPanel.tsx:69-97` | `handleSend(text)` — draft-mode mint+send (`:77-87`) or live send (`:92-96`); optimistic bubble via returned `event_id` |
| `src/pages/chat/ChatPanel.tsx:153,172` | `Composer`/`HomeHero` wired to `onSend={handleSend}` |
| `src/lib/session-bootstrap.ts:44-53` | `sendLiveUserMessage(sessionId, text)` → `submitUserMessage` + query-cache touches |
| `src/lib/agent-client.ts:93-103` | `submitUserMessage` — `POST ${API}/sessions/${id}/messages`, body `JSON.stringify({ text })` |
| `src/lib/agent-client.ts:84-91` | `SubmitMessageResponse {accepted, event_id}` — event_id used as optimistic bubble id |

- The composer sends **text only**. Nothing on this path reads workspace form state today.
- Where FE could source the dirty draft at send time:
  - `useFormDirtyRegistry` (`src/components/workspace/useFormDirtyRegistry.ts:8-18`): entries carry `{id, label, isDirty, isValid, reset}` — **no value accessor**. `selectAnyDirty` / `selectDirtyLabels` / `resetAllDirty` (`:74-92`) already give a global dirty signal reachable from ChatPanel (`ParameterDesignPanel.tsx:166` shows the `selectAnyDirty(useFormDirtyRegistry.getState())` call pattern).
  - Actual values live only behind `formRef` (`DynamicFormHandle.getValues`): held by `ParameterDesignPanel.tsx:179`, read at footer CTAs `:853` / `:863` (`formRef.current?.getValues() ?? {}`). The forms register via `useParamsFormHandle` (`useImperativeHandle` at `forms/useParamsFormHandle.ts:57-66`).
  - So the minimal FE change shape is: extend the dirty-registry entry with a `getValues` handle (the registry is the only surface that spans workspace→chat), plus the trial id (`shownTrial?.trialId`, `ParameterDesignPanel.tsx:195`) and executor.

### BE path (BIC-agent-service)

| File:Line | Role |
|---|---|
| `app/api/routers/sessions.py:65-69` | `SubmitUserMessageRequest {text: 1..10_000}` — `extra="forbid"` |
| `app/api/routers/sessions.py:85-106` | Route: mints `TurnInput(kind=USER_MESSAGE, source=USER, user_message=UserMessagePayload(text))` **at API time** so `turn_id` is fixed before the event persists; 202 |
| `app/data/turn_schemas.py:22-28` | `UserMessagePayload {text}` — frozen, `extra="forbid"` |
| `app/data/turn_schemas.py:87-109` | `TurnInput` — frozen envelope; exactly one payload field non-None per kind |
| `app/session/service.py:102-154` | `submit_user_message`: `assert_user_owns` (`:137`) → mint `UserMessageSubmittedEvent` (`:145-149`) → `orchestrator.persist_event` + `broadcaster.emit` (`:150-151`) → `orchestrator.submit_turn` (`:153`); fail-loud ordering (event fails ⇒ turn never enqueued) |
| `app/events/orch_emitted.py:43-58` | `UserMessageSubmittedEvent {text}` — apply is a noop (pure session-log marker); persisted BEFORE worker enqueue so bubble survives refresh |
| `app/session/orchestrator.py:328-343` | Worker dequeues `TurnInput`, loads ctx, runs `runtime.invoke(ctx, turn_input)` |

- Invariant: `seq(user_message_submitted) < seq(turn_started)` via BIGSERIAL (contracts.md §3a; `service.py:114-118`).
- Idempotency: none server-side on `/messages` — FE must dedupe (`L1/http-routes.md:267,276`).

### DTO sharing

- `SubmitUserMessageRequest` / `SubmitUserMessageResponse` are **defined inline in `app/api/routers/sessions.py`** — NOT in BIC-shared-types. BIC-shared-types carries Mind/robot/MQ contracts (`bic_shared_types/clients/...`), not the FE↔BE session REST DTOs.
- FE mirrors by hand per portal convention (portal CLAUDE.md: "update `src/types/events.ts` / `src/lib/agent-client.ts` first... header comments cite the authoritative backend file paths").
- Contract doc of record: `.trellis/spec/BIC-agent-portal/backend-contract.md:51` (the `/messages` row) + `.trellis/spec/BIC-agent-service/backend/contracts.md:125-159` (§3a).

### Where a form-draft attachment could ride

Two in-pattern options surfaced by the code:

1. **Same request** — extend `SubmitUserMessageRequest` with an optional draft field (e.g. `{trial_id, params}` or per-executor). Every hop is `extra="forbid"`, so the thread is explicit: `sessions.py:65` → `UserMessagePayload` (`turn_schemas.py:22`) and/or `UserMessageSubmittedEvent` (`orch_emitted.py:43`).
   - If put on `UserMessageSubmittedEvent`: it persists to `session_events` and replays over SSE — FE `user_message_submitted` handling and `decode_history` (`orchestrator.py:570-599`, reads `payload["text"]` only) are unaffected unless deliberately surfaced. Event kinds registry: FE `src/types/events.ts` + `KINDS` in `sse-client.ts` unchanged (same kind).
   - If put only on `UserMessagePayload` (turn envelope, not the event): it reaches the worker/L3 without touching the event stream — but then the draft is NOT durable if the queue is lost (contra the reason the event is persisted synchronously, `contracts.md:159`).
2. **Immediately-before sibling request** — a lenient draft POST modeled on `POST /sessions/{id}/objective/draft` (see `objective-draft-precedent.md`), persisting to `trials.params` (via an event so live tabs sync) before the `/messages` POST. Then the existing `reception_node.py:437` whole-blob re-seed + a SessionContext/prompt surface carries it to the LLM with no `/messages` contract change. Two POSTs = ordering handled by FE `await` (the turn only starts after `/messages` lands, and the worker queue serializes per session — `orchestrator.py:298-326`).

## Caveats / Not Found

- No existing FE code path passes any workspace state with a chat message — this is net-new wiring on the FE regardless of option.
- `SubmitUserMessageRequest.text` has a 1..10_000 length gate; a draft blob must be its own field, not smuggled into `text`.
- Concurrency note: form-confirm (`/forms/confirm`) is a different, CAS-guarded path (`sessions.py:151-166`, `orchestrator.py:383-438`) — the draft-on-send flow must not be confused with confirm; confirm stays the only phase-advancing write.
