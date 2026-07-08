# SSE freeze: heartbeat cure + honest browser-path guard

## Goal

The two demo scenarios — **(1) TLC auto-retry** and **(2) full workflow TLC→CC→RE** —
freeze the UI when run **manually in a real browser**, yet the Playwright E2E suite
reports **green**. "Green" must mean "a chemist can actually get through the flow on
screen", not "the backend emitted the right events". Today it means only the latter.

Close that gap with two independently-verifiable deliverables:

- **Child A (BE heartbeat)** — the *cure*: emit a periodic SSE keepalive so the live
  stream is never silently reaped, so reconnect+replay recovers fast.
- **Child B (FE honest guard)** — the *alarm*: a new spec that goes RED when the
  visible UI freezes, so this class of bug can never hide behind a green suite again.

## Root cause (evidence, not hypothesis)

Verified by source inspection this session:

1. **Heartbeat ABSENT.** `BIC-agent-service/app/api/routers/sse.py:107-117` `_encode()`
   emits only `id:` / `event:` / `data:`. The `event_stream()` generator
   (`sse.py:96-98`) yields encoded events only — **no periodic `: keepalive\n\n`
   comment**. Nothing keeps an idle connection warm.
2. **Replay PRESENT and DONE.** `Last-Event-ID` parsing (`sse.py:45-63`) + broadcaster
   replay (`broadcaster.py:92-173`) + FE seed (`sse-client.ts:22`) are implemented;
   task `05-27-sse-replay` is archived. Replay works **once a reconnect happens**.
3. **Reconnect depends on a clean drop.** FE (`sse-client.ts:104-122`) relies on native
   `EventSource` to fire `onerror` → `connect()` and re-send `Last-Event-ID`. With no
   heartbeat, the local `127.0.0.1:7890` proxy / a half-open TCP can leave the stream
   idle without a prompt `onerror`, so reconnect (and therefore replay) does not fire
   for tens of seconds → **frozen page**. Matches the manual symptom ("page freezes /
   nothing happens") and the documented SSE failure mode (sloppy reconnect, 30s+,
   "heartbeat is a must-have").
4. **The suite is structurally blind.** All three relevant specs converge on backend
   truth and recover in ways a user cannot:
   - `tlc-retry-flow.spec.ts` — final asserts via psql + `/snapshot` + `/events`;
     conditional `page.reload()` recovers the one UI wait.
   - `cc-re-chained-flow.spec.ts` — in-page SSE capture with a **`/api/sessions/:id/events`
     fallback at every gate** + conditional reload.
   - `tlc-e2e-final-chain.spec.ts` — psql-only final asserts; zero dynamic UI waits.
   Per-spec verdict: **all three would pass through a frozen UI.**

## Requirements

- **R1 (Cure)** The SSE stream MUST emit a keepalive comment on a fixed interval
  (target ~15s) so an otherwise-idle connection is not reaped, and a real drop
  surfaces fast enough for native reconnect + `Last-Event-ID` replay to recover.
- **R2 (Contract-safe)** The keepalive MUST NOT alter the `id:`/`event:`/`data:`
  framing or the replay cursor semantics. FE already tolerates unnamed/keepalive
  lines via `onmessage` (`sse-client.ts:110-111`) — confirm, don't assume.
- **R3 (Alarm)** A NEW Playwright spec MUST drive a full chain and assert ONLY on
  the visible DOM, with **no** `/events` fallback, **no** `page.reload()` recovery,
  **no** `waitForParamsForm` nudge, **no** `window.__*` capture. It MUST fail when
  the live UI freezes even though backend truth is correct.
- **R4 (Separation — Drake's hard rule)** Test changes touch only `tests/`; product
  changes touch only `app/`. Child A introduces no test coupling; Child B edits no
  product code and does NOT modify the existing three specs (they remain valid
  backend-contract proofs).
- **R5 (Spec sync, Rule 10)** If the keepalive becomes part of the wire contract,
  update the L3 `sse-contract` spec in the same change set as Child A.

## Acceptance Criteria

- [ ] **AC1 (reproduce first)** The freeze is reproduced live (manual run + `curl
      --noproxy '*' /api/sessions/:id/events` showing BE has events the page is
      missing) BEFORE the fix — so the cure is proven against a real repro, not
      assumed. Fail loud if it cannot be reproduced (re-scope if so).
- [ ] **AC2 (cure works)** With heartbeat enabled, the same manual full-chain run
      (both scenarios) completes on screen without a freeze across repeated runs.
- [ ] **AC3 (contract intact)** Existing BE SSE tests + the three E2E specs still
      pass; replay-on-reconnect still works (`Last-Event-ID` path unbroken).
- [ ] **AC4 (alarm bites)** The new honest-guard spec PASSES on a healthy stream and
      FAILS when the UI is frozen — demonstrated by temporarily disabling heartbeat
      (or simulating a stall) and observing the spec go red while the old specs stay
      green. This is the proof the alarm actually catches the bug.
- [ ] **AC5 (separation honored)** Child A diff is product-only; Child B diff is
      test-only and leaves the existing three specs byte-unchanged.

## Constraints

- Test code must not affect real product code, and vice versa (R4).
- Local proxy `127.0.0.1:7890` breaks localhost curl — always `--noproxy '*'` or
  unset proxy envs when probing.
- `05-27-sse-replay` is DONE — do NOT rebuild replay; the missing piece is heartbeat.

## Task map

- **Child A** `06-30-be-sse-heartbeat` (BIC-agent-service) — the cure.
- **Child B** `06-30-fe-honest-guard` (BIC-agent-portal) — the alarm.
- Ordering: A and B are independent and can proceed in parallel. AC4 needs A's
  heartbeat toggle to demonstrate red→green, so run B's red/green proof after A
  lands (or by manually disabling heartbeat).

## Notes

- This is the named anti-pattern: "an API returns the right response and the user
  still sees a blank screen" — the fix is a pass condition that is a user-observable
  outcome, not a technical contract.

## Closeout (2026-06-30)

All three children implemented + committed; 957 BE pytest green. Scope grew by one
child (C, plan-stage prompt fix) when child B's first live run surfaced a SECOND bug
(plan-stage prose abandon asking for a SMILES it doesn't need).

- A `06-30-be-sse-heartbeat` — commit `cf355fb` (agent-service `feat/tlc-objectlocation-passthrough`)
- C `06-30-plan-stage-backstop` — commit `10a7428` (same branch); PROMPT fix, not a
  routing backstop (Drake rejected determinism — keep plan a real LLM+tools call)
- B `06-30-fe-honest-guard` — commit `2ae117c` (portal `feat/portal-lifecycle-objective-form`)

**DEFERRED (Rule 9 — not done, not silently dropped):** live bench verification.
AC1 (reproduce freeze), AC2 (manual chain no freeze), AC4 (honest spec red→green when
heartbeat toggled), AC6/B-AC5 (honest spec passes the plan gate end-to-end) ALL require
a `bic-e2e-runner` live run with the agent BE restarted to load the heartbeat. Code
landed + unit-verified; live proof intentionally deferred by Drake. Re-open / re-run
before relying on the green as a user-facing guarantee.
