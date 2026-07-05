# Research: Playwright spec migration — objective-first opening

- **Query**: Migration recipe for 5 stale plan-first specs to objective-first flow
- **Scope**: internal
- **Date**: 2026-07-03

---

## 1. Reference Skeleton (form-edit-sync-on-send.spec.ts)

### Session creation
```ts
// form-edit-sync-on-send.spec.ts:218-222
const created = await page.request.post('/api/sessions', { data: {} })
expect(created.ok(), 'POST /sessions must succeed').toBeTruthy()
const sessionId = (await created.json()).session_id as string
expect(sessionId).toBeTruthy()
```

### Objective prompt shape (exact text)
```ts
// form-edit-sync-on-send.spec.ts:260-272
const msg = await page.request.post(`/api/sessions/${sessionId}/messages`, {
  data: {
    text:
      'Run a column chromatography purification. The robot should perform ' +
      'ALL workflow steps (TLC, column chromatography, fraction pool, and ' +
      'rotary evaporation). Reaction SMILES: ' +
      `${REACTION_SMILES} . Use bromobenzene as the baseline material. Target ` +
      '95% purity, 80% yield, baseline feed amount 200 mg. For the CC step: ' +
      'purify a 1.5g sample with PE:EA 20:1 as the mobile phase, target ' +
      'product Rf around 0.3; the sample cartridge is at bic_09B_l4_001. ' +
      'Please open the objective confirmation form.',
  },
})
```
Required fields in message: SMILES, baseline material, purity target, yield target, feed amount.
"robot for ALL steps" is REQUIRED — without it, plan_dynamic_prompt.py flips unnamed steps to
type='manual' and manual steps get no job row (07-02 run-5 finding, line 259).
The CC details (sample size, mobile phase, cartridge) are included in the SAME message so
collecting_params has every presence-gate field in context from the start.

### Poll for experiment_objective stage
```ts
// form-edit-sync-on-send.spec.ts:277-285
await expect
  .poll(async () => (await fetchSnapshot()).experiments?.[0]?.stage, {
    message: 'agent did not create the experiment at experiment_objective — ...',
    timeout: OBJECTIVE_STAGE_TIMEOUT_MS,   // 90_000
    intervals: [1_000, 2_000, 3_000],
  })
  .toBe('experiment_objective')
```
`fetchSnapshot` calls `GET /api/sessions/${sessionId}/snapshot` (line 229-232).

### POST /objective/confirm (exact URL, body, headers)
```ts
// form-edit-sync-on-send.spec.ts:289-302
const objectiveConfirm = await page.request.post(
  `/api/sessions/${sessionId}/objective/confirm`,
  {
    data: {
      name: 'Biphenyl Suzuki CC purification',
      reaction_smiles: REACTION_SMILES,
      feed_amount_mg: 200,
      target_purity_pct: 95,
      target_yield_pct: 80,
    },
  },
)
expect(objectiveConfirm.ok(), 'objective confirm must succeed').toBeTruthy()
expect((await objectiveConfirm.json()).stage).toBe('workflow_design')
```
All /api/* calls ride the Vite proxy which injects X-User-Id automatically. No explicit headers needed.
The response body carries `.stage == 'workflow_design'` on success.

### Post-confirm wait for plan / Workflow Design heading
```ts
// form-edit-sync-on-send.spec.ts:309-327
await page.goto(`/chat/${sessionId}`)
await page.waitForLoadState('domcontentloaded')
const composer = page.getByPlaceholder(/Ask the agent|Ask for status|design a workflow/)
await expect(composer).toBeVisible({ timeout: 15_000 })

const planHeading = page.getByRole('heading', { name: /^Workflow Design$/i })
try {
  await expect(planHeading).toBeVisible({ timeout: PLAN_PROPOSE_TIMEOUT_MS })  // 90_000
} catch {
  // duo-panel nudge: one chemist-realistic message
  await composer.fill('Please design and propose the workflow for this experiment.')
  await composer.press('Enter')
  await expect(planHeading, '...').toBeVisible({ timeout: PLAN_PROPOSE_TIMEOUT_MS })
}
```
The 07-01 hand-off auto-runs PlanAgent in the confirm follow-up turn — no extra message needed.
A one-shot nudge handles the LLM-abandon case (duo-panel).

### Specialist-filtered params-form instrumentation
```ts
// form-edit-sync-on-send.spec.ts:134-144 (Window declaration)
declare global {
  interface Window {
    __paramsFormEvents: { receivedAt: number; specialistKind: string }[]
  }
}

// form-edit-sync-on-send.spec.ts:179-205 (addInitScript)
window.__paramsFormEvents = []
// ... wraps EventSource.prototype.addEventListener ...
// On form_requested with confirm_kind === 'params':
window.__paramsFormEvents.push({
  receivedAt: Date.now(),
  specialistKind: data.original_action?.specialist_kind ?? '',
})
```
Wire field: `data.original_action?.specialist_kind` — values: 'tlc' | 'cc' | 're'.

```ts
// form-edit-sync-on-send.spec.ts:244-249 (filter functions)
const backendParamsFormCount = async (specialist: string): Promise<number> =>
  (await fetchEvents()).filter(
    (e) =>
      e.kind === 'form_requested' &&
      e.payload.confirm_kind === 'params' &&
      e.payload.original_action?.specialist_kind === specialist,
  ).length
const inPageParamsFormCount = (specialist: string): Promise<number> =>
  page.evaluate(
    (kind) => window.__paramsFormEvents.filter((e) => e.specialistKind === kind).length,
    specialist,
  )
```
Replaces the unfiltered `window.__paramsFormCount += 1` pattern in cc-re-chained and task-progress-stream.

### Helper functions used
All from `tests/helpers.ts`:
- `resetLabState(label?)` — bench reset, waits for robot idle
- `confirmParamsThroughMaterialDialog(page, { beforeValidate? })` — clicks params-confirm → dialog → validate → confirm-dispatch
- `waitForParamsForm({ composer, minCount, label, fullTimeoutMs, count })` — counts params forms with one-shot nudge

---

## 2. Per-Spec Migration Recipe

### cc-re-chained-flow.spec.ts

**Current stale lines:**
- Line 213: `test.setTimeout(35 * 60_000)` — OVERRIDES the 12-min config cap (not cosmetic)
- Lines 282-329: direct chat prompt → plan heading gate (turn-1 Workflow Design wait with no objective confirm)
- Line 256: `window.__paramsFormCount += 1` — unfiltered, counts TLC params as CC

**Intent to preserve:**
1. CC → RE chained plan: two task_created(cc), task_created(re) in fixed order
2. Bug-1 regression: non-live CC subtab renders real params, not sample fixture
3. Bug-2 regression: form locks on dispatch
4. Per-trial workspace (trialsById): CC params survive the RE task_created reset
5. Append-model: both result-stage-cc and result-stage-re cards coexist after both legs
6. No turn_failed after the chain
7. Typed evidence rendered (assertTypedEvidenceRendered)

**Migration plan:**
a. REPLACE lines 213-329 (setTimeout + localStorage clear + composer.fill + plan heading wait + Confirm Plan click) with the full objective-first opening (POST /sessions → objective message → poll stage → POST /objective/confirm → page.goto(`/chat/${sessionId}`) → plan heading wait → Confirm Plan click).

b. The old prompt `'For RXN-001 purification: run column chromatography...'` (line 306-309) MUST be replaced with the reference spec's objective message shape: SMILES + baseline + purity/yield targets + feed amount + "robot for ALL steps" + CC details (sample, mobile phase, Rf, cartridge). This is the only way to make the fixed TLC-first workflow activate with a CC step that still has its lab_logistics populated.

c. CRITICAL TLC-first trap: the fixed workflow is TLC(robot) → CC → FP → RE. CC is Locked until the TLC leg's result is ACCEPTED. The current cc-re-chained spec has a "upload TLC plate" step at lines 385-397 (a manual plate upload path used by the OLD CC-first flow). After migration, the TLC leg is a REAL robot round loop, not a plate upload. Replace the upload block with the full TLC leg from form-edit-sync-on-send.spec.ts (§3. Confirm the plan → §4. TLC leg: params → tubes → confirm → §5. TLC robot loop → Accept). Only after TLC Accept does CC unlock. The CC leg then needs NO manual plate upload (cc-carryforward: accepted TLC result flows into CC from_user).

d. REPLACE `window.__paramsFormCount` with `window.__paramsFormEvents` + specialist-filtered counters. Change `waitForParamsFormWithReload(1, 'CC')` to use `specialist='cc'`, and `waitForParamsFormWithReload(2, 'RE')` to use `specialist='re'` (but count must now start at 0 per specialist, not a running total — i.e., `inPageParamsFormCount('cc') >= 1` and `inPageParamsFormCount('re') >= 1`).

e. LOWER test.setTimeout from 35min. The reference spec (full TLC + CC legs) uses 30min. A TLC + CC + RE chain needs more: ~35-40min is appropriate. Remove the old 35*60_000 line from the test body; the outer config cap is 12min (config file) so you MUST keep an in-test setTimeout for the longer chain. Recommend `test.setTimeout(40 * 60_000)` to cover TLC(8min) + CC + RE.

f. The `backendParamsFormCount` function (line 350-353) is also unfiltered. Replace with specialist-filtered version.

**Lines NOT to touch:**
- `waitForReviewHeading`, `assertTypedEvidenceRendered` helpers (still valid)
- Bug-1 regression block (lines 571-625): valid, operates on RE leg state
- Bug-2 regression (Task 06-16 lock-on-dispatch): valid, check if it applies in the new flow
- RE leg steps (§9-15): unchanged
- Final assertions (lines 792-850): unchanged

---

### honest-chain-guard.spec.ts

**Current stale line:**
- Line 95: `await expect(page.getByRole('heading', { name: /^Workflow Design$/i })).toBeVisible(...)` — direct chat prompt → Workflow Design wait, no objective confirm

**Intent to preserve:**
This spec is the photographic NEGATIVE of cc-re-chained. Pass condition = user-observable DOM only. FORBIDDEN: /api/sessions reads, /snapshot, window.__, page.reload(), waitForParamsForm nudge (line 25-26 comment). The spec intentionally goes RED when SSE stalls.

**Migration plan:**
a. Replace the opening (lines 82-96) — the composer.fill + Enter + plan heading wait — with the objective-first API sequence. HOWEVER: this spec forbids window.__, /api/sessions reads, /snapshot, page.reload(). This creates a tension with the objective-first opening which uses `page.request.post('/api/sessions', ...)` and `page.request.get('/snapshot')`.

b. Resolution: the API calls in the objective opening are SETUP (bench precondition, like resetLabState), not recovery/fallback. The PRD's "no /api/sessions read" rule refers to MID-FLOW fallback reads that mask SSE stalls. The objective confirm is deterministic infrastructure, not a recovery crutch. Use the same `page.request.post` calls for session create and objective confirm (as the reference spec does at lines 218-302). The honest-guard constraint applies AFTER the session is in workflow_design and the page is navigated.

c. After the objective confirm and page.goto, the plan heading wait (PLAN_PROPOSE_TIMEOUT_MS, with the duo-panel nudge) is fine — it is an SSE-observable DOM wait.

d. The old CC-only prompt (line 85-89) must be replaced with the full objective message (SMILES + all required fields + "robot for ALL steps"). The TLC-first workflow will activate and the spec must drive the TLC leg (params form + tube declare + accept) before CC. This is a significant new section.

e. The TLC leg steps match the reference spec exactly (waitForSpecialistParamsForm → cc-params-form visible → tlcRxn/tlcTarget/tlcEluent fills → confirmParamsThroughMaterialDialog with tube cells A1/A2 → Accept result button). All waits are on DOM elements → compatible with the honest-guard constraint.

f. NO window.__ capture, NO /events fallback, NO page.reload() anywhere in the TLC leg.

g. The CC/RE legs after TLC are already pure DOM waits in the current spec (lines 114-209) — keep them as-is.

h. NO change needed for `__paramsFormCount` (the spec already has ZERO usage — line 119 comment: "No window.__paramsFormCount, no /events fallback, no nudge").

**Test.setTimeout:** Needs increase from 35min to cover TLC robot loop (~8min) + CC (~7min) + RE (~14min) = ~30-35min. Keep `test.setTimeout(35 * 60_000)` at line 68 or increase to 40min.

---

### manual-live-demo.spec.ts

**Current stale lines:**
- Line 265-276: prompt → Workflow Design wait (turn-1 plan gate, no objective confirm)
- Line 179-207: `window.__paramsFormCount` init (unfiltered)
- Step 6 (line 296-315): polls `window.__paramsFormCount >= 1` with no specialist filter

**Intent to preserve:**
1. Full CC demo flow: plan → refine ("update sample amount to 1g") → chemist override (1.5) → params confirm with body assertion → rts-phase "Go ahead and submit" → dispatch → MQ progress → result review
2. D2 regression: no JSON leak in plan bubble
3. G3 regression: PMC/SMC toggle
4. TLC plate upload via fileChooser (click button path, not setInputFiles on hidden input)
5. Params confirm POST body assertion (confirm_kind, from_user.sample_quantity.quantity=1.5, recommended present)
6. rts-phase two-step gate (confirm → separate go-ahead message)

**Migration plan:**
a. Replace lines 251-276 (composer.fill CC prompt + plan heading wait) with the objective-first opening.

b. The old CC prompt is only one-step (CC only, no TLC). After migration with "robot for ALL steps", the fixed workflow will include TLC first. The spec MUST then drive the TLC leg before reaching CC params. This changes the flow substantially.

c. The TLC plate upload (steps 5-6, lines 342-373) will now happen as part of the TLC leg (NOT as a pre-CC upload). The "TLC leg" in the reference spec replaces the plate-upload path: real robot round loop instead. Remove the fileChooser TLC upload block and replace with the TLC specialist leg (params + tubes + confirm + accept).

d. G3 regression (PMC/SMC toggle, lines 334-339): This toggle is inside TlcUploadControl. In the new flow, TLC is a robot leg (not upload-based). Verify whether the toggle still exists in the TLC params form context. If TlcUploadControl is only shown for CC pre-upload in the old flow, this G3 test may no longer be reachable. FLAG: may need to remove the G3 toggle check or relocate it to the TLC form (if the toggle exists there too).

e. The rts-phase "Go ahead and submit" gate (lines 491-523) is CC-specific and predates deterministic dispatch (task 06-09). In the current modern flow, the params-confirm IS the dispatch (no separate go-ahead). Replace step 10b (composer.fill + "please submit" message) with the deterministic dispatch pattern from cc-re-chained.

f. `window.__paramsFormCount` → replace init (line 180) and polls (lines 306-314, 404-412) with specialist-filtered `__paramsFormEvents` pattern. But given the TLC leg now runs first, filter for 'cc' when waiting for the CC form.

g. The free-text refinement step ("update sample amount to 1g", step 7) and the chemist manual override (step 8, 1.5g) are CC-leg internal — they work the same after the TLC leg completes. Keep them.

h. The confirm POST body assertion (lines 447-475) is valid — keep as-is.

i. test.setTimeout: currently 20min. Needs increase to 40min+ to cover TLC robot loop.

**This spec is the most complex migration** because it predates deterministic dispatch and has the rts-phase two-step gate. The rts-phase gate either (a) needs to be removed entirely if the modern flow doesn't have it, or (b) kept if the CC specialist still uses it. Check: does `form_edit_sync_on_send` have a rts-phase gate? It does NOT — the params confirm dispatches directly. The rts-phase gate is obsolete and should be REMOVED.

---

### task-progress-stream.spec.ts

**Current stale line:**
- Line 223: `await expect(page.getByRole('heading', { name: /^Workflow Design$/i })).toBeVisible(...)` — turn-1 Workflow Design wait, no objective confirm

**Intent to preserve:**
1. Verify `task_progress` SSE events arrive per-step (not just terminal)
2. Fast-path dedupe regression: ≥2 distinct task_progress events
3. Terminal task_progress emitted by `_handle_terminal`
4. No pending steps in terminal snapshot
5. Bug-2 regression: form locked on dispatch (lines 328-360)

**Migration plan:**
a. Replace lines 199-237 (composer.fill CC-only prompt + plan heading wait + Confirm Plan click) with the objective-first opening.

b. The spec currently drives a CC-only flow (single step). After migration with "robot for ALL steps", the fixed workflow includes TLC first. The task_progress assertions are scoped to a single trial (CC). With TLC first, there will be TLC task_progress events too. The spec must either:
   - Drive the full TLC leg first and then monitor CC progress (filtering by trial_id), OR
   - Be rewritten to assert on the TLC trial's progress events (simplest fix since TLC also generates task_progress)

c. The `fetchEvents` function is already present (line 239-245). The `reTrialId` tracking pattern in cc-re-chained (lines 724-726) shows how to isolate a specific trial.

d. The TLC plate upload block (lines 251-270) is replaced by the real TLC robot leg (params → tubes → accept). After accept, CC begins. The task_progress assertions then target the CC trial (filter by trial_id from the task_created event sequence — first task_created = TLC, second = CC for the CC-focused assertions).

e. `window.__paramsFormCount` (line 141, 171) → replace with specialist-filtered `__paramsFormEvents`. The CC gate becomes `inPageParamsFormCount('cc') >= 1`.

f. Bug-2 regression (lock on dispatch, lines 328-360): still valid for CC — keep unchanged.

g. test.setTimeout: currently 10min. Needs increase to cover TLC leg (~8min) + CC params (~4min) + CC run (~1min) = ~15min. Recommend `test.setTimeout(20 * 60_000)`.

---

### tlc-upload-chain.spec.ts

**Current stale lines:**
- Line 169 (T2, inside test): `const planProposed = await page.getByRole('heading', ...).waitFor(...)` + `test.skip(!planProposed, ...)` — skip-guards T2/T3 on plan not arriving; plan never arrives without objective confirm → T2/T3 will always skip
- Line 311 (T3): same pattern — `test.skip(!planProposed, ...)`

**Intent to preserve:**
- T1 (lines 74-133): pure API test, NO UI, NO plan — presign creds + S3 round-trip. ZERO CHANGE needed.
- T2 (lines 135-263): full chain to /tlc/recognize — drive UI to mint task_id then hit recognize. Intent: verify ChemEngine recognize returns real spots.
- T3 (lines 265-388): FE-only guard — presign body shape (session-prefixed key), recognize carries tlc_file_key not tlc_image_url, TlcThumbnail presigns GET.

**Migration plan:**
a. T1: no change.

b. T2: Replace lines 159-172 (page.goto + composer.fill + planProposed waitFor + test.skip) with the objective-first opening. The plan will arrive via the objective confirm path, so `planProposed` will always be true and `test.skip(!planProposed)` is removed. The task_created enabling the upload button still happens — the upload at line 196 + status wait at line 199 are unchanged.

c. T2: After migrate, the session is already created (POST /sessions) and objective confirmed (POST /objective/confirm). Navigate to /chat/${sessionId} instead of '/'. The plan heading wait comes from the objective confirm hand-off. After plan arrives + Confirm Plan click, the TLC params form mounts. But T2 only needs a `taskId` for the recognize call — the task_id is available from the first task_created event (which fires on plan_confirmed). The upload can happen right after task_created (as in the current spec, gated on tlc-upload-button enabled).

d. T2 critical question: the current T2 uploads via CC's TlcUploadControl. In the fixed workflow, the TLC leg is a robot leg (not upload-based). Is TlcUploadControl shown during the TLC robot leg or only for CC? CHECK: In the reference spec (form-edit-sync-on-send), after Confirm Plan the TLC robot leg starts — there is NO TLC plate upload in the reference spec. The TlcUploadControl appears to be a CC pre-step widget. If TlcUploadControl is still shown when the CC specialist is active (after TLC completes), T2 can still drive the upload during the CC leg. But if the CC leg is locked until TLC Accept, T2 needs to drive the full TLC leg first before it can upload for CC. This is the same problem as cc-re-chained: the full TLC robot loop must complete before CC unlocks. T2's intent (recognize chain test) may be achievable more simply by using the API-only path (POST /tlc/recognize directly after creating a session with the objective done) — but that bypasses the FE chain T2 intends to test.

e. T2 recommendation: Drive the TLC robot leg first (same as reference spec: TLC params → tube cells → confirmParamsThroughMaterialDialog → Accept result). Then the CC leg unlocks, TlcUploadControl mounts (or is it already present?). Upload the plate in CC context. This preserves T2's intent of testing the FE → presign → S3 → recognize chain. The test.setTimeout increases from 420s (7min) to ~20min.

f. T3: Same as T2 — replace the opening with objective-first, remove test.skip(!planProposed), drive TLC leg first, then upload in CC context. test.setTimeout increases similarly.

g. test.skip removal: T2:169 `test.skip(!planProposed, ...)` and T3:315 `test.skip(!planProposed, ...)` are DELETED. These were only needed because the plan never arrived; with objective confirm, it always arrives.

---

## 3. Shared Helper Convention

**Current state:** The objective-first opening sequence (POST /sessions → message → poll stage → POST /confirm → page.goto → plan heading wait) appears ONLY in `form-edit-sync-on-send.spec.ts` (the reference spec). No shared helper exists yet.

**Modern specs that share today:**
- `tlc-retry-flow.spec.ts` and `form-edit-sync-on-send.spec.ts` share `resetLabState`, `confirmParamsThroughMaterialDialog` from `tests/helpers.ts`
- `tlc-e2e-final-chain.spec.ts`, `tlc-params-tube-selector.spec.ts` share the same helpers
- The objective API sequence is NOT yet in helpers.ts

**Convention check:** helpers.ts exports three functions. The objective-first sequence would be the fourth. Given that ALL 5 stale specs need it (plus future specs), and the modern specs already use it, extracting to helpers.ts is the right call.

**Recommendation:** ADD a `driveObjectiveFirstSession` helper to `tests/helpers.ts`:
```ts
// Proposed helper signature
export async function driveObjectiveFirstSession(page: Page, opts: {
  reactionSmiles: string
  baselineMaterial: string
  feedAmountMg: number
  targetPurityPct: number
  targetYieldPct: number
  objectiveName: string
  extraPromptDetails?: string   // cc details, etc.
}): Promise<{ sessionId: string; composer: Locator }>
```
Returns `sessionId` (for later API calls) and `composer` (for nudges).

The specialist-filtered `__paramsFormEvents` instrumentation is test-internal (it requires `addInitScript` before page load). It should NOT go in helpers.ts — each spec injects it in its own `addInitScript` block. The `backendParamsFormCount(specialist)` and `inPageParamsFormCount(specialist)` functions can be locally defined per spec (they close over `sessionId`/`page` anyway).

The `waitForSpecialistParamsForm` wrapper (form-edit-sync-on-send.spec.ts:339-359) wraps `waitForParamsForm` with the specialist filter — keep per-spec (it closes over local `composer`, `inPageParamsFormCount`, `backendParamsFormCount`).

**Convention match:** helpers.ts already has `waitForParamsForm` as a complex function with injected `count`. The `driveObjectiveFirstSession` helper follows the same pattern (injectable, testable, returns state the caller needs). This is consistent with existing convention.

---

## 4. Runnability

### Playwright config routing per spec

| Spec | Config file | testIgnore in default? |
|------|-------------|----------------------|
| `cc-re-chained-flow.spec.ts` | `playwright.cc-re-chained.config.ts` (testMatch scoped) | NOT in testIgnore; excluded because requires focused config |
| `honest-chain-guard.spec.ts` | `playwright.config.ts` (default) | NOT excluded |
| `manual-live-demo.spec.ts` | `playwright.live.config.ts` | EXCLUDED via testIgnore at `playwright.config.ts:17` |
| `task-progress-stream.spec.ts` | `playwright.config.ts` (default) | NOT excluded (despite header comment saying to use live config — header is stale) |
| `tlc-upload-chain.spec.ts` | `playwright.config.ts` (default) | NOT excluded |

Caveat: `task-progress-stream.spec.ts` header (line 30-34) says to run with `playwright.live.config.ts` but the spec does NOT use testMatch. It runs under the default config `playwright.config.ts`. The header comment is stale.

### Run commands

```bash
# cc-re-chained (focused config required)
VITE_HIDE_DEVTOOLS=1 pnpm exec playwright test \
  --config=playwright.cc-re-chained.config.ts \
  --project chromium --reporter list --workers 1

# honest-chain-guard (default config, workers=1 for LLM)
VITE_HIDE_DEVTOOLS=1 pnpm exec playwright test \
  tests/honest-chain-guard.spec.ts \
  --project chromium --reporter list --workers 1

# manual-live-demo (live config)
VITE_HIDE_DEVTOOLS=1 pnpm exec playwright test \
  --config=playwright.live.config.ts \
  --project chromium --reporter list --workers 1

# task-progress-stream (default config)
VITE_HIDE_DEVTOOLS=1 pnpm exec playwright test \
  tests/task-progress-stream.spec.ts \
  --project chromium --reporter list --workers 1

# tlc-upload-chain (default config)
VITE_HIDE_DEVTOOLS=1 pnpm exec playwright test \
  tests/tlc-upload-chain.spec.ts \
  --project chromium --reporter list --workers 1

# All 5 together (except manual-live-demo which needs its own config)
VITE_HIDE_DEVTOOLS=1 pnpm exec playwright test \
  tests/cc-re-chained-flow.spec.ts  \  # use focused config for this one
  tests/honest-chain-guard.spec.ts \
  tests/task-progress-stream.spec.ts \
  tests/tlc-upload-chain.spec.ts \
  --project chromium --reporter list --workers 1
```

### Proxy caveat
From CLAUDE.md: `curl` needs `--noproxy '*'` (127.0.0.1:7890 proxy masks localhost). In Playwright specs, `page.request.*` targets the Vite dev server which proxies to :8800. No explicit `--noproxy` needed for Playwright (it doesn't use the system HTTP proxy for `page.request` calls against localhost). The `resetLabState` helper already uses `--noproxy '*'` in its curl commands (helpers.ts:39).

### workers=1 convention
From portal CLAUDE.md comment and spec headers: LLM-driven specs must use `--workers=1`. The cc-re-chained config (playwright.cc-re-chained.config.ts:22) already sets `workers: 1`. The live config (playwright.live.config.ts:19) also sets `workers: 1`. The default config does NOT set workers (defaults to auto). When running LLM specs under the default config, always pass `--workers=1` explicitly.

`VITE_HIDE_DEVTOOLS=1` is required for headless runs — the floating devtools buttons intercept clicks on workspace form CTAs (form-edit-sync comment lines 48-50 and portal CLAUDE.md).

---

## 5. Summary: Per-Spec Migration Table

| Spec | Stale lines | Key changes | Blocking trap |
|------|-------------|-------------|---------------|
| `cc-re-chained-flow.spec.ts` | :213 (setTimeout), :256 (__paramsFormCount), :282-329 (plan-first opening + prompt) | Full objective opening; replace CC-only prompt with SMILES+targets; add TLC robot leg before CC; specialist-filter paramsFormEvents; lower/keep setTimeout (40min); remove TLC plate-upload block | TLC is now a real robot leg (NOT upload). CC is locked until TLC Accept. Must drive full TLC leg (params+tubes+robot loop+accept) before CC. |
| `honest-chain-guard.spec.ts` | :95 (plan heading without confirm) | Objective-first opening (API setup, not recovery); replace CC-only prompt with full objective message; add TLC robot leg (DOM-only waits, no page.reload/API fallback); no __paramsFormCount used | Must add TLC leg using DOM-only waits (spec forbids /api/sessions reads and page.reload inside the flow). Objective API calls (setup) are allowed. |
| `manual-live-demo.spec.ts` | :265 (plan heading), :179-207 (__paramsFormCount init), :296-315 (unfiltered poll), :491-523 (rts-phase go-ahead) | Objective opening; replace CC prompt; add TLC robot leg; remove rts-phase go-ahead gate (deterministic dispatch now); specialist-filter paramsFormEvents; remove TLC fileChooser upload; increase setTimeout (40min+) | G3 toggle (PMC/SMC) may not be reachable if TlcUploadControl is CC-only. rts-phase two-step gate is OBSOLETE — remove. |
| `task-progress-stream.spec.ts` | :223 (plan heading), :141,171 (__paramsFormCount) | Objective opening; add TLC robot leg; after TLC accept, CC task_created is the second task_created; filter task_progress by CC trial_id; specialist-filter paramsFormEvents; increase setTimeout (20min) | task_progress assertions must be scoped to the CC trial (second task_created, not first which is TLC). |
| `tlc-upload-chain.spec.ts` | :169 (T2 test.skip on plan), :311 (T3 test.skip) | T1: no change; T2/T3: objective opening + navigate to /chat/${sessionId}; remove test.skip(!planProposed); drive TLC robot leg first; upload in CC context; increase setTimeout (20min+) | TlcUploadControl is a CC widget. Must drive full TLC robot loop before CC unlocks. Then upload during CC collecting_params phase. |

### Helper recommendation
Extract `driveObjectiveFirstSession()` to `tests/helpers.ts` — 4th export after resetLabState/confirmParamsThroughMaterialDialog/waitForParamsForm. Keep specialist-filtered `__paramsFormEvents` instrumentation per-spec (addInitScript + local filter functions).
