# Type FE↔BE contracts for TLC / Analyze / FP / result-review

## ⚑ Umbrella role — PILOT child (reconciliation 2026-06-15)

This task is the **typed-evidence PILOT child** of a larger umbrella that also covers the FE-side
task `BIC-agent-portal/.trellis/tasks/06-15-plan-driven-specialist-tabs-and-results-drop-sample-stages`
(plan-driven tabs + 5 stubbed executors + 3 new param forms). See
[`research/reconciliation-analysis.md`](research/reconciliation-analysis.md) for the full
source-verified analysis. Adopted: **Option (c)** — one umbrella, phased children.

- **This child's job**: establish the typed result-payload PATTERN on cc/re (typed `CcEvidence`/
  `ReEvidence`, camelCase casing, the `result_review` `OriginalAction` arms, the `_analyze_result`
  injection). Scope is UNCHANGED — cc/re only, no creep.
- **The other children REUSE this pattern**: when tlc/analyze/fp stub executors land (FE-side
  task), their canned `task_result_analyzed` payloads MUST be typed `*Evidence` models — NOT
  free-form dicts (Rule 11). This corrects the FE contract-delta's §2/§3 (which left the canned
  `analysis` as a raw dict).
- **⚠ COLLISION NOTE (Rule 5)**: both this child AND the FE task's BE-child edit
  `app/runtime/graphs/specialists/tools.py:501-555` (`_analyze_result`). They must NOT edit it
  blind/in parallel. This pilot lands FIRST and owns the typed-evidence shape; the executor-fanout
  child builds on top. The FE delta also missed a 4th executor-literal site
  (`specialist_dispatcher.py:131`) — flagged for that child, not this one.

## Goal

The FE renders five specialist stages (TLC, CC, Analyze, Fraction-Pool, RE) across two
surfaces — param-design forms and result-review evidence cards. Today only **CC** and **RE**
have real typed BE contracts. The other three param forms (TLC/Analyze/FP) and **all five**
result-review evidence bodies are populated from hardcoded FE fixtures. This task captures the
full BE contract work required to replace that fixture data with real, typed, wire-delivered
contracts — and to stand up the distribution bridge so FE types stop drifting from BE by hand.

## What I already know (validated 13/13 against source — see Research References)

- BE `form_payloads.py` defines only `CCParamsForm` (L117) + `REParamsForm` (L188).
- TLC is smuggled into `CCFromUserFields` as loose context: `tlc_file_key`, `rf_values`,
  `product_rf` (L87/91/95) — NOT its own form.
- `bic_shared_types.mcp_protocol.tlc` already ships `TLCSpot`/`TLCPlateResult`/`TLCResult`
  **plus** a far larger recognition+mixcase protocol (caveat 1 — more reuse available than the
  3 result types).
- **No** `analyze` executor / MCP protocol / shared type (greenfield) — BUT a working
  `analyze_*_result` tool already exists inside cc/re specialists and emits
  `TaskResultAnalyzedEvent` (caveat 2 — build on it, don't duplicate).
- **No** fraction-pool shape anywhere in BE or shared-types (fully greenfield).
- `OriginalAction` union + `TYPED_ORIGINAL_ACTIONS` register only `cc_params`, `re_params`,
  `plan`.
- `TaskResultAnalyzedEvent.analysis: dict[str, Any] = {}` — free-form blob written to
  `trials.analysis` (JSONB). This is the single wire feeding all 5 result cards.
- form_payloads.py docstring (L28-31) + runtime_emitted.py `TODO(result_review)` (L505-507)
  both explicitly defer the typed result-review payload to "a follow-on ticket" — tracked in
  `events.md`.
- CC↔TLC coupling is **load-bearing**: `build_cc_param_request` fabricates a standalone
  `TLCResult(product_rf, plates=[])` (L231) — any TLC-form extraction must preserve this shim
  or CC recommend breaks (caveat 3).
- shared-types is Python/hatchling-only — no `package.json`, no TS/JSON-schema artifact. FE has
  no dependency on it; FE mirrors are hand-ported with `// Codegen TODO` comments.
- FE `specialist-forms.ts:11-14` names `datamodel-code-generator (Pydantic → TS)` as the
  intended codegen bridge, gated on shared-types shipping json-schema artifacts.
- FE fixtures: `sample-stage-data.ts` (`TLC_SAMPLE`/`ANALYZE_SAMPLE`/`FP_SAMPLE`) +
  `result-stage-fixtures.ts` (5 cards, `fixture: true`). None dispatched to BE.
- FE `result-stage-model.ts` already defines the full typed evidence union
  (`TlcEvidence`/`CcEvidence`/`AnalysisEvidence`/`FpEvidence`/`ReEvidence` + `AiVerdict`/
  `ManualConclusion`/`EvidenceAction`) — **this is the de-facto target schema BE must converge
  toward** (caveat 5).

## The 6 BE work items (umbrella)

| # | What to define | Where | Has template? |
|---|---|---|---|
| 1 | `TLCParamsForm` + confirm-action arm | `form_payloads.py` | ✅ CC/RE pattern + TLC domain types exist |
| 2 | `AnalyzeParamsForm` + confirm arm | `form_payloads.py` + new shared type | ❌ greenfield (analyze tool seed exists) |
| 3 | `FractionPoolParamsForm` + confirm arm | `form_payloads.py` + new shared type | ❌ greenfield |
| 4 | Typed `result_review` payload (5 evidence bodies) | `runtime_emitted.py` / `form_payloads.py` | ❌ flagged TODO, free-form today |
| 5 | Per-stage executors emitting real evidence | agent runtime / lab-service | ❌ depends on robot data availability |
| 6 | JSON-schema/TS artifact from shared-types + codegen bridge | `bic-shared-types` build | ❌ not built |

## MVP Decision (ADR-lite)

**Context**: The 6-item list spans non-greenfield (#1 TLC, #4 result-review) and greenfield
(#2 Analyze, #3 FP) stages plus enablers (#5 executor evidence, #6 codegen bridge). CC and RE
are the ONLY two stages whose executors actually run and produce real result data today —
highest readiness across every axis. The greenfield stages have no runtime concept to contract
yet; TLC's recognition runs but its result currently rides the CC form's `TLCResult` shim.

**Decision**: MVP = an **end-to-end CC/RE result-review vertical slice** — a CC/RE-scoped
intersection of #4 (type the result-review payload) and #5 (executor emits real typed evidence).
Concretely: replace the CC/RE `analyze_*_result` tool's free-form `analysis: dict[str, Any]`
output with typed `CcEvidence` / `ReEvidence` payloads, type the `TaskResultAnalyzedEvent` wire
to carry them, add the 4th `OriginalAction` arm for result-review, update `events.md`, and
converge FE off `result-stage-fixtures.ts` (cc + re cards) onto the real wire.

**Consequences**:
- CC/RE param forms are NOT touched (already typed) — except verifying the CC↔TLC `TLCResult`
  shim is not disturbed.
- TLC/Analysis/FP result cards stay on fixtures this wave (deferred children).
- #1/#2/#3/#6 and the TLC/Analysis/FP halves of #4/#5 remain documented as deferred children of
  this umbrella.
- FE `result-stage-model.ts` (`CcEvidence`/`ReEvidence`) is the convergence target — BE types
  must match it (or we update both contract + spec together per Rule 10).
- Risk: if the CC/RE executors don't actually carry enough structured data to fill
  `CcEvidence`/`ReEvidence` (rack, fractions, checkpoints), the wire is typed but underfilled.
  This is the first thing to verify in Phase 2 codebase research.

## MVP Decision — REFINED (ADR-lite #2, supersedes the data-source assumption)

**Context**: Research found the CC/RE analyze path (`_analyze_result`, `tools.py:501`) is
statically deferred — it `raise MindCallError` unconditionally (`:518`) and emits an untyped
`{"status":"deferred", "notice":...}` blob. CC's real Mind endpoint IS wired in the client
(`mind_client.py:155` → `/api/cc/result-protocol` → `CCResultResponse`) but never called; RE's
`analyze_result` dispatches to a PARAM endpoint (`/api/rotavap/get-params`) — no RE
result-evidence source exists at all.

**Decision (Drake, 2026-06-15)**: **Contract-first, data-stubbed.** Do NOT wait for the Mind
service. Keep the analyze path deferred from Mind, but replace the untyped placeholder with
**typed, STUBBED** `CcEvidence` / `ReEvidence` payloads:
- The wire (`TaskResultAnalyzedEvent`) becomes typed; `OriginalAction` gains the `result_review`
  arm. These are the real deliverable.
- The evidence DATA is mocked (static/derived stub) until Mind/Mars is live — we don't care that
  Mind isn't started yet.
- **RE evidence shape**: keep FE's RICH `ReEvidence` (`checkpoints[] {checkpoint, target,
  observed, statusLabel, ok}`) as the typed contract. BE fills it with STUB checkpoint rows
  derived from the RE param-spec targets (`observed = target`, `ok = true`) until Mars realtime
  inference lands. RE analyze logically returns `success: true`; the rich card is presentation.
- **CC evidence shape**: keep FE's `CcEvidence`; BE emits a typed stub `CcEvidence` (shape-valid,
  mocked values) instead of calling the deferred Mind endpoint.

**Consequences**:
- No dependency on Mind/ChemEngine being deployed — unblocks implementation today.
- FE `result-stage-model.ts` shapes (`CcEvidence`/`ReEvidence`) are UNCHANGED — they win as the
  contract; BE converges to them. FE only drops the `fixture: true` cc+re cards once the typed
  wire delivers the (stubbed) data.
- The stub is a documented seam: when Mind/Mars land, swap the stub producer for the real
  `mind.analyze_result(CCResultRequest)` mapper / Mars inference — wire + types already correct.
- Risk retired: "source data doesn't exist" no longer blocks — we own the stub.
- New risk: stub must be clearly marked (not silently shipped as real) — fail-loud (Rule 9). A
  `MindNoticeEvent(phase="post")` or equivalent should still signal "evidence is stubbed."

## Technical Approach — resolved design decisions (Phase 2, ADR-lite #3)

Driven by `research/phase2-implementation-map.md`. Five open decisions resolved with Drake
(2026-06-15) so the implementer does not improvise contract shape (Rule 1):

1. **Wire casing → Pydantic `alias_generator=to_camel` + `populate_by_name=True`.** FE consumes
   the evidence body DIRECTLY off the wire and is camelCase (`rackCols`, `statusLabel`). BE
   `CcEvidence`/`ReEvidence` keep snake_case Python fields but serialize camelCase via
   `ConfigDict`. FE shape unchanged; BE stays Pythonic internally. (Decision #1 — highest impact.)
2. **Wire carrier → typed `evidence` SIDECAR on `TaskResultAnalyzedEvent`**, not a union on
   `analysis`. Keeps the raw-dict `analysis` path intact for TLC/Analysis/FP (surgical, Rule 3).
3. **Card chrome → FE-default.** `summary`/`aiVerdict`/`manualConclusion`/`evidenceActions` stay
   FE presentation; BE ships only the evidence body. Matches PRD R6.
4. **OriginalAction → TWO arms: `cc_result` + `re_result`** (separate `CcResultReviewAction` /
   `ReResultReviewAction`), mirroring the `cc_params`/`re_params` one-arm-per-specialist pattern
   (Rule 8). Not a single nested-discriminator arm.
5. **RE checkpoints stub source**: Bath-temp + Pressure derive from
   `state.params_draft["recommended"]` (`REParam.temperature_c`, `air_pressure[].pressure_mbar`,
   `observed = target`, `ok = true`). Rotation-speed + endpoint have NO `REParam` source → fully
   static stub. Fallback to fully-static checkpoints if `recommended` is empty (fail-loud, no crash).

### Load-bearing edit sites (from research EDIT-SITE CHECKLIST — non-obvious ones)

- `_analyze_result` (`tools.py:501-555`) is THE injection point; `task_type` ("cc"/"re") branches
  which evidence model to build. Replace the `{"status":"deferred"}` dict; keep
  `MindNoticeEvent(phase="post")` (R5).
- `FormRequestedEvent._enforce_typed_action` (`runtime_emitted.py:355-382`) AND `assertions.py:197`
  both gate `typed_required` to `("params","plan")` — BOTH must add `"result_review"` or a raw
  dict silently bypasses the new typed contract.
- `scenario_monitor_exp` (`run_scenarios.py:528-544`) currently ASSERTS THE ABSENCE of
  result_review — these negatives are this task's scope and must FLIP to positive (looks
  intentional; it isn't).

## Implementation progress

### PR1 — DONE (schema + plumbing, no behavior change) — 2026-06-15
- `CcEvidence`/`ReEvidence` + nested rows (`RackTube`/`FractionRow`/`ReCheckpointRow`) in
  `form_payloads.py` (camelCase via `alias_generator=to_camel` + `populate_by_name=True`),
  field-matched to FE `result-stage-model.ts`.
- `CcResultReviewAction`/`ReResultReviewAction` arms registered in `OriginalAction` (tags
  `cc_result_review`/`re_result_review`), `TYPED_ORIGINAL_ACTIONS`, `__all__`.
- `TaskResultAnalyzedEvent.evidence: CcEvidence | ReEvidence | None = None` sidecar (`:598`),
  `analysis` dict unchanged.
- Verified: `uv run ruff check` clean, `uv run pyright app/` 0 errors, `uv run pytest` 656 passed
  (no regression). (IDE new-diagnostics about py3.9 unions / unresolved bic_shared_types are an
  editor-interpreter artifact — the uv toolchain is clean; disregarded.)

### PR1→PR2 RE-SLICE (dispatch correction — Rule 1/Rule 9)
The two typed-action gate flips (`_enforce_typed_action` + `assertions.py:199` → add
`"result_review"`) were ORIGINALLY scoped to PR1 but are **atomically coupled** to the
`_analyze_result` typed emission: `_analyze_result` is the ONLY runtime emitter of a
result_review form and still emits a raw dict, so flipping the gate alone breaks `auto_analyze`
(`test_l3_reception_node_split_e2e::test_task_terminal_drains_cleanly`). **Moved to PR2** — the
gate flip ships in the SAME change as the typed-stub emission. PR1 left the gate at
`("params","plan")` and the tree green.

### PR2 — DONE (typed evidence FLOWS + all 5 models defined) — 2026-06-15 — commit `73cc632`
- `_analyze_result` emits typed `CcEvidence`/`ReEvidence` stubs (cc/re) onto both the
  `TaskResultAnalyzedEvent.evidence` sidecar and a typed `Cc/ReResultReviewAction`. Mind stays
  deferred (`raise MindCallError` + `MindNoticeEvent(phase=post)` + raw `analysis` dict kept).
- RE checkpoints: temp+pressure derived from `params_draft.recommended`; rotation/endpoint static;
  fail-loud static fallback.
- Both typed-action gates flipped to include `result_review` (atomic with the emission).
- `EventBase.to_wire_payload()` → `by_alias=True` (verified no-op for all 34 existing kinds).
- **Scope expansion (Drake 2026-06-15)**: pilot now DEFINES all 5 evidence models —
  `TlcEvidence`/`AnalysisEvidence`/`FpEvidence` (+ nested rows) added DEFINED-BUT-NOT-EMITTED;
  `evidence` sidecar union widened to all 5. tlc/analyze/fp canned-but-defined for the fanout child.
  (`TlcCriterionRow.passed` aliases to wire key `pass`.)
- Verified: ruff/pyright clean, 656 passed, empirical by_alias dumps match FE keys for all 5.

### PR3 — DONE (FE binds the live evidence wire) — 2026-06-15 — commit `760d3ca` (BIC-agent-portal)
- `TaskResultAnalyzedEvent.evidence?: ResultStageEvidence | null` added to FE event type.
- `workspaceStore.resultEvidence` set from `e.evidence`; in INITIAL_DATA + PER_TASK_RESET_KEYS
  (resets per trial — no cc→re bleed).
- `adaptResultStages`: live cc/re stage binds typed wire evidence (`evidence.kind === id`),
  flips `fixture=false` (drops Sample-evidence badge); double-gated so re can't render on cc.
  Fixtures kept as pre-event fallback. tlc/analyze/fp untouched.
- `ResultConfirmationPane` threads `resultEvidence` into the adapter.
- Specs `sse-contract.md` + `backend-contract.md` updated (Rule 10).
- Verified: pnpm typecheck / check / build clean. E2E NOT run (needs live :8800+:5174; spec also
  lacks an evidence-render assertion — follow-up coverage gap, Rule 7).
- NOTE: `vite.config.ts` `host:'0.0.0.0'` (pre-existing 18:00 edit, not ours) left UNCOMMITTED.

## PR4 — CORRECTIONS (Drake 2026-06-15, supersedes earlier RE/persistence decisions)

Two corrections after Drake reviewed the shipped pilot:

1. **RE evidence collapses to `{success: bool}`** (REVERSES ADR-lite #2's "keep rich ReEvidence").
   Drake's ORIGINAL directive was "RE analyze returns just `success: true`"; the rich
   `checkpoints[]` table I shipped wrongly followed a later answer without flagging it overrode
   that directive (Rule 5 miss). FIX: `ReEvidence = {success: bool}`. Drop `ReCheckpointRow`,
   `_build_re_evidence_stub`'s checkpoint derivation, and the FE RE card's checkpoints table →
   render a simple success/fail. CC evidence is UNCHANGED (rich rack/fractions stands).

2. **Persist the typed evidence to `trials.analysis`** (was: emitted on the wire but NEVER
   persisted — sidecar was "live but dark", lost on replay). COLUMN SEMANTICS (Drake's ruling):
   - `trials.result` = RAW MQ result from the Robot (the `{steps:[...]}` Lab blob, written by
     `event_ingress.apply_terminal_from_lab` at `event_ingress.py:137`) — **DO NOT TOUCH** (writing
     evidence here would clobber the Lab steps — collision confirmed).
   - `trials.analysis` = the ANALYZED result returned from Mind — typed `evidence` belongs HERE.
   `TaskResultAnalyzedEvent.apply()` already targets `trials.analysis` (writes the free-form
   `analysis` dict today). FIX: write the typed `evidence.model_dump(by_alias=...)` into
   `trials.analysis` so the analyzed-result object is persisted + survives replay. Schema
   authority: per-execution result/analysis lives on `trials`, NOT `jobs` (jobs is pure grouping).

## Acceptance Criteria status (MVP)
- [x] BE `CcEvidence`/`ReEvidence` models exist; field-match FE (+ all 5 defined).
- [x] `TaskResultAnalyzedEvent` carries typed CC/RE evidence; raw-dict path intact for others.
- [x] `OriginalAction` has cc_result/re_result arms; round-trips through the HITL gate.
- [x] CC/RE analyze emits typed stub evidence; `MindNoticeEvent` still signals stubbed source.
- [x] FE cc + re result cards render from the wire (fixture=false on event); TLC/Analysis/FP unchanged.
- [x] `events.md` + `.trellis/spec/` updated — DONE: L3/events.md + L4/events.md + contracts.md
      (BE, commit `0c37f89`), sse-contract.md + backend-contract.md (FE, commit `760d3ca`). All
      stale PR1-interim claims removed; specs match shipped PR2 (Rule 10 closed).
- [ ] Scenario/E2E: CC + RE terminal trial → result_review gate shows typed evidence end-to-end.
      OPEN — needs live stack + a new evidence-render assertion (cc-re-chained-flow lacks it).

### ⚠ TASK-LINEAGE NOTE (unresolved — needs Drake confirm)
A second BE pilot task appeared 2026-06-15 18:39 at
`BIC-agent-service/.trellis/tasks/06-15-typed-specialist-result-review-evidence-cc-re-pilot`
(in the REAL git repo; its PRD already encodes the "all 5 models" scope). PR1+PR2 were committed
under THIS root task's lineage but the code lives in that repo. Working assumption: the 18:39 task
is the better home (lives where code+commits are). PR3 + spec updates should likely track there.
Reconcile/merge the two task dirs before `/trellis:finish-work`.

### ⚠ PR3 load-bearing note — wire serialization casing (RESOLVED in PR2)
`EventBase.to_wire_payload()` uses `model_dump(mode="json")` WITHOUT `by_alias=True`, so the new
`evidence` sidecar serializes snake_case by default (FE would get `rack_cols`, not `rackCols`).
PR2 MUST thread `by_alias=True` (or `serialize_by_alias`) on the evidence dump so the FE contract
holds. Without this, the camelCase alias is defeated on the wire.

## Deferred children (documented, not in MVP)

- #1 TLCParamsForm + confirm arm (extract from CC shim)
- #2 AnalyzeParamsForm + analyze shared type + executor concept
- #3 FractionPoolParamsForm + FP shared type + executor concept
- #4/#5 TLC + Analysis + FP evidence bodies (rest of result-review)
- #6 shared-types json-schema + datamodel-code-generator bridge

## Resolved Questions

- (Q2) Do CC/RE executors carry enough data to fill the evidence? → **NO, and we don't need it.**
  Research (`research/cc-re-evidence-readiness.md`) found the analyze path is statically deferred
  and RE has no telemetry source. RESOLVED by the contract-first/stub decision (ADR-lite #2):
  type the wire, stub the data.
- (Q3) Where do `CcEvidence`/`ReEvidence` models live? → **`app/events/form_payloads.py`**
  (BE-local), beside `CCParamsForm`/`REParamsForm` and the `OriginalAction` union. Defers the
  shared-types/codegen-bridge move to child #6.

## Requirements (MVP — converged)

R1. Define typed BE `CcEvidence` / `ReEvidence` Pydantic models (Rule 11 — type-first) whose
    field shapes MATCH FE `result-stage-model.ts` (`CcEvidence` rich fractions/rack/uvTrace;
    `ReEvidence` rich `checkpoints[]`). FE is the contract authority — BE converges to it.
R2. Type the `TaskResultAnalyzedEvent` wire to carry the typed evidence for CC/RE, replacing
    `analysis: dict[str, Any]` for these two stages. Keep the raw-dict path alive for the
    not-yet-typed stages (TLC/Analysis/FP) — surgical, no regression (Rule 3).
R3. Add the `result_review` arm to `OriginalAction` / `TYPED_ORIGINAL_ACTIONS` (4th arm).
R4. CC/RE analyze path (`_analyze_result`) emits typed STUB evidence instead of the untyped
    `{"status":"deferred"}` blob:
    - CC: typed stub `CcEvidence` (mocked values) — do NOT call Mind yet; leave the deferred
      seam + a clear note that data is stubbed.
    - RE: typed `ReEvidence` with `checkpoints[]` STUB rows derived from RE param targets
      (`observed = target`, `ok = true`).
R5. Stub must fail loud (Rule 9): keep `MindNoticeEvent(phase="post")` (or equivalent) so the
    wire signals "evidence is stubbed, not real Mind/Mars output." No silent fake-as-real.
R6. FE: remove `fixture: true` cc + re cards from `result-stage-fixtures.ts`; render the cc + re
    result cards from the real (stubbed) wire. TLC/Analysis/FP cards stay on fixtures.
R7. Update `events.md` (wire change) + relevant `.trellis/spec/` contract docs in the SAME
    change set (Rule 10).

## Acceptance Criteria (MVP)

- [ ] BE `CcEvidence`/`ReEvidence` Pydantic models exist; field-for-field match FE shapes.
- [ ] `TaskResultAnalyzedEvent` carries typed CC/RE evidence; raw-dict path intact for other stages.
- [ ] `OriginalAction` has a `result_review` arm; round-trips through the HITL gate.
- [ ] CC/RE analyze emits typed stub evidence; `MindNoticeEvent` still signals stubbed source.
- [ ] FE cc + re result cards render from the wire (no `fixture: true` for cc/re); TLC/Analysis/FP
      cards unchanged.
- [ ] `events.md` + `.trellis/spec/` updated in the same change set.
- [ ] Scenario/E2E: CC + RE terminal trial → result_review gate shows typed evidence end-to-end.

## Definition of Done (team quality bar)

- Tests added/updated (unit + scenario where appropriate)
- Lint / typecheck / CI green
- `.trellis/spec/` contract docs updated for every contract touched (Rule 10)
- `events.md` updated for result-review wire changes
- FE fixture removal verified — no orphaned `fixture: true` / sample-stage imports for shipped stages

## Out of Scope (explicit)

- Actually calling the Mind service (`mind.analyze_result`) — the deferred seam stays; we emit
  typed STUB evidence. The stub→real swap is a follow-up once Mind/ChemEngine is deployed.
- RE real telemetry / Mars realtime inference — `checkpoints[]` rows are stubbed from param
  targets until that source exists.
- Deferred children (separate tasks): #1 TLCParamsForm, #2 AnalyzeParamsForm, #3
  FractionPoolParamsForm, #6 shared-types json-schema + datamodel-code-generator bridge.
- TLC / Analysis / FP result-evidence bodies — those cards stay on FE fixtures this wave.
- CC/RE param forms — already typed; untouched except verifying the CC↔TLC `TLCResult` shim
  (caveat 3) is not disturbed.
- Moving evidence models into `bic-shared-types` — deliberately BE-local for now (Q3).

## Research References

- [`../archive/2026-06/06-13-integrate-current-fe-be-for-cc-re-e2e/research/contract-gap-claims-verification.md`](../archive/2026-06/06-13-integrate-current-fe-be-for-cc-re-e2e/research/contract-gap-claims-verification.md)
  — 13/13 claims CONFIRMED + 5 caveats (TLC over-ships, analyze tool seed, CC↔TLC shim,
  result-review double-anchored, FE evidence union = target schema).

## Technical Notes

- BE: `BIC-agent-service/app/events/form_payloads.py`, `app/events/runtime_emitted.py`,
  `app/runtime/graphs/specialists/`, `app/runtime/types/plan.py`, `app/data/models.py`.
- Shared: `BIC-shared-types/bic_shared_types/mcp_protocol/{tlc,cc,re}.py`, `pyproject.toml`.
- FE: `BIC-agent-portal/src/types/specialist-forms.ts`,
  `src/components/workspace/forms/sample-stage-data.ts`,
  `src/components/workspace/result/{result-stage-model,result-stage-fixtures}.ts`.
