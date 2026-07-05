# FE honest browser-path E2E guard

Parent: `06-30-sse-heartbeat-honest-guard`. This is **Child B — the alarm**.

## Goal

Add a NEW Playwright spec that drives a full chain and asserts ONLY on the visible
DOM a chemist sees. It MUST go RED when the live UI freezes on an SSE stall, even
though backend truth is correct — turning today's invisible bug into a failing test.
**Test code only.**

## Why a new spec (not edits to existing ones)

The three existing specs are valid **backend-contract** proofs and stay unchanged.
They are green-through-a-freeze by design (backend-truth asserts + reload/fallback/
nudge recovery). Editing them to be "honest" would destroy their contract-proof value
and violate Drake's separation rule. The honest path is a SEPARATE, additive spec.

## Requirements

- **R1 (visible-DOM-only asserts)** Every success assertion reads on-screen state the
  user sees: chat bubbles, result cards (`result-stage-cc` / `result-stage-re`),
  the "Experiment Review" heading, "Confirmed result review." text, Accept buttons.
- **R2 (NO backend fallback)** Forbidden in this spec: `page.request.get('/api/sessions/.../events')`,
  `/snapshot`, any psql, and any `window.__*` capture mirror. If the UI doesn't show
  it, the spec fails. (Contrast: `cc-re-chained-flow.spec.ts` falls back to `/events`
  at every gate — that is exactly what we must NOT do here.)
- **R3 (NO recovery crutches)** No `page.reload()` mid-flow, no `waitForReviewHeading`
  reload branch, no `waitForParamsForm` nudge (no "Please proceed with the parameters."
  composer fill). A frozen page must stay frozen and the spec must time out → red.
- **R4 (real waits)** Use Playwright auto-retrying assertions (`expect(locator)...`)
  on DOM, with generous per-step timeouts tuned to real robot durations (RE air_pressure
  edited to `{duration_min:1, pressure_mbar:1}` per bench convention to keep runs short).
- **R5 (scope)** Pick ONE canonical full chain to guard first — recommend the
  TLC→CC→RE chain (the scenario that freezes). The TLC auto-retry scenario can be a
  second honest spec later; MVP is one honest full-chain guard.
- **R6 (separation)** New file under `tests/`; the existing three specs are byte-
  unchanged; no product code touched. May reuse pure bench-setup helpers
  (`resetLabState`) but NOT the recovery/fallback helpers.

## Acceptance Criteria

- [ ] **AC1 (passes healthy)** With heartbeat enabled (Child A landed), the new spec
      passes against a healthy stream, end to end, reading only the DOM.
- [ ] **AC2 (fails frozen)** With heartbeat DISABLED (or an injected stall), the new
      spec FAILS (times out on a DOM element that never renders) while the existing
      three specs still pass — the proof the alarm actually bites. This red/green
      demonstration is the deliverable, not just a passing run.
- [ ] **AC3 (no forbidden calls)** Grep the new spec: zero `/api/sessions`, zero
      `/snapshot`, zero `window.__`, zero `page.reload(`, zero nudge fills.
- [ ] **AC4 (separation)** `git diff` shows only a new test file (+ optional helper);
      the three existing specs unchanged; no `src/` or backend change.

## Constraints

- Test code only — touches no product code.
- `--workers=1` (one live bench). Requires portal `:5173` + agent BE `:8800` up.
- Reset both sides before the run (lab `/admin/reset-to-test-data`, agent `/reset`).
- Depends on Child A for the AC2 red/green demo (toggle heartbeat). The spec itself
  can be authored independently and first observed RED today (no heartbeat yet) — that
  IS the bug-visible proof.
