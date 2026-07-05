# Objective draft live-sync event

> Child of `06-21-align-l1-l2-experiment-workflow-lifecycle`. Closes the gap flagged in
> `06-22-experiment-objective-subagent` design §2a: agent chat-driven objective-draft edits
> don't reach the FE form until confirm. The FE consumption is part of the portal task.

## Goal

When the Experiment Objective subagent edits the objective draft via its tools (`update_objective_params`,
`parse_reaction`, `confirm_goal`), persist the partial draft to `experiments.objective` and broadcast
it via SSE so the FE objective form updates **live** — exactly the write-through the CC params tools
already get via `TaskParamsSetEvent`.

## Problem (verified in code)

The 3 objective-draft-mutating tools (`tools.py` ~1292/1345/1403) do `Command(update={"objective_draft": merged})`
but **emit NO event** — because `TaskParamsSetEvent` is trial-scoped (`apply` writes `trials.params`,
`trial_id=...`) and the objective is experiment-scoped with no trial. So:
- The FE objective form sees agent edits only at confirm (or via the direct draft API), not live.
- A hard refresh mid-agent-edit loses the agent's in-progress draft (it lives only in graph state until confirm).

`TaskParamsSetEvent` (`runtime_emitted.py:637`) is the exact precedent: a `RuntimeEmittedEvent` emitted by
EVERY params-mutating tool so "chat-driven edits reach the FE form BEFORE any form_requested." This task
adds the experiment-scoped twin.

## Requirements

### R1. `ExperimentObjectiveDrafted` runtime event

* New `RuntimeEmittedEventBase` (turn-scoped — emitted inside the graph turn via `emit_event(runtime, ...)`,
  like `TaskParamsSetEvent`). Fields: `experiment_id: str`, `objective: dict` (the merged partial draft).
* `apply()`: `UPDATE experiments.objective` with the draft payload (merge/replace — match how the draft
  API persists; `experiments.objective` is the same JSONB column). Does NOT change `experiments.stage`
  (draft ≠ confirm). Idempotent (a re-apply just re-writes the same draft).
* Layer-neutral: `app/events/**` cannot import `app.core.enums` — no enum needed here (no stage write).

### R2. The 3 objective tools emit it

* `update_objective_params`, `parse_reaction`, `confirm_goal` emit `ExperimentObjectiveDrafted(experiment_id=…, objective=merged)`
  after mutating `objective_draft`, via `emit_event(runtime, ...)` — mirroring how CC tools emit
  `TaskParamsSetEvent`. The tools must take `runtime` (they currently don't — `update_objective_params`
  dropped it because there was no event; restore it).
* `experiment_id` source: the objective subgraph state carries `experiment_id` (`ObjectiveSubgraphState`).
  Use `state.experiment_id`. If it can be `None` (experiment not yet created in this turn), guard: skip the
  emit when there's no experiment id (the draft still lands in graph state; the event only adds live-sync
  once the experiment exists).

### R3. Codec + snapshot

* Register in `test_events_codec.py` `_EVENT_FACTORIES` (the exhaustiveness guard requires it).
* No snapshot DTO change — `experiments.objective` is already on the snapshot; this event just keeps it
  fresh live. A hard refresh reads the persisted draft from the snapshot (fixing the lost-on-refresh case).

## Out of Scope

* The FE objective form consuming the live event — that's `06-22-portal-lifecycle-objective-form` (it must
  add the `experiment_objective_drafted` kind to its SSE/event-dispatcher and update the form on it).
* The confirm flow (`ExperimentObjectiveConfirmedEvent`) — already shipped.
* Any stage change.

## Acceptance Criteria

* [ ] `ExperimentObjectiveDrafted` runtime event; `apply` writes `experiments.objective`, no stage change.
* [ ] `update_objective_params` / `parse_reaction` / `confirm_goal` emit it after mutating the draft (and take `runtime`).
* [ ] Emit is guarded when `experiment_id` is absent (no crash on a pre-creation draft).
* [ ] Codec round-trip + exhaustiveness pass; `apply` test (writes objective, leaves stage).
* [ ] Tool tests assert the event is emitted with the merged draft.
* [ ] ruff / format / pyright (app+tests) / full pytest green; spec updated (events.md).

## Definition of Done

* Event + 3 tool emits + tests committed; events.md documents the new event.
* Parent `06-21` banner notes this live-sync slice done + the portal-consumption follow-up.
* Verification commands pass.
