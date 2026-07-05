# Design — BE SSE heartbeat (Child A)

## ⚠️ Spec correction vs. PRD (Rule 5 / Rule 10)

The PRD proposed putting the heartbeat in L1 (`sse.py` `event_stream()`). **The L1 spec
forbids this.** `sse-handler.md:111-113`:

> "MVP does not emit explicit SSE comment heartbeats... If a future deployment behind
> aggressive proxies needs heartbeats, **add them in the broadcaster (so L1 stays a
> pure encoder)**."

So the heartbeat lives in **L2 broadcaster** (`app/session/broadcaster.py`), not L1.
L1 gains only a tiny encoder branch for the comment. This is the spec's own
anticipated path — our `127.0.0.1:7890` proxy is exactly the "aggressive proxy" case.

## Where it goes (verified against real code)

| Concern | Location |
|---|---|
| Heartbeat tick | `broadcaster.py` `_gen()` Phase-2 live-drain loop (`:149-169`) |
| Wire encoding | `app/api/routers/sse.py` `_encode()` (`:107-117`) — add comment branch |
| Interval constant | `broadcaster.py` module constants (`:38-42`, next to `MAX_REPLAY_EVENTS`) |
| Cleanup | existing `finally: self._remove_connection(conn)` (`:170-171`) — **no new teardown** |

Path drift noted: spec says `app/api/sse_handler.py`; real path is
`app/api/routers/sse.py`. Reconcile in the spec update (R5).

## Approach — timeout on the queue pull (no background task)

The live-drain loop currently blocks on `await conn.outbox.get()`. Wrap it in
`asyncio.wait_for(..., timeout=HEARTBEAT_INTERVAL_S)`; on `TimeoutError`, yield a
keepalive sentinel and continue. **Chosen over a background `asyncio.Task`** because:

- The timeout is self-cancelling — nothing to leak, nothing to cancel in `finally`
  (satisfies R3 with zero new cleanup code; Rule 2 simplicity).
- A real event still pulls immediately (the timeout only fires when truly idle), so
  no added latency on the hot path (R1).
- Replay (Phase 1) is untouched — heartbeat only exists in the live phase, so the
  replay-then-live dedup race is unaffected (R4).

```python
# broadcaster.py  _gen() Phase 2
while True:
    try:
        item = await asyncio.wait_for(conn.outbox.get(), timeout=HEARTBEAT_INTERVAL_S)
    except TimeoutError:                       # py3.12: asyncio.TimeoutError is TimeoutError
        yield _KEEPALIVE                        # module-level sentinel (see below)
        continue
    if item.serialized is None:
        ...kick sentinel — unchanged...
    ...existing dedup gate unchanged...
```

## Wire representation — keepalive sentinel SerializedEvent

A keepalive is an SSE **comment** (`: keepalive\n\n`) — no `id:`/`event:`/`data:`.
`SerializedEvent` can carry it as a sentinel; `_encode()` special-cases it:

```python
# broadcaster.py (module level)
_KEEPALIVE = SerializedEvent(session_seq=None, kind="keepalive", payload_bytes=b"")

# sse.py _encode()  (add as the FIRST branch)
if ev.kind == "keepalive":
    return b": keepalive\n\n"        # comment — browser ignores, proxy stays warm
```

`session_seq=None` guarantees **no `id:` line** even if the branch were missed, so it
can never pollute `Last-Event-ID` (consistent with the D41 `text_delta` rule). The FE
already tolerates comment lines via `onmessage` (`sse-client.ts:110-111`) and they
match no named `KINDS` listener, so they are silently ignored on the client — correct.

## Interval

`HEARTBEAT_INTERVAL_S = 15` as a `broadcaster.py` module constant (mirrors
`REPLAY_BATCH_SIZE` / `MAX_REPLAY_EVENTS` placement). 15s is the research-recommended
floor and is < typical proxy idle timeouts. **Not** added to `config.py` — no
per-environment need yet (Rule 2); promote later if a deployment requires it.

## Contract / spec impact (R5, Rule 10)

`sse-handler.md` currently says "MVP does not emit heartbeats". This change makes it
emit them. Update `sse-handler.md` § "Heartbeat / Idle Keepalive" in the SAME change
set: document the 15s broadcaster-emitted `: keepalive\n\n`, the sentinel mechanism,
and fix the `app/api/routers/sse.py` path drift. The FE contract table gains one row:
"comment keepalive every ~15s → ignored by client, keeps proxy connection warm".

## What this does NOT touch

- Replay path (`_replay`, Phase 1) — unchanged.
- Dedup gate, kick sentinel, outbox overflow — unchanged.
- `_Connection` dataclass — unchanged (no per-conn task needed).
- `config.py` — unchanged.

## Risks

- **Heartbeat counted as an event in tests** — existing tests `_drain(stream, limit=N)`
  expect exactly N real events. Idle-timeout heartbeats could leak in. Mitigated:
  tests pull events faster than 15s, but the new BE test (below) must assert
  heartbeats are NOT counted in replay/live event counts. Verify against
  `tests/unit/test_broadcaster_replay.py` + `tests/integration/test_sse_replay.py`.
- **`asyncio.wait_for` cancels the inner `get()` on timeout** — the awaited
  `outbox.get()` is cancelled cleanly each interval; confirm no item is lost (an item
  arriving exactly at timeout). asyncio guarantees the future is cancelled before
  TimeoutError propagates; a queued item stays in the queue for the next `get()`. Safe,
  but the new test must cover "event arrives right as heartbeat fires".
