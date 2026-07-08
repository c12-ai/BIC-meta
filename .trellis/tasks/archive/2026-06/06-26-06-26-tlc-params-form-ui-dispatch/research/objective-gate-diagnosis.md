# Research: objective-gate diagnosis — why a "fully-specified TLC objective" gets clarified and no experiment is created

- **Query**: Why does the agent respond clarify/query and create NO experiment when a chemist submits a TLC objective from the portal?
- **Scope**: internal (BIC-agent-service) + live read-only probe on :8800
- **Date**: 2026-06-27

## ROOT CAUSE (one line)

**Missing-field clarify — the objective ReAct agent correctly calls `request_clarification` because the submitted reaction SMILES is malformed (a single-molecule / product-only string with no `>>`), which fails the `RxnSmiles` validator inside `parse_reaction`. NOT intent-misclassification, NOT an admittance refusal, NOT TLC-specific.** The "Query support not implemented" stub the earlier subagent saw is a SECOND, separate code path (intent classifier → query stub) that this reproduction did **not** trigger; it only fires for question-with-zero-execute-signal phrasing AND is unrelated to whether the experiment is created. The actual experiment-creation blocker is the SMILES shape.

Verified live: same imperative phrasing + a malformed SMILES → `request_clarification`, no experiment; same phrasing + a well-formed `reactants>>products` SMILES → full ladder → `experiment_created` + `form_requested`.

---

## 1. The reception → classification → routing trace (file:line + code)

A `USER_MESSAGE` turn flows: `route_entry` → (parallel) `intent_detection` + `user_admittance` → `route_after_admit` → one of {reject | query_agent | objective_subgraph | plan_subgraph | specialist_dispatcher}.

### route_entry — fan-out (no classification here)
`app/runtime/graphs/nodes/route_entry.py:60-64`
```python
if kind == TurnKind.USER_MESSAGE:
    return [
        Send(NODE_INTENT_DETECTION, state),
        Send(NODE_USER_ADMITTANCE, state),
    ]
```

### intent_detection — the ONLY Execute-vs-Query classifier (one LLM call)
`app/runtime/graphs/nodes/intent_detection.py:29-37` (system prompt) and `:93-102`:
```python
chat_model = llm.chat_model_structured.with_structured_output(_IntentDecision)
raw = await chat_model.ainvoke([...])
decision = assert_structured(raw, _IntentDecision, where="intent_detection")
intent_route = "execute" if decision.intent == "Execute" else "query"
```
Prompt (`:29-37`): "Execute = dispatch/advance/cancel an experiment ('run a CC', 'submit it')"; "Query = read info ('is it done?', 'what is the current status?')".

### user_admittance — content safety only (pass/reject); does NOT gate execute/query
`app/runtime/graphs/nodes/user_admittance.py:39-82`. Defaults to `pass` when uncertain (`:65-66`). Chemistry asks like "do CC" / "run a column" are explicitly admitted. This path is NOT the blocker.

### route_after_admit — the branch that decides create-vs-clarify-vs-query
`app/runtime/graphs/nodes/route_after_admit.py:69-95`:
```python
if state.admittance_verdict == "reject":
    goto = NODE_EMIT_ADMITTANCE_REJECT
else:
    has_in_flight = pick_in_flight_task(state) is not None
    if state.intent_route == "query" and not has_in_flight:
        goto = NODE_QUERY_AGENT                       # <-- query stub path
    elif has_in_flight:
        goto = NODE_SPECIALIST_DISPATCHER
    else:
        experiment = state.ctx.experiment
        if experiment is None or experiment.stage == ExperimentStage.EXPERIMENT_OBJECTIVE:
            goto = NODE_OBJECTIVE_SUBGRAPH           # <-- experiment-creation head
        elif experiment.stage == ExperimentStage.WORKFLOW_DESIGN:
            goto = NODE_PLAN_SUBGRAPH
        elif experiment.stage == ExperimentStage.PARAMETER_DESIGN:
            goto = NODE_SPECIALIST_DISPATCHER
        else:
            goto = NODE_OBJECTIVE_SUBGRAPH
```

So there are TWO distinct "clarify-ish" outcomes that create no experiment:
- **(P1) Query-stub path** — `intent_route == "query"` + no in-flight task → `query_agent` → emits the literal stub and returns `{}` (no experiment). `app/runtime/graphs/nodes/query_agent.py:29-36`:
  ```python
  emit_event(runtime, TextDoneEvent,
      text="Query support is not yet implemented; please rephrase as an execution request or try again later.")
  return {}
  ```
- **(P2) Objective-clarify path** — `intent_route == "execute"` (or query-with-in-flight) + no in-flight + (no experiment OR stage==experiment_objective) → `objective_subgraph`, whose ReAct agent may call `request_clarification` and never reach `request_objective_confirmation` → no experiment.

`experiment_created` is emitted in exactly ONE place: the objective subgraph's `_emit_form_node` (`app/runtime/graphs/specialists/objective.py:254-263`), reached only when the ReAct agent's last tool was `request_objective_confirmation` and was not refused (`_post_route`, `objective.py:169-171`). Any other terminal (clarification, prose, refusal) → `narrate` → no experiment.

---

## 2. What triggers "query" vs "clarify" instead of experiment creation

### (a) The query/execute classifier
`intent_detection.py:93-102` (above). A message with no clear dispatch verb that reads as a status/info question → `Query` → P1 stub. This is the source of the earlier subagent's "Query support not implemented" sighting — but it is phrasing-driven and only fires when there is no in-flight task.

### (b) The clarification trigger inside the objective agent (the real blocker here)
The objective ReAct loop is prompted to run a fixed ladder and to clarify rather than guess. `app/runtime/middleware/dynamic_prompts.py:425-448` (`collecting_objective` instructions):
```
Exit choice:
  (A) request_objective_confirmation() -- when confirm_goal succeeded ... STOP after.
  (B) request_clarification(question=...) -- when a required field
      (reaction SMILES, the baseline material + feed amount, the
      purity/yield targets) is genuinely unknown and not extractable
      from chat. Do NOT silently default. STOP after.
```

The hard gate that forces (B) for a bad SMILES lives in `parse_reaction`:
`app/runtime/graphs/specialists/tools.py:1604-1617`
```python
draft = state.objective_draft or {}
reaction_smiles = draft.get("reaction_smiles")
if not isinstance(reaction_smiles, str) or not reaction_smiles:
    return ("parse_reaction: cannot build the Mind request -- reaction_smiles is missing. ...")
try:
    parse_request = ExperimentMaterialParseRequest(rxn=reaction_smiles)
except (ValidationError, ValueError) as exc:
    return (f"parse_reaction: cannot build the Mind request -- invalid reaction_smiles: {exc}. "
            "Collect a valid reaction SMILES from the chemist (update_objective_params) and retry.")
```

`ExperimentMaterialParseRequest.rxn` is typed `RxnSmiles`, whose validator REQUIRES exactly two `>` characters:
`BIC-shared-types/bic_shared_types/common/types.py:8-20`
```python
def _validate_rxn_smiles(v: str) -> str:
    parts = v.split(">")
    if len(parts) != 3:
        raise ValueError("reaction SMILES must contain exactly two '>' characters "
                         "(format: 'reactants>agents>products' or 'reactants>>products')")
    reactants, _, products = parts
    if not reactants or not products:
        raise ValueError("reaction SMILES must have non-empty reactants and products")
    return v
```
A single-molecule SMILES (e.g. `CC(=O)Oc1ccccc1C(=O)O`, zero `>`) → `ValueError` → `parse_reaction` returns the soft "invalid reaction_smiles" string → the agent (per the prompt) calls `request_clarification` → turn ends with no experiment. This is **diagnosis (c): a real missing/invalid required field**, not intent misclassification.

---

## 3. Is it TLC-specific or general? — GENERAL (objective-stage; TLC-agnostic)

There is **no TLC-specific logic anywhere in the reception / admittance / intent / route_after_admit / objective path.** The objective subgraph collects a chemistry objective (reaction SMILES + reactant rows + purity/yield targets) and is identical regardless of which executor the later plan uses:
- The objective tool catalogue (`build_objective_tools`, `tools.py:1516-1784`) has `update_objective_params`, `parse_reaction`, `confirm_goal`, `validate_objective_params`, `request_clarification`, `request_objective_confirmation` — none mention TLC/CC/RE.
- The objective header/prompt (`dynamic_prompts.py:393-453`) is executor-agnostic ("DEFINE the objective of one purification experiment").
- TLC only appears LATER, after the objective confirms (stage → workflow_design → plan emits the fixed TLC→CC→FP→RE workflow → parameter_design where TLC params live). The TLC stage is never reached because the experiment is never created.

So the SAME malformed-SMILES failure would block a CC or RE objective identically. The earlier subagents framed it as "TLC" only because their target workflow was TLC; the gate is upstream of any executor choice. The CC/RE chained E2E specs pass because they feed `>>`-form SMILES (see §4).

---

## 4. Exact reproduction + divergence point (live read-only probe on :8800)

Three throwaway probe sessions (created, message posted, SSE replayed from `last_event_id=0`; no state mutation beyond the throwaway sessions; nothing reset):

| Probe | Message (phrasing + SMILES) | Tool sequence observed | Result |
|---|---|---|---|
| QUESTION-phrased, **bad SMILES** | "Can you run a TLC for MED005? SMILES is `CC(=O)Oc1ccccc1C(=O)O` ..." | `update_objective_params` → `parse_reaction` (invalid rxn) → **`request_clarification`** | text_done clarify; **NO experiment_created** |
| IMPERATIVE-phrased, **bad SMILES** | "Run a TLC purification for MED005. Reaction SMILES `CC(=O)Oc1ccccc1C(=O)O` ..." | `update_objective_params` → `parse_reaction` (invalid rxn) → **`request_clarification`** | text_done clarify; **NO experiment_created** |
| IMPERATIVE-phrased, **good `>>` SMILES** | "Run a TLC for this reaction: `CC(=O)OC(C)=O.OC(=O)c1ccccc1O>>CC(=O)Oc1ccccc1C(=O)O` . Baseline salicylic acid 500 mg, purity 95%, yield 80%." | `update_objective_params` → `parse_reaction` → `update_objective_params` → `confirm_goal` → `validate_objective_params` → `request_objective_confirmation` | **`experiment_created` + `form_requested`** ✅ |

**Divergence is the SMILES shape, not the phrasing.** BOTH the question- and imperative-phrased bad-SMILES probes routed to `objective_subgraph` (not the query stub) and BOTH clarified — so phrasing was NOT the determinant in this reproduction. The earlier bic-e2e-runner note ("a follow-up phrased as a question gets mis-classified as query → 'Query support not implemented'") describes path P1, a real but DIFFERENT bug that is orthogonal to experiment creation; it did not reproduce here for an objective-shaped first message.

Corroborating in-repo evidence (the passing E2E spec spells out the exact rule):
`BIC-agent-portal/tests/objective-workflow-live.spec.ts:24-30`
```
// The LLM nondeterminism is bounded by a fully-specified objective: a full
// reaction SMILES (reactants >> product) + explicit purity/yield/baseline ...
// drive the agent through update_objective_params → parse_reaction → confirm_goal →
// request_objective_confirmation ... An under-specified objective (e.g. product-only
// SMILES) makes the agent correctly call `request_clarification` instead.
```
The spec's working SMILES (`:42`): `Brc1ccccc1.OB(O)c1ccccc1>>c1ccc(-c2ccccc2)cc1` (a `>>` reaction). The CC/RE chained + task-progress specs likewise use `>>` forms. The first bic-e2e-runner run THIS session reached `plan_proposed` because it fed a well-formed reaction objective; the runs that got "clarify" fed a molecule/product-only SMILES.

---

## 5. What WOULD unblock it (diagnosis only — NO code changed)

Verdict: this is **(c) a missing/invalid required-field clarify**, and the cleanest fix is **(a) the user/E2E input** — supply a well-formed reaction SMILES.

- **(a) User-side / E2E phrasing+input fix — RECOMMENDED, zero code.** The E2E test (and any chemist) must send a reaction SMILES in `reactants>>products` (or `reactants>agents>products`) form, not a single-molecule/product-only SMILES. The agent's clarify behavior is CORRECT — it is refusing to fabricate reactants. This is the real unblock for the UI→lab TLC E2E. The passing pattern already exists: copy the SMILES style from `BIC-agent-portal/tests/objective-workflow-live.spec.ts:42`. No file in BIC-agent-service needs to change.

- **(b) Classifier-prompt change — NOT needed for this bug.** Would only address path P1 (a question-phrased follow-up hitting the query stub). If P1 is ever the blocker, the touch point is the intent prompt at `app/runtime/graphs/nodes/intent_detection.py:29-37` (broaden Execute coverage) — but the query stub itself is `app/runtime/graphs/nodes/query_agent.py:34`. Leave alone unless P1 is independently reproduced.

- **(c) Missing-field-handling change — possible but a behavior change, needs owner sign-off.** If the desire is "create the experiment even from a product-only SMILES and let the chemist fix the reaction in the form," the gate that forces clarify is `app/runtime/graphs/specialists/tools.py:1606-1617` (`parse_reaction`'s `RxnSmiles` construction) plus the prompt's exit-choice (B) at `app/runtime/middleware/dynamic_prompts.py:444-447`. Loosening this would let `request_objective_confirmation` run on an incomplete objective — counter to the deliberate "Do NOT silently default" design (the same [[project_missing_param_clarify_not_default]] principle). Do NOT do this without a product decision; the current behavior is intentional fail-loud.

- **(d) Other — N/A.** Not an admittance refusal (admittance passes chemistry asks), not a routing bug, not TLC-specific.

### Single most actionable line
The E2E/user message must carry a `>>` reaction SMILES. Reference the working input at `BIC-agent-portal/tests/objective-workflow-live.spec.ts:42` and the validator contract at `BIC-shared-types/bic_shared_types/common/types.py:8-20`. No BIC-agent-service code change is required to unblock the TLC E2E.

## Caveats / Not Found

- Live probes used a deterministic Mind stub (parse/goal-confirm are stubbed per the spec comment), so the well-formed-SMILES success reflects the stubbed Mind path, which is what the E2E exercises.
- I did NOT reproduce path P1 (query stub) for an objective-shaped first message — both bad-SMILES probes routed to the objective subgraph. P1 remains a real but separate path; if a later turn (post-objective, no in-flight) phrased purely as a question is the failing case, re-probe specifically for it.
- Probe sessions are throwaway (user `probe-diag-readonly`); no reset performed, no existing session state mutated.
