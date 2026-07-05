# PRD — Repair stale FE E2E selectors masking suite signal

Lightweight cleanup task (PRD-only). Repo: BIC-agent-portal.

## Problem

Two consecutive live E2E runs showed ~12-21 failures dominated by STALE test
selectors, not product regressions — masking real signal. Three rot sites:

1. **Composer placeholder regex (dominant).** Source placeholders are now
   `Composer.tsx:121` home = "Ask for status, design a workflow, or describe the
   next operation..." and `:172` in-session = "Ask the agent…". 9 specs (14
   occurrences) still match `/Ask the agent|Type your question/` — "Type your
   question" no longer exists, so `getByPlaceholder(...).fill()` times out on the
   fresh `/` route. The PROVEN-correct pattern (used by 3 already-passing specs:
   tlc-retry-flow, tlc-e2e-final-chain, tlc-params-tube-selector) is
   `/Ask the agent|Ask for status|design a workflow/`.
2. **portal-smoke heading.** `portal-smoke.spec.ts:133` asserts heading
   `/I am Talos, your lab assistant\./` — copy removed; UI now shows "Talos
   control desk" (`BrandHeader.tsx:26`, `HomeHero.tsx:63`).
3. **workspace-state-gating.** `workspace-state-gating.spec.ts:5` "dispatch-only
   ... hides Monitor" asserts `lifecycle-tab-monitor toHaveCount(0)` — stale since
   commit b57260e made all three lifecycle tabs always render.

## Scope / requirements

- R1: Replace the stale composer regex in the 9 specs with the proven pattern.
  Specs: reasoning-streaming, live-backend-plan, live-backend, confirm-msg-bubble,
  tlc-upload-chain, task-progress-stream, manual-live-demo, cc-re-chained-flow,
  persist-bubbles-hard-refresh. (tlc-retry-flow already uses a composerSel
  constant — update that constant if it carries the stale text; the 3 passing
  specs already use the correct regex — do not touch.)
- R2: Fix portal-smoke heading assertion to the current "Talos control desk" copy
  (or the current home hero heading — verify against source).
- R3: Fix workspace-state-gating "dispatch-only" test to the post-b57260e
  behavior: Monitor/Result tabs always render; assert the dispatch-only INTENT a
  different way (e.g. active tab stays Task, Monitor pane shows its empty/again
  state) rather than tab absence. Rule 7 — keep the test meaningful, don't just
  delete the assertion.

## Out of scope

- Genuine product/SSE-stall failures (tlc-retry-flow TLC-params late render,
  attempt-switcher, rack-layout DOM drift) — those are NOT stale selectors and
  are tracked separately. This task ONLY repairs stale test code.

## Acceptance criteria

- [ ] AC1: The 9 placeholder specs locate the composer (no placeholder timeout).
- [ ] AC2: portal-smoke passes (heading assertion matches current copy).
- [ ] AC3: workspace-state-gating "dispatch-only" passes AND still verifies the
  dispatch-only intent (Rule 7 — not a hollowed-out assertion).
- [ ] AC4: No NON-stale spec is altered (the 3 already-passing placeholder specs
  untouched; no product code touched).

## Constraints

- Surgical (Rule 3): test files + nothing in src/. Match the proven regex pattern
  exactly (Rule 8). Port 5173, bypass localhost proxy.
