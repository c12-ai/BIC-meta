# Research: Reconciliation — Task A (type-specialist-contracts) vs Task B (plan-driven-specialist-tabs)

- **Query**: Two overlapping 06-15 tasks. Determine precise relationship/conflicts and recommend a reconciliation.
- **Scope**: internal (BE `BIC-agent-service` + FE `BIC-agent-portal` + shared-types), against live source.
- **Date**: 2026-06-15

> **Task A** = `/Users/drakezhou/Development/BIC/.trellis/tasks/06-15-type-specialist-contracts/` (BE-side, has `prd.md` + 3 research files).
> **Task B** = `/Users/drakezhou/Development/BIC/BIC-agent-portal/.trellis/tasks/06-15-plan-driven-specialist-tabs-and-results-drop-sample-stages/` (FE-rooted, NO `prd.md` / NO `task.json` — only `research/contract-delta.md`).

---

## 0. TL;DR VERDICT

**A is NOT a conflicting alternative to B, and NOT a clean subset either. A is the *result-review evidence vertical* of one specialist stage-pair (cc/re), while B is the *horizontal executor-fanout* across all 5 stages. They intersect in exactly ONE file region — `_analyze_result` (`tools.py:501-555`) and the `result_review` contract surface — and they make a *genuinely contradictory choice* there:**

- **A types the `result_review` wire** (adds typed `CcEvidence`/`ReEvidence` + two new `OriginalAction` arms `cc_result_review`/`re_result_review`).
- **B explicitly says "no new event KIND, reuse existing kinds" and routes everything through `confirm_kind=params` + `result_review` with a CANNED `analysis` dict** — i.e. B keeps the raw `analysis: dict[str, Any]` path that A is trying to retire.

**These two are mutually exclusive *only at the `result_review` typing decision*; everywhere else they are orthogonal/complementary.** B does NOT need A's typed evidence arms to function (it ships canned dicts); A does NOT need B's executor fanout to function (it only touches cc/re). 

**Recommended reconciliation: option (c-variant) — one umbrella, two phased children, with A RE-SCOPED to be B's BE-child "vertical slice" and explicitly designated the *pilot* that proves the typed-evidence pattern on cc/re before B fans it out to tlc/analyze/fp.** A's typed-evidence work is *necessary-but-folded-in*, NOT unnecessary. See §6 for the exact new scope.

---

## 1. Code-State Reality Check (verified against live source)

Both tasks are **100% greenfield in code** — nothing started in either repo.

| B's §5 / §4 claim | Verified location | Status |
|---|---|---|
| `executor: Literal["cc", "re"]` in `plan.py` | `BIC-agent-service/app/runtime/types/plan.py:53` (`TaskDraft.executor`) | ✅ CONFIRMED |
| executor literal in `form_payloads.py` | `app/events/form_payloads.py:361` (`PlanStep.executor: Literal["cc","re"]`) | ✅ CONFIRMED |
| executor literal in `specialist.py` | `app/runtime/types/specialist.py:76` (`SpecialistKind = Literal["cc","re"]`) | ✅ CONFIRMED |
| **(B §5 MISSED a 4th site)** dispatcher hardcodes routing | `app/runtime/graphs/nodes/specialist_dispatcher.py:131` (`goto: Literal["cc_subgraph","re_subgraph"]`) | ⚠️ NOT in B's §5 list — B's "parameterized stub subgraph" must add routing arms HERE too |
| FE `Job.executor` union is `'cc'\|'re'` | `BIC-agent-portal/src/types/events.ts:101` | ✅ CONFIRMED (B §4 must widen) |
| FE workspace `executor` is `'cc'\|'re'` | `src/stores/workspaceStore.ts:125`; `ParameterDesignPanel.tsx:69` `type Executor='cc'\|'re'`; `result-stage-adapters.ts:22` | ✅ CONFIRMED |
| FE `SpecialistStage` union | `src/stores/workspaceStore.ts:36` = `'tlc'\|'cc'\|'analyze'\|'fp'\|'re'` | ⚠️ **ALREADY 5-way.** B §4's "widen `SpecialistStage`" is mostly DONE — the *stage* enum is already 5-way; only the *live `executor`/`Job.executor`* mirrors are 2-way. B slightly over-states the FE type work. |
| Robot/Manual toggle exists | `src/components/workspace/StepStrip.tsx:66,101-103` — `isRobot = executor==='cc'\|\|'re'`, label `Robot`/`Manual` | ⚠️ Exists as a **derived display badge**, NOT an authoring toggle. B's "Robot/Manual authoring" UI is genuinely greenfield; the badge is read-only today. |
| B's event sequence matches cc/re today | `cc.py`: `TaskParamsSetEvent` (`:483`) → `FormRequestedEvent` `confirm_kind=params` (`:284`) → `TaskDispatchedEvent` (`:311`) → `TaskResultAnalyzedEvent`+result_review (`:493` region, via `_analyze_result`) | ✅ CONFIRMED — B's §3 sequence is accurate |
| tlc/analyze/fp forms / stub subgraphs / typed evidence / result_review arm | grep of BE+FE source (logs excluded) | ✅ **NONE EXIST — fully greenfield for both A and B** |

**Decisive shared fact (the linchpin):** `result_review` is *deliberately* left out of the typed union TODAY. `form_payloads.py` (OriginalAction block) comment, verbatim:

> `confirm_kind="result_review"` remains outside this union and uses the legacy dict path until a follow-on ticket types it.

And `_enforce_typed_action` (`runtime_emitted.py:356-372`) requires typed actions ONLY for `confirm_kind in ("params","plan")` — `result_review` flows as a free-form dict by design. **A's entire MVP is "be that follow-on ticket." B's design explicitly chooses to NOT be that ticket** (it reuses the free-form `analysis` dict). This is the contradiction, and it is real but narrow.

---

## 2. Field-by-field Overlap & Contradiction Map

| Concern | Task A | Task B | Relationship |
|---|---|---|---|
| **Stages in scope** | cc + re ONLY (TLC/Analyze/FP explicitly DEFERRED) | ALL 5 (cc/re unchanged + tlc/analyze/fp NEW) | **B SUPERSET** on breadth. A defers exactly what B requires. |
| **`executor` enum** | UNTOUCHED (cc/re already typed) | Grow `cc\|re` → `cc\|re\|tlc\|analyze\|fp` at 3 (really 4) sites | **B-only** (A is orthogonal here) |
| **Param forms (TLC/Analyze/FP)** | DEFERRED children #1/#2/#3 | REQUIRED now (`TLCParamsForm`/`AnalyzeParamsForm`/`FPParamsForm`) | **DIRECT CONTRADICTION of timing** (A=later, B=now). Not a shape conflict — A even pre-scoped these as the same 3 forms. |
| **`result_review` wire typing** | TYPE IT: typed `CcEvidence`/`ReEvidence` sidecar on `TaskResultAnalyzedEvent` + 2 new `OriginalAction` arms (`cc_result_review`/`re_result_review`) + extend `_enforce_typed_action` | DO NOT type it: "no new event KIND, reuse existing kinds"; canned `analysis` dict through the existing free-form path | **MUTUALLY EXCLUSIVE at the typing decision.** Both touch `_analyze_result`; A retires the raw dict for cc/re, B leans on it for all 5. |
| **`analysis` raw-dict path** | Keep for TLC/Analyze/FP; replace for cc/re with typed evidence | Keep for ALL 5 (canned payloads ride it) | **CONTRADICT for cc/re only.** Compatible for tlc/analyze/fp (both keep raw dict there). |
| **Lab round-trip** | UNTOUCHED — A doesn't dispatch; it only types the post-result analyze wire. Real cc/re still call Lab via `submit_l4_execution`. | tlc/analyze/fp BYPASS Lab — `task_dispatched` is synthetic/canned, no `submit_l4_execution` | **Orthogonal.** A never touches dispatch; B's stub only affects the 3 new executors, not cc/re's real Lab call. |
| **Dispatcher routing** | UNTOUCHED | Must add `tlc/analyze/fp` → stub-subgraph arms at `specialist_dispatcher.py:131` | **B-only** |
| **FE sample layer** | NOT deleted — TLC/Analyze/FP cards STAY on fixtures (`sample-stage-data.ts`, `result-stage-fixtures.ts`); only cc+re `fixture:true` cards dropped | DELETE the ENTIRE FE sample layer (stub now provides real payloads for all 5) | **CONTRADICT.** A keeps tlc/analyze/fp fixtures (because no BE source); B deletes them (because the stub backfills them). B's deletion is only safe *after* B's stub executors ship. |
| **FE evidence target schema** | FE `result-stage-model.ts` `CcEvidence`/`ReEvidence` = contract authority; BE converges | Same `result-stage-model.ts` is the render target for all 5 (`TlcEvidence`/`AnalysisEvidence`/`FpEvidence` also already exist at `:56/:112/:125`) | **AGREE.** Same source-of-truth file. A converges 2 of the 5; B needs all 5. |
| **Casing on the wire** | RESOLVED: Pydantic `alias_generator=to_camel` + `populate_by_name=True` (camelCase out, snake_case Python) | UNRESOLVED — B's OPEN ITEMs don't even reach the casing question | **A is strictly ahead.** A's casing decision is reusable by B verbatim. |
| **`confirm_kind` literals** | unchanged (`plan\|params\|result_review`) | unchanged (B §5 I-CONTRACT-5) | **AGREE** |
| **Card chrome (summary/aiVerdict/...)** | FE-default; BE ships only evidence body | B implies canned `analysis` renders unchanged via `ResultConfirmationPane` | **AGREE in spirit** (both keep chrome FE-side) |

### Are A's typed arms and B's "reuse kinds" compatible or mutually exclusive?

**Mutually exclusive as written, but only because B under-specifies.** B's claim "no new event KIND" is *literally true even under A* — A adds NO new SSE event kind either (it adds a typed `evidence` *sidecar field* on the existing `task_result_analyzed` kind and two new `OriginalAction` *union arms*, not a new wire kind). So "no new KIND" is not actually where they conflict.

The real conflict: **B routes the result through a CANNED `analysis: dict` (untyped), A routes it through a typed `evidence` model.** B does NOT need A's `CcEvidence`/`ReEvidence` arms to render — it ships a dict shaped to match what `ResultConfirmationPane` already eats (the fixture shape). So **B keeps the raw analysis dict; A retires it for cc/re.** If B ships first with canned dicts for cc/re, it directly contradicts A's typed wire. If A ships first, B's tlc/analyze/fp can *either* emit raw dicts (A left that path alive) *or* adopt A's typing pattern (better).

### Does B's stub-executor pattern conflict with or subsume A's typed-wire approach?

**Subsumes at the structural level, contradicts at the typing level.** B's "grow executor enum + parameterized stub subgraph + canned `task_dispatched`+`task_result_analyzed`" is a *broader machine* that, for tlc/analyze/fp, produces exactly the kind of post-result `task_result_analyzed` event A types for cc/re. The stub's canned `task_result_analyzed` payload (B §3) is THE SAME EVENT A is typing. So B's machine *will emit the event A types* — meaning A's typed-evidence work is the natural "what shape is the canned payload?" answer that B's §2 OPEN ITEM #2 leaves unresolved. **A is the typed-payload spec that B's stub needs but hasn't written.**

---

## 3. The MARS/Stub Philosophy — Same Idea, Different Granularity

**They are the SAME idea at two different seams. A is a strict conceptual subset of B's philosophy.**

- **A's seam (data-level):** stub the *evidence DATA* inside `_analyze_result`. The Mind call stays deferred (`tools.py:518` `raise MindCallError`), the wire+types become real, the `CcEvidence`/`ReEvidence` *values* are mocked until Mind/Mars lands. The swap point = "replace the stub producer with `mind.analyze_result(CCResultRequest)` mapper" (PRD ADR-lite #2). One small function per stage.
- **B's seam (executor-level):** stub the *whole executor round-trip* — `task_dispatched + task_result_analyzed` are canned (no Lab call). The swap point = "the canned `task_dispatched`+`task_result_analyzed` emit is the ONE function per stage MARS replaces with the real robot/Lab round-trip" (B §3).

These are nested seams, not competing ones:
- B's stub bypasses the **Lab dispatch** (the robot round-trip) → produces a canned `task_result_analyzed`.
- A's stub bypasses the **Mind analyze** (the AI inference) → produces typed-but-mocked evidence *inside* `task_result_analyzed`.

For tlc/analyze/fp, BOTH seams are stubbed (no Lab AND no Mind). For cc/re, B leaves Lab real (A confirms cc/re still call `submit_l4_execution`) and only the Mind/evidence is stubbed — which is **exactly A's seam.** So:

> **A's "stub the evidence data, keep the Mind seam deferred" IS B's per-stage MARS-replaceable function, viewed at the evidence-payload granularity for the two stages (cc/re) whose Lab round-trip is already real.** A is the finer-grained, already-decided instance of B's coarser philosophy.

The two are consistent. A even satisfies B's unstated need: B §2 OPEN ITEM #2 ("define the exact field set of each new form / the canned `analysis` shape") is, for the result side, precisely the `*Evidence` typing A has already specified for cc/re and that B would extend to tlc/analyze/fp.

---

## 4. Which Is the Better Contract Design?

**Neither dominates; they're at different altitudes. The best design is A's typing discipline applied inside B's executor-fanout frame.**

### B's design (grow enum + reuse wire kinds + stub Lab round-trip)
- **Pros:** Maximally surgical on the *wire* — no new SSE kind, no new HTTP route, no new error envelope (B §0.4). The fanout is "safe to grow" precisely because it reuses kinds. The MARS swap is one clean function per stage.
- **Cons:** It keeps the *untyped* `analysis: dict[str, Any]` as the result carrier for all 5 stages. That is a Rule-11 (type-first) regression frozen in place: the canned payload is shape-matched to a fixture by hand, with no Pydantic model gating it. B's OPEN ITEMs (§1 plan-confirm `form_values` shape, §2 the three form field sets AND the canned analysis shape) are genuinely unresolved and **block B from starting** — B itself says "BE child fills the OPEN ITEMs before FE binds forms."

### A's design (typed evidence sidecar + 2 new OriginalAction arms)
- **Pros:** Type-first (Rule 11). Closes the explicitly-deferred `result_review` typing gap. Resolves the highest-impact contract-shape decision (camelCase via `alias_generator`) that B hasn't even reached. Surgical: keeps the raw-dict path alive for the not-yet-typed stages (so it does NOT block B's tlc/analyze/fp from using dicts in the interim).
- **Cons:** Narrow — only cc/re. On its own it leaves 3 stages untyped and on fixtures, which is a *partial* contract. The two new `OriginalAction` arms add union surface (mild).

### Does adopting B make A's typed-evidence work unnecessary, necessary-but-folded-in, or orthogonal?

**Necessary-but-folded-in.** B's stub *emits the very event A types*. If B ships canned dicts and A never happens, the result wire stays untyped forever and the `result_review`-deferred TODO never closes — and B's tlc/analyze/fp canned payloads would have no typed contract, just hand-matched dicts (the exact anti-pattern Rule 11 forbids). **A is the typed-payload contract B's stub *should* emit.** Folding A in upgrades B from "canned dicts" to "typed canned evidence" — the same stub, now shape-gated by Pydantic. That is strictly better for the eventual MARS swap (the swap target is `CCResult → CcEvidence` mapper, which only exists if `CcEvidence` is a real type).

### B's OPEN ITEMs that block it (and that A partially resolves)
- **B §1 OPEN ITEM** — plan-confirm `form_values` shape for Robot/Manual selection: **A does NOT resolve this** (A doesn't touch plan authoring). Still open.
- **B §2 OPEN ITEM** — exact field sets of `TLCParamsForm`/`AnalyzeParamsForm`/`FPParamsForm`: **A does NOT resolve the param-FORM side** (A defers all three). BUT A's research (`cc-re-evidence-readiness.md`, PRD caveats) already maps the TLC reuse (`bic_shared_types.mcp_protocol.tlc` ships `TLCSpot`/`TLCPlateResult`/`TLCResult`) and the CC↔TLC `TLCResult` shim load-bearing constraint — so A's research *de-risks* B's TLC form, even though A defers building it.
- **B's implicit result-payload shape** — the canned `analysis` for cc/re: **A FULLY resolves this** (typed `CcEvidence`/`ReEvidence` + casing decision). This is the one OPEN-ITEM-adjacent surface A closes outright.

---

## 5. Verdict

**A is neither a clean subset nor a conflicting alternative — it is the typed-evidence *pilot vertical* of B's horizontal fanout, with one genuine point-contradiction (typed `result_review` vs canned dict).**

- **Subset?** Structurally close (A's `_analyze_result` typing is a 2-stage instance of B's per-stage stub), but A makes a *stronger* contract choice (typed) than B's text (canned dict). So A is a "subset-plus-upgrade," not a plain subset.
- **Conflict?** Only at the `result_review` typing decision and the FE-fixture-deletion timing. Both are reconcilable by sequencing (A first, typed; B extends the pattern to 3 more stages).
- **Orthogonal?** Largely yes for the executor-enum growth, dispatcher routing, param forms, plan-authoring UI, and Lab-bypass — A touches none of these.

**They must be reconciled, not run in parallel as-is**, because both edit `_analyze_result` and both decide the `result_review` contract — if B ships canned dicts there while A types it, the last writer silently wins and Rule 5 (don't average conflicts) / Rule 10 (contract+spec same change set) are both violated.

---

## 6. Recommended Reconciliation — Option (c): one umbrella, A re-scoped as B's typed BE-child pilot

Of the four options:
- **(a) re-scope A as B's BE-child wholesale** — too much; A would inherit B's 3 param forms + dispatcher fanout + plan-authoring, blowing past A's deliberately-narrow MVP and pulling in B's unresolved OPEN ITEMs.
- **(b) keep A narrow + B deferred** — leaves the `_analyze_result` / `result_review` contradiction unowned; when B later starts it'll either duplicate or contradict A. Rejected (defers the conflict, doesn't resolve it).
- **(c) merge into one umbrella with phased children** — RECOMMENDED. A becomes the **typed-evidence pilot child (cc/re)** that *establishes the result-payload contract pattern*; B's tlc/analyze/fp executors become **later children that REUSE A's typed evidence pattern** (each emits a typed `*Evidence`, not a hand-matched dict) plus the orthogonal executor-enum/dispatcher/forms/authoring work.
- **(d) something else** — not needed.

### Why (c) and what each option costs
- **(c) cost:** A stays small (cc/re only — no scope creep) but is *re-labeled* as B's BE-child phase-1 and adopts B's "no raw dict for stub payloads" discipline. B's contract-delta gets one correction: tlc/analyze/fp canned payloads must be **typed `*Evidence` models**, not free-form dicts (closing B §2's result-shape OPEN ITEM by extension of A's pattern). The umbrella's only new obligation is a one-line cross-reference so neither child edits `_analyze_result` blind.
- **(c) risk retired:** the `_analyze_result` double-edit collision; the untyped-canned-dict Rule-11 regression in B; the FE-fixture-deletion ordering (B can only delete tlc/analyze/fp fixtures *after* its stub executors emit typed evidence, which depends on A's pattern existing).

### Exact new scope statement for A (re-scoped, surgical)

> **Task A — "Type the CC/RE result-review evidence wire (pilot for plan-driven specialist fanout)."**
> Type the `result_review` contract end-to-end for the two stages whose Lab round-trip is already real (cc/re): add Pydantic `CcEvidence`/`ReEvidence` (camelCase via `alias_generator=to_camel` + `populate_by_name=True`, matching FE `result-stage-model.ts` byte-for-byte), carry them as a typed `evidence` sidecar on `TaskResultAnalyzedEvent` (raw-dict `analysis` path kept alive for the not-yet-typed stages), add `cc_result_review`/`re_result_review` arms to `OriginalAction` + extend `_enforce_typed_action`/`assertions.py` typed-required set to include `result_review`, emit typed STUB evidence in `_analyze_result` (Mind stays deferred, `MindNoticeEvent(phase="post")` stays — fail-loud), flip the `scenario_monitor_exp` negative result_review assertions to positive, and converge FE cc+re result cards off `result-stage-fixtures.ts` onto the wire. **This task is the contract pilot: it establishes the typed-`*Evidence` payload pattern that the sibling plan-driven-tabs task (B) will extend to tlc/analyze/fp.** TLC/Analyze/FP param forms, executor-enum growth, dispatcher fanout, plan-authoring UI, and full FE sample-layer deletion remain B's scope.

### Which of A's existing research/decisions SURVIVE (all of them)
- ✅ ADR-lite #2 (contract-first, data-stubbed) — survives unchanged; it IS B's per-stage MARS seam at evidence granularity (§3 above).
- ✅ ADR-lite #3 all 5 decisions (camelCase alias; typed `evidence` sidecar not union-on-`analysis`; FE-default card chrome; TWO arms `cc_result`/`re_result`; RE checkpoints from `params_draft["recommended"]`) — all survive; the casing+sidecar decisions are directly reusable by B's tlc/analyze/fp.
- ✅ `phase2-implementation-map.md` edit-site checklist — survives verbatim; it is the cc/re half of B's eventual 5-stage edit map.
- ✅ `cc-re-evidence-readiness.md` "blocked at source, so stub" verdict — survives; it's *why* A stubs, and the same reasoning extends to tlc/analyze/fp (also no source → also stubbed), which is precisely B's thesis.
- ⚠️ One PRD framing changes: "Deferred children #1/#2/#3 (TLC/Analyze/FP forms)" should be re-pointed from "deferred children of A" to "owned by sibling task B" — same deferral, new owner.

### Which of B's OPEN ITEMs A must resolve (and which it must NOT)
- **A MUST resolve (already has):** the result-side payload shape for cc/re — the typed `CcEvidence`/`ReEvidence` + casing. This becomes the *template* B copies for `TlcEvidence`/`AnalysisEvidence`/`FpEvidence`. (B §2 result-shape half — closed by A.)
- **A MUST NOT take on (stays B's):** B §1 plan-confirm `form_values` Robot/Manual shape; B §2 param-FORM field sets for the 3 new forms; dispatcher fanout; executor-enum growth at the 4 sites (`plan.py:53`, `form_payloads.py:361`, `specialist.py:76`, `specialist_dispatcher.py:131`); FE Robot/Manual authoring + plan-driven tabs + full sample-layer deletion.

### One correction A must hand back to B (Rule 5 — surface, don't average)
B's contract-delta §5 lists only 3 executor-literal sites; the **dispatcher routing literal at `specialist_dispatcher.py:131` (`goto: Literal["cc_subgraph","re_subgraph"]`) is a 4th site** B's "parameterized stub subgraph" must edit (or replace with a stub-subgraph map). B §4 also slightly over-states FE type work: `SpecialistStage` (`workspaceStore.ts:36`) is ALREADY the 5-way union; only the live `executor`/`Job.executor` mirrors (`events.ts:101`, `workspaceStore.ts:125`) are still `'cc'|'re'`.

---

## Caveats / Not Found

- Task B has **no `prd.md`, no `task.json`** — it is a research-only proposal (`contract-delta.md` self-labels "PROPOSED … shared source of truth for parallel BE + FE work"). It is not a started/owned task in the lifecycle sense; this asymmetry (A is a real task, B is a floating delta doc) supports folding B's BE half under A's umbrella rather than treating B as a peer task.
- The `contract-gap-claims-verification.md` referenced by A's PRD lives in **`.trellis/tasks/archive/2026-06/06-13-integrate-current-fe-be-for-cc-re-e2e/research/`** (archived), not the path the PRD cites — the link is stale but the file exists; its 13/13-confirmed claims still hold against current source (re-spot-checked: `executor` literals, `_analyze_result` deferred Mind, `result_review` outside the typed union).
- I did not independently re-verify every one of A's 13 prior claims (they were verified in the archived file); I re-verified the load-bearing ones that decide the A/B relationship: executor literals (4 sites), the cc event sequence, `_analyze_result` shape, `result_review`-outside-the-typed-union, and the FE `executor`/`SpecialistStage`/evidence-union state. All confirmed.
- I did not trace B's claimed `plan` confirm `form_values` path for Robot/Manual authoring to source — B itself flags it as an OPEN ITEM, so there is nothing to verify yet; it remains genuinely unresolved and would block B's FE child.
