# Implement — Plan-stage prompt fix (Child C)

Product code only; PROMPT body only. Read `design.md` first. Mirror the
ExperimentObjective prompt's `NO PROSE-ONLY` + exit structure (Rule 8). No routing,
no backstop, no `tool_choice` (Drake, 2026-06-30).

## Ordered checklist

1. **Read the objective prompt (read-only)** — `dynamic_prompts.py:378-442`,
   especially the `NO PROSE-ONLY` rule (`:425-427`) and `Exit choice` block
   (`:429-436`). This is the pattern to mirror.

2. **Edit `plan_dynamic_prompt._PLAN_BODY`** (`plan_dynamic_prompt.py:37-82`): ADD a
   block (after the existing fixed-workflow + robot/manual rules, before/around the
   "you MUST end by calling request_plan_confirmation" paragraph) that says, in the
   objective prompt's voice:
   - NO PROSE-ONLY: never end the turn with prose and zero tool calls.
   - You need NOTHING from the chemist: do not ask for a reaction SMILES, structure,
     materials, or any input — the objective (incl. SMILES) was defined+confirmed
     upstream, before this stage. There is no clarification to request here.
   - Single exit: ALWAYS call `request_plan_confirmation(plan=...)`. STOP after.
   Keep the existing step/robot-manual rules intact (Rule 3).

3. **Update the L3 plan spec** (Rule 10) IF it documents the prompt exit contract —
   add the no-prose/no-ask rule. Confirm the spec file first; skip if not applicable.

4. **Tests:** if a plan-prompt unit/snapshot test exists, update it to assert the new
   block is present. If plan-prompt behavior is only observable via a live LLM turn,
   do NOT fabricate a unit test — state loud (Rule 9) that the real proof is the live
   re-run (AC5), and rely on the honest-guard spec as the detector.

## Validation commands

```bash
cd BIC-agent-service
uv run ruff check app/ && uv run ruff format --check app/
uv run pyright app/
uv run pytest -q          # existing plan tests must stay green (prompt-only change)
git diff --stat app/      # expect ONLY plan_dynamic_prompt.py (+ maybe spec)
```

## Cross-child live proof (the real AC)

Re-run the honest-guard spec (hand to the `bic-e2e-runner` agent per CLAUDE.local):
```
cd BIC-agent-portal && pnpm exec playwright test tests/honest-chain-guard.spec.ts --workers=1 --reporter=line
```
- Expected: the plan gate no longer dead-ends — "Workflow Design" renders, the chain
  advances. (Whether it then reaches GREEN depends on Child A's SSE heartbeat; a stall
  at a LATER long-wait gate is the SSE bug, not this one.)

## Review gates

- After step 2: `git diff` is prompt-only; happy-path rules unchanged.
- After step 4: `uv run pytest` green.
- Cross-child: live re-run advances past the plan gate (AC5).

## Rollback

Revert the prompt edit. Plan stage returns to the prose-abandon-possible state. No
code/routing/data change to undo.

## Dependency

This is the UNBLOCKER for the honest-guard's real SSE proof (Child B): until the plan
gate stops dead-ending, the honest spec can't reach the long robot waits where Child
A's SSE-stall freeze surfaces. Do Child C first.
