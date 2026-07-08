# Align plan-first E2E specs with objective-first flow

## Goal

Every Playwright spec that gates on turn-1 "Workflow Design" predates the objective-first
flow (07-01: stage-gated objective routing `7cecc46` + deterministic backstop `b8b4bbb`) and
fails deterministically: the agent now correctly clarifies for SMILES/purity/yield instead of
proposing a plan. Align them with the modern pattern.

## Known-stale (from task 07-02 runs 1-3, 2026-07-02)

- `tests/cc-re-chained-flow.spec.ts` — pre-objective prompt + turn-1 Workflow Design gate;
  also its 35-min config couples other flows to it.
- Any other spec with the same first-gate shape (sweep `tests/` for the Workflow Design
  heading wait without a preceding objective confirm).
- Also check `tests/tlc-retry-flow.spec.ts` post-R7: its round loop depends on the robot mock
  shipping a plate image on START_TLC (mock patched in working tree 2026-07-02 — see
  mars_interface_mock/tlc_mock_interface.py; that patch is uncommitted).

## Modern pattern (proven in 07-02 run 3)

`POST /sessions` → objective prompt (SMILES + baseline + feed amount + purity/yield targets)
→ poll `experiments[0].stage == 'experiment_objective'` → `POST /objective/confirm` →
auto-proposed plan (07-01 hand-off; no extra message) → fixed TLC-first workflow: drive the
TLC leg (specialist-filtered form gates!) before anything CC. Reference implementation:
`tests/form-edit-sync-on-send.spec.ts` (task 07-02).

## Acceptance Criteria

- [ ] All live-backend specs pass on a bench with the R7-aligned robot mock.
- [ ] No spec waits on a turn-1 Workflow Design heading.
- [ ] Params-form gates are specialist-filtered (the unfiltered confirm_kind count was a
  proven false-positive source).

## Scope correction (2026-07-03, sonnet research-agent pass) — PARTIALLY_VALID, narrowed

Still stale (turn-1 Workflow Design gate, no objective confirm): `cc-re-chained-flow.spec.ts:316`,
`honest-chain-guard.spec.ts:95`, `manual-live-demo.spec.ts:265`, `task-progress-stream.spec.ts:223`.
Unfiltered `__paramsFormCount` false-positive risk: `cc-re-chained-flow` + `honest-chain-guard`.
DROP from scope: (a) robot-mock START_TLC plate-image patch — committed as mars_interface_mock
`61d29c9`, tree clean; (b) 35-min config coupling — `playwright.cc-re-chained.config.ts` already
at 12 min and testMatch-scoped to the one spec (spec-internal `test.setTimeout(35min)` remains,
cosmetic). Reference pattern `form-edit-sync-on-send.spec.ts` is MERGED (portal `1c713d81`);
already-modern specs: `tlc-retry-flow`, `tlc-params-tube-selector`, `tlc-e2e-final-chain`.

## Second verification pass (2026-07-03 19:23, sonnet) — VERDICT: PARTIALLY_VALID, 3 corrections

Verified on portal main `db1fc3b2`, mock `61d29c9` (clean). Corrections to the section above:

1. `honest-chain-guard.spec.ts` has ZERO `__paramsFormCount` usage (line 119 explicitly
   forgoes it; it waits on UI enable state). The unfiltered-count false-positive risk exists
   ONLY in `cc-re-chained-flow.spec.ts:256` (`confirm_kind === 'params'` with no
   specialist_kind filter — counts TLC params as CC).
2. Spec-internal `test.setTimeout(35min)` (`cc-re-chained-flow.spec.ts:213`) is NOT cosmetic —
   in Playwright it OVERRIDES the 12-min config cap for that test. Remove/lower it during the
   rewrite.
3. MISSED SPEC: `tlc-upload-chain.spec.ts:169,311` gates on Workflow Design without objective
   confirm. Skip-guarded (`test.skip(!planProposed)`) so it degrades to a skip instead of a
   hard fail — architecturally stale, its T2/T3 legs will now skip forever. Add to scope.

Definitive migration list: `cc-re-chained-flow.spec.ts:316` (+ unfiltered count at :256 +
setTimeout at :213), `honest-chain-guard.spec.ts:95`, `manual-live-demo.spec.ts:265`,
`task-progress-stream.spec.ts:223` (hard-fail); `tlc-upload-chain.spec.ts:169,311`
(silent-skip). All other claims above re-confirmed.

## DECISION NEEDED (Drake) — tlc-upload-chain T2/T3 intent unreachable (found 2026-07-04)

`ccConsumesRobotTlc` (`ParameterDesignPanel.tsx:137-142`) is true whenever a robot TLC job
precedes CC — always the case in the fixed workflow with "robot for ALL steps" — and
`allowTlcUpload = !ccConsumesRobotTlc` (`:734`) unmounts `TlcUploadControl` (`:742`). So the
FE upload → presign → recognize chain T2/T3 exist to guard CANNOT be driven in the migrated
flow. T1 (API-only) stays green and covers presign creds + prefix + S3 round-trip. Options:
(a) manual-TLC objective variant ("chemist ran TLC manually, robot does CC/FP/RE") — would
    re-enable TlcUploadControl in CC context, but needs a `driveObjectiveFirstSession`
    extension AND bench validation that a no-TLC-job plan reaches a confirmable CC form
    (07-02 run-5: manual steps get no job row — cursor behavior unverified);
(b) delete T2/T3, keep T1 (+ move tlc-client contract checks to a component/unit test);
(c) leave T2/T3 skip-guarded as-is (status quo: they skip forever — dishonest green).

RESOLVED 2026-07-05 (Drake): option (a) — "CC without TLC preceding is still valid." T2/T3
migrated with the manual-TLC objective variant (`workflowClause` override added to
`driveObjectiveFirstSession`; skip-forever guards deleted; waitForResponse/waitForRequest
moved to just before the upload so the 120s clock doesn't expire during bring-up). Bench run
must validate that a manual-TLC plan reaches a confirmable CC form (07-02 run-5: manual
steps get no job row — cursor behavior still bench-unverified).
