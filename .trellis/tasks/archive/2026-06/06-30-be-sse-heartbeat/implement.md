# Implement — BE SSE heartbeat (Child A)

Product code only. Read `design.md` first. No test-file edits to FE; BE test is part
of this child (tests the BE contract, not the FE).

## Ordered checklist

1. **Reproduce the freeze (parent AC1 — do this FIRST, fail loud if it won't repro).**
   - Reset both sides (`/admin/reset-to-test-data` + agent `/reset`, `--noproxy '*'`).
   - Run a manual full chain in the browser; when it freezes, `curl --noproxy '*' -N`
     the SSE stream and `curl --noproxy '*' /api/sessions/:id/events` — confirm BE has
     events the frozen page never rendered. Record evidence in the task log.
   - If it does NOT reproduce: STOP, re-scope with Drake (the cure may be wrong).

2. **Add the interval constant** — `broadcaster.py:~42`:
   `HEARTBEAT_INTERVAL_S = 15` (next to `MAX_REPLAY_EVENTS`).

3. **Add the keepalive sentinel** — `broadcaster.py` module level:
   `_KEEPALIVE = SerializedEvent(session_seq=None, kind="keepalive", payload_bytes=b"")`.

4. **Wrap the live-drain pull** — `broadcaster.py` `_gen()` Phase 2 (`:149`):
   replace `item = await conn.outbox.get()` with the `asyncio.wait_for` + `TimeoutError
   → yield _KEEPALIVE; continue` block from `design.md`. Phase 1 replay untouched.

5. **Add the encoder branch** — `sse.py` `_encode()` (`:107`), as the FIRST line:
   `if ev.kind == "keepalive": return b": keepalive\n\n"`.

6. **Update the spec (Rule 10, same change set)** — `sse-handler.md`:
   - § "Heartbeat / Idle Keepalive": replace "MVP does not emit" with the 15s
     broadcaster-emitted keepalive + sentinel mechanism.
   - Fix path drift: `app/api/sse_handler.py` → `app/api/routers/sse.py`.
   - Add the FE-contract row for the keepalive comment.

7. **Add a BE test** (Rule 7 — encodes WHY): in `tests/` near
   `test_broadcaster_replay.py` / `test_sse_replay.py`:
   - idle connection yields `: keepalive` after the interval (use a short patched
     interval, not a real 15s sleep);
   - keepalive is NOT counted as a replayable event (replay/live counts unchanged);
   - an event arriving right as the heartbeat fires is not lost;
   - keepalive carries no `id:` (cannot pollute `Last-Event-ID`).

## Validation commands

```bash
cd BIC-agent-service
uv run ruff check app/ && uv run ruff format --check app/
uv run pyright app/
uv run pytest -q                       # incl. new heartbeat test + existing replay tests
# manual cure proof (parent AC2):
curl --noproxy '*' -N http://localhost:8800/api/sse/<sid>   # see ": keepalive" every ~15s
```

## Review gates

- After step 5: diff is product-only (`broadcaster.py` + `sse.py`) + spec — no FE,
  no test-code coupling (parent AC5 BE side).
- After step 7: `uv run pytest` green INCLUDING the existing replay tests (AC3).
- Final: manual chain (both scenarios) runs without freeze (parent AC2).

## Rollback

Single-commit, additive. Revert the commit; behavior returns to no-heartbeat MVP.
No migration, no data change, no config change.
