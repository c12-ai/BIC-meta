# Research: Adversarial verification of contract-gap analysis (13 claims)

- **Query**: Validate a contract-gap analysis against ACTUAL SOURCE; verdict per claim with file:line evidence.
- **Scope**: mixed (BE `BIC-agent-service`, FE `BIC-agent-portal`, Shared `BIC-shared-types`)
- **Date**: 2026-06-15
- **Method**: Read canonical files directly. Ignored `.claude/worktrees/*` copies — only the live tree counts.

## Verdicts

### Surface 1 — Param-design forms (form_payloads.py)

**[1] CONFIRMED** — `BIC-agent-service/app/events/form_payloads.py`
Only two `*ParamsForm` classes are defined: `CCParamsForm` (L117) and `REParamsForm` (L188). No `TLCParamsForm`, `AnalyzeParamsForm`, or `FractionPoolParamsForm`. The `__all__` (L446-468) lists exactly: `CCParamsForm`, `REParamsForm`, their sub-models (`CCFromUserFields`, `CCLabLogistics`, `REFromUserFields`, `RELabLogistics`), confirm actions, plan types, and gate helpers — nothing else form-shaped.

**[2] CONFIRMED** — `form_payloads.py:87-100`
`CCFromUserFields` (L59) carries the three TLC-context fields verbatim: `tlc_file_key: str | None` (L87), `rf_values: list[float] | None` (L91), `product_rf: float | None` (L95). The class docstring (L66-69) explicitly calls these "TLC-recognition context … NOT sent to Mind recommend." Confirms TLC is smuggled into CC, not its own form.

**[3] CONFIRMED** — `BIC-shared-types/bic_shared_types/mcp_protocol/tlc.py`
`TLCSpot` (L80), `TLCPlateResult` (L94), `TLCResult` (L106) all exist as Pydantic models. (Note: the file ships far more — `TLCMixcaseRequest/Response`, `TLCResultRequest/Response`, `TLCPlateRecognitionRequest/Response`, `TLCMixcaseAssessment`, etc. The analysis under-states what TLC ships.)

**[4] CONFIRMED** — BE + shared-types
- No `analyze` executor: specialist graph dir `app/runtime/graphs/specialists/` contains only `cc.py`, `re.py` (+ `rehydrate.py`, `tools.py`, `__init__.py`). Executor type is `Literal["cc", "re"]` at `app/runtime/types/plan.py:53` and `form_payloads.py:361`.
- No analyze MCP protocol: `bic_shared_types/mcp_protocol/` = `cc.py`, `re.py`, `tlc.py`, `experiment.py`, `_base.py`, `__init__.py`. No `analyze.py`.
- No analyze shared type: `grep "class Analyz|AnalyzeResult|AnalysisResult"` over shared-types → 0 hits.
- CAVEAT / nuance: the word "analyze" DOES appear in BE as the **tool function** `analyze_*_result` inside the CC/RE specialists (`tools.py` ~L510, L938) which emits `TaskResultAnalyzedEvent`. That is a post-execution analysis step owned by the cc/re specialists — NOT a standalone `analyze` executor. Claim is about the executor/protocol/type, all of which are genuinely greenfield. CONFIRMED, but builders must not confuse "no analyze executor" with "no analyze logic" — the result-analysis tool already exists.

**[5] CONFIRMED** — BE + shared-types
`grep "fraction_pool|fractionpool|FractionPool|FP_"` over `app/` and `bic_shared_types/` → 0 hits. No domain/shared shape for fraction-pool. Greenfield. (FE has FP fixtures only — see [12].)

**[6] CONFIRMED** — `form_payloads.py:411-428`
`OriginalAction` discriminated union (L411) registers exactly three arms: `Tag("cc_params")` → `CCParamsConfirmAction`, `Tag("re_params")` → `REParamsConfirmAction`, `Tag("plan")` → `PlanConfirmAction`. `TYPED_ORIGINAL_ACTIONS` tuple (L424) = `(CCParamsConfirmAction, REParamsConfirmAction, PlanConfirmAction)`. Matches the claim's `cc_params`, `re_params`, `plan`.

### Surface 2 — Result-review wire

**[7] CONFIRMED** — `app/events/runtime_emitted.py:564-587`
`TaskResultAnalyzedEvent` (L564) declares `analysis: dict[str, Any] = {}` (L579) — free-form blob. Its `apply()` (L581) writes `fields={"analysis": self.analysis}` to `tx.trials.update_fields` (L584-587), i.e. UPDATE `trials.analysis`. Column is `trials.analysis Mapped[dict | None]` JSONB at `app/data/models.py:236`. All three sub-claims hold.

**[8] CONFIRMED** — `form_payloads.py:28-31` (module docstring)
"Result-review variant is still deliberately NOT included here: a follow-on ticket will type that payload separately. `FormRequestedEvent` continues to accept `original_action: OriginalAction | dict[str, Any]` so the RESULT_REVIEW raw-dict path keeps working until the typed variant lands." Also reinforced at L408-410. Confirms the deliberate not-yet-typed flag.

**[9] CONFIRMED** — `runtime_emitted.py:505-507`
`# TODO(result_review): when chemist-editable fields are added to the result-review form (today form_values is empty), persist them here symmetrically. Tracked in events.md.` Claim said "around line 505" — exact. Context (L503-504) shows params writes `form_values` to `trials.params`; result_review path has no editable fields yet.

### Surface 3 — Distribution

**[10] CONFIRMED** — shared-types build + FE package.json/imports
- shared-types `pyproject.toml`: `[build-system] requires=["hatchling"]`, `build-backend="hatchling.build"`, `[tool.hatch.build.targets.wheel]` → Python wheel only. `requires-python = ">=3.10"`. No `package.json` anywhere under shared-types (excluding `.venv`). No `*.ts` and no `*schema*.json` artifacts emitted.
- FE `BIC-agent-portal/package.json`: `grep "shared-types|bic-shared"` → 0 hits. No dependency.
- FE `src/` only *mentions* `bic_shared_types.*` in comments (e.g. `specialist-forms.ts:3`, `events.ts:215`, `skill-labels.ts:3`) as the authority-citation for hand-ported mirrors — never an import. Confirms Python-only, no shipped TS/JSON-schema artifact, no FE dep.

**[11] CONFIRMED** — `BIC-agent-portal/src/types/specialist-forms.ts:11-14`
`// Codegen TODO: replace this file with output from datamodel-code-generator (Pydantic → TS) once bic-shared-types ships json-schema artifacts. Until then, any backend schema change must be reflected here by hand.` Names datamodel-code-generator as the intended bridge gated on json-schema artifacts. Exact match.

### FE fakery surface

**[12] CONFIRMED** — FE fixtures, not BE-wired
- Param-design fakes live in `BIC-agent-portal/src/components/workspace/forms/sample-stage-data.ts`: `TLC_SAMPLE` (L21), `ANALYZE_SAMPLE` (L34), `FP_SAMPLE` (L81) — hardcoded literals. Header (L5-11): "TLC / Analyze / Fraction Pool have NO backend params contract yet, so their forms render this sample data with local-only edit state … Nothing here is ever dispatched — confirm stays exclusive to the live executor stage." Consumed by `TlcStageForm.tsx`, `FpStageForm.tsx` (and an analyze form) via static import, not from a store/SSE.
- Result fakes: `src/components/workspace/result/result-stage-fixtures.ts` — header (L1-3) "Demo fixture evidence for the five Result stage cards (PRD D6: typed frontend fixtures for evidence the backend doesn't send yet)." `fixture: true` appears 5× (one per card). `RESULT_STAGE_FIXTURES` (L230) maps 5 stages: `tlc, cc, analysis, fp, re`. Both clauses of the claim hold (5 fake result cards, hardcoded, BE-disconnected).
- Nuance: filename is `sample-stage-data.ts`, NOT a single file literally named with each constant — claim named the *constants* correctly, which is what matters.

**[13] CONFIRMED** — `src/components/workspace/result/result-stage-model.ts`
All named interfaces exist: `EvidenceAction` (L29), `AiVerdict` (L37), `ManualConclusion` (L42), `TlcEvidence` (L56), `CcEvidence` (L83), `AnalysisEvidence` (L112), `FpEvidence` (L125), `ReEvidence` (L139). The five evidence shapes form a union (L145-149). Note the analyze evidence is named `AnalysisEvidence` (not `AnalyzeEvidence`) — claim spelled it `AnalysisEvidence`, correct.

## Caveats / Things the analysis MISSED or under-stated

1. **TLC ships much more than `TLCSpot/TLCPlateResult/TLCResult`.** `tlc.py` also exports full Apex↔Mind request/response protocol (`TLCMixcaseRequest/Response`, `TLCResultRequest/Response`, `TLCPlateRecognitionRequest/Response`) and assessment/trial types. If the integration only plans to reuse the 3 result types, it is leaving a typed recognition+mixcase protocol on the table.

2. **"No analyze executor" ≠ "no analyze logic."** A working `analyze_*_result` tool already exists inside the cc/re specialists and emits the (free-form) `TaskResultAnalyzedEvent`. Greenfield applies to the *executor/protocol/typed-shape*, not to the act of analyzing a result. Build on the existing tool, don't duplicate it.

3. **CC↔TLC coupling is load-bearing, not incidental.** `build_cc_param_request` (`form_payloads.py:216`) fabricates a standalone `TLCResult(product_rf, plates=[])` (L231) — accepted contract per Drake 2026-06-12 comment. Any move to a real TLC form must preserve this standalone-mode shim or CC recommend breaks.

4. **The result-review typed-payload gap is double-anchored.** Both the BE form_payloads docstring ([8]) and runtime_emitted TODO ([9]) point to `events.md` as the tracking doc. Whoever types result_review should update `events.md` + add a 4th `OriginalAction` arm — currently the union hard-excludes `result_review` (it rides the `dict[str, Any]` path).

5. **FE evidence union (`result-stage-model.ts`) is already a stronger contract than anything BE emits.** FE has typed `TlcEvidence/CcEvidence/AnalysisEvidence/FpEvidence/ReEvidence` + `AiVerdict/ManualConclusion`, but BE only emits `analysis: dict[str, Any]`. When wiring, the FE types are effectively the *target* schema BE must converge toward — they are the de-facto spec for the result-review payload that BE hasn't typed yet.

## SUMMARY

All 13 claims are **CONFIRMED** against source — none refuted, none merely partial. The analysis is solid and safe to build on. The only corrections are *under-statements*, not errors:
- TLC ships a far larger protocol than the 3 result types cited (caveat 1).
- "analyze" greenfield is about the executor/protocol/type; a result-analysis *tool* already exists and emits `TaskResultAnalyzedEvent` (caveat 2).
- The CC form's standalone `TLCResult` shim is a load-bearing coupling to watch during any TLC-form extraction (caveat 3).
- FE's typed evidence union already encodes the result-review schema BE has deliberately left untyped — treat it as the convergence target (caveat 5).
