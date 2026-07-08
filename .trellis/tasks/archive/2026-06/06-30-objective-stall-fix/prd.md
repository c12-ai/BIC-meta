# PRD — Objective-stall fix (deterministic objective→plan advance + helpful empty states)

**Parent task.** Owns the source requirement set, the child map, and cross-child
acceptance. Not an implementation target itself — work lives in the two children.

## Problem

A live BIC session (`d0a99969`) is frozen at `experiment.stage =
experiment_objective`: an objective was *recommended* and a `pending_decision
{kind: objective, status: pending}` was minted, but it was **never confirmed**,
so `plans=[] jobs=[] trials=[]`. The workspace Monitor / Result / Parameter-Design
tabs are all empty as a downstream symptom.

Root cause (research-verified — see each child's `research/`):

- **(B) LLM flake (proximate):** the objective propose path emits the confirm
  form **only** if the LLM calls `request_objective_confirmation`
  (`objective.py:169-171`). There is **no deterministic backstop**, unlike the CC
  stage (`cc.py:178-233`) which promotes a complete draft to a form even with
  zero tool calls. When the LLM ends in prose, the turn produces no form, no
  confirm, and the experiment stays frozen.
- **(A) Asymmetric deterministic path:** the Duo-panel direct REST confirm
  (`POST /objective/confirm`) advances the stage but does **not** resolve the
  pending objective decision (`handle_objective_confirm` uses `persist_event`,
  not the CAS), leaving a phantom `pending` decision after the experiment moved
  on.
- **UX:** the three empty tabs give generic "nothing here yet" copy instead of
  telling the chemist to confirm the objective.

## Goal

Make the objective→plan advance **deterministic and Duo-panel-safe** (the chemist
can always progress with or without the agent), and make the workspace empty
states point the user at the pending objective instead of dead-ending.

## Scope (children)

| Child | Slug | Owns |
|---|---|---|
| BE | `06-30-objective-backstop-be` | Part 1 deterministic objective-form backstop (`objective.py`), Part 1b REST-confirm resolves the dangling decision (`fast_path_handlers.py`), Part 2 planner-prompt hardening (`dynamic_prompts.py`), + spec updates (`graphs.md`, `events.md`). |
| FE | `06-30-objective-empty-states-fe` | Part 3 pending-objective empty states + CTA for Monitor & Result (Parameter-Design deferred), reading existing store signals. |

**Ordering — BE before FE (Drake, 2026-06-30).** Although the FE consumes only
the *existing* contract (so it could run in parallel), we sequence **BE lands and
freezes the contract first, then FE implements against merged BE**. This removes
all parallel drift between the two subagents at the cost of wall-clock. The BE
child does not change the objective form/decision contract (it only adds a
deterministic path to the SAME `FormRequestedEvent(objective)`), so the freeze is
cheap — but sequencing makes "consistency" a fact, not a hope.

## Shared contract — single source of truth (both children MUST cite this)

Both subagents are built by **copying the proven CC sibling**, exactly how the
objective subgraph itself was originally built (task 06-22 copied
`cc-patterns-for-objective.md`). The consistency authority for THIS work is
`research/cc-consistency-pattern.md` — both children's manifests load it.

The objective form/decision/confirm contract is **already shared and frozen** —
the FE consumes it unchanged:

| Fact | Authority (BE-owned) | FE mirror |
|---|---|---|
| Emitted event | `FormRequestedEvent(confirm_kind="objective", original_action=ObjectiveConfirmAction)` — `events.md` §3.6 | `backend-contract.md` §2.1 |
| Snapshot row | `pending_decisions[]{decision_id, kind:"objective", original_action, status}` — `contracts.md` §2 | `backend-contract.md` §2.1 (line ~70) |
| Confirm POST | `POST /sessions/{id}/forms/confirm` (agent) / `POST /objective/confirm` (duo-panel) — `contracts.md` §3c / §3c-user-initiated | `form.md` AC-FORM-8 |
| Stall signal | `experiment.stage == 'experiment_objective'` (NOT `status` — see out-of-scope) | `workspaceStore.stage` |
| Completeness predicate | `objective_params_form_problems_from_values` (`form_payloads.py:626`, already used `tools.py:1715`) | n/a (BE-only) |

**Rule for both children:** do not redefine any row above. BE may only *add a
deterministic path* to the existing emit; FE may only *read* the existing signals.
Any change to a row is a contract change → update the BE authority spec in the
same change set (Rule 10) and re-sync the FE mirror.

## Consistency mechanisms (all four, per Drake)

1. **Copy-the-sibling research** — `research/cc-consistency-pattern.md` is the
   single authority both children cite (BE §(a) for the backstop shape, FE §(c)
   for the CTA precedent). Mirrors how CC built objective originally.
2. **Curated manifests** — both children's `implement.jsonl`/`check.jsonl` point
   at the SAME contract spec files; the FE manifest pulls the BE `events.md` by
   absolute path so the FE implementer reads the BE authority (CC 06-17 precedent).
3. **Cross-child acceptance + cross-layer E2E** — `tlc-retry-flow.spec.ts`
   (AC #4) is the both-layers-green gate; divergence fails a test, not just review.
4. **Sequencing** — BE freezes the contract before FE starts (see Ordering above).

## Cross-child acceptance criteria

1. A session whose objective draft is **complete** but where the LLM does **not**
   call `request_objective_confirmation` still ends the turn with a
   `FormRequestedEvent(objective)` (deterministic backstop). Verified by a BE
   scenario/unit test that drives the objective subgraph with a prose-only,
   complete-draft turn and asserts a form is emitted.
2. After a direct `POST /objective/confirm`, the snapshot shows **no** lingering
   `pending_decisions[kind=objective, status=pending]` — the decision is resolved
   in the same transaction that advances the stage.
3. At `stage = experiment_objective`, the Monitor and Result tabs render a
   "confirm the objective" empty state with a CTA that routes to Task → Objective
   step (no duplicated objective form). Verified by an FE Playwright/fixture test.
4. The existing E2E `tlc-retry-flow.spec.ts` passes **without** relying on the
   chemistry-nudge LLM workaround for the objective leg (the deterministic
   backstop covers the abandon shape). Re-run to confirm the group-C flake is
   gone.
5. Spec updated in the same change set (Rule 10): `graphs.md` §1.5a and
   `events.md` objective row reflect the new deterministic backstop; no
   code↔spec drift.

## Out of scope (flagged, not fixed here)

- **`experiments.status` never advances past `recommended`.** Research found no
  writer that flips it. This is a separate latent bug; track independently. Do
  NOT use `status` as a stall signal anywhere in this work — `stage` is the
  authority.
- Broader planner-flake hardening beyond the objective leg.

## Resolved during planning (CC-consistency research)

- `atomic_resolve` (not `atomic_confirm`) is the confirmed verb for the duo-panel
  REST confirm — `contracts.md §3c-user-initiated`.
- The objective completeness predicate already exists
  (`objective_params_form_problems_from_values`, `form_payloads.py:626`) — not
  something the BE child must author.
- The objective form/decision contract is already shared & frozen — the FE child
  needs no BE contract change.

## Open questions for Drake

- Confirm `experiments.status` non-advance is out of scope for this task (track
  as a separate ticket) — assumed yes.
