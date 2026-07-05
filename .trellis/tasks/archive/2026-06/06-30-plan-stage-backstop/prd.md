# Plan-stage prompt fix (stop spurious SMILES ask)

Parent: `06-30-sse-heartbeat-honest-guard`. **Child C — the second cure** (plan
reliability). Product code only; separate from the SSE + test work.

> **Approach decided by Drake (2026-06-30): prompt fix, NOT a deterministic backstop.**
> Keep the plan stage a simple LLM + ReAct/tools call. Do NOT add a code path that
> synthesizes the plan and bypasses the LLM's decision, and do NOT force `tool_choice`.
> Instead, fix the PROMPT so the model reliably calls `request_plan_confirmation`
> instead of asking for input it doesn't need. Root-cause, minimal, stays ReAct+tools.
> (See memory `feedback_planagent_keep_llm_simple`.)

## Goal

When the plan-stage LLM ends its turn with **prose and zero tool calls** (abandon
shape 6) instead of calling `request_plan_confirmation`, the turn dead-ends: the
chemist sees a spurious clarification (observed: a request for the reaction SMILES)
and no `plan_proposed` / plan form is ever emitted. **Fix the plan prompt** so the
model understands it needs nothing further from the chemist and reliably emits the
fixed plan via the terminal tool.

## Root cause (verified)

- The plan is a **FIXED 4-step workflow** TLC→CC→FP→RE; the LLM only picks robot vs
  manual (`plan_dynamic_prompt.py:37-82`, `plan.py:42-60`). It does NOT choose steps.
- SMILES is **not** needed at plan stage — plan is only reachable at
  `stage==workflow_design`, AFTER the objective (with SMILES) is confirmed
  (`plan_subgraph.py:268-305`). So the SMILES request is **spurious**.
- `objective._post_route` (`objective.py:173-186`) and `cc._post_react_route`
  (cc.py:230-233) auto-promote a complete draft to `emit_form` on a prose/no-tool
  ending. **`plan_subgraph._post_react_route` (`plan_subgraph.py:137-152`) does NOT** —
  it only routes `tool→emit_form`, else `narrate`. That asymmetry is the bug.

## The fix: mirror ExperimentObjective's prompt contract

The objective prompt (`dynamic_prompts.py:414-437`) has two things the plan prompt
lacks: a **`NO PROSE-ONLY`** rule (never end with prose + zero tool calls) and an
explicit **exit-choice** block. The plan prompt has neither, so the model is free to
end with a prose SMILES request. The fix adds the objective-style block to the plan
prompt — specialized to the plan's reality: the plan needs NOTHING from the chemist
(steps fixed, SMILES already confirmed upstream), so the only valid exit is
`request_plan_confirmation`; there is no clarification to ask.

This keeps the plan stage a real LLM + ReAct/tools call (Drake's ask) and changes ONLY
the prompt — no routing change, no backstop, no `tool_choice`, no `_emit_form_node`
risk.

## Requirements

- **R1** Add a `NO PROSE-ONLY` instruction to `plan_dynamic_prompt._PLAN_BODY`:
  the model must never end the turn with prose and zero tool calls.
- **R2** Add an explicit instruction that the plan stage needs NOTHING from the
  chemist — never ask for a reaction SMILES, structure, materials, or any input; the
  objective (incl. SMILES) was already defined+confirmed upstream. There is no
  clarification exit at this stage.
- **R3** State the single exit: ALWAYS end by calling `request_plan_confirmation`.
- **R4** Match the objective prompt's voice/format for conformance (Rule 8). Keep the
  existing fixed-workflow + robot/manual rules in `_PLAN_BODY`; ADD the block, don't
  rewrite them.
- **R5** No routing / node / tool-binding changes. Prompt only.

## Acceptance Criteria

- [ ] **AC1** With the prompt fix, a chained CC+RE prompt that omits a SMILES no longer
      produces a prose SMILES-request turn — the model calls `request_plan_confirmation`
      and `plan_proposed` + `form_requested(plan)` are emitted.
- [ ] **AC2** The happy path (model already calls the tool) is unchanged.
- [ ] **AC3** Only the prompt body changed — no diff in routing, nodes, or tool
      bindings (Rule 3 surgical).
- [ ] **AC4** BE pytest green. Add/adjust a prompt-level test if one exists for plan
      prompts (Rule 7: the WHY is "the plan stage must never ask the chemist for input
      it already has"). If plan-prompt behavior is only observable via live LLM, note
      that the real proof is AC6 and say so loud (Rule 9) rather than faking a unit test.
- [ ] **AC5** Re-running `honest-chain-guard.spec.ts` no longer dead-ends at the plan
      gate (it then proceeds toward its real SSE-stall target).

## Constraints

- Product code only; prompt body only. No routing/backstop/tool_choice changes.
- Read the objective prompt (`dynamic_prompts.py:378-442`) before editing (Rule 6);
  mirror its `NO PROSE-ONLY` + exit structure (Rule 8).
- Residual risk (Rule 9): a prompt fix is probabilistic, not a hard guarantee. Drake
  chose this over a deterministic backstop. If the prose turn recurs at a meaningful
  rate in live traces, revisit with Drake — do NOT unilaterally add a backstop.
- If the L3 plan spec documents the prompt's exit contract, update it (Rule 10).

## Dependency / ordering

This is the **blocker for the honest-guard's real proof** (Child B / 06-30-fe-honest-
guard): until the plan gate stops dead-ending, the honest spec can't reach the long
robot waits where the SSE-stall freeze (Child A) actually surfaces. Implement before
re-running the honest spec for its red/green SSE proof.
