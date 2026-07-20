# Turn and external-execution isolation

Status: architecture boundary confirmed. In-process capability isolation, Turn admission/claim/closure authority, deadline precedence, cancellation semantics, and effect fencing are accepted; exact schemas, protocol spellings, storage fields, recovery mechanics, and timing values remain provisional.

## Confirmed boundary

- One Turn processes one normalized Turn Input.
- `turn_id` is allocated at enqueue; Turn execution begins at L2 dequeue.
- The Turn ends when L2 durably records its terminal lifecycle result.
- Context loading, Agent execution, governed read-only queries, Proposal construction, and synchronous Proposal adjudication may be inside the Turn.
- The Turn Working Context is reconstructed under the current claim from immutable Invocation Context, protected current-fact projections, stored rolling summary, recent durable Session Events, and admitted typed contributions. In-Turn Query Result Snapshots and Agent State remain transient and do not carry into another Turn.
- Outbox execution and Lab/Nexus Task execution are outside the Turn.
- Callback and reconciliation stimuli create a new Turn rather than resume the originating Turn.
- Turn, Proposal, Outbox Command, and external Task use separate identities and state models.

Session output follows three commit classes:

| Event class | Examples | Commit path |
|---|---|---|
| Transient stream delta | `reasoning_delta`, `tool_call_delta`, `text_delta` | Broadcast only; no persistence. |
| Durable conversation or observation output | `text_done`, `tool_result`, `mind_notice`, node lifecycle | L2 Turn-output persistence; no Proposal. |
| Workflow transition | `PlanConfirmed`, `TaskParamsSet`, `TaskDispatched`, and related events | Ordered append inside the accepted Proposal transaction. |

`user_message_submitted` commits in Input Admission. `FormRequested` and its pending decision commit with the accepted business action. Terminal Session Events commit with the unique Turn Terminal Outcome and do not pass through the Proposal slot.

## Confirmed closure invariants

The following are accepted as the initialization point for detailed design:

- **Foundation execution closure**: every started Foundation invocation must close with one machine-readable Foundation Execution Outcome rather than forcing L2 to infer success from iterator exhaustion. The concrete result variants and fields remain open.
- **L2 persistence closure**: L2 is the only owner that converts execution closure, deadline, cancellation, shutdown, or recovery into the durable Turn lifecycle record.
- **Exactly one durable terminal**: every admitted Turn must eventually have one, and only one, durable terminal result. This requires database and recovery mechanisms; it is not guaranteed by the current `session_events` implementation.

These three closures are distinct. A Foundation invocation can close while L2 terminal persistence is still retrying, and a persisted Turn terminal does not cancel or roll back an already committed Proposal or Outbox Command.

## Confirmed isolation model

- V1 uses strong in-process contract isolation, not a separate Foundation service.
- Foundation and trusted Domain Agent Definitions receive only Pure capabilities, governed Read-Only Query ports, and a typed Proposal port. Domain Proposal Policies receive only neutral immutable intent/current-fact views and pure decision contracts.
- An optional Query Agent declares the `light` model level and receives graph-specific grants limited to Pure and Read-Only Query capabilities. It has neither a Proposal Tool nor the Proposal Port, External Command adapter, Persistence handle, workflow-policy capability, mutation credential, or mixed read/write client; routing cannot widen that composition.
- They cannot import or receive workflow persistence, concrete L2 services, outbox implementations, state-changing external clients, or a generic service locator.
- The Proposal port is implemented under L2 authority. Its adjudication transaction is short and closes before control returns to continuing Agent execution.
- No transaction or entity lock crosses an LLM, narration, graph-continuation, or read-only-query await.
- All external mutations, including deterministic and reconciliation paths, cross the Outbox executor boundary.
- Turn cancellation never propagates through an already committed Proposal/Outbox boundary.
- User-visible Turn Cancellation is an explicit product capability: it targets one identified admitted Turn and cannot be implemented as local stream teardown.
- Cancellation and Proposal acceptance serialize through the same L2 Turn/effect authority using transactional first-commit-wins semantics. Cancel-first prevents later Proposal acceptance; Proposal-first preserves the committed transition and Outbox Command while cancellation stops only remaining Agent work/output.
- Cancellation authorization uses the trusted Turn Initiator captured at admission plus current Session capabilities: initiator with `CHAT` for self-cancellation, or any current `EXECUTE` member for peer cancellation. Collaboration focus is not authority.
- User cancellation eligibility is limited to L2-admitted `source=USER` Turns (currently user message, form confirmation, and genuine user decision response). MQ, scheduler, and reconciliation Turns reject the user API and remain governed by deadline/watchdog/recovery.
- Cancellation retains only persisted completed output segments. The active emit-only text/reasoning/tool-call fragment is discarded across live and replay; no partial-output draft is added in v1.
- Every eligible 202 Input Admission receipt exposes the stable server-assigned Turn identity. Portal cancels only through `POST /sessions/{session_id}/turns/{turn_id}/cancel` with an empty body and an authenticated actor; no mutable Session `current` alias or client-supplied actor is admitted.
- The cancellation endpoint returns HTTP 200 only after durable closure is known. Its idempotent result distinguishes a cancellation terminal from an already-won completion/failure/timeout terminal, while full terminal detail remains in Session Event/history projection.
- The request that first commits cancellation retains its authenticated Cancellation Actor in the same terminal transaction. The actor is distinct from the Turn Initiator, survives for internal audit, and cannot be overwritten by duplicate cancellation; it is not projected to Portal in v1.
- Immediate closure uses the terminal commit timestamp and cancellation kind; v1 adds no separate cancellation-request timestamp, source field, or free-text reason.
- Static lint, import-linter, type/architecture tests, Composition Root tests, and startup validation jointly enforce the boundary as required CI gates.
- Unknown imports, dependencies, ports, tools, and runtime components are denied by default.
- Process or sandbox isolation is demand-gated for future untrusted executable capabilities.

## Confirmed Turn effect limit

- Each Turn has one durable accepted-effect slot.
- Rejected candidate adjudications do not close the slot; a corrected candidate may be submitted.
- The same candidate is idempotent under delivery retry, while a materially corrected intent receives a new Proposal identity.
- The first accepted Proposal closes the slot transactionally. All later Proposal calls in that Turn are non-mutating closed-slot outcomes.
- One accepted Proposal may represent multiple entity changes, ordered Session Events, and correlated Outbox Commands belonging to one business action.
- After acceptance, the active Foundation invocation is limited to pure/read-only work and grounded narration.
- This is not current behavior: current L2 commits streamed events one by one, current L3 performs direct persistence and commands, and process-local submit locking compensates for observed parallel duplicate calls.
- The target accepts the observable failure-path change: before Proposal commit no workflow-action prefix is visible; after commit the whole ordered action is visible even if the Turn later fails. Each migrated action records the legacy partial prefix and target atomic trajectory. Durable conversation or observation output remains independent.

## Confirmed durable admission split

- L2 Input Admission and claimed Turn execution are separate phases.
- One admission transaction validates/deduplicates the normalized input, performs applicable deterministic CAS/fact changes, appends the input receipt/Session Event, and creates the durable queued Turn.
- HTTP or MQ success is acknowledged only after that transaction commits.
- An input rejected before admission commit creates no Turn.
- `turn_id` and the immutable Turn Input exist from admission; queue latency remains outside the execution deadline.
- A worker claim begins execution and must be recoverable after process loss.
- Deterministic admission changes and the optional L3 Proposal have distinct provenance and identities; admission does not consume the Turn effect slot.
- The durable work item supports recovery only. It does not persist authoritative Workflow Facts in Agent State or create a durable LangGraph thread.
- An execution-eligible reclaim reconstructs the Turn Working Context under the new claim generation instead of resuming a mutable Session context or durable graph checkpoint. A reclaim that observes the absolute deadline has elapsed skips Foundation and competes for timeout closure.

## Confirmed minimal claim fencing

- Recovery keeps the same logical `turn_id` and atomically increments a row-level `claim_generation`.
- `lease_owner` and `lease_expires_at` determine reclaim eligibility; lease expiry alone does not grant the stale claimant continued authority.
- Proposal adjudication, effect-slot closure, durable output, terminal persistence, and live broadcast verify the current generation.
- A stale claimant has no mutation, closure, or narration authority.
- `claim_generation` is an internal fencing token, not a public lifecycle identity.
- V1 has no Attempt table, Attempt events, public Attempt ID, or durable Agent checkpoint.
- Historical claims remain trace/log data until a named consumer passes a demand gate.

## Confirmed minimal Turn state machine

- The Turn row uses only `queued`, `running`, and `terminal` operational states.
- Initial claim transitions `queued -> running`; an expired reclaim remains `running` and replaces the claim generation/lease.
- Exactly one fenced terminal CAS transitions the logical Turn to `terminal`.
- Completion, failure, timeout, and cancellation are typed Turn Terminal Outcome data, not states.
- Queue, heartbeat, lease expiry, and reclaim do not create Portal-visible lifecycle states. Accepted user cancellation transitions `queued|running -> terminal` immediately and creates no durable `cancelling` or `cancel_requested` phase.
- Terminal row update and compatible terminal Session Event append occur in one L2 transaction.
- User cancellation appends the distinct persisted `turn_cancelled` terminal Session Event; it is not projected as `turn_failed`.
- A losing duplicate terminal writer returns the existing result and emits no duplicate terminal event.
- After cancellation closure, cooperative execution interruption and resource cleanup may continue locally, but the claimant has no Proposal, persistence, terminal, or broadcast authority.

## Confirmed outcome orthogonality

- Turn Terminal Outcome, Proposal outcome, Outbox Command outcome, and Lab/Nexus Task outcome remain independent.
- A Proposal may be accepted and committed before the Turn later fails or times out during narration or cleanup.
- Later Turn failure cannot roll back the accepted transition, reopen the effect slot, or implicitly cancel the command.
- The Turn Terminal Outcome describes Agent execution/response closure only; it cannot be interpreted as the business action or physical task outcome.
- Correlation uses identities/provenance rather than a copied total-state enum.
- Structured committed events remain visible through snapshot/SSE/replay even if the correlated Turn terminal is unsuccessful.

## Provisional terminal schema boundary

- A small, orthogonal typed terminal record is the agreed direction; no concrete field list or enum is frozen.
- Candidate kinds and metadata are starting proposals evaluated in `turn-terminal-outcome-catalog.md`.
- Every persisted field requires a named consumer and action that cannot be satisfied by existing durable state or telemetry.
- `failure_stage` is not currently confirmed. Graph/component location remains telemetry-only unless a stable persisted use is demonstrated.
- The live documented 9 × 7 failure/stage matrix is not inherited automatically because its producer implements only a narrow subset.

## Confirmed deadline semantics

- The first successful claim fixes one absolute `execution_deadline_at` for the logical Turn.
- Reclaim, model retry, tool retry, and replacement workers cannot reset or extend it.
- Foundation, model, Query, and Proposal calls receive the lesser of their component cap and remaining Turn budget.
- L2 retains a configurable terminal-closure reserve rather than allowing L3 to consume the entire deadline.
- A claimant observing an expired deadline skips Foundation and competes only for the unique timeout terminal.
- Cancellation is eligible only when the authoritative L2 terminal decision occurs strictly before `execution_deadline_at`; equality and later decisions select timeout even if the watchdog is delayed.
- A post-deadline cancellation path may persist or observe the timeout terminal and returns the non-cancellation `already_terminal` disposition.
- Queue wait is measured separately and does not consume execution time.
- Outbox Command and Lab/Nexus Task deadlines remain independent.
- Exact timeout, component-cap, and reserve values are not frozen.

## Current implementation facts to preserve or challenge

- `TurnInput` currently has five kinds: user message, form confirmation, decision response, decision expiry, and task terminal callback.
- L2 serializes Turns per session and currently applies a 900-second timeout over context load, L3 stream consumption, per-event persistence, and broadcast.
- Current persisted lifecycle markers are `turn_started`, `turn_completed`, and `turn_failed`.
- Current explicit worker cancellation during simplified shutdown can escape without a persisted terminal marker; the target exactly-one rule is not yet an implementation fact.
- Current Portal intentionally exposes no Stop control; its `AbortController` and SSE close paths only stop local hydration/reception and do not cancel backend execution.
- `session_events` has no terminal uniqueness constraint, so duplicate enqueue/replay can also create more than one apparent terminal.
- Current `turn_completed` means the runtime iterator ended cleanly, not that any Lab Task completed.
- Current L3 is wired with live Lab, Mind, MinIO, and Persistence dependencies and directly performs several external mutations; the desired isolation is not present today.
- Deterministic TLC and L2 reconciliation paths also issue Lab mutations, so executor exclusivity cannot be limited to LLM-originated tool calls.
- Cancelling a coroutine cannot establish whether an in-flight external HTTP request was accepted, and does not cancel a Lab Task that already exists.

## Lifecycles that must remain separate

| Lifecycle | Identity | Authority | Begins | Ends | Current open questions |
|---|---|---|---|---|---|
| Turn | `turn_id` | L2 | input dequeued | durable Turn Terminal Outcome | exact schema, persistence/recovery mechanics |
| Agent execution | candidate `agent_run_id` | Foundation within L3 | Foundation invocation | Foundation Execution Outcome and cleanup | exact return contract, cooperative model/tool interruption |
| Proposal | `proposal_id` | trusted factory + L2 adjudication | intent bound to trusted envelope | typed adjudication/durable provenance | final outcome taxonomy |
| Outbox Command | BIC command ID | L2 transaction + outbox executor | accepted effectful Proposal commits | command receipt reaches terminal command state | attempt model, lease, retry gate, cancellation |
| Lab/Nexus Task | external task ID | Nexus/Lab | external system accepts command | external authority reports terminal state | callback ordering, reconciliation, cancellation acknowledgement |

## Detailed decisions still required

This list feeds child-slice design without reopening the confirmed architecture boundary:

1. Exact Foundation Execution Outcome variants and their mapping to Turn Terminal Outcomes.
2. Exact Turn Terminal Outcome fields, requiredness, retention, and compatibility mapping through consumer-driven Field Necessity Records.
3. Final Proposal Outcome taxonomy and action-state diagrams.
4. Exact Query Result, context-contribution, and protected-context field shapes.
5. Exact Outbox Command attempt, lease, ambiguous-delivery, ordering, recovery, and receiver-idempotency mechanics.
6. Exact admission storage, input-specific dedupe fields, claim-generation storage, and legacy backfill mechanics.
7. ADR-0035's workflow-lifetime behavior identity, retention, rollback, in-flight work, migration, and history contract before any production deployment must preserve experiments across releases; no v1 storage design is required now.
8. Concrete execution deadline, component cap, lease, heartbeat, and terminal-closure reserve values.
9. Cooperative shutdown and provider/tool cleanup behavior that cannot alter an already committed Proposal, command, or Turn Terminal Outcome.
10. Exact cancellation response JSON spellings, provider interruption behavior, and mixed-version rollout mechanics.

## Required evidence and diagrams

- a state machine for each lifecycle in the table;
- a deadline and cancellation ownership matrix;
- failure-injection sequences at every commit/call/receipt boundary;
- per-action legacy partial-prefix and target atomic failure trajectories around Proposal commit;
- compatibility mapping for existing `turn_started`, `turn_completed`, `turn_failed`, SSE behavior, and optimistic partial text;
- tests proving no Agent cancellation silently cancels or duplicates an already committed External Command.
- an additive API/Portal contract for exact-`turn_id` cancellation, including multi-tab projection and rollback behavior;
- a reviewed `turn-terminal-outcome-catalog.md` and consumer-driven field matrix before schema freeze.

## Evidence

- `research/turn-lifecycle-evidence.md`
- `research/execution-isolation-evidence.md`
- `research/architecture-gate-evidence.md`
- `research/current-multi-effect-turn-behavior.md`
- `research/input-admission-evidence.md`
- `research/claim-fencing-evidence.md`
- `research/user-turn-cancellation-evidence.md`
