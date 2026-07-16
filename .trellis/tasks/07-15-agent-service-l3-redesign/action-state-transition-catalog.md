# Action-state transition catalog

Status: required detailed-design artifact; outcome taxonomy not yet frozen.

## Purpose

Derive the Proposal Outcome taxonomy and deterministic workflow transition model from an exhaustive inventory rather than fitting current actions into a premature enum.

## Session Event scope

This catalog covers workflow-transition events, not every live or durable Agent output.

| Event class | Examples | Commit path |
|---|---|---|
| Transient stream delta | `reasoning_delta`, `tool_call_delta`, `text_delta` | Broadcast only; no persistence. |
| Durable conversation or observation output | `text_done`, `tool_result`, `mind_notice`, node lifecycle | L2 Turn-output persistence; no Proposal. |
| Workflow transition | `PlanConfirmed`, `TaskParamsSet`, `TaskDispatched`, and related compatible events | Ordered append in the accepted Proposal transaction. |

`user_message_submitted` belongs to Input Admission and is excluded from the Proposal inventory. `FormRequested` creates a pending decision and commits with the accepted business action; it is not an independent Proposal.

Each action must answer:

1. Who or what may initiate it?
2. Which authoritative current state makes it eligible?
3. Which Principal capabilities, active decisions, versions, and other preconditions apply?
4. Which typed outcomes are meaningfully different to the Agent, API caller, audit trail, and operator?
5. Which Workflow Facts change atomically?
6. Which Session Event is appended, and what external wire projection remains compatible?
7. Which Outbox Commands are created, if any?
8. What identity, uniqueness, retry, duplicate, stale, and replay behavior applies?
9. Which layer, Domain Pack, or external authority owns each decision?
10. What partial workflow-action trajectory can the legacy path expose on failure, and what all-or-nothing trajectory must the target expose before and after Proposal commit?

## Required columns

| Action | Initiator | Domain | Eligible current state | Preconditions and capabilities | Proposal kind/schema | Proposal Outcomes | Workflow Fact mutation | Session Event / wire projection | Outbox Command | External response | Idempotency and replay | Legacy failure trajectory / target atomic trajectory | Decision owner | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Candidate action inventory

These are evidence-derived candidates, not the final taxonomy:

| Candidate action | Evidence source | Status |
|---|---|---|
| Set or revise objective | Current workflow and #136 transition table | To model |
| Confirm objective | Current durable-decision path | To model |
| Set or revise plan draft | Current workflow and #136 transition table | To model; draft-only before confirmation. Confirmed Plan structural revision is out of v1 |
| Confirm plan | Current durable-decision path | To model |
| Set task parameters | Existing typed-tool -> `task_params_set` -> L2 apply path | To model |
| Confirm or reject parameters | Current form/decision CAS and #94 policy | To model |
| Validate material readiness | #94 action inventory and Production PRD | To model |
| Submit or dispatch trial | Current specialist path and #94/#136 | To model |
| Correlate Lab task callback | Current ingress plus revised precommitted command identity | To model |
| Record progress/result evidence | Lab/MQ ingress and cross-repo evidence contract | To model |
| Confirm or reject result review | Current form/decision CAS and #94 policy | To model |
| Retry a failed or unsatisfactory trial | #94 TLC auto-retry and meta issues | To model as a new Trial under the same confirmed Plan and Step, not a Plan edit or Turn Attempt |
| Cancel an external job | #94 action inventory | Future/out of v1; distinct from Agent Turn cancellation and not approved until Lab Task cancellation semantics exist |
| Export ELN report | #94 action inventory and Production PRD gate | To model |
| Expire or supersede a decision | Meta #138 and current scheduler/decision paths | To model |

## Required views

The completed artifact must include:

- one table covering all actions and state combinations;
- one aggregate-level state diagram per distinct workflow aggregate whose transitions are not obvious from the table;
- one end-to-end sequence for each action that creates an External Command;
- one failure-cut view per action showing that pre-commit target failure exposes no workflow-transition prefix and post-commit failure exposes the complete ordered action;
- an adopt/adapt/drop mapping from #94 and #136 action/effect/result concepts;
- an explicit list of incompatible or redundant existing result types to remove;
- compatibility mapping to existing REST, SSE, snapshot, replay, MQ, and error behavior.
