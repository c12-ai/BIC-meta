# Research: Objective draft precedent — POST /sessions/{id}/objective/draft

- **Query**: Payload, validation leniency, persistence, and whether/how the objective draft is surfaced to the LLM via SessionContext today.
- **Scope**: internal (BIC-agent-service + portal)
- **Date**: 2026-07-02

**Summary**: The objective draft endpoint is the closest existing lenient-draft-sync pattern: all-optional body, sync 200, persists straight to `experiments.objective` with NO event and NO stage change. **Critical caveat: the REST-persisted draft reaches the DB and `ctx.experiment.objective`, but it is NOT seeded into the objective subgraph's `objective_draft` state and NOT rendered into `objective_dynamic_prompt` — i.e. today the LLM does not actually see FE-typed objective edits on the next turn** (only the confirm path falls back to `ctx.experiment.objective`). So the precedent proves the FE→BE persist leg, but the BE→LLM leg is exactly the gap this task must close for specialist params — do not copy the objective flow blindly.

## Findings

### Endpoint + payload (L1)

| File:Line | Detail |
|---|---|
| `app/api/routers/sessions.py:353-376` | `POST /sessions/{session_id}/objective/draft`, `status_code=200` (sync, not 202 — no turn is enqueued) |
| `app/api/routers/sessions.py:299-313` | `ObjectiveDraftRequest` — **all fields optional** (`name`, `reaction_smiles`, `reactants=[]`, `target_purity_pct`, `target_yield_pct`), still `extra="forbid"` |
| `app/api/routers/sessions.py:253-269` | `ObjectiveReactantInput` — lenient rows ("amount/equivalents may be empty until Mind recalculation fills them") |
| `app/api/routers/sessions.py:316-321` | `ObjectiveDraftResponse` — echoes the persisted draft (`experiment_id`, `name`, `objective`) |
| `app/api/routers/sessions.py:324-340` | Contrast: `ObjectiveConfirmRequest` is strict (required name/smiles/targets/feed_amount, ranges) — leniency is draft-only |

### Service + persistence (L2)

- `app/session/service.py:600-625` — `save_objective_draft`: `assert_user_owns` → `_resolve_active_experiment` (`:685-707`; 422 `form_validation_failed` if no active experiment — draft does NOT create one) → delegate to fast path. "Draft does NO field validation beyond what the L1 request schema enforces — partial payloads are accepted (design §6)."
- `app/session/fast_path_handlers.py:609-672` — `handle_objective_draft`:
  1. Service-draining preflight (`:634-637`).
  2. Optional Mind material-parse when `reaction_smiles` present (`:643-660`; malformed SMILES → 422).
  3. Persist merged objective via `tx.experiments.update_fields(experiment_id, {"objective": ..., "name": ...})` (`:662-666`).
  4. **Writes NO event and does NOT advance the Level-1 stage** (`:620-622`).
- Portal caller: `src/lib/agent-client.ts:316-321` `saveObjectiveDraft` (body typed at `:278`); wired from `ExperimentObjectiveStep.tsx`.

### How (and whether) the draft reaches the LLM today

- Loader: `experiments.list_by_session` at `orchestrator.py:526` → `ctx.experiment.objective` (JSONB dict on `ExperimentSnapshot`, `app/repositories/experiments_repo.py:61`). So the draft IS in `SessionContext`.
- Objective subgraph projection (`app/runtime/graphs/factory.py:282-297`): seeds only `{ctx, experiment_id, form_confirm_payload}` — **`objective_draft` enters every turn as `None`** (`objective_subgraph_state.py:95`).
- `rehydrate_objective_state` (`rehydrate_objective.py:28-40`): rebuilds `messages` only.
- `objective_dynamic_prompt` (`dynamic_prompts.py:633-647`): header + phase block only — no draft rendering, no ctx read (explicitly "NO trial/plan prior-step carry-forward block").
- The only ctx-side draft reads are on the CONFIRM path: `_confirmed_name_and_objective` falls back to `ctx.experiment.objective` (`objective.py:228-233`) and `_emit_form_node` reads `ctx.experiment.name` (`objective.py:292`).
- Consequence: the deterministic backstop `_post_route` (`objective.py:175-188`) checks `state.objective_draft` — which only reflects **this turn's tool writes**, never the REST-persisted draft. A chemist who fills the objective form via REST drafts and then chats gets an LLM that re-derives the objective from chat text alone.

### The reverse direction (agent → FE) for the objective

- `update_objective_params` tool emits `ExperimentObjectiveDrafted` (`tools.py:1582-1620`, emit at `:1610`) — apply replaces `experiments.objective`; FE live-syncs (`event-dispatcher.ts:218+`). This is the experiment-scoped twin of `TaskParamsSetEvent` (`L4/events.md:162`). Emit guarded on truthy `experiment_id`.

### What the precedent gives the new feature

Reusable pieces if a `POST /sessions/{id}/params/draft`-style leg is chosen:
- Lenient all-optional request model + strict-confirm sibling (sessions.py pattern).
- Auth + drain preflight + Mind-outside-tx + single-tx persist ordering (`fast_path_handlers.py:609-672`).
- Sync 200 echo response.

Deltas the params version would need:
- Target is `trials.params` (trial-scoped), not `experiments.objective` — and `trials.params` already has an event-owned write path (`TaskParamsSetEvent.apply`, phase-conditional; `runtime_emitted.py:637-`, see overwrite-policy-surface.md). A REST draft write should reuse/mirror that apply semantics rather than raw `update_fields`, and likely SHOULD emit an event (unlike objective) so other tabs + replay stay consistent.
- The BE→LLM leg must be built explicitly (SessionContext field + prompt block, or pre-turn `trials.params` persist + the `reception_node.py:437` re-seed) — the objective flow demonstrates that persisting alone does NOT surface to the LLM.

## Caveats / Not Found

- Found no test or spec asserting the objective REST draft is visible to the objective LLM — consistent with the gap above (checked `factory.py`, `route_after_admit.py`, `route_entry.py`, `rehydrate_objective.py`, `dynamic_prompts.py`).
- Whether this objective gap is itself a bug worth fixing in the same task is a design decision — flagging per Rule 5/9, not deciding here.
