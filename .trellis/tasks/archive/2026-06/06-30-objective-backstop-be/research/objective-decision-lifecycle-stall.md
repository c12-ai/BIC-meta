# Research: Objective decision lifecycle stall (session d0a99969)

- **Query**: Why is a BIC session stuck with experiment `recommended` / stage `experiment_objective`, a pending OBJECTIVE decision, and empty plans/jobs/trials? Where is the objective decision minted vs resolved, what triggers confirmation, why does the flow stall, and where would a fix go?
- **Scope**: internal (BIC-agent-service)
- **Date**: 2026-06-30
- **Verdict**: **(C) BOTH** — a pure-LLM-flake propose path (no deterministic objective→form backstop) AND a deterministic-confirm path that does NOT clean up the dangling pending decision. See §Verdict.

---

## TL;DR for the four questions

1. **Objective decision MINTED** at `app/runtime/graphs/specialists/objective.py:275-281` (`FormRequestedEvent(confirm_kind="objective")`); its `apply` INSERTs the `pending_decisions` row (`app/events/runtime_emitted.py` `FormRequestedEvent.apply`). **RESOLVED** only on a `FORM_CONFIRM(objective)` turn via CAS at `app/session/orchestrator.py:426` (`atomic_confirm`). The stage advance (`experiment_objective → workflow_design`) is owned by `ExperimentObjectiveConfirmedEvent.apply` at `app/events/bypass_emitted.py:128-140`.
2. **Trigger** is BOTH (a) a user action AND (c) a deterministic backend mint — there are TWO confirm paths (see §2). `experiments.status='recommended'` is the INSERT default and is NEVER advanced — it is **not** the stuck signal.
3. **Stall cause**: the objective propose path has **NO deterministic backstop** (unlike CC). The form is emitted ONLY if the LLM calls `request_objective_confirmation` (`objective.py:169-171`). If the LLM ends in narrate, the turn produces no form, no decision — the experiment never gets created or stays at `experiment_objective` with a stale dangling decision. See §3.
4. **Fix chokepoints**: (a) `objective.py:_post_route` (146-171) needs a complete-draft promotion mirroring `cc.py:_post_react_route` (178-233); (b) the direct REST confirm `fast_path_handlers.py:handle_objective_confirm` (663-751) must resolve any pending objective decision. See §4.

---

## Findings

### Files Found

| File Path | Role |
|---|---|
| `app/runtime/graphs/specialists/objective.py` | Objective subgraph — mints the objective FormRequestedEvent (propose) + acks (confirm). The stall lives here. |
| `app/runtime/graphs/nodes/route_after_admit.py` | Stage gate: routes execute turns to `objective_subgraph` while stage==`experiment_objective` (lines 78-95). |
| `app/runtime/middleware/dynamic_prompts.py` | `_OBJECTIVE_HEADER` (393-423) + `_OBJECTIVE_PHASE_INSTRUCTIONS` (425-453) — the planner prompt for the objective leg. |
| `app/session/service.py` | `submit_form_confirm` (the agent confirm path) + `_build_confirmed_event` / `_build_objective_confirmed_event` (387-531) + `confirm_objective` facade (627-673). |
| `app/session/fast_path_handlers.py` | `handle_objective_confirm` (663-751) — the DIRECT REST confirm path; does NOT touch pending_decisions. |
| `app/session/orchestrator.py` | `persist_event` (359-378, no CAS) vs `persist_event_with_decision_cas` (380-435, resolves the decision). |
| `app/events/bypass_emitted.py` | `ExperimentObjectiveConfirmedEvent` (101-140) — the stage-advancing event; `apply` writes objective/name/stage. |
| `app/events/runtime_emitted.py` | `FormRequestedEvent.apply` (INSERT pending_decisions) + `ExperimentCreatedEvent.apply` (INSERT experiments). |
| `app/repositories/experiments_repo.py` | `status` server-default `'recommended'` (50, 123); `_UPDATABLE_FIELDS` = {name,status,objective,stage,started_at} (33). |
| `app/repositories/snapshot_repo.py` | `get_pending_by_session` filters `status='pending'` only (15, 104). |
| `app/core/enums.py` | `ExperimentStage` (96-108): experiment_objective → workflow_design → parameter_design. |
| `app/api/routers/sessions.py` | `confirm_objective` route (378) → `POST /objective/confirm`. |
| `BIC-agent-portal/tests/tlc-retry-flow.spec.ts` | The failing E2E — proves the recovery contract (nudge → deterministic REST confirm), lines 132-227. |

---

### (1) Objective decision lifecycle — mint → resolve → stage/status advance

**MINT (where the pending OBJECTIVE decision comes from):**

- `app/runtime/graphs/specialists/objective.py:275-281` — `_emit_form_node` emits
  `FormRequestedEvent(decision_id=uuid4(), confirm_kind=ConfirmKind.OBJECTIVE.value, original_action=ObjectiveConfirmAction(...))`.
- `FormRequestedEvent.apply` (L2, `app/events/runtime_emitted.py`) INSERTs the `pending_decisions` row (`decision_id` / `confirm_kind='objective'` / `status='pending'` / `original_action` JSONB / `expires_at`). This is the `pending_decisions[0]{kind:"objective", status:"pending"}` seen in the snapshot.
- Same node, `objective.py:254-263` — when `ctx.experiment is None` it ALSO mints `experiment_id` and emits `ExperimentCreatedEvent`, whose `apply` INSERTs the `experiments` row with `status='recommended'` (the server default) and `stage='experiment_objective'`. This is `experiments[0]{status:"recommended", stage:"experiment_objective"}` in the snapshot.

**RESOLVE (where the pending decision is supposed to flip to confirmed):**

- ONLY on a `FORM_CONFIRM(objective)` turn. `app/session/service.py:submit_form_confirm` (200-304) → `persist_event_with_decision_cas` (`app/session/orchestrator.py:380-435`) → `tx.decisions.atomic_confirm(...)` at **`orchestrator.py:426`** (CAS on `status='pending'`, kind match). This is the ONLY writer that flips `pending_decisions.status='pending' → 'confirmed'` for the objective channel (spec `events.md` §3.2: "*ConfirmedEvent.apply does not write to pending_decisions; the CAS owns the flip").

**STAGE advance (`experiment_objective → workflow_design`):**

- `app/events/bypass_emitted.py:128-140` — `ExperimentObjectiveConfirmedEvent.apply`. Writes `objective`/`name` always; writes `stage='workflow_design'` ONLY when `experiment.stage == 'experiment_objective'` (idempotent / no-backward, line 138-139).
- The `route_after_admit` stage gate (`route_after_admit.py:88-95`) reads this stage on the NEXT execute turn: `experiment_objective` → objective_subgraph; `workflow_design` → plan_subgraph; `parameter_design` → specialist_dispatcher.

**STATUS advance (`recommended → ?`):** **NONE.** `experiments.status` is the INSERT default `'recommended'` (`experiments_repo.py:50,123`) and is NEVER advanced by any event apply (no `status` write in `ExperimentObjectiveConfirmedEvent.apply`, `PlanProposedEvent.apply`, or `PlanConfirmedEvent.apply`). It is in `_UPDATABLE_FIELDS` but no code path writes it. **CONCLUSION: `status='recommended'` is a permanent label, NOT a stuck signal.** The real stuck signal is `stage='experiment_objective'` + a dangling pending objective decision.

---

### (2) What triggers objective confirmation — (a) AND (c), per Duo-panel

There are TWO confirm paths that BOTH mint the SAME stage-advancing `ExperimentObjectiveConfirmedEvent`:

| Path | Trigger | Entry | Resolves pending decision? | Advances stage? |
|---|---|---|---|---|
| **Agent FORM_CONFIRM** | FE `POST /sessions/{id}/forms/confirm` with `confirm_kind=objective` (after the agent fired `FormRequestedEvent`) | `service.submit_form_confirm` → `_build_objective_confirmed_event` (`service.py:479-531`) → `persist_event_with_decision_cas` | **YES** — `atomic_confirm` at `orchestrator.py:426` | YES (via `ExperimentObjectiveConfirmedEvent.apply`) |
| **Direct duo-panel REST** | FE `POST /sessions/{id}/objective/confirm` (workspace form, no agent needed) | route `sessions.py:378` → `service.confirm_objective` (627-673) → `fast_path_handlers.handle_objective_confirm` (663-751) | **NO** — uses `persist_event` (`orchestrator.py:359`), which has NO `atomic_confirm` / `atomic_resolve`; never touches `pending_decisions` | YES (same `ExperimentObjectiveConfirmedEvent.apply`) |

The direct REST path is the **Duo-panel escape hatch** — the chemist confirms the objective from the workspace WITHOUT the agent (`http-routes.md` line 27; `dynamic` prompt does not gate it). The E2E spec exercises exactly this fallback at `tlc-retry-flow.spec.ts:203-223` (when the live form is missed, POST `/objective/confirm` directly and assert `stage==workflow_design`).

**Asymmetry bug (load-bearing for this incident):** the direct path advances the stage but leaves the pending objective decision at `status='pending'`. `service.confirm_objective` (`service.py:627-673`) takes no `decision_id` and the handler never resolves a decision. So a session where the agent DID mint the objective decision, then the chemist confirmed via the workspace REST path, ends with `stage=workflow_design` BUT a still-`pending` objective decision in the snapshot. (In the observed snapshot the stage is still `experiment_objective`, so this particular session never reached confirm at all — see §3 — but this asymmetry is a real second defect to fix per Q4b.)

---

### (3) WHY the flow stalls here — no deterministic objective→form backstop

The stall is in the objective PROPOSE path. Trace `app/runtime/graphs/specialists/objective.py`:

- The objective form is emitted ONLY from `_emit_form_node` (227-291), reached ONLY when `_post_route` returns `"emit_form"`.
- `_post_route` (146-171) returns `"emit_form"` **only if** `state.last_tool_name == TOOL_NAME_REQUEST_OBJECTIVE_CONFIRMATION and not state.last_tool_refused`. Otherwise → `"narrate"` (a text-only reply, END, no form, no decision).
- The subgraph docstring (162-167) and spec `graphs.md` §1.5a ("**No deterministic auto_* backstop**") confirm this is intentional MVP simplicity: "the prompt-level rules + the terminal-tool gate cover the abandon shapes for MVP; add a backstop later only if live traces show the LLM abandoning the ladder."

**This is the LLM-flake vector.** If the planner LLM:
- ends the ReAct loop with prose instead of calling `request_objective_confirmation`, OR
- mis-orders the ladder (`parse_reaction → confirm_goal → request_objective_confirmation`) and gives up, OR
- mis-reads the `objective-confirmation form emitted` ToolMessage as a new user request and re-deliberates (the same Qwen `enable_thinking` loop the plan subgraph guards against — `graphs.md` §1.5 gotcha) and then abandons,

then the turn ends in `narrate` with NO `FormRequestedEvent`. Result: either no experiment row at all, or (if a prior turn minted the experiment + decision but a later turn was supposed to re-emit and didn't) the experiment stays at `stage=experiment_objective` with a stale pending decision and no plan/jobs/trials downstream — exactly the snapshot.

**Contrast — CC has the backstop the objective lacks.** `app/runtime/graphs/specialists/cc.py:_post_react_route` (178-233) deterministically promotes ANY non-refused `collecting_params` turn whose draft is COMPLETE to `emit_form`, **even when zero tools ran** (213-233; `last_tool_name is None` accepted). The objective `_post_route` has no such promotion — a complete objective draft with a prose-only ending falls through to `narrate` and the workspace stays empty. This is the single structural gap.

**Prompt is the only guard today** (`dynamic_prompts.py:436-447`): `_OBJECTIVE_PHASE_INSTRUCTIONS["collecting_objective"]` carries a `NO PROSE-ONLY` rule and an `Exit choice (A) request_objective_confirmation` instruction. The E2E's "chemistry nudge" (`tlc-retry-flow.spec.ts:143-154`) is a workaround that re-prompts the LLM to "open the objective confirmation form" — it works only when the LLM complies, which is exactly the flake. Bare nudges get admittance-rejected as off_topic (spec comment line 140-141), so the nudge must carry chemistry — fragile.

The stage gate (`route_after_admit.py:88`) keeps routing every execute turn back into `objective_subgraph` until confirm, so re-prompting CAN recover — but only via a flaky LLM tool call, which violates the Duo-panel principle (user should be able to proceed without the agent). The deterministic escape is the direct REST confirm (§2), which the FE falls back to.

---

### (4) Fix chokepoints (FILE:LINE)

**(4a) Make objective→form deterministic / not LLM-dependent (the primary fix — Duo-panel + LLM-flake):**

- **`app/runtime/graphs/specialists/objective.py:146-171`** (`_post_route`) — add a complete-draft promotion mirroring `cc.py:_post_react_route` (178-233): when `state.objective_draft` parses as a COMPLETE `ObjectiveParamsForm` (and `confirm_goal` ran / values present) and the confirmation tool was NOT refused, return `"emit_form"` even when `last_tool_name` is not the terminal tool (including `None`). This converts a prose-only-but-complete objective turn into a form emit, exactly as CC does.
- **`app/runtime/graphs/specialists/objective.py:227-291`** (`_emit_form_node`) — relax the implicit assumption that the terminal tool ran; CC's `_emit_form_node` (`cc.py:259-277`) already accepts `last_tool_name is None` for the router-promoted path. Mirror that here.
- Spec to update in the same change set (Rule 10): `graphs.md` §1.5a ("No deterministic auto_* backstop" paragraph) and `events.md` §4.1 objective row.

NOTE: the deterministic REST confirm (`/objective/confirm`) ALREADY gives the user a non-LLM path to advance the stage. So the minimal Duo-panel fix is arguably already in place at the stage level; (4a) is about making the AGENT-driven form appear deterministically so the chemist gets the rich workspace form instead of having to hand-fill the REST payload.

**(4b) Resolve the dangling pending decision on the direct REST confirm (the asymmetry bug from §2):**

- **`app/session/fast_path_handlers.py:663-751`** (`handle_objective_confirm`) — it uses `persist_event` (no CAS) and never resolves the pending objective decision. Add a `decisions.atomic_resolve` / best-effort confirm for any `status='pending'` objective decision in this session inside the same tx (mirror how `handle_decision_accept` at `fast_path_handlers.py:225-260` calls `atomic_resolve`). Today a direct confirm advances the stage but leaves `pending_decisions[kind=objective]` stuck `pending`, so the snapshot keeps showing a phantom pending decision after the experiment moved on.
- This requires threading the active objective `decision_id` into `confirm_objective` (`service.py:627-673`) — currently it takes none. Resolve it server-side by querying the session's pending objective decision rather than trusting a client-supplied id (Duo-panel: the FE may not have one).

**(4b-prompt) Harden the planner prompt/path for the TLC-retry phrasing:**

- **`app/runtime/middleware/dynamic_prompts.py:393-453`** (`_OBJECTIVE_HEADER` + `_OBJECTIVE_PHASE_INSTRUCTIONS`) — the objective leg phrasing. The TLC-retry scenario's first user message is a workflow/plan request ("design a workflow…") that the objective agent must first turn into an OBJECTIVE form. The prompt already has `NO PROSE-ONLY` + exit-A, but it does not explicitly handle "user asked for a plan/retry but we're still at objective" — the LLM can drift into describing the plan in prose (abandon shape 6, per the E2E comment at `tlc-retry-flow.spec.ts:140`). Strengthen the header to: "If the chemist describes a workflow/plan/retry but no objective is confirmed yet, FIRST drive the objective ladder to a form — do not narrate a plan." This is a prompt-side mitigation; (4a) is the load-bearing deterministic fix.
- The Qwen `enable_thinking` re-deliberation loop (re-reading the `objective-confirmation form emitted` ToolMessage as a new request) is already partially guarded in `_OBJECTIVE_HEADER:419-422`; the plan subgraph additionally caps `recursion_limit=25` (`objective.py:393` already does the same), so the abandon-by-loop shape is bounded but still ends in failure rather than a form — (4a) is what makes the COMPLETE-draft case recover deterministically.

---

## Verdict — (A), (B), or (C)?

**(C) BOTH.** Two independent defects compound:

- **(B) Pure LLM flake** is the proximate cause of THIS snapshot: the objective propose path emits the form ONLY when the LLM calls `request_objective_confirmation` (`objective.py:169-171`), with **no deterministic backstop** (unlike CC's complete-draft promotion). The LLM abandoned the ladder → no form → no confirm → dangling pending decision, experiment frozen at `experiment_objective`, empty plans/jobs/trials. This matches the E2E `tlc-retry-flow` "plan_proposed never arrived even after a chemistry nudge" failure (the objective leg is the same shape one stage earlier).
- **(A) Missing deterministic objective→plan path** is the systemic gap: the only non-LLM escape is the direct REST `/objective/confirm`, and that path itself does NOT resolve the pending decision (`handle_objective_confirm` uses `persist_event`, not the CAS), so even the deterministic recovery leaves a phantom pending decision in the snapshot. A clean Duo-panel design needs (4a) [deterministic agent form emit] AND (4b) [REST confirm resolves the decision].

---

## Caveats / Not Found

- I did NOT find a code path that advances `experiments.status` past `'recommended'`. If a future stage is supposed to flip status (e.g. to `active`/`completed`), that writer does not exist yet — `status` is currently a dead label. Flagging per Rule 9; confirm intended semantics with Drake before treating `recommended` as a stall indicator anywhere.
- I did not run the session repro live (research-only). The snapshot + code trace are consistent, but the EXACT LLM abandon shape for session `d0a99969` (prose-ending vs ladder-misorder vs Qwen re-deliberation loop) is not recoverable from the snapshot alone — it would need the `session_events` log / SSE trace for that turn.
- `_build_objective_confirmed_event` (`service.py:479-531`) has a D40 fallback that walks the active experiment when `form_values` is empty — so the agent FORM_CONFIRM path is robust to an empty echo. The asymmetry in §2 is specific to the DIRECT REST path, not this one.
- The objective subgraph's `recursion_limit=25` (`objective.py:393`) bounds the Qwen re-deliberation loop to ~3-5 min before `GraphRecursionError → TurnFailedEvent`, but that surfaces as a failed turn, NOT a recovered form. Not a backstop for the complete-draft case.
