# Design — Objective form backstop + REST-confirm decision resolution (BE)

Child of `06-30-objective-stall-fix`. Research: `research/objective-decision-lifecycle-stall.md`.

## Key design correction (read first)

The objective `_post_route` docstring (`objective.py:158-167`) **deliberately
deferred** a deterministic backstop, arguing the objective ladder needs to chain
**two** Mind calls (parse → goal) vs CC's one. That reasoning applies only to the
**recommend/auto_* shape** — NOT to the **complete-draft shape**.

For the complete-draft case (our stalled session — the draft already had
reactants + `reaction_smiles` + targets), **no Mind call is needed**: the draft is
already complete, so promotion is a pure routing decision, exactly like CC shape 1
(`cc.py:230-233`). The completeness validator **already exists and is already
used** in this layer: `objective_params_form_problems_from_values`
(`form_payloads.py:626`, called at `tools.py:1715`, exported `form_payloads.py:1105`).
Confirmed by `cc-consistency-pattern.md` follow-up — it is NOT something this child
must author.

**Decision:** implement ONLY the complete-draft promotion (CC shape 1). Do NOT add
an `auto_parse`/`auto_goal` in-graph Mind chain (CC shape 2) — that is the part
the original deferral correctly flagged as complex, and our incident does not need
it. This keeps the fix surgical (Rule 2) and addresses the actual abandon shape.

## R1 — Complete-draft promotion (objective.py)

### `_post_route` (`objective.py:146-171`)
Add a complete-draft branch BEFORE the final `return "narrate"`, mirroring
`cc._post_react_route:228-231`:

```python
if state.last_tool_name == TOOL_NAME_REQUEST_OBJECTIVE_CONFIRMATION and not state.last_tool_refused:
    return "emit_form"
# Backstop (06-30): complete-but-unconfirmed objective draft + prose-only or
# non-terminal-tool ending → promote deterministically. No Mind call needed —
# the draft is already complete. Mirrors cc._post_react_route shape 1.
# Runs even when last_tool_name is None (cold prose-only turn).
if not state.last_tool_refused:
    if not objective_params_form_problems_from_values(state.objective_draft or {}):
        return "emit_form"
return "narrate"
```

- Import `objective_params_form_problems_from_values` from `form_payloads`
  (already importable — `tools.py:116` proves the path).
- **AC2 guard:** an incomplete draft yields problems → falls through to `narrate`.
  No premature form.
- Refused confirmation still falls through (unchanged).

### `_emit_form_node` (`objective.py:227-291`)
Already reads `state.objective_draft` (not `last_tool_args`) and already tolerates
a missing terminal tool structurally (it takes no args). The only hardening: drop
any implicit assumption that `last_tool_name == TOOL_NAME_...`. CC's emit node
documents `None` as an allowed router-promoted entry (`cc.py:271-277`); add the
same one-line comment here. No behavioral change to the emit body itself.

### Why this is safe
- HITL preserved: a form is emitted, the chemist still confirms it. We are not
  auto-confirming — only auto-*proposing* the form the LLM should have proposed.
- Experiment creation already lives in `_emit_form_node` (`objective.py:254-263`),
  so the promoted path still mints `ExperimentCreatedEvent` when needed.

## R2 — REST confirm resolves the dangling decision (fast_path_handlers.py)

The asymmetry: `POST /objective/confirm` → `handle_objective_confirm`
(`fast_path_handlers.py:663-751`) uses `persist_event` (no CAS) and never touches
`pending_decisions`. So a direct confirm advances `stage → workflow_design` but
leaves `pending_decisions[objective]` stuck `pending`.

### Fix
Inside the same transaction that persists `ExperimentObjectiveConfirmedEvent`,
resolve any `status='pending'` objective decision for the session. Pattern to
mirror: `handle_decision_accept` (`fast_path_handlers.py:225-260`) which calls
`atomic_resolve`.

- **Server-side lookup, not client-supplied id** (Duo-panel: FE may have no
  decision_id). Query the session's pending objective decision
  (`decisions` repo / `snapshot_repo.get_pending_by_session` filtered to
  `kind=objective`), then `atomic_resolve(decision_id, ...)` in the same tx.
- If no pending objective decision exists (pure duo-panel, agent never minted
  one), this is a no-op — stage still advances. Idempotent.
- Thread the resolution through `service.confirm_objective` (`service.py:627-673`)
  — it currently takes no decision context; resolve internally.

### Verb resolved (CC research, `cc-consistency-pattern.md` §1b + bonus)
Use **`atomic_resolve`** in the same tx as the stage advance — confirmed by the
duo-panel pattern in `contracts.md §3c-user-initiated` (line ~301) and the sibling
handlers `handle_decision_accept`/`handle_decision_reject`
(`fast_path_handlers.py:232,345`). The agent FORM_CONFIRM path uses
`persist_event_with_decision_cas`; the direct REST path mirrors the user-initiated
duo-panel CAS. No open question remains.

## R3 — Prompt hardening (dynamic_prompts.py:393-453)

Additive, defense-in-depth. Strengthen `_OBJECTIVE_HEADER` so "design a workflow /
retry" phrasing first drives the objective ladder to a form, not a prose plan:

> If the chemist describes a workflow/plan/retry but no objective is confirmed
> yet, FIRST drive the objective ladder to a confirmation form — do not narrate a
> plan.

This lowers how often the R1 backstop fires; R1 is the guarantee.

## Spec updates (Rule 10 — same change set)

- `graphs.md` §1.5a — replace the "No deterministic auto_* backstop" paragraph
  with: complete-draft promotion added (06-30), matching CC shape 1; auto_parse/
  auto_goal still intentionally absent.
- `events.md` — objective row: note the direct REST confirm now resolves the
  pending objective decision (no phantom pending after confirm).

## Data flow (after fix)

```
execute turn @ stage=experiment_objective
  └─ objective_subgraph ReAct
       ├─ LLM calls request_objective_confirmation → emit_form   (unchanged)
       └─ LLM ends prose, draft COMPLETE → _post_route promotes → emit_form  (NEW R1)
            └─ FormRequestedEvent(objective) + ExperimentCreatedEvent
chemist confirms:
  ├─ agent FORM_CONFIRM → CAS resolves decision + advances stage   (unchanged)
  └─ direct POST /objective/confirm → advances stage + RESOLVES decision (NEW R2)
```

## Test plan

- Unit (objective subgraph): prose-only complete draft → assert `_post_route`
  returns `emit_form` (AC1). Incomplete draft → `narrate` (AC2).
- Scenario (`scripts/`): direct `/objective/confirm` then snapshot → assert no
  pending objective + `stage=workflow_design` (AC3).
- E2E: re-run `tlc-retry-flow.spec.ts`, objective leg reaches form w/o nudge (AC4).

## Risks

- Over-firing R1 on a draft that *looks* complete to the values-validator but the
  chemist wanted to keep editing. Mitigation: HITL form still gates — the chemist
  edits in the FE form before confirming. Same risk CC already accepts.
