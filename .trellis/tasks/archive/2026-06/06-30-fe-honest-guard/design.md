# Design — FE honest browser-path guard (Child B)

Read `prd.md` first. Test code only; the existing three specs stay byte-unchanged.

## The principle

The existing specs prove the **backend contract** and recover like no real user can
(backend-truth asserts + reload + `/events` fallback + nudge). This spec proves the
**user can see the flow happen**. Its pass condition is a user-observable outcome, not
a technical contract — the named fix for "green suite, blank screen".

It must be the photographic negative of `cc-re-chained-flow.spec.ts`:

| `cc-re-chained-flow.spec.ts` (keep as-is) | New honest guard (this child) |
|---|---|
| in-page capture → falls back to `/api/sessions/:id/events` at every gate | DOM only; NO `/events`, NO `/snapshot`, NO psql |
| `waitForReviewHeading` reloads if heading missing | NO `page.reload()` mid-flow |
| `waitForParamsForm` nudges agent if no form | NO nudge fill |
| `window.__taskProgressEvents` mirror | NO `window.__*` |
| final asserts read persisted events | final asserts read visible DOM |

## Scope (MVP — one chain)

Guard the **TLC→CC→RE full chain** — the scenario that freezes manually. The TLC
auto-retry honest spec is a follow-up, not MVP (PRD R5). One honest full-chain guard
that bites is worth more than two half-built ones (Rule 2).

## What it drives (real user actions only)

1. Reset bench (reuse `resetLabState` — pure setup, allowed; it is NOT a recovery
   crutch). Open chat, send the chemist prompt.
2. For each leg (TLC, CC, RE): wait for the params form to appear **on screen**
   (`expect(locator).toBeVisible()`), chemist-edit required fields like a real user
   (cartridge slot, RE `{duration_min:1, pressure_mbar:1}`), click Confirm.
3. Wait for the result card / "Experiment Review" heading to render **on screen**,
   click "Accept result", wait for the visible "Confirmed result review." bubble.
4. Final assertions = visible DOM only:
   - both result cards coexist: `result-stage-cc` + `result-stage-re` visible;
   - exactly 2 "Confirmed result review." bubbles visible;
   - no error/toast surface visible.

## The hard rule: no escape hatches

Every wait is `expect(domLocator).toBeVisible({ timeout })` with a generous per-leg
timeout sized to real robot duration (CC/RE minutes; cap per leg). When the stream
stalls, the locator never appears, the assertion times out, the spec goes **red**.
There is deliberately no recovery path. This is the whole point.

Helpers allowed: `resetLabState` (bench setup). Helpers FORBIDDEN: `waitForParamsForm`
(nudges), `waitForReviewHeading` (reloads), any `fetchEvents`/snapshot/psql helper.

## Config / runner

- New file `tests/honest-chain-guard.spec.ts`, default `playwright.config.ts`
  (`testIgnore`s only `manual-live-demo`). `--workers=1` (one live bench).
- Per-leg `expect` timeout must exceed real robot time; set explicit `{ timeout }` per
  assertion (the default 30s would false-fail a legit 2-min CC). Document the chosen
  caps inline citing bench durations.
- Requires portal `:5173` + agent BE `:8800` up; reset both sides first.

## How AC2 (the red proof) works

- **Heartbeat ON (Child A landed):** stream stays warm → all DOM locators appear →
  spec GREEN (AC1).
- **Heartbeat OFF (or injected stall):** stream stalls during a long robot wait → the
  next result card never renders → spec times out → RED, while the existing three
  specs stay green (they read backend + reload). That divergence is the deliverable.
- Today, BEFORE Child A, the spec can be observed RED on a real freeze — the
  bug-visible proof, immediately.

## What this does NOT do

- No edits to `tlc-retry-flow` / `cc-re-chained-flow` / `tlc-e2e-final-chain`.
- No product code. No new helpers in `helpers.ts` unless purely DOM (prefer inline).
- Does not assert backend correctness — that is the existing specs' job; this one
  asserts only what the chemist sees.
