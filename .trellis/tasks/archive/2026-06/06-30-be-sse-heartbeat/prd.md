# BE SSE heartbeat keepalive

Parent: `06-30-sse-heartbeat-honest-guard`. This is **Child A — the cure**.

## Goal

Emit a periodic SSE keepalive comment on `GET /sse/{session_id}` so an idle stream
is never silently reaped by the local `7890` proxy or a half-open TCP, and so a real
drop surfaces fast enough for native `EventSource` reconnect + `Last-Event-ID` replay
to recover. **Product code only.**

## Where

- `BIC-agent-service/app/api/routers/sse.py`
  - `event_stream()` generator (`:96-98`) — currently `async for ev in stream: yield _encode(ev)`.
  - `_encode()` (`:107-117`) — emits `id:`/`event:`/`data:`.
- The keepalive is a comment line: `: keepalive\n\n` (leading colon = SSE comment,
  ignored by `EventSource`, surfaces on FE `onmessage`, which the FE already tolerates
  — `sse-client.ts:110-111`).

## Requirements

- **R1** Inject a `: keepalive\n\n` write on a fixed interval (~15s; final value is a
  design decision — must be < the proxy/LB idle timeout) WITHOUT blocking real event
  delivery. The interval races against `async for ev in stream`; the design must merge
  the heartbeat tick with the event drain (e.g. `asyncio.wait_for` timeout on the
  stream pull, or a merged async iterator). Do NOT serialize behind a slow event.
- **R2** Keepalive MUST NOT carry an `id:` line (it is not a replayable event) and
  MUST NOT advance the replay cursor / `session_seq`.
- **R3** On client disconnect the heartbeat machinery MUST be cancelled/cleaned up
  (no leaked timers/tasks — the documented #1 SSE footgun).
- **R4** No change to event ordering, framing, or the `Last-Event-ID` replay path.

## Acceptance Criteria

- [ ] **AC1** `curl --noproxy '*' -N http://localhost:8800/api/sse/<sid>` on an idle
      session shows `: keepalive` lines arriving on the ~15s cadence.
- [ ] **AC2** A full manual chain (both scenarios) no longer freezes on screen —
      keepalives flow throughout the long robot waits (rolls up to parent AC2).
- [ ] **AC3** BE pytest green (`uv run pytest -q`); replay-on-reconnect still recovers
      a gap (`Last-Event-ID` path unbroken).
- [ ] **AC4** No leaked asyncio tasks after a client disconnects.

## Spec impact (Rule 10)

- If keepalive cadence becomes a contractual guarantee the FE relies on, update the
  L3 `sse-contract` spec in THIS change set. Read it before editing the writer.

## Constraints

- Product code only — no test-file edits in this child.
- Read `sse.py` + `broadcaster.py` register/replay before touching the writer
  (Rule 6); heartbeat must not interfere with the two-phase replay→live handoff.
