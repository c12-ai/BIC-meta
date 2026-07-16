# LLM and external-execution isolation evidence

Evidence baseline: BIC Agent Service live `main` at `12a84f3238a952f00eb95b24c1943f8303041350`.

## Current coupling

The current L3 graph is constructed with live Lab, Mind, MinIO, and Persistence dependencies. It performs reasoning, read calls, state-changing external calls, and some persistence within the same Turn coroutine. The isolation target is therefore a material behavior change, not a description of the current architecture.

Observed state-changing paths include:

- Lab task submission from specialist tools;
- TLC cleanup, append-observation, and append-round operations from deterministic graph nodes;
- material reconciliation mutations from L2;
- post-response persistence of Lab task identity;
- process-local duplicate-submit locks and caches compensating for weak receiving-side idempotency.

An executor-exclusivity rule must cover all state-changing external calls, including deterministic and reconciliation paths. Restricting only model-originated tools would retain competing command authorities.

Primary code:

- `app/runtime/runtime.py`
- `app/runtime/graphs/factory.py`
- `app/runtime/graphs/specialists/tools.py`
- `app/runtime/graphs/specialists/tlc.py`
- `app/runtime/graphs/nodes/specialist_dispatcher.py`
- `app/session/material_reconcile.py`
- `app/session/service.py`

## Current ambiguous-delivery failures

The current task-submission sequence performs live reads, calls `lab.submit_task`, and only then persists the returned Lab task identifier. If the receiver accepts the request but the response or local persistence is lost:

- the caller cannot prove whether the command happened;
- automatic retry may create a duplicate task;
- an early callback may arrive before correlation exists;
- process-local duplicate suppression does not survive restart.

Current code comments record a case where parallel model tool calls created four Lab tasks because receiving-side idempotency was not honored. The MQ consumer uses bounded redelivery to bridge part of the callback/mapping race, which is recovery compensation rather than a durable protocol.

Primary code:

- `app/runtime/graphs/specialists/tools.py`
- `app/mq/consumer.py`
- `app/session/event_ingress.py`

## Reads are not classified consistently

- Query Agent and specialist tools call Lab REST directly with inconsistent fail-soft/fail-loud behavior.
- A semantic read may use POST, such as dry-run preparation validation; HTTP method cannot establish effect class.
- Query results do not uniformly carry source authority, observation time, freshness, or typed partial/error status.
- Mind POSTs are external computation but do not appear to mutate authoritative product state. They require deadline/failure policy but not necessarily outbox command semantics.
- Presigned URLs are non-mutating capabilities that can outlive a Turn; future object writes would be External Commands.
- MCP discovery has no local effect classification or allowlist. Production wiring is currently dormant, so it is not evidence of safe activation.

Primary code:

- `app/infrastructure/lab_client.py`
- `app/runtime/graphs/nodes/query_agent.py`
- `app/infrastructure/mind_client.py`
- `app/infrastructure/s3_client.py`
- `app/runtime/tools/registry.py`
- `app/main.py`

## Cancellation does not resolve command uncertainty

Model calls and external calls are awaited within the Turn coroutine. Cancelling or timing out that coroutine cannot establish whether a request was accepted remotely, and it cannot stop Lab Task execution or a blocking client operation already running in a thread. Lab task cancellation is currently unimplemented.

Consequently:

- cancellation before Proposal commit may prevent the requested action;
- cancellation after Proposal/Outbox commit must not roll it back or silently cancel it;
- cancellation during an executor HTTP attempt produces an ambiguous command outcome unless the receiving system supplies a durable idempotency/correlation contract;
- physical cancellation, when supported, must be a new Proposal and External Command rather than an implication of Turn cancellation.

## Candidate protocol to evaluate

This is evidence-backed discussion input, not yet a confirmed design:

1. L3 performs pure computation, governed read-only queries, and typed Proposal construction only.
2. L2 adjudicates a Proposal in a short transaction against reloaded/locked facts and persists transition provenance, Session Event, correlation, and optional Outbox Command.
3. The outbox executor alone invokes every state-changing external API.
4. Command results re-enter through durable receipts/callbacks and may enqueue a new Turn; they never resume the originating L3 coroutine.
5. Turn, Proposal, Outbox Command, and external Task cancellation/deadline semantics remain independent.
6. Ambiguous delivery is represented explicitly rather than treated as success or automatically retried.
7. Automatic retry is enabled only after a per-command receiving-side idempotency proof.
8. Read-only tools use locally reviewed capability metadata and return typed provenance/freshness; remote MCP discovery cannot self-declare authority.

## Open isolation decisions

- logical in-process contract isolation versus an independent Foundation process;
- the concrete interaction shape for Proposal adjudication while an Agent invocation is active;
- deadline and cancellation ownership on each side of the Proposal commit;
- semantics for a Turn that fails after one or more Proposals have committed;
- command lease recovery and the explicit `unknown`/ambiguous-delivery state;
- ordering keys for multi-step Lab mutations;
- compatibility timing of `task_dispatched` and other existing visible events;
- propagation of user principal provenance when downstream calls use a service account.
