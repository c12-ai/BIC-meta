# Post-TLC Follow-ups: Playwright Flake + Placeholder Test Stale-Sync

## Goal

Close out two test-quality issues surfaced during the AWS S3 China verification of `06-03-tlc-image-s3-persistence`:

1. **FE — Playwright T2 race.** `tests/tlc-upload-chain.spec.ts` uses `page.on('response', ...)` to capture the `POST /tlc/recognize` response, but the listener loses the race against the e2e assertion in ~50% of runs even though the server returns 200. Replace with `page.waitForResponse(predicate)`.
2. **BE — `test_handle_task_status_transition_placeholder_no_emit` is stale.** The test still asserts the OLD `in_progress → in_progress` silent-return behavior; the handler was deliberately changed to **emit** every non-None `derived_key` (including the placeholder case) to keep the FE step strip live. Update the test + reconcile the handler's docstring with the actual behavior.

## What I already know

**Issue 1 (Playwright, FE):**
- File: `BIC-agent-portal/tests/tlc-upload-chain.spec.ts:141`
- Pattern: `let recognized: RecognizeCapture | null = null; page.on('response', async (r) => { ... recognized = { ... } })`
- Assertion at `:190` fires before listener callback completes its `await r.text()`.
- Backend logs prove `POST /tlc/recognize` returns 200 and emits `tlc_recognized` event — pure test-side race.
- Standard Playwright fix: `const recognized = await page.waitForResponse(r => r.url().includes('/tlc/recognize') && r.request().method() === 'POST', { timeout: 60000 })` — returns a `Response` directly, no race.

**Issue 2 (BE handler test, stale-sync):**
- Test: `BIC-agent-service/tests/unit/test_fast_path_handlers_system.py:308` `test_handle_task_status_transition_placeholder_no_emit`
- Asserts: `broadcaster.emit.assert_not_awaited()` + `announced_transitions == ["pending_to_in_progress"]`
- **Current handler behavior** (`app/session/fast_path_handlers.py:391-405`): emits on every non-None `derived_key`, including `in_progress_to_in_progress` placeholder. Explanation in code comment at line 391-399:
  > "Dropping those events left the workspace step strip frozen on the first snapshot for the entire task duration. Emit on every non-None derived_key so each Lab push surfaces to the FE."
- **Stale docstring** at line 374-377 still says "`in_progress_to_in_progress` (placeholder) → silent return". Contradicts the actual code 17 lines below.
- This is case E (test outdated to deliberate code change), NOT case D (code regression). Confirmed by reading the handler.

## Locked decisions

- **Bundle both fixes in one task** (Option A from brainstorm) — both surfaced from the same verification run, both are 1-file edits.
- **Issue 1 fix shape:** replace `page.on('response')` + null state + manual try/catch with `page.waitForResponse(predicate, { timeout })`. Standard Playwright idiom.
- **Issue 2 fix shape:** update the test to assert the **current** behavior (emit fires once on the second in_progress; `announced_transitions` array reflects two entries) AND reconcile the handler docstring at line 374-377 to match the code below it.

## Requirements

1. `BIC-agent-portal/tests/tlc-upload-chain.spec.ts` T2 uses `page.waitForResponse(...)` for `/tlc/recognize`. No more `page.on('response', ...)` for this purpose.
2. T2's race condition is gone — `recognized` is always populated before the assertion runs (because `waitForResponse` blocks until the response is available).
3. `BIC-agent-service/tests/unit/test_fast_path_handlers_system.py::test_handle_task_status_transition_placeholder_no_emit` is updated to match the current handler behavior:
   - `broadcaster.emit.assert_awaited()` (NOT `assert_not_awaited`)
   - `announced_transitions` reflects the actual recorded keys after two `in_progress` calls
4. `BIC-agent-service/app/session/fast_path_handlers.py` docstring at line 374-377 reconciled with the code at line 391-405 — no more conflicting claims.
5. The test's name is updated to reflect the new behavior (`_placeholder_no_emit` is misleading; suggest `_placeholder_emits_for_step_strip` or similar). Keep the original test as a regression marker if helpful, or rename — pick one (don't keep both).

## Acceptance Criteria

- [ ] AC1: `BIC-agent-portal/tests/tlc-upload-chain.spec.ts` T2 passes 5/5 consecutive runs (no flake).
- [ ] AC2: `pnpm playwright test tests/tlc-upload-chain.spec.ts` exits green with 3/3 tests passing.
- [ ] AC3: `uv run pytest tests/unit/test_fast_path_handlers_system.py` exits green with all 13 tests passing (currently 12/13).
- [ ] AC4: Re-reading `fast_path_handlers.py:370-410` shows the docstring and code in agreement.
- [ ] AC5: `ruff check . && uv run ruff format --check . && uv run pyright app/` green on agent-service.
- [ ] AC6: Frontend lint/typecheck green on portal (whichever the project uses — `pnpm lint` / `pnpm typecheck`).

## Definition of Done

- AC1–AC6 satisfied
- One bundled commit per repo (one for portal, one for service) — see Out of Scope re. cross-repo commit
- No regression in adjacent tests
- Updated PRD + this task archived via `/trellis:finish-work`

## Out of Scope (explicit)

- The pre-existing parallel-window dirty work (`app/session/orchestrator.py` refactor, `app/session/worker.py`, `ParameterDesignPanel.tsx`, etc.). Not my mess (Rule 3). I will commit ONLY my targeted edits.
- Investigating other Playwright flakes outside `tlc-upload-chain.spec.ts`.
- Refactoring `fast_path_handlers.py` beyond the docstring fix.
- Reverting the handler behavior change (the emit-on-every-key behavior is the intended one per the code comment — only test + docstring catch up).
- Adding new tests beyond fixing the existing one (YAGNI — current test surface is enough).

## Open Questions (none blocking)

None — both fixes are scoped and the root cause for Issue 2 is confirmed E (test out of date to deliberate code change), not a regression.

## Technical Notes

**Issue 1 — Playwright fix sketch:**
```typescript
// Before (flaky):
let recognized: RecognizeCapture | null = null
page.on('response', async (r) => {
  if (r.url().includes('/tlc/recognize') && r.request().method() === 'POST') {
    try { recognized = { status: r.status(), body: await r.text() } }
    catch { recognized = { status: r.status(), body: '' } }
  }
})
// ... interact with UI ...
expect(recognized, '...').not.toBeNull()

// After (deterministic):
const recognizePromise = page.waitForResponse(
  r => r.url().includes('/tlc/recognize') && r.request().method() === 'POST',
  { timeout: 60_000 },
)
// ... interact with UI ...
const response = await recognizePromise
const recognized: RecognizeCapture = { status: response.status(), body: await response.text() }
```

**Issue 2 — Test fix sketch:**
```python
# Before (asserts OLD silent-return behavior):
broadcaster.emit.assert_not_awaited()
assert snap.announced_transitions == ["pending_to_in_progress"]

# After (matches current emit-every-non-None-key behavior):
broadcaster.emit.assert_awaited_once()  # or assert_awaited (twice total counting first call)
assert snap.announced_transitions == ["pending_to_in_progress", "in_progress_to_in_progress"]
# Test name also updated to reflect new semantics
```

**Issue 2 — Docstring reconciliation sketch** (`fast_path_handlers.py:374-377`):
```python
# Remove this stale bullet:
- ``in_progress_to_in_progress`` (placeholder) → silent return; no
  template message for repeated in-progress pushes.
# Replace with a single accurate statement that matches lines 391-405.
```

**Spec/contract files consulted:**
- `BIC-agent-service/.trellis/spec/backend/L2/fast-path-handlers.md` — verify the placeholder behavior is documented here or only in code
- `BIC-agent-portal/.trellis/spec/frontend/quality-guidelines.md` — Playwright conventions if any
- `BIC-agent-portal/tests/tlc-upload-chain.spec.ts` — the only test file touched

**Contract surface — NONE CHANGED.** Both fixes are internal: one test rewrite + one docstring fix + one Playwright idiom swap. No FE↔BE / L1↔L2↔L3↔L4 / service-to-service contract is altered. Rule 10 satisfied.
