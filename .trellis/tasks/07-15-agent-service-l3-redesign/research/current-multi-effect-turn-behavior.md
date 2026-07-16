# Current multi-effect Turn behavior

Evidence baseline: BIC Agent Service live `main` at `12a84f3238a952f00eb95b24c1943f8303041350`.

## There is no current Proposal acceptance slot

- `Runtime.invoke` returns an async event stream rather than a typed business-action result.
- L2 iterates every non-emit-only event and runs `apply(event) + append(event)` in a new transaction for that event.
- A single Turn can therefore durably commit several workflow mutations before the runtime iterator ends.
- If a later graph node, persistence operation, or external call fails, earlier per-event transactions remain committed and the Turn later emits `turn_failed` best-effort.
- No row, unique constraint, or L2 guard limits one Turn to one accepted business action.

Primary code:

- `app/session/orchestrator.py:350-403`
- `app/runtime/runtime.py`

## One event can already represent a multi-entity business transition

Current event reducers sometimes perform several entity changes in one transaction. For example, `PlanConfirmedEvent.apply` freezes the plan, writes confirmed parameters, materializes all robot jobs, and advances the experiment stage. This is evidence that the target Proposal should represent an action-level transition rather than map one-to-one to a row mutation or current event.

Primary code:

- `app/events/runtime_emitted.py:460-574`
- `app/session/orchestrator.py:405-460`

## Representative multi-event Turns

Current Chemistry graphs routinely express one user/system interaction as several separately committed events:

- objective proposal can emit experiment creation, objective draft, and form request events;
- plan proposal emits plan-proposed and form-requested events separately;
- plan-confirm continuation can create a trial, seed parameters, add a recommendation, and request confirmation;
- result analysis can emit analyzed, analysis-completed, and form-requested events;
- TLC retry can emit result analysis, a new trial, new parameters, Lab-ID assignment, and dispatch before directly appending a Lab round.

Primary code:

- `app/runtime/graphs/specialists/objective.py:381-451`
- `app/runtime/graphs/plan_subgraph.py:458-487`
- `app/runtime/graphs/nodes/specialist_dispatcher.py:334-373`
- `app/runtime/graphs/specialists/tools.py:1420-1434`
- `app/runtime/graphs/specialists/tlc.py:1084-1126`
- `app/runtime/graphs/specialists/tlc.py:1272-1316`

## L3 performs persistence outside the per-event path

After Lab accepts `submit_task`, the tool directly opens a Persistence transaction to bind `lab_task_id` before returning. It also emits assignment/dispatch events whose reducers later write related state again. The duplicate write is intentionally idempotent and exists to close a callback race, but it proves that current Turn changes do not pass through one atomic action boundary.

Primary code:

- `app/runtime/graphs/specialists/tools.py:1063-1144`

## Multiple model command calls are possible today

The current source records a live incident in which the model emitted four parallel `submit_l4_execution` calls in one step. All four observed no Lab task binding, all four POSTed, and Lab created four tasks because it did not honor the supplied idempotency key. The mitigation is a per-trial process-local mutex and first-success cache:

- it is not a durable per-Turn or per-Proposal invariant;
- it disappears on restart;
- failed/ambiguous submits are intentionally not cached;
- it does not generalize to other command kinds.

Primary code:

- `app/runtime/graphs/specialists/tools.py:610-621`
- `app/runtime/graphs/specialists/tools.py:964-970`

## Deterministic graph nodes also issue commands

State-changing external calls are not limited to the model-facing submit tool:

- TLC observation dispatch directly calls `lab.append_observation` after emitting a phase marker;
- TLC auto-retry emits several trial/dispatch events and directly calls `lab.append_round`;
- TLC result paths directly call `lab.cleanup`;
- result-review acceptance cleanup occurs in the specialist dispatcher before it continues routing.

These paths are designed around successive callback Turns, but there is no general runtime gate proving that only one external mutation can occur in a Turn. Some routing combinations must be reviewed explicitly for sequences such as cleanup followed by next-job dispatch.

The current `TerminalOnceMiddleware` does not establish this invariant: it covers a small confirmation-sentinel set and does not include `submit_l4_execution`.

Primary code:

- `app/runtime/graphs/specialists/tlc.py:1077`
- `app/runtime/graphs/specialists/tlc.py:1141-1198`
- `app/runtime/graphs/specialists/tlc.py:1200-1335`
- `app/runtime/graphs/nodes/specialist_dispatcher.py:125-220`
- `app/runtime/constants.py:92-149`

## Pre-dequeue changes are a separate current path

Some user/API and MQ handling performs deterministic CAS/reducer/event work before or independently of the L3 runtime stream and then submits a Turn for subsequent Agent handling. Such input-authority changes are not evidence of multiple accepted Agent Proposals because no Proposal abstraction exists yet; they must be modeled separately from the Turn effect slot.

The target design must state whether these remain a durable input-admission transaction or move into Turn execution. In either case, they cannot be hidden inside the one-Proposal rule, and the current in-memory session queue is not a durable receipt that can recover an admitted-but-never-dequeued Turn.

Primary code:

- `app/session/service.py`
- `app/session/orchestrator.py:405-460`
- `app/session/event_ingress.py`

## Migration implication

The target one-accepted-Proposal rule is intentionally stronger than the current implementation:

- multiple entity changes and compatibility events that implement one business action move into one L2 Proposal transaction;
- one action may create multiple ordered Outbox Commands when the action-state catalog proves that they belong together;
- rejected candidate Proposals do not consume the Turn acceptance slot;
- after acceptance, later Proposal attempts return a deterministic closed-slot outcome and cannot write state;
- current multi-command routing paths require explicit adopt/adapt/split decisions in the action-state transition catalog rather than an assumption that existing code already has one-command-per-Turn behavior.
