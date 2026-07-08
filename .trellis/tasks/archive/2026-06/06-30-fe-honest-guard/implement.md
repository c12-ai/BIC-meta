# Implement — FE honest browser-path guard (Child B)

Test code only. Read `design.md` first. The existing three specs stay byte-unchanged.

## Ordered checklist

1. **Study the chain's real UI selectors** (read-only) from `cc-re-chained-flow.spec.ts`
   and `tlc-e2e-final-chain.spec.ts`: the params-form testids, Confirm button names,
   `result-stage-cc` / `result-stage-re`, "Experiment Review" heading, "Confirmed
   result review." text, "Accept result" button. Reuse the SELECTORS; do NOT reuse
   their recovery/fallback logic.

2. **Create `tests/honest-chain-guard.spec.ts`** driving TLC→CC→RE with DOM-only waits:
   - `resetLabState` (allowed setup), open chat, send chemist prompt.
   - Per leg: `await expect(paramsForm).toBeVisible({ timeout: LEG_CAP })` → chemist-edit
     required fields → click Confirm → `await expect(resultCard).toBeVisible({ timeout:
     ROBOT_CAP })` → click "Accept result" → `await expect(confirmedBubble).toBeVisible()`.
   - Final: both `result-stage-cc` + `result-stage-re` visible; exactly 2 "Confirmed
     result review." bubbles; no error surface.

3. **Self-audit for escape hatches** (the spec's integrity = parent AC3):
   ```bash
   cd BIC-agent-portal
   grep -nE "/api/sessions|/snapshot|window\.__|page\.reload\(|waitForParamsForm|waitForReviewHeading|fetchEvents|pg\(" tests/honest-chain-guard.spec.ts
   # MUST return nothing.
   ```

4. **Observe RED today** (bug-visible proof, before Child A): run the spec against the
   current no-heartbeat backend; on a real freeze it must time out red. Capture the
   failing locator + that the existing three specs still pass on the same bench.

5. **(After Child A lands) Observe GREEN** with heartbeat on (AC1), then the red/green
   demo for AC2: toggle heartbeat off → this spec red, others green.

## Validation commands

```bash
cd BIC-agent-portal
pnpm check                                   # biome lint+format+imports
pnpm exec playwright test tests/honest-chain-guard.spec.ts --workers=1 --reporter=line
git diff --stat                              # only the new file (+ maybe a DOM-only helper)
git diff tests/cc-re-chained-flow.spec.ts tests/tlc-retry-flow.spec.ts tests/tlc-e2e-final-chain.spec.ts
# ^ MUST be empty — existing specs unchanged (parent AC5 FE side).
```

## Review gates

- After step 3: the grep returns nothing (no backend/fallback/reload/nudge).
- After step 4: spec is observed RED on a real freeze (proves it bites).
- After step 5 (post-A): spec GREEN healthy, RED when heartbeat off → parent AC4.
- `git diff` on the three existing specs is empty (parent AC5).

## Rollback

Delete the new spec file. Zero product impact, zero impact on existing specs.

## Dependency note

Authoring is independent of Child A. The GREEN-healthy run (AC1) and the red/green
demo (AC4) need Child A's heartbeat + its toggle. Sequence: author + RED-today now;
finish GREEN/red-green demo after Child A.
