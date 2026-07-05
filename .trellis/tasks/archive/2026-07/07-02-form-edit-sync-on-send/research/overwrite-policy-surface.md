# Research: Overwrite policy surface — task_params_set emitters vs FE re-sync

- **Query**: Where `task_params_set` is emitted BE-side, the FE re-sync effect that lets agent proposals clobber chemist edits, and what a "chemist edits win" policy would need to touch on both sides.
- **Scope**: internal (both repos)
- **Date**: 2026-07-02

**Summary**: `TaskParamsSetEvent` fires from EVERY draft-mutating tool (11+ emit sites) carrying the FULL unified draft; FE `onTaskParamsSet` whole-replaces `trial.params`, and `useParamsFormHandle`'s re-sync effect (`useParamsFormHandle.ts:40-47`) resets the form **with no `touched` guard — by explicit product contract ("agent proposal is authoritative and ALWAYS overwrites")**. A "chemist edits win" policy therefore reverses a documented contract (Rule 5: surface, don't blend). BE-side there is already precedent for guarded merges: `TaskParamsSetEvent.apply` is phase-conditional (post-confirm sections carried forward, `target_window` pinned — tasks 06-28/06-29), and the LLM prompt already carries a RE-RECOMMEND rule keyed on chemist changes. The missing input is the LLM never *seeing* unsynced edits — which is this task's core.

## Findings

### BE emit sites (all carry the FULL merged draft, `{trial_id, params}`)

| File:Line | Emitter |
|---|---|
| `app/runtime/graphs/specialists/tools.py:964` | `update_cc_params` (unified from_user/lab_logistics merge) |
| `app/runtime/graphs/specialists/tools.py:1034` | CC `recognize_tlc_plate` (agent-tool path) |
| `app/runtime/graphs/specialists/tools.py:1088` | `recommend_cc_params` (Mind recommendation → `recommended`) |
| `app/runtime/graphs/specialists/tools.py:1342` | `update_tlc_params` |
| `app/runtime/graphs/specialists/tools.py:1390` | `recommend_tlc_params` |
| `app/runtime/graphs/specialists/tools.py:1876` | RE update tool(s) (`update_re_from_user` / `update_re_lab_logistics`) |
| `app/runtime/graphs/specialists/cc.py:501` | CC subgraph node emit (auto/backstop path) |
| `app/runtime/graphs/specialists/re.py:416` | RE subgraph node emit |
| `app/runtime/graphs/specialists/tlc.py:779` | TLC Rf-loop write-through of the round's recognition |
| `app/runtime/graphs/specialists/tlc.py:910` | TLC auto-retry seed onto the new trial |
| `app/runtime/graphs/nodes/specialist_dispatcher.py:215-222` | Carry-forward seed persist right after `TaskCreatedEvent` (guarded on `from_user.tlc_result`) |

- Design intent (`tools.py:38-39`): "Every tool that mutates `params_draft` emits `TaskParamsSetEvent`" — write-through timing so chat-driven edits reach the live form BEFORE any `form_requested`.
- Tool-side merge basis: tools merge onto `state.params_draft` (section-wise `_merge_params_draft`, `specialist.py:32-61`), which reception seeded from persisted `trials.params` (`reception_node.py:437-438`). **So if chemist edits are persisted to `trials.params` before the turn, the LLM's update tools merge ON TOP of them instead of on a stale base** — this is the natural BE-side "chemist edits win as baseline" seam.

### Event apply — existing guarded-overwrite precedent

- `TaskParamsSetEvent` class: `app/events/runtime_emitted.py:637` (apply at `:658`, guard around `:667`).
- Phase-conditional apply (task 06-28 D1 + 06-29, documented `.trellis/spec/BIC-agent-service/backend/L4/events.md:161`):
  - trial in `collecting_params` → **full replace** (emitter authoritative);
  - past `collecting_params` (params confirmed) → carry forward confirmed `recommended`/`lab_logistics` the incoming blob omits AND pin confirmed `from_user.target_window` — "a stale in-flight turn's blob must NOT revert the confirmed state".
- Known clobber hazard already documented in code: `tlc.py:723-734` — "a stale `task_params_set` clobbered the confirmed …" error message. Precedent that overwrite bugs here are real and were fixed at the APPLY layer, not the FE.
- `FormConfirmedEvent.apply` (confirm path) full-replaces `trials.params` with the chemist's `form_values` — "chemist is authoritative" at confirm time (`L3/events.md:82`, `L4/events.md:163`).

### FE surface

| File:Line | Behavior |
|---|---|
| `src/lib/event-dispatcher.ts:168-174` | `task_params_set` → `workspace.onTaskParamsSet(evt)`; comment: fires from every draft-mutating tool, even outside a `form_requested` gate |
| `src/stores/workspaceStore.ts:1113-1139` | `onTaskParamsSet`: **REPLACES** `trial.params` with `e.params`, clears `paramsValidationErrors`, opens workspace, auto-switches to Parameter Design |
| `src/components/workspace/ParameterDesignPanel.tsx:639-641` | `coerce*ParamsForm(params)` memoized on `params` identity → new `initial` object per event |
| `src/components/workspace/forms/useParamsFormHandle.ts:35-38` | `reset` = rebuild draft from `initial`, `setTouched(false)` |
| `src/components/workspace/forms/useParamsFormHandle.ts:40-47` | **The re-sync effect**: `useEffect(() => reset(), [reset])` — every new `initial` identity resets the form. Comment: "Per product contract: agent proposal is authoritative and ALWAYS overwrites the local draft (no `touched` guard). Chemist can edit again or ask the agent to re-propose." |
| `src/components/workspace/forms/useParamsFormHandle.ts:49-55, 68-78` | `touched` flips on any `update`/`mutate`/`setValues`; mirrored to `useFormDirtyRegistry` as `isDirty` |
| `src/components/workspace/useFormDirtyRegistry.ts:74-92` | Global selectors `selectAnyDirty` / `selectDirtyLabels` / `resetAllDirty` — dirty state IS globally visible; values are NOT |

### What a "chemist edits win / agent must not clobber unsynced edits" policy touches

FE:
1. `useParamsFormHandle.ts:40-47` — replace the unconditional reset with a touched-aware policy (skip reset while `touched`, or field-level merge: agent values land only on untouched fields). This **reverses the documented product contract in the comment** — the comment and `.trellis/spec/BIC-agent-portal/backend-contract.md:392` (replace-merge wording) must be updated together (Rule 5/10).
2. Decide the release point for `touched`: today only `reset()` clears it. If edits are synced to the BE on send, the successful sync is the natural `setTouched(false)` point (the incoming echo `task_params_set` then legitimately re-syncs).
3. `workspaceStore.onTaskParamsSet` (`workspaceStore.ts:1113`) — store-level replace is what feeds `initial`; a store-side merge is the alternative seam if the policy should also protect against reload/replay (form-local `touched` dies on unmount/refresh).
4. Registry (`useFormDirtyRegistry.ts`) — needs a `getValues` (and trial id/executor) handle if the dirty draft must be readable at chat-send time (see user-message-submission-path.md).

BE:
1. Surface the chemist draft to the LLM (SessionContext/prompt block and/or pre-turn `trials.params` persist → `reception_node.py:437` re-seed) — otherwise the agent will keep re-emitting drafts computed from a stale base and any FE guard just hides the disagreement.
2. If the draft is persisted pre-turn: `TaskParamsSetEvent.apply`'s `collecting_params` full-replace (`runtime_emitted.py:658+`) means the agent's next tool emit still whole-replaces the row — but since tools merged on top of the re-seeded (chemist-inclusive) draft, chemist values survive UNLESS the LLM deliberately changed them. Field-level "chemist wins even over deliberate agent change" would need an apply-level pin like the 06-29 `target_window` precedent — significantly heavier; flag as a design choice.
3. Prompt layer: the RE-RECOMMEND rule (`dynamic_prompts.py:197-199, 268-270, 350-353`) already instructs re-recommendation when "the chemist changes ANY from_user field" — a chemist-draft prompt block plugs straight into this existing instruction.

## Caveats / Not Found

- No existing `touched`-guard variant anywhere in the portal forms — the overwrite-always behavior is uniform (cc/re/tlc share `useParamsFormHandle`).
- The objective form (`ExperimentObjectiveStep.tsx`) has its own draft/sync flow (REST draft + `experiment_objective_drafted`) — not covered by `useParamsFormHandle`; policy change there is separate scope.
- Exact tool names at `tools.py:1876` block (RE update) not re-verified line-by-line beyond the grep hit; the emit-per-mutating-tool invariant is spec-guaranteed (`L3/events.md:86`).
