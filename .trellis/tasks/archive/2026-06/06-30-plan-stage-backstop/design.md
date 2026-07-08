# Design — Plan-stage prompt fix, ExperimentObjective pattern (Child C)

Read `prd.md` first. Product code only. Keep the plan stage a simple LLM + ReAct/tools
call. **No deterministic backstop, no `tool_choice` forcing** (Drake, 2026-06-30).
Fix the PROMPT, following the ExperimentObjective pattern.

## Why the plan turn dead-ends (root cause in the prompt)

`plan_dynamic_prompt._PLAN_BODY` (`plan_dynamic_prompt.py:37-82`) says "always output 4
steps" and "you MUST end by calling `request_plan_confirmation`" — but it NEVER tells
the model that it needs **nothing** from the chemist to do so, and never forbids the
zero-tool prose turn. So when the user prompt lacks a reaction SMILES, the model
"helpfully" asks for one (a clarification the plan stage does not need — SMILES is
already confirmed upstream at the objective stage). The prompt does not close that door.

## The ExperimentObjective pattern to follow

`dynamic_prompts.py` objective prompt has TWO things the plan prompt lacks:

1. **An explicit `NO PROSE-ONLY` rule** (`:425-427`):
   > "never end this turn with prose and ZERO tool calls — start the ladder ... or ask
   > the chemist (request_clarification)."
   Every outcome is channeled into a tool call. The prose dead-end is explicitly banned.

2. **An explicit two-exit `Exit choice` block** (`:429-436`): (A) terminal confirmation
   tool when ready, (B) `request_clarification` ONLY when a required field is *genuinely
   unknown and not extractable from chat* — "Do NOT silently default."

## Applying it to plan (where the exits collapse)

The plan stage is simpler than objective: the steps are FIXED and it needs NO chemist
input to draft them (no SMILES, no materials, no targets — all upstream). So the
two-exit pattern collapses to effectively ONE exit:

- **(A) `request_plan_confirmation(plan=...)`** — ALWAYS the exit. The plan can always
  be drafted (4 fixed steps; robot/manual defaults to all-robot). There is no
  legitimate "required field unknown" case at this stage.
- There is **no exit (B)**: the plan stage must NOT ask the chemist for anything
  (no SMILES, no structure, no materials). That's the whole bug.

So the plan prompt gains an objective-style block, specialized:

```
NO PROSE-ONLY: never end this turn with prose and ZERO tool calls. You need
NOTHING further from the chemist to draft this plan — the steps are fixed and
the reaction objective (SMILES, materials, targets) was already defined and
confirmed at the objective stage, BEFORE this stage runs. Do NOT ask the
chemist for a reaction SMILES, structure, materials, or any other input. There
is no clarification to request here.

Exit: ALWAYS end by calling request_plan_confirmation(plan=...) with the fixed
4-step plan. That is the only valid way to end this turn. STOP after.
```

(Exact wording finalized at impl time; match the objective prompt's voice/format for
conformance — Rule 8.)

## Why this is the right fix (not a backstop)

- Stays a real LLM + ReAct/tools turn — the model still drafts the plan and makes the
  robot/manual call. We only remove the *reason* it abandons (Drake's ask).
- Mirrors a proven in-repo pattern (ExperimentObjective `NO PROSE-ONLY` + explicit
  exits) — Rule 8 conformance, not a new mechanism.
- Smallest possible change: one prompt body, no routing change, no new node, no
  `_emit_form_node` risk (the `:285` ValueError can't be hit because we don't touch the
  emit path — the tool still fires normally).

## What this does NOT touch

- `_post_react_route` / routing — unchanged (no backstop).
- `_emit_form_node` — unchanged.
- Tool bindings / `tool_choice` — unchanged (no provider-level forcing).
- The fixed-workflow rules already in `_PLAN_BODY` — kept; we ADD the no-prose/no-ask
  block, we don't rewrite the existing step rules.

## Residual risk (honest, Rule 9)

A prompt fix is **probabilistic**, not a hard guarantee — an LLM can still, rarely,
ignore an explicit instruction. That is the tradeoff Drake chose (keep it a simple LLM
call) vs. a deterministic backstop (hard guarantee but bypasses the LLM). If live
traces later show the prose turn still recurs at a meaningful rate, revisit with Drake
— do NOT unilaterally add a backstop. The honest-guard spec (Child B) is the detector
that would surface a recurrence.

## Spec impact (Rule 10)

Prompt wording change; no wire-contract change. If the L3 plan spec documents the plan
prompt's exit contract, update it to include the no-prose/no-ask rule. Confirm at impl.
