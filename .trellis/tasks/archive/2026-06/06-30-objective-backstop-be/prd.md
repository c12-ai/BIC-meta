# PRD — Deterministic objective form backstop + planner-prompt hardening (BE)

Child of `06-30-objective-stall-fix`. See parent `prd.md` for the full incident.

## Goal

Make the objective leg advance deterministically so a session can never freeze at
`stage = experiment_objective` with a complete-but-unconfirmed objective. Two
defects, one prompt mitigation.

## Requirements

### R1 — Deterministic objective-form backstop (load-bearing)
When the objective draft is **complete** (reactants + `reaction_smiles` + targets
present; `confirm_goal` satisfied) and the confirmation tool was **not refused**,
the objective subgraph MUST emit `FormRequestedEvent(objective)` even if the LLM
ended the turn without calling `request_objective_confirmation` (including
`last_tool_name is None`). Mirror the existing CC complete-draft promotion
(`cc.py:_post_react_route` 178-233 / `_emit_form_node` 259-277).
- Chokepoint: `app/runtime/graphs/specialists/objective.py:146-171` (`_post_route`)
  + `:227-291` (`_emit_form_node` accept router-promoted path).
- An incomplete draft MUST still fall through to `narrate` (no premature form).

### R2 — Direct REST confirm resolves the dangling decision
`POST /objective/confirm` MUST resolve any `status='pending'` objective decision
for the session in the **same transaction** that advances the stage, so the
snapshot never shows a phantom pending objective after confirm.
- Chokepoint: `app/session/fast_path_handlers.py:663-751`
  (`handle_objective_confirm`) — currently uses `persist_event` (no CAS). Resolve
  server-side by querying the session's pending objective decision (do NOT trust a
  client-supplied id — Duo-panel: the FE may not have one). Mirror
  `handle_decision_accept` (`fast_path_handlers.py:225-260`) `atomic_resolve`.
- Thread the resolution through `service.confirm_objective` (`service.py:627-673`).

### R3 — Planner-prompt hardening (mitigation, not the guarantee)
Strengthen the objective-leg prompt so "design a workflow / retry" phrasing first
drives the objective ladder to a form instead of narrating a plan in prose.
- Chokepoint: `app/runtime/middleware/dynamic_prompts.py:393-453`
  (`_OBJECTIVE_HEADER` + `_OBJECTIVE_PHASE_INSTRUCTIONS`).

## Acceptance Criteria

- [ ] AC1: A prose-only, complete-draft objective turn emits
  `FormRequestedEvent(objective)`. Unit/scenario test on the objective subgraph.
- [ ] AC2: An incomplete-draft prose-only turn does NOT emit a form (still
  `narrate`). Regression guard so R1 doesn't over-fire.
- [ ] AC3: After `POST /objective/confirm`, `get_pending_by_session` returns no
  pending objective decision AND `stage == workflow_design`. Scenario test.
- [ ] AC4: `tlc-retry-flow.spec.ts` objective leg reaches a confirmable form
  without the chemistry-nudge LLM workaround.
- [ ] AC5: Specs updated same change set — `graphs.md` §1.5a (drop "No
  deterministic backstop"; document the complete-draft promotion) and `events.md`
  objective row. No code↔spec drift (Rule 10).

## Constraints

- Surgical (Rule 3): touch only the objective subgraph, the objective REST
  handler/service, the objective prompt, and the two specs. Do NOT refactor the
  CC path being mirrored.
- Do NOT touch `experiments.status` (parent out-of-scope).
- No new backward-compat shims unless Drake asks (global rule).

## Consistency (Drake — maintain BE↔FE)

- **Copy the CC sibling, do not invent.** Authority:
  `../06-30-objective-stall-fix/research/cc-consistency-pattern.md` §(a) — the
  exact shape to mirror is `cc.py:230-233` (complete-draft promotion, NO Mind
  call) + `cc.py:281-288` (`tool_name=None` allowed). The completeness predicate
  already exists: `objective_params_form_problems_from_values`
  (`form_payloads.py:626`, used at `tools.py:1715`) — do NOT author a new one.
- **Do not change the objective form/decision contract.** R1 only adds a
  deterministic path to the SAME `FormRequestedEvent(objective)` the FE already
  consumes (parent PRD "Shared contract" table). Only R2 touches the confirm
  handler, and only to resolve the decision — the emitted shape is unchanged.
- **This child lands FIRST** and freezes the contract before the FE child starts
  (parent PRD Ordering). Surface any unavoidable contract change immediately —
  the FE child is built against merged BE.

## Research

- `research/objective-decision-lifecycle-stall.md` — full mint→resolve→advance
  trace with file:line for every chokepoint; verdict (C) BOTH.
- `../06-30-objective-stall-fix/research/cc-consistency-pattern.md` — the CC
  consistency authority shared with the FE child.
