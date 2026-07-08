# Research: CC's BE↔FE consistency pattern (the model to copy for the objective fix)

- **Query**: Study CC end-to-end across BE + FE. Document (a) CC's deterministic
  backstop shape, (b) the exact shared spec files that define the CC cross-layer
  contract [→ our manifest entries], (c) CC's FE pending→CTA empty-state precedent,
  (d) the concrete consistency mechanism CC used so we replicate it for the
  objective parent + 2 children.
- **Scope**: mixed (internal BE + internal FE + spec docs + prior task artifacts)
- **Date**: 2026-06-30
- **Repos**: BE `/Users/drakezhou/Development/BIC/BIC-agent-service`, FE `/Users/drakezhou/Development/BIC/BIC-agent-portal`

> TL;DR for the parent: the objective subgraph was BUILT (task 06-22) by literally
> copying CC, and the copy job is already written down in a research file
> (`cc-patterns-for-objective.md`). The objective stage *deliberately omitted* CC's
> deterministic backstop (objective.py:162-171, 254). Our fix re-adds the ONE shape
> objective needs — CC's "complete-draft promotion" (shape 1, no Mind call). The
> cross-layer contract is already a single source of truth: BE `events.md` §3.5/§3.6/§3c
> + `contracts.md` §3c-user-initiated own the wire; the FE `backend-contract.md` §2.1/§2.2
> mirrors it and cites the BE files. The FE pending→CTA precedent already ships:
> `ResultConfirmationPane.tsx:43-63`.

---

## (a) CC's deterministic backstop shape — CONFIRMED, and which shape objective mirrors

CC's post-ReAct router has **three** deterministic promotions; objective needs only **shape 1**.

### Shape 1 — complete-draft promotion (THIS is the one we mirror; NO Mind call)

`cc._post_react_route` (`app/runtime/graphs/specialists/cc.py:230-233`):

```python
if not state.last_tool_refused and state.current_phase == "collecting_params":
    draft = state.params_draft or {}
    if not cc_params_form_problems_from_values(draft):
        return "emit_form"
```

- **What makes a draft "complete"**: the SAME problems-fn the validate tool and the
  L2 confirm gate use — `cc_params_form_problems_from_values(draft)` returns an empty
  list (`app/events/form_payloads.py`, cited by `cc.py:48-50`). Empty problems ⇒ promote.
- **`last_tool_name is None` is accepted**: this branch never reads `tool_name`. It
  fires even when ZERO tools ran the turn (a prose-only turn whose draft is already
  complete) — see the docstring at `cc.py:221-229` and `graphs.md` §2.1
  (`test_post_react_route_no_tool_complete_draft_promotes_to_emit_form`). The
  downstream `_emit_form_node` tool-name guard at `cc.py:281-288` **explicitly allows
  `tool_name is None`** ("``None`` is allowed: the router promotes a prose-only turn").
- **The form event emit**: `cc._emit_form_node` (`cc.py:259-302`) reads the draft from
  `state.params_draft` (NOT `last_tool_args`), parses it as the LENIENT `CCParamsForm`
  (`cc.py:290`), wraps it in `CCParamsConfirmAction(task_id, params)` and calls
  `emit_event(runtime, FormRequestedEvent, decision_id=uuid4(), confirm_kind=ConfirmKind.PARAMS.value, original_action=...)` (`cc.py:295-301`).
- **NO Mind call on shape 1 — CONFIRMED.** Shape 1 only re-checks the local draft and
  emits the form. The only Mind-calling promotion is shape 2 (`auto_recommend`), which
  is a *separate* branch (`cc.py:238-239` → `_auto_recommend_node` at `cc.py:486-505`,
  which calls `mind.recommend_param`). Our objective fix uses shape 1, so it needs **no
  Mind call**.

### Shape 2 — `auto_recommend` (NOT mirrored): `cc.py:238-239`, calls Mind. Skip.
### Shape 3 — `auto_analyze` (NOT mirrored): `cc.py:246-249`, trial-scoped. Skip.

### Why objective is currently missing this (the bug to fix)

`objective._post_route` (`objective.py:169-171`) has the terminal-tool exit ONLY:

```python
if state.last_tool_name == TOOL_NAME_REQUEST_OBJECTIVE_CONFIRMATION and not state.last_tool_refused:
    return "emit_form"
return "narrate"
```

The omission is **deliberate and documented**: `objective.py:162-167` and `graphs.md`
§1.5a line 254 ("**No deterministic `auto_*` backstop** (Rule 2 — simplicity)") say a
backstop was skipped because the *parse→goal→confirm* ladder would need to chain TWO
Mind calls. **But that reasoning only blocks the auto_recommend-style backstop (shape 2).**
The **complete-draft promotion (shape 1) needs no Mind call** — it just re-checks
`state.objective_draft` against an objective problems-fn and promotes to `_emit_form_node`,
which already exists at `objective.py:227-291` and already emits
`FormRequestedEvent(confirm_kind=objective, original_action=ObjectiveConfirmAction)`.
So the BE child adds a shape-1 branch to `objective._post_route` mirroring `cc.py:230-233`
verbatim, gated on an objective completeness check (the objective analog of
`cc_params_form_problems_from_values`). `objective._emit_form_node` already tolerates a
prose-only promotion (it reads `state.objective_draft`, never `last_tool_args`).

---

## (b) CC's BE→FE contract — the shared spec files (THESE ARE OUR MANIFEST ENTRIES)

### What CC emits that the FE consumes

One event, three coupled facts:

1. **`FormRequestedEvent`** with `confirm_kind="params"` and a typed
   `original_action = CCParamsConfirmAction(task_id, params: CCParamsForm)`
   (`cc.py:295-301`).
2. The typed payload `CCParamsForm` / `CCParamsConfirmAction` live in
   `app/events/form_payloads.py` and are a member of the `OriginalAction` discriminated
   union (`events.md` §3.6 table, tag `"cc_params"`).
3. The **snapshot** carries it as a `pending_decisions[]` row
   `{decision_id, kind, original_action, status:'pending'}` (FE `backend-contract.md`
   §2.1 line 70). The FE confirm POSTs `{decision_id, confirm_kind, form_values}` to
   `POST /sessions/{id}/forms/confirm` (FE `backend-contract.md` §2.2 line 135).

**Objective is already wired the same way** — `ObjectiveConfirmAction` (tag `"objective"`)
is in the SAME union (`events.md` §3.6 last row, line 161) and `TYPED_ORIGINAL_ACTIONS`
(line 165). So the objective form/decision/snapshot contract is ALREADY shared — the FE
empty-state child consumes the EXISTING contract and needs no BE contract change
(matches the parent PRD line 41-46).

### WHERE the contract is written down — the single source of truth (no duplication)

The contract is **BE-authored, FE-mirrored** (not duplicated — the FE doc literally cites
the BE files). For the CC form/decision/confirm contract:

**BE (authority):**

| File | Section | What it pins |
|---|---|---|
| `BIC-agent-service/.trellis/spec/backend/L3/events.md` | §3 `FormRequestedEvent` row (line 84) · §3.5 net-new field table (line 127, `FormConfirmedEvent`) · **§3.6 `original_action` discriminated union** (lines 148-165) · §3c API-time confirm wiring (lines 195-205) | The `FormRequestedEvent` shape, `confirm_kind` literal, the typed `*ConfirmAction` union (CC + objective rows), `_enforce_typed_action`, the confirm-time event mint |
| `BIC-agent-service/.trellis/spec/backend/L3/graphs.md` | §2 / §2.2 (CC routing + `emit_form`, lines 287-357) · §1.5a (objective subgraph, lines 218-254) | The router→emit_form topology, the backstop shapes, the objective subgraph shape + the "no auto backstop" note we are amending |
| `BIC-agent-service/.trellis/spec/backend/contracts.md` | §2 entity-write boundaries (`pending_decisions` row, line 67) · **§3c** (lines 200-294) · **§3c-user-initiated** (lines 295-304) | The cross-layer confirm contract; the duo-panel "mint a decision at confirm time" rule; the CAS (`atomic_confirm`/`atomic_resolve`) that resolves the pending decision — directly relevant to the §1b dangling-decision fix |

**FE (mirror — cites the BE files):**

| File | Section | What it pins |
|---|---|---|
| `BIC-agent-portal/.trellis/spec/backend-contract.md` | §2.1 `SessionSnapshot` (`pending_decisions[]` row, line 70) · §2.2 forms/confirm (line 135-178) · §3.3 event kinds · §6 invariants (I-CONTRACT-5, line 508) | The snapshot DTO, the confirm POST body, the `confirm_kind` enum — the FE-side echo of `events.md` + `contracts.md` |
| `BIC-agent-portal/.trellis/spec/ui/L3/form.md` | full (event flow + AC-FORM-8 duo-panel, line 67 · AC-FORM-9 lock, line 68) | The FE form-confirm HITL behavior, the duo-panel CTA rule that cites `contracts.md §3c-user-initiated` |
| `BIC-agent-portal/.trellis/spec/ui/L3/workspace.md` | §"backend-owned workspace routing statuses" (lines 116-147) · P2 tab grammar (lines 82-114) | How `pending_decisions[].kind` drives tab visibility + empty states — the doc our FE empty-state child edits |

**How CC avoids BE/FE drift today**: the FE `backend-contract.md` header (FE CLAUDE.md
"Event shapes … mirror BIC-agent-service/app/events/{runtime_emitted,orch_emitted,form_payloads}.py")
and each FE spec row cite the BE authority file. There is ONE source of truth (the BE
`events.md`/`contracts.md`), and the FE doc is an explicit mirror with citations, enforced
by Rule 10 (contract change ⇒ update spec in the same change set). The cross-layer
manifests (see (d)) put the BE spec files INTO the FE task's context by absolute path, so
the implementer reads both halves before touching the contract.

---

## (c) CC's FE pending→CTA empty-state precedent — ALREADY SHIPS

The exact pattern the objective empty-state child mirrors is live in
`ResultConfirmationPane.tsx` (the `result_review` gate):

`BIC-agent-portal/src/components/workspace/ResultConfirmationPane.tsx:28-65`:

```tsx
const pendingForm = useWorkspaceStore((s) => s.pendingForm)
const isPending = pendingForm?.formKind === 'result_review'
const { confirm } = useSubmitForm(pendingForm?.decisionId)
const submitReview = (accept: boolean) => confirm('result_review', { accept })
...
<EmptyTitle>{isPending ? 'Result review pending' : 'No analysis yet'}</EmptyTitle>
<EmptyDescription>
  {isPending ? 'The review gate is open; ...' : 'The experiment result will appear here ...'}
</EmptyDescription>
{isPending && ( /* CTA buttons: Request rework / Accept result calling submitReview */ )}
```

This is the **smart empty-state**: read a pending-decision signal from the store, swap the
empty title/description, and render an inline CTA. The two panes the objective child must
upgrade are currently **dumb** empty states (no pending awareness):

- `BIC-agent-portal/src/components/workspace/MonitorPane.tsx:22-36` — flat
  `<EmptyTitle>No live execution yet</EmptyTitle>` (`data-testid="monitor-empty"`).
- `BIC-agent-portal/src/components/workspace/ResultConfirmationPane.tsx:36-67` — already
  has the `isPending` arm for `result_review`; the objective child adds an
  *objective-pending* arm above it.
- `BIC-agent-portal/src/components/workspace/ParameterDesignPanel.tsx:484-522` — the
  `no-backend-data` (line 490-499) + `Stage locked` (line 508-521) `Empty` primitives
  (Parameter-Design is **deferred** per parent PRD line 41).

The shared building block is the shadcn `Empty` primitive
(`Empty / EmptyHeader / EmptyMedia / EmptyTitle / EmptyDescription`, imported from
`@/components/ui/empty`) plus a `Button` CTA — exactly what `ResultConfirmationPane` uses.
The objective child's "confirm the objective" CTA routes to Task→Objective step (per parent
PRD AC #3) instead of POSTing a confirm; the empty-state structure is identical to the
`ResultConfirmationPane:49-63` block.

**The pending-objective store signal already exists**: the snapshot hydrates
`pending_decisions` into the workspace store, and `workspaceStore.pendingForm` /
`pendingDecisions` already carry `kind/decision_id/original_action` (see
`workspaceStore.ts`, consumed by `ResultConfirmationPane.tsx:28`,
`ParameterDesignPanel.tsx:101`,179). So the FE child reads `stage === experiment_objective`
+ the pending objective decision from existing store state — no BE change (parent PRD line 44).

---

## (d) The CONCRETE consistency mechanism CC used — and how to replicate it

CC kept BE+FE consistent with **three** mechanisms, in priority order. Replicate all three.

### Mechanism 1 (the strongest, and the literal precedent): a "copy-the-sibling" research file

The objective subgraph itself was built by EXTRACTING CC's patterns into a research file,
then mirroring them. That file is:

`BIC-agent-service/.trellis/tasks/06-22-experiment-objective-subagent/research/cc-patterns-for-objective.md`

It quotes CC verbatim with file:line headers — §1.4 `_post_react_route (cc.py:177-255, full)`,
§1.5 `_emit_form_node (cc.py:258-301, full)`, §3.2 `CCParamsConfirmAction`, §3.4 the
`OriginalAction` union "exact lines to extend". The objective code then cites it as
authority: `objective.py:6-7`, `objective_subgraph_state.py:2-4`
("Authority: … `research/cc-patterns-for-objective.md`").

**This research file (cc-consistency-pattern.md) IS the same mechanism for our fix.** Our
BE child should cite section (a) above as the verbatim shape to copy (`cc.py:230-233` +
`cc.py:281-288`); the FE child cites section (c) (`ResultConfirmationPane.tsx:43-63`).

### Mechanism 2: curated `implement.jsonl` / `check.jsonl` manifests that point each layer at the SAME contract spec files — including cross-repo by absolute path

CC tasks did NOT leave the manifests as the `_example` stub. They listed the exact contract
spec files (Rule 10). Concrete examples to copy:

**BE `06-21-specialist-prompt-slim/implement.jsonl`** (the backstop-doc task) put graphs.md +
specialist_tools.md in BOTH implement and check, with reasons tying the router backstop to
the spec:

```jsonl
{"file": ".trellis/spec/backend/L3/graphs.md", "reason": "§2.1/§2.2 document the specialist topology + system-prompt content and the _post_react_route backstops (shape 5/6/7) that make the rule cuts safe; §2.1 prompt-content description must be updated to match the slimmed block."}
{"file": ".trellis/spec/backend/L3/specialist_tools.md", "reason": "I-ST-F names the LOOP-BREAKER HARD RULE ... the slim must keep this invariant true and update I-ST-F in the same change (R5)."}
```

**The cross-layer move (THE key replication target)** — FE
`06-17-implement-experiment-objective` put **BE spec files by ABSOLUTE PATH** into the FE
manifest so the FE implementer reads the BE contract:

```jsonl
{"file": ".trellis/spec/backend-contract.md", "reason": "Portal-to-agent-service HTTP/SSE/snapshot contract; ... snapshot parity."}
{"file": ".trellis/spec/frontend/state-management.md", "reason": "Workspace store and selector patterns for replacing frontend-only objective state with backend-backed state."}
{"file": "/Users/drakezhou/Development/BIC/BIC-agent-service/.trellis/spec/backend/mind-agent-contract-call-chain.md", "reason": "Backend Agent-to-Mind ... call-chain contract."}
{"file": "/Users/drakezhou/Development/BIC/BIC-agent-service/.trellis/spec/backend/L4/persistence.md", "reason": "Backend experiment/plan/job/trial persistence shape ..."}
```

**Concrete manifest entries for OUR children** (curate these — currently both children's
manifests are the `_example` stub):

- **BE child `06-30-objective-backstop-be`** `implement.jsonl` / `check.jsonl`:
  - `.trellis/spec/backend/L3/graphs.md` — §1.5a is where we amend the "no auto backstop"
    note (line 254) to document the shape-1 complete-draft promotion.
  - `.trellis/spec/backend/L3/events.md` — §3.6 `FormRequestedEvent(objective)` row stays
    true; confirm the objective emit path is unchanged.
  - `.trellis/spec/backend/contracts.md` — §3c-user-initiated (lines 295-304) is the model
    for Part 1b: `handle_objective_confirm` must resolve the pending decision via the CAS,
    not bare `persist_event` (see §1b finding below).
- **FE child `06-30-objective-empty-states-fe`** `implement.jsonl` / `check.jsonl`:
  - `.trellis/spec/ui/L3/workspace.md` — the backend-owned routing/empty-state contract
    (lines 116-147) the new objective empty states must follow.
  - `.trellis/spec/backend-contract.md` — §2.1 snapshot `pending_decisions[]` (line 70) the
    FE reads the pending objective decision from.
  - `.trellis/spec/frontend/state-management.md` — the store/selector convention for reading
    the pending signal.
  - cross-layer (absolute path): `/Users/drakezhou/Development/BIC/BIC-agent-service/.trellis/spec/backend/L3/events.md`
    — §3.6 so the FE implementer sees the `ObjectiveConfirmAction` shape it consumes.
  - this research file:
    `/Users/drakezhou/Development/BIC/.trellis/tasks/06-30-objective-stall-fix/research/cc-consistency-pattern.md`
    — section (c) names the `ResultConfirmationPane` precedent to mirror.

### Mechanism 3: the parent PRD owns the cross-child acceptance + a cross-layer E2E

The parent PRD (`06-30-objective-stall-fix/prd.md`) already does the "parent owns the
cross-layer contract" job: it lists both children, the shared root requirement, and
cross-child acceptance criteria (lines 49-68), including a **cross-layer E2E**
(`tlc-retry-flow.spec.ts`, AC #4 line 62). This mirrors how CC consistency was proven —
the FE manifests above name "E2E fixture: workspace fixture must assert ... pending
result-review empty-state actions" (`workspace.md` line 147). Keep AC #4 as the
both-layers-green gate.

---

## Bonus finding — the §1b dangling-decision bug, confirmed at source

The parent PRD's Part 1b: `handle_objective_confirm`
(`BIC-agent-service/app/session/fast_path_handlers.py:663-751`) advances the stage but
leaves a phantom `pending` objective decision. **Confirmed**: at line 735 it calls
`self._orchestrator.persist_event(event)` (bare persist) — it never touches
`pending_decisions`. Contrast the sibling `handle_decision_accept` /
`handle_decision_reject` which call `tx.decisions.atomic_resolve(...)`
(`fast_path_handlers.py:232`, `345`) to flip the decision, and the form-confirm path which
uses `persist_event_with_decision_cas` (`contracts.md §3c`, line 293). The fix mirrors the
duo-panel pattern in `contracts.md §3c-user-initiated` (line 301): resolve the pending
objective decision in the SAME transaction that advances the stage (via the CAS), so no
phantom `pending` row survives (parent PRD AC #2, line 56).

---

## Caveats / Not found

- **Objective completeness problems-fn**: CC has `cc_params_form_problems_from_values`
  (`form_payloads.py`). I did NOT verify an equivalent `objective_*_problems_from_values`
  exists for `ObjectiveParamsForm`. The BE child must confirm/author the objective
  completeness predicate before wiring shape 1 — it is the load-bearing input to the
  promotion branch. (The lenient `ObjectiveParamsForm` is at `app/events/form_payloads.py`,
  imported by `objective.py:60-64`.)
- **Snapshot pending→store hydration for objective specifically**: I confirmed the snapshot
  DTO carries `pending_decisions[{kind, original_action, status}]` (FE `backend-contract.md`
  line 70) and that `pendingForm` is read by the panes, but did not trace whether
  `kind === 'objective'` already maps into `workspaceStore.pendingForm` or only
  `params`/`result_review`. The FE child should verify the dispatcher/snapshot-hydrate
  handles the objective kind (check `event-dispatcher.ts` + `workspaceStore.ts` +
  `session-loader.ts`); if objective is filtered out, the empty-state CTA may instead key
  off `stage === 'experiment_objective'` + `objectiveConfirmed === false` (FE-only signals
  already in the store per `workspace.md` line 68), which needs no BE change.
- The CC `06-15` result-review pilot tasks (BE
  `06-15-typed-specialist-result-review-evidence-cc-re-pilot`, FE
  `06-15-flip-cc-re-result-evidence-authority-to-be`) left their manifests as the `_example`
  stub — so the strongest curated-manifest exemplars are `06-21-specialist-prompt-slim`
  (BE) and `06-17-implement-experiment-objective` + `06-16-per-trial-...` (FE), quoted above.
