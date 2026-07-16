# Agent Service L3 redesign

Status: proposed architecture for review. This document records the agreed architecture boundary and does not authorize implementation.

## Design intent

Restructure Agent Service so that current Chemistry behavior remains externally compatible, experimental domains can be added without changing the domain-neutral Agent kernel, and future Agent capabilities can be introduced through evidence-backed seams without creating new workflow authorities or side-effect bypasses.

## Architecture coordinates

L1-L4 remain the only layer taxonomy:

| Layer | Stable responsibility | Not protected |
|---|---|---|
| L1 Access Layer | Protocol adaptation for external inputs and outputs | Current route/module placement |
| L2 Workflow Host | Cross-turn coordination and the sole deterministic workflow-change path | Current helper boundaries and reducer placement |
| L3 Agent Runtime | Turn-scoped probabilistic execution that emits typed outputs | Y-4 topology and TLC/CC/FP/RE wiring |
| L4 Infrastructure Adapter | Technical I/O implementations behind explicit ports | Current client/repository packaging |

Dependency and ownership rules become CI-enforced architecture contracts.

### Target architecture at a glance

This is a responsibility map, not a frozen package layout or Python API:

```text
Portal / Lab callbacks / Scheduler / Reconciliation
                        |
                        v
                  L1 Access Layer
       protocol admission + compatible projection
                        |
                        v
                  L2 Workflow Host
  +---------------------+------------------------------+
  | Input Admission     | durable Turn Host            |
  | Workflow Fact owner | Experiment Workflow Kit      |
  | Domain Proposal Policy | Proposal/CAS/events/outbox|
  +---------------------+------------------------------+
             | invoke one Turn              ^
             | immutable context             | typed Proposal / adjudication
             v                               |
                  L3 Agent Runtime
  +----------------------------------------------------+
  | Agent Foundation                                   |
  | model execution, context budget, stream adaptation,|
  | governed tool dispatch, execution closure          |
  | -> Foundation Execution Outcome                    |
  | Experiment Workflow Kit L3 components              |
  | objective/plan/step-cycle/report orchestration      |
  |                         +------------------------+  |
  |                         | Domain Agent Definition|  |
  |                         | typed Step definitions,|  |
  |                         | tools, context/evidence|  |
  |                         | scientific narration   |  |
  |                         +------------------------+  |
  +----------------------------------------------------+
          | Model Port              | Query Port
          v                         v
   L4 model adapter          L4 read-only adapter

   L3 Proposal Port ---------------------------> L2 adjudication
   L2 persistence/outbox ports ---------------> L4 adapters
                                                    |
                                                    v
                                       exclusive Outbox Executor
                                                    |
                                                    v
                                           Lab/Nexus commands
```

The Composition Root validates a static catalog of trusted installed Domain Pack, Workflow Template, and Behavior Target versions, then resolves each authoritative Workflow Behavior Binding to one exact internal runtime implementation identity/version, one exact Domain Proposal Policy in L2, and one exact Domain Agent Definition in L3. The Experiment Workflow Kit contributes shared, layer-aligned L2 and L3 components but owns neither runtime nor persistence authority. Workflow Facts remain L2-authoritative; Physical Execution Facts remain Lab/Nexus-authoritative; Session Events are compatible audit/UI projections. Future memory, Skill, and MCP capabilities must enter through explicit governed seams rather than a second workflow authority or a generic service container.

### In-process hard isolation

Foundation v1 and trusted installed Domain Packs remain co-located with Agent Service. The boundary is nevertheless treated as a hard capability boundary:

```text
L2 Turn Host
  -> invokes Foundation with immutable Invocation Context
       -> Pure Tool
       -> governed Query Port -> read adapter
       -> Proposal Port -> short L2 adjudication transaction -> typed outcome

accepted Proposal transaction
  -> durable Outbox Command
  -> independently owned executor lifecycle
  -> state-changing external adapter
```

- L3 imports contract packages, not concrete L2, persistence, outbox, or external-command implementations.
- Foundation and Domain Agent Definitions receive narrow execution ports rather than raw clients, repositories, transaction handles, or a generic service locator. Domain Proposal Policies receive only neutral immutable Proposal/current-fact views and pure decision contracts.
- A Proposal Port may return a typed adjudication outcome to the active Agent invocation, but its L2 implementation owns a short transaction that finishes before model execution continues.
- No transaction or entity lock spans a model call, narration call, graph continuation, or Read-Only Query.
- Every external mutation, including deterministic TLC operations and L2 reconciliation, is materialized as an Outbox Command and executed by the exclusive executor.
- Turn deadline and cancellation stop future Agent work and uncommitted Proposal submission only. They do not cross a committed Outbox boundary.

Process isolation is deferred because v1 executes only trusted, statically installed code. Untrusted runtime Skills, MCP tools, or plugins require a new demand-gated threat model and may introduce a sandbox or separate execution process.

### Executable boundary gates

No single checker can prove the isolation boundary. Required CI and startup gates divide responsibility as follows:

The current baseline does not yet provide this system. Ruff, mypy, and Pyright are configured, but Import Linter is absent and the existing import-hygiene pytest module contains only a few regex rules. Live L3 constructors already receive Persistence, repositories, and a raw Lab protocol that mixes reads and mutations. The migration must therefore introduce these gates before treating package relocation as isolation evidence.

| Gate | Responsibility | Examples of violations it must reject |
|---|---|---|
| Static lint | Universally banned imports/APIs and unsupported framework-private usage | `langgraph._internal`, protected-package use of explicitly banned infrastructure entry points |
| Import Linter | Authoritative direct/transitive package dependency direction, forbidden edges, and domain independence | Foundation importing L2/session, persistence, concrete infrastructure, Chemistry, or Biology; a Domain Pack importing concrete workflow repositories or command clients |
| Strict boundary typing | Narrow capability-shaped ports and no type erasure at protected constructors/factories | `Any`, `object`, unchecked casts, mixed read/write client protocols, or generic service containers crossing into Foundation/Domain Packs |
| Architecture tests | Actual composition and semantic escape hatches that an import graph cannot see | constructor or closure receives raw `Persistence`, Lab command client, transaction, outbox repository, or a malicious pack requests undeclared capability |
| Composition Root tests | The actual object graph contains only declared ports | undeclared dependency injected into Foundation/Domain Pack; concrete domain imported by Foundation composition |
| Startup manifest validation | Runtime registration is complete, classified, and default-deny | unclassified tool, model-visible External Command, missing Query capability/source metadata, incompatible Domain Pack contract |
| Transaction/integration tests | Runtime side-effect ordering that static analysis cannot prove | an external command before commit, a non-executor mutation, or cancellation rolling back/duplicating a committed command |

Each contract has a negative fixture so CI also detects accidental removal or weakening of the gate. Architecture checks are required status checks, not advisory reports.

Import Linter is the dependency-graph authority and runs in a dedicated required CI job plus pre-commit. Ruff remains the fast hygiene gate and is not used as a substitute for layer contracts. Pyright becomes strict for neutral contracts, Foundation, and Domain Pack boundaries; a second type checker is activated only if it proves an additional required property.

The target Import Linter contracts are semantic until the package-layout plan names their concrete modules:

- Foundation has no persistence/repository/ORM, concrete L2/session, command-client, raw MCP transport, or concrete-domain dependency.
- A Domain Agent Definition may depend only on the reviewed Foundation SPI and neutral query/Proposal contracts, not concrete L2, persistence, or external adapters.
- A Domain Proposal Policy may depend only on neutral domain/Proposal/current-fact/transition-plan contracts, not Foundation, L3 execution, repositories, transactions, outbox implementations, or external adapters.
- Neutral types shared by the two faces cannot reverse-import either layer implementation.
- Only the outbox executor adapter resolves state-changing external clients.
- L4 adapters remain leaves and cannot import workflow or Agent policy.
- durable Turn Terminal Outcome and terminal-projection construction remain L2-owned.
- one dedicated Composition Root is the sole reviewed cross-layer wiring location.

The current mixed Lab protocol must be split by capability. A read adapter may use whatever transport method implements a semantically reviewed read, but it exposes no state-changing operation. Tool and port classification never derives from HTTP verbs.

Three orthogonal boundaries operate within this model:

- **Agent Foundation**: the domain-neutral execution kernel inside L3.
- **Domain Pack**: one versioned domain implementation whose Manifest binds a Domain Agent Definition consumed by L3 and a Domain Proposal Policy consumed by L2.
- **Proposal Boundary**: the only seam through which probabilistic L3 output can request deterministic L2 change.

`Proposal Layer` is not used because it would create a second, overlapping layer taxonomy.

### Two orthogonal seams at the L2/L3 boundary

“The Domain Pack sits at the L2/L3 boundary” and “L2 invokes L3 through one Agent Runtime Port” describe different axes and do not conflict:

```text
Startup composition axis
------------------------
one Domain Pack Manifest/version
        |-- Domain Proposal Policy ----> bind into generic L2
        `-- Domain Agent Definition ----> bind into L3 Foundation

Runtime execution axis
----------------------
L2 Turn Host
        |-- Agent Runtime Port ---------> L3 Foundation + Agent Definition
                                              |
                                              `-- Proposal Port
                                                       |
                                                       v
                                  L2 Proposal Host + Domain Proposal Policy
```

The Domain Pack is therefore a coherent extension module spanning the boundary through two separately governed faces; it is not a runtime layer between L2 and L3. The Agent Runtime Port remains the sole L2-to-L3 execution entrance. The Proposal Port is a separate L3-to-L2 request/reply seam for desired effects, and the Agent face never calls the Policy face directly.

The original architecture already defined `runtime.invoke(ctx, turn)` as the unique L2-to-L3 channel and described L2 as coordinating “what to do next” while L3 executes “how to think about this Turn.” The redesign preserves that responsibility shape while removing current raw dependencies and preventing generic L2 from learning domain graph topology.

### Domain-neutral Agent Runtime Port

The L2 Turn Host sees one conceptual operation: execute one admitted Turn using an immutable invocation request. It cannot address a specialist, Agent, graph, node, prompt, or tool. The Composition Root prevalidates the workflow's immutable Behavior Target and resolves it to one internal runtime implementation plus its exact Foundation, Experiment Workflow Kit, and Domain Agent Definition composition; neither Portal input nor model output selects the target or Pack.

The Port returns typed runtime output and one machine-readable **Foundation Execution Outcome**. That outcome states how the Foundation invocation closed and is available before durable L2 closure; it is not the authoritative lifecycle result of the logical Turn. L2 combines it with authoritative workflow, cancellation, deadline, and fencing facts to persist exactly one **Turn Terminal Outcome**. Their exact Python containers, streaming protocol, fields, and mapping table remain detailed contract decisions, but the boundary cannot expose Persistence, a transaction, raw Lab/Nexus clients, concrete graph state, or an iterator whose exhaustion is the only success signal.

### Three reuse zones and one sealed composition boundary

The common substrate is deeper than Agent Foundation alone. V1 uses three responsibility and reuse zones inside the existing L1-L4 architecture:

| Reuse zone | Shared responsibility | Explicit exclusion |
|---|---|---|
| Agent Foundation | Domain-neutral model/tool execution, context budgeting, stream normalization, Proposal and Query plumbing, deadline/cancellation propagation, telemetry, transient graph execution, and one Foundation Execution Outcome | Experiment-product progression, durable Turn Terminal Outcomes, and scientific semantics |
| Experiment Workflow Kit | Cross-domain Objective, Plan, serial Step-cycle, applicable confirmation, execution-correlation, result-analysis progression, and deterministic report orchestration through layer-aligned L2/L3 components | Persistence or transaction authority, a second runtime, a Base Domain Pack, or a general workflow DSL |
| Domain Pack | Domain Step definitions, schemas, prompts, parameter-design behavior, evidence meaning, result analysis, domain Proposal policy, and typed deterministic report contributions | Reimplementation of Foundation or Experiment Workflow Kit mechanics |

A large Domain Pack is not itself a design failure when its size represents irreducible scientific behavior. The failure condition is that a second domain must rebuild execution mechanics or semantically identical experiment-workflow mechanics. The Biology validation slice is therefore a leverage test, not only a registration test.

The Experiment Workflow Kit owns the v1 macro topology. The Domain Agent Definition owns scientific composition inside typed Steps and may produce a bounded step-local loop intent whose corresponding pure policy remains on the L2 face, but it cannot replace the Objective/Plan/serial-Step/Completion/Summary skeleton, return an arbitrary precompiled graph, or provide unrestricted executable nodes. It composes reviewed Foundation-issued execution capabilities and Experiment Workflow Kit components through typed Python contracts. It cannot construct its own model/tool loop, compile or run the macro graph, normalize streams, implement deadline/cancellation/closure, call raw infrastructure clients, or acquire persistence. Import Linter, strict boundary typing, object-graph tests, and network/model tripwires enforce this structurally rather than observing good behavior after the fact.

The Experiment Workflow Kit is not extracted from code resemblance alone. Safety and authority invariants enter their neutral owner immediately. Other behavior is promoted only when Chemistry and Biology use the same domain-neutral contract with identical semantics, cross-domain conformance tests pass without `domain_key` branches, and extraction deletes duplication from both Packs. Prompts, scientific action schemas, evidence meaning, and domain transitions remain in a Pack even when their implementations look similar.

Current code already demonstrates all three categories but mixes their boundaries:

- `app/runtime/runtime.py::Runtime.invoke` contains reusable Turn-scoped graph invocation, stream translation, sequencing, and observability mechanics that belong in Foundation, while the current constructor still receives Persistence and concrete/raw service capabilities.
- `app/runtime/graphs/factory.py` combines Chemistry topology with repeated subgraph projection, stream relay, and compilation mechanics that Foundation should host once.
- `app/runtime/graphs/specialists/_entry_pipeline.py::EntryStepSpec` and `_narrate_pipeline.py::NarrateStepSpec` emerged because recommend/form/narrate mechanics had been copied across Chemistry specialists. They are evidence for an Experiment Workflow Kit, not reasons to move Chemistry vocabulary into Foundation.
- TLC/CC/FP/RE schemas, prompts, carry-forward, evidence interpretation, and executor-specific behavior remain Chemistry Domain Pack material.

Deletion and locality tests accompany the Biology leverage test. Removing Chemistry must leave Foundation, the Kit, and Biology conformance tests runnable without Chemistry vocabulary. Removing the common substrate should make substantial execution and experiment-workflow machinery visibly reappear in both Packs. A Biology prompt or evidence change touches Biology; a deadline or stream change touches Foundation; a serial progression correction touches the Kit; and a Biology action precondition touches its Policy face.

### V1 serial Experiment Workflow Template

V1 deliberately fixes one cross-domain experimental-product shape:

```text
Experiment Objective
  -> Experiment Plan
       ordered finite list of domain-defined Experiment Steps
  -> for each current Step, strictly serially:
       Preparation / Parameter Design
         includes recommendation when the domain provides it
         -> execution-bearing design: compatible pre-execution Confirmation Gate
         -> no system-generated parameters: typed not_required result,
            with no synthetic parameter form or confirmation
       Experiment Execution
         -> accepted Proposal / Outbox Command / Lab or Nexus Task
         -> asynchronous callback or reconciliation creates a new Turn Input
       Result Analysis
         -> domain evidence interpretation
         -> required compatible result-confirmation policy, when applicable
         -> authoritative Plan Progression Decision
       -> advance to the next ordered Step
  -> Plan Completion
  -> Summary Document (Chemistry v1: existing deterministic ELN report)
```

The three primary Step phases are Preparation/Parameter Design, Experiment Execution, and Result Analysis. Parameterized or robot Steps produce a typed execution-bearing design and use the existing compatible pre-execution confirmation surface. A manual Step with no system-generated execution parameters returns a typed `not_required` preparation result and proceeds without a fabricated parameter schema, empty Portal form, or new confirmation interaction; its existing human completion and evidence interaction occurs during Experiment Execution. Confirmation is therefore a deterministic gate only when the current Step exposes an execution-bearing design, not a mandatory fourth Agent capability phase. Existing compatible result confirmation remains part of closing Result Analysis. Objective and Plan confirmation behavior remains governed by the compatible product workflow and is not moved into L3 prompt convention.

This workflow spans multiple Turns and external lifecycles; it is never one long-lived LangGraph run. L2 owns the authoritative Experiment Workflow Model, current-Step selection, confirmation state, and serial advancement. L3 receives the current immutable workflow context for one Turn and may request at most one accepted effectful transition through the Proposal Boundary. Outbox Commands and Lab/Nexus Tasks continue independently, and their callback or reconciliation signals are admitted as new Turns.

Only one Step may be active for execution at a time. A Plan cannot complete until every ordered Step has completed under its domain evidence and applicable confirmation policy. In Chemistry v1, **Summary Document** is the cross-domain architectural name for the existing deterministic, AI-free ELN report artifact. The Experiment Workflow Kit owns completion gating and report orchestration, while the Chemistry Domain Pack supplies typed deterministic report data and sections derived only from confirmed Workflow Facts and correlated Physical Execution Facts. Agent-generated finale narration is a separate conversational output: it cannot supply report facts, alter the ELN, or replace it. The report remains an artifact, not a new workflow authority.

The v1 template does not implement parallel Steps, DAG routing, nested Plans, arbitrary conditional branching, runtime Step insertion/reordering, or a general workflow language. Failure, timeout, cancellation, and external retry are still required lifecycle outcomes, but they do not create additional workflow topology. Extensibility comes from localizing serial progression inside the Experiment Workflow Kit, using stable Plan and Step identities, and versioning the contract when a proven future consumer needs another shape—not from building an unused general engine now.

### Confirmed Plan freeze and Trial rework

Plan structure and Plan progression are separate authorities. Confirmation freezes the ordered Step identities, order, execution ownership/type, and domain Step-definition references. L2 may continue to advance dedicated progression facts, but no generic repository update, Domain Pack, L3 node, model output, later confirmation, or replay may edit the confirmed structure in place.

```text
Plan draft/proposal
  -> confirmation
  -> Confirmed Plan: immutable Step structure
       |
       | normal result acceptance
       `-> L2 advances dedicated progression facts only

current Step needs rework/re-execution
  -> create a new Trial under the same Plan + Step identity
  -> confirm changed execution parameters when applicable
  -> preserve prior Trial evidence and outcomes
```

A Trial is a scientific execution-and-analysis instance, not a Turn Attempt. It can span an execution Proposal, Outbox Command, external Task, callbacks, analysis, and several new Turns while remaining under one planned Step. Rework never duplicates the Step in Plan topology and never reopens an old Turn. Domain-specific retry limits and verdict rules remain in the Domain Pack; the Kit owns only the reusable Trial lifecycle and confirmation/progression seams.

Structural Plan change after confirmation is unsupported in v1 and fails without mutation. This refactor does not add a Revision API, lineage or active-revision view, Revision-specific Portal behavior, or speculative persistence fields. If a future approved product use case needs to change remaining Steps, it must preserve completed history and use a new confirmed Plan identity rather than weakening the freeze; all other Revision semantics are deliberately deferred.

The current code approximates this boundary but does not enforce it completely. `PlanConfirmedEvent.apply` treats re-confirmation as an idempotent no-op, new proposals supersede only recommended/proposed Plans, and `PlansRepo.advance_cursor` is intended as the sole progression writer. However, generic Plan update methods do not consistently predicate writes on non-confirmed status, so freeze still depends on call discipline and comments rather than a complete L2/repository/database invariant. The redesign must make the negative path executable through transaction, repository, database, and architecture tests.

### Typed Domain Step Definitions

The fixed macro workflow narrows the earlier phrase “the Domain owns graph topology.” In v1, the Experiment Workflow Kit owns the macro topology and phase order. A Domain Pack owns Plan/Step scientific definitions, phase behavior, and bounded step-local loop semantics; it does not recreate the shared graph.

The target boundary is conceptual until Chemistry and Biology exercise it; the following names and method shapes are not frozen:

```text
Domain Pack Manifest
  -> neutral Step identity + compatible contract versions
       |
       |-- L3 Agent face: typed Domain Step Definition
       |     |-- Step identity and domain language
       |     |-- Preparation / Parameter Design capability
       |     |     `-- execution-bearing design or typed not_required
       |     |-- Execution Intent capability
       |     `-- Result Analysis capability
       |            `-- optional typed scientific loop intent
       |
       `-- L2 Policy face: Domain Proposal Policy
             |-- confirmation and execution preconditions
             |-- typed transition decisions
             `-- optional pure Step Loop Policy

Experiment Workflow Kit
  -> composes the registered Definition into the fixed Step cycle
  -> supplies only phase-scoped context and governed ports
  -> owns applicable confirmation routing, Trial lifecycle, execution correlation,
     result-review progression, serial cursor, completion, and deterministic report orchestration
```

The two Domain Pack faces bind through neutral Step identity and compatible typed contracts, not one executable object crossing L2/L3. The Agent face may produce typed domain intent and scientific analysis, but cannot call the Policy implementation. The Policy face may decide pure domain preconditions and transition meaning, but cannot receive models, graph execution, tools, Agent State, repositories, or transaction handles. Generic L2 remains the fact, transaction, CAS, event, and outbox authority.

`Domain Step Definition` is one small aggregate whose fields reference deep phase modules. It is not a long record of optional callbacks. Independent Parameter/Execution/Analysis registries are also rejected because they fragment one scientific Step, weaken generic type relationships, and encourage runtime maps, casts, and service-location. Strict typing forbids `Any`, `object`, raw graph/node callables, and generic containers at this boundary.

Execution ownership is data on the confirmed Plan Step, not a topology choice:

- a robot Step's Preparation/Parameter Design capability produces a typed execution-bearing design for the compatible confirmation surface, and its Execution Intent capability produces typed effect intent for trusted Proposal construction and the L2/outbox path;
- a manual Step with no system-generated parameters returns typed `not_required` from Preparation/Parameter Design, then exposes the existing human-completion and evidence-input contract during Experiment Execution without a synthetic parameter form or confirmation;
- both traverse the same conceptual phase topology, Trial, analysis, result-review, progression, and summary lifecycle; the confirmation gate applies only to an execution-bearing design, and neither Step type may fabricate completion or call persistence/external commands directly.

A step-local loop is similarly bounded. Result Analysis may produce a typed scientific loop intent; the pure Policy face decides whether current facts permit another Trial and supplies domain transition meaning. The Kit/L2 create and fence the Trial. The loop cannot insert a Step, move the Plan cursor, or become a custom graph escape hatch. TLC-specific verdict thresholds and retry limits therefore stay in Chemistry while the repeat-Trial lifecycle remains shared.

Current code provides migration evidence but not the final SPI. `_entry_pipeline.py::EntryStepSpec` already injects per-Step schemas and recommendation behavior into shared routing, and `_narrate_pipeline.py::NarrateStepSpec` injects grounded language into shared narration. CC/RE largely vary by typed schemas and requests, TLC varies in recommendation, evidence, and local retry policy, and FP uses deterministic design/analysis. Conversely, the current graph factory still constructs every Chemistry specialist explicitly, submission code mixes shared mechanics with raw clients/persistence, and manual Steps are skipped rather than traversing the common lifecycle. The migration deepens the useful specs and removes these graph/effect leaks; it does not freeze their current `Any`, tool-name, event, or client-shaped interfaces.

Scientific variation inside the three-phase cycle is added through a new Step Definition or phase implementation. A future parallel, DAG, nested, or additional-phase workflow requires a separately reviewed versioned Experiment Workflow Template contract. V1 does not reserve raw graph hooks for that hypothetical topology.

## State authority

| Data | Authority | Non-authoritative consumers or projections |
|---|---|---|
| Product workflow facts | Agent Service workflow model | Workflow Views, Agent runtime context, Session Events |
| Physical execution facts | Nexus/Lab | Agent Service correlated projection |
| UI history and audit | Append-only Session Events | Live SSE, cold snapshot, replay projection |
| Agent working state | LangGraph execution state/checkpoint | Agent nodes and middleware within a bounded execution |

The canonical model is **entity-authoritative, event-projected progress**, not an event-sourced workflow. Live, snapshot, and replay paths must remain semantically equivalent.

## Deterministic effect flow

```text
L1 input
  -> L2 loads current facts and invokes one L3 turn
  -> Agent Foundation + Experiment Workflow Kit + Domain Pack produce text, read-only results, or a typed Proposal
  -> L2 Proposal Boundary reloads/locks current facts
  -> global capability checks + Domain Proposal Policy + CAS
  -> one transaction: workflow transition + Session Event + optional Outbox Command
  -> commit
  -> broadcast committed event
  -> outbox executor alone performs External Command
  -> receipt transaction records external identity/outcome
  -> externally compatible dispatched/progress event becomes visible
```

There is no parallel Proposal reducer, event log, persisted baton authority, or direct L3 external command path.

### Proposal construction trust boundary

Model-controlled output stops at a typed Intent Payload. The model may select a registered Proposal kind and provide only the domain fields exposed by that kind's schema.

A trusted Proposal Factory binds the payload to:

- actual Principal Context and effective capabilities;
- workflow, session, turn, Agent run, and domain identities;
- component and schema versions;
- expected-version or other CAS preconditions;
- Agent/tool/Skill provenance;
- stable Proposal and idempotency identities.

The model cannot supply or override these fields. The resulting Proposal Envelope is still only a request: L2 reloads or locks current facts and performs the authoritative capability, policy, and concurrency decision.

### Proposal identity and receipt model

- The trusted Proposal Factory creates `proposal_id` once for a logical tool call and records it in lean Agent State before submission.
- Identity is stable across attempts of the same Agent run and binds the stable run, tool call, Proposal kind, and target workflow. Payload equality alone does not define identity.
- Accepted transition provenance records `proposal_id` internally. Each Outbox Command identity is derived from `proposal_id`, command kind, and ordinal.
- Database uniqueness makes repeated submission observationally idempotent: it returns or reconstructs the prior durable result instead of applying again.
- V1 has no generic Proposal Receipt aggregate. Accepted transition/outbox provenance is the durable receipt; non-accepted adjudications are typed and audited without changing Workflow Facts.

The concrete Proposal Outcome taxonomy is intentionally **not frozen** in this document. It will be derived from `action-state-transition-catalog.md` after every action/state pair and its persistence, event, command, compatibility, and replay consequences are reviewed.

### One accepted business action per Turn

Foundation may obtain several typed Proposal adjudications while correcting a rejected candidate, but L2 allows at most one accepted effectful Proposal for a `turn_id`.

```text
Turn effect slot: OPEN
  -> candidate rejected -------> OPEN (corrected candidate allowed)
  -> duplicate candidate ------> prior outcome, no new write
  -> candidate accepted/commit -> CLOSED
  -> later Proposal call ------> deterministic closed-slot outcome
```

The accepted Proposal represents one business action. It may perform several entity mutations, append multiple ordered compatibility events, and create multiple correlated Outbox Commands in one L2 transaction. This does not permit an LLM to compose independent actions through consecutive mutation calls.

The acceptance slot is a durable L2 invariant enforced atomically under concurrency and replay. Agent State, prompts, graph routing, and process-local locks may improve behavior but are not the authority. Once the slot closes, Foundation continues only with pure/read-only operations and grounded narration.

Rejected redelivery of the same logical candidate preserves `proposal_id` and returns its recorded outcome. A materially corrected intent is a new logical candidate with a new `proposal_id`; it is eligible only while the Turn slot remains open.

#### Current-code difference

Live main has no Proposal slot or equivalent invariant. L2 consumes a stream of events and commits every non-ephemeral event in a separate transaction, so one Turn may leave several durable mutations before later failure. Some reducers already implement a legitimate multi-entity business action—for example plan confirmation updates the plan, materializes jobs, and advances the experiment—which should become one Proposal transaction rather than several row-level Proposals.

Current L3 also persists `lab_task_id` directly after Lab submission, and the source records an incident where four parallel submit tool calls created four Lab tasks before a process-local lock/cache was added. Deterministic TLC nodes directly issue cleanup, observation, and round-append commands. The target rule is therefore a deliberate strengthening: every such path must be mapped in the action-state catalog, not grandfathered as already compliant.

The Turn effect slot governs L3-sourced Proposals; it does not retroactively classify deterministic input-admission changes as Agent Proposals. Current API/form/MQ paths may apply facts or CAS before the L3 turn. The architecture fixes atomic durable admission before acknowledgement; only the exact transaction/storage shape for each input kind remains to be specified in `turn-execution-isolation.md`.

## External-command semantics

- The outbox executor is the sole authority that may perform a state-changing external call.
- The Outbox Command has a stable precommitted BIC command identifier.
- Callback-before-response is correlated by that identifier or fails closed.
- Automatic retry is disabled per command type until receiving-side idempotency is verified.
- Existing `task_dispatched` semantics remain gated on a durably recorded Lab task identifier.

## Turn and external-execution lifecycles

### Durable Input Admission

Input admission and Turn execution are separate L2 phases:

```text
L1 user/system/callback input
  -> L2 admission transaction
       -> validate identity, authority, schema, source dedupe, and CAS
       -> apply deterministic input fact change when applicable
       -> append input receipt / Session Event
       -> insert immutable Turn Input and queued lifecycle record
     commit
  -> acknowledge HTTP/MQ producer

durable worker claim
  -> execution deadline starts
  -> reload current facts
  -> invoke Foundation
  -> optional one accepted Proposal
  -> persist unique Turn Terminal Outcome
```

An input rejected before transaction commit is not an admitted Turn. A committed Turn survives process loss between acknowledgement and claim. `turn_id` is allocated during admission, while execution begins only at successful claim; timestamps and service objectives for the two phases remain distinct.

The deterministic input transition and the later L3 Proposal have separate provenance. For example, accepting a form or projecting a Lab callback can change Workflow Facts during admission, after which the resulting Turn may propose at most one next business action. The admission transition does not consume the Turn effect slot.

This is not a durable Agent thread. The queued record stores the normalized immutable input and operational lifecycle needed for recovery. Foundation still reconstructs context from current authoritative facts on each execution attempt.

#### Current-code difference

Current admission has five inconsistent shapes and ends in an in-process `asyncio.Queue`. A user-message event can commit before queue-full returns HTTP 429; form/decision transitions can commit while bounded enqueue failure is swallowed and HTTP 202 still returns; MQ can ACK after queue insertion even though a later process crash loses the in-memory item. Decision expiry is represented in production as a user-sourced decision rejection rather than the declared scheduler expiry input. These are baseline defects, not target semantics.

The in-memory queue may remain as a wake-up optimization, but PostgreSQL admission and claim are the only correctness path. User messages remain intentionally distinct without a Portal-supplied idempotency key; payload equality is never used as deduplication.

### Minimal claim fencing

Recovery reuses the same logical `turn_id`; it does not create a replacement input or a first-class Attempt entity. The durable Turn row holds:

- monotonic `claim_generation`;
- `lease_owner` and `lease_expires_at`;
- optional operational claim/heartbeat timestamps.

Initial claim and reclaim atomically increment the generation. Foundation receives the generation as an immutable internal execution token. Every L2 surface reached by Foundation verifies it before accepting a Proposal, closing the effect slot, persisting a durable Agent output, writing the Turn Terminal Outcome, or broadcasting a live frame.

```text
Turn T, generation 1 -> claimant A stalls
lease expires
Turn T, generation 2 -> claimant B owns execution
claimant A resumes -> stale_claim; no write or broadcast authority
```

This prevents a lease from becoming an unsafe proof of termination while keeping V1 small. There is no `TurnAttempt` table, Attempt Session Event, public Attempt ID, or durable graph checkpoint. Per-claim history remains in tracing/logging unless a separately approved consumer requires persistence.

Current field deployment is a single Compose/Uvicorn process, so competing claimants do not exist today. The fence becomes necessary with the durable lease-reclaim mechanism itself and avoids making singleton, exclusive restart, and manual-only recovery permanent platform constraints.

### Minimal Turn operational state

The Turn row has three operational states:

```text
queued --claim----------------------> running --terminal CAS--> terminal
                                         |
                                         +--expired reclaim----> running
                                            generation + 1
```

- `queued` means admission committed and no current execution owns the row.
- `running` means one current claim generation owns execution. An expired reclaim replaces the owner/lease and increments the fence without creating a new lifecycle state.
- `terminal` means L2 durably closed the logical Turn exactly once.

Completion, failure, timeout, and cancellation are typed Turn Terminal Outcome data, not row states. An accepted user cancellation closes either `queued -> terminal` or `running -> terminal` immediately; it does not introduce a request/cancelling lifecycle phase. Lease expiry, heartbeat, and recovery remain operational metadata/signals rather than additional lifecycle phases.

Persistence Closure writes the Turn Terminal Outcome to the row and appends its terminal projection in one fenced transaction. Existing completion/failure projections remain compatible, while accepted user cancellation appends the separately staged `turn_cancelled` projection. If either write fails, neither commits. A concurrent or repeated writer that loses the CAS returns the stored Turn Terminal Outcome and emits nothing new.

No Portal/shared-type addition is required for queued, lease, or reclaim status. Existing terminal wire events remain projections; the durable Turn row is the operational authority.

### Absolute execution deadline

The logical Turn receives one absolute `execution_deadline_at` on its first successful claim. It is immutable across claim generations.

```text
remaining = execution_deadline_at - now
component_budget = min(component_cap, remaining - terminal_closure_reserve)
```

Model, governed Query, and Proposal-adjudication calls use bounded derivatives of this remaining budget. Internal retry consumes the same budget. Component execution stops before the deadline so L2 retains a configurable reserve for fenced terminal persistence.

An expired reclaim does not invoke Foundation. The current claimant attempts the unique timeout Turn Terminal Outcome directly. Cancellation uses the same hard cutoff: L2 checks an authoritative clock at the terminal decision, allows cancellation only while the decision is strictly before `execution_deadline_at`, and selects timeout at equality or afterwards. A late watchdog cannot let a post-deadline Stop relabel timeout as cancellation; the cancellation path may itself complete or observe timeout closure and then returns the `already_terminal` semantic disposition. Queue latency has its own timestamps/SLO and does not reduce the first-claim budget. Outbox executor attempts and Lab/Nexus Tasks retain independent deadlines and are never timed out by the originating Turn.

The current 900-second constant, component caps, lease cadence, and closure-reserve duration are not frozen here. They require measured configuration and failure tests.

### Orthogonal lifecycle outcomes

Turn, Proposal, Outbox Command, and Lab/Nexus Task outcomes answer different questions:

| Outcome | Question answered | Does not claim |
|---|---|---|
| Turn Terminal Outcome | Did L2 durably close the Agent execution and required response? | Whether the requested business action or physical task succeeded |
| Proposal outcome | Did L2 accept the requested business action against current facts and policy? | Whether an external command was delivered or a Lab Task completed |
| Command outcome | What happened to one external delivery attempt/lifecycle? | The physical task's scientific result |
| Lab/Nexus Task outcome | What did the external execution authority report? | Whether the Agent narrated it successfully |

Therefore this sequence is valid:

```text
Proposal accepted and committed
  -> Workflow Facts / Session Events / Outbox Command durable
  -> post-commit narration times out
  -> Turn Terminal Outcome = timed_out or failed at narration stage
  -> Proposal remains accepted; Outbox Command continues
```

The Turn effect slot remains closed across the failure. A reclaim or later input cannot reinterpret the accepted action as absent. Portal progress is driven by the committed structured workflow events, while the Turn Terminal Outcome independently reports the degraded Agent response. The exact Portal presentation of this correlation belongs to the compatibility mapping, not to a combined status enum.

### Turn Terminal Outcome schema remains provisional

The current four-category and metadata examples are starting hypotheses only. Exact names, values, fields, and requiredness are derived in `turn-terminal-outcome-catalog.md` from terminal cases and named consumers.

In particular, `failure_stage` is not a confirmed durable field. Live code declares a 9 × 7 failure/stage matrix but the actual classifier emits only a small subset and routes most errors through `runtime_invoke`. Topology labels are unstable across the proposed refactor and currently have no demonstrated recovery authority. Component and operation diagnostics remain trace attributes unless a consumer-driven review proves a persistent semantic need.

Every candidate terminal field must complete the five-question Field Necessity Record in `turn-terminal-outcome-catalog.md`. The record names its consumer and changed action, proves why existing facts/trace are insufficient, declares compatibility exposure, and demonstrates cross-domain/topology stability. The completed `failure_stage` record is the reference example.

A Turn is one bounded execution of one normalized Turn Input. Its identity is allocated when queued; execution begins when L2 dequeues it and ends when L2 durably records its Turn Terminal Outcome. Queue latency is measured separately from the execution deadline.

A Turn may include context loading, LLM reasoning, Pure and Read-Only Query Tools, Proposal construction, and the synchronous L2 transaction that adjudicates a Proposal caused by the input. It does not include later outbox execution or the Lab/Nexus Task lifecycle.

```text
Turn Input queued (turn_id allocated)
  -> L2 dequeues: Turn execution begins
  -> Foundation execution + governed tools
  -> optional Proposal adjudication and Outbox Command commit
  -> L2 persists Turn Terminal Outcome: Turn ends

Outbox Command (bic_command_id)
  -> executor attempt/receipt
  -> external Lab Task (lab_task_id)
  -> callback/reconciliation
  -> new Turn Input (new turn_id)
```

Turn, Proposal, Outbox Command, and external Task have distinct identities, status models, deadlines, cancellation rules, and terminal conditions. Correlation never overloads one identifier as another lifecycle.

The architecture-level isolation, claim fencing, absolute-deadline precedence, cancellation serialization, Execution Closure, and Persistence Closure semantics are closed. `turn-execution-isolation.md` retains only exact Foundation Execution Outcome and Turn Terminal Outcome schemas and mapping, storage/protocol shapes, command-recovery mechanics, concrete timing values, and cooperative shutdown/provider-interruption details that cannot change a committed closure.

### Explicit user Turn cancellation

User-visible cancellation is confirmed product scope, not a demand-gated Foundation option. Portal must offer a chatbot-style Stop action for the exact queued or running user Turn. A local SSE close, route-navigation abort, or disabled composer is not cancellation because it leaves backend execution and Proposal authority alive.

The confirmed additive protocol uses `POST /sessions/{session_id}/turns/{turn_id}/cancel` with an empty body and an actor derived only from authentication. Each eligible HTTP 202 Input Admission receipt—user message, form confirmation, and genuine user decision response—adds the stable server-assigned Turn identity so Portal can target queued work before `turn_started` appears. The proposed receipt spelling is `turn_id`; exact JSON response field and enum spellings remain provisional until contract freeze.

The cancellation endpoint returns HTTP 200 only after L2 has committed the unique cancellation Turn Terminal Outcome or observed the already committed terminal winner. Its response distinguishes two semantic dispositions: `cancelled` means this or an earlier request durably cancelled the Turn, while `already_terminal` means a non-cancellation terminal had already won. It does not duplicate the full Turn Terminal Outcome because `turn_cancelled`, Session history, and replay remain the Portal projection authority. Unknown or Session-mismatched identities return 404, unauthorized callers return 403, and known ineligible Turns return 409.

Cancellation and Proposal acceptance share one L2 serialization point and use **transactional first-commit wins**. If cancellation commits first, it irrevocably removes later Proposal-acceptance authority for that Turn. If Proposal acceptance commits first, the accepted Workflow Fact changes and Outbox Commands remain valid; a later cancellation stops only further model, query, narration, and output work. This prevents the system from both claiming that cancellation prevented an effect and committing that effect invisibly.

An accepted cancellation transaction immediately performs L2 Persistence Closure: it writes the unique cancellation Turn Terminal Outcome and terminal projection, closes any still-open effect authority, and makes all later durable output or live broadcast writes ineligible. The cooperative signal that interrupts Foundation/model/tool execution and its eventual resource cleanup occur after this authoritative closure. A stuck provider call may temporarily consume resources, but it cannot keep the user-visible Turn in `running` or retain Proposal/output authority. There is no durable `cancelling` state.

Cancellation authorization is evaluated against current Session membership plus a trusted Turn Initiator reference captured during durable admission. The initiator may cancel their own Turn while retaining `CHAT`; any owner/collaborator with current `EXECUTE` may cancel another member's eligible Turn; an observer cannot cancel another member's Turn. Focus ownership is not cancellation authority, and Portal-supplied actor/initiator fields are never trusted. The semantic initiator reference is required internally, but its concrete column name/type and any wire exposure are not frozen.

The authenticated Principal whose request first commits the cancellation Turn Terminal Outcome is retained in that same transaction as the internal Cancellation Actor. It is distinct from the Turn Initiator and is immutable under duplicate cancellation, so a peer intervention remains attributable after transient authentication context and traces disappear. The reference is not exposed through Portal-facing cancellation events, history, or HTTP in v1; its column shape and authorized internal audit access remain provisional. Immediate Persistence Closure already supplies the relevant timestamp, and no named consumer justifies a separate `cancel_requested_at`, cancellation-source field, or free-text reason.

V1 user-facing eligibility is limited to trusted user-triggered Turns: `USER_MESSAGE`, `FORM_CONFIRM`, and genuine user `DECISION_RESPONSE` admissions. MQ task-terminal, scheduler expiry, and reconciliation Turns cannot be cancelled through the user API because stopping them could swallow authoritative callback, analysis, or recovery continuations. Their deadline/watchdog/recovery policy remains responsible for closure, while administrator/operational cancellation is a separate internal capability. Eligibility uses L2-assigned source/kind and Turn Initiator, never a client claim. Cancelling a form/decision continuation does not undo deterministic facts already committed during Input Admission.

Cancellation output convergence follows the existing durable boundary. Persisted completed `text_done`, `reasoning_done`, and tool-result segments remain visible. Portal removes the currently unfinished emit-only text/reasoning/tool-call fragment, marks any open execution presentation interrupted, and renders a non-error cancellation marker. This intentionally sacrifices ChatGPT-style retention of the last unfinished fragment so live, replay, refresh, and multi-tab projections agree without a new L2 output-draft aggregate. `turn_cancelled` carries no partial text, and durable partial-response retention remains demand-gated.

This architecture treats these cancellation invariants as complete. Exact JSON spellings, cooperative provider interruption, and mixed-version release mechanics are delegated to the separately releasable cancellation slice rather than reopening the L3 architecture boundary.

## Domain extensibility

The first Domain Pack contract is provisional. A complete production-shaped Chemistry vertical slice exercises it first, and the remaining Chemistry paths migrate incrementally while the contract remains changeable. A minimal internal Biology validation slice then exercises objective, plan, execution-bearing parameter confirmation or typed `not_required` manual preparation, Proposal handling, simulated Lab execution and asynchronous progress, result confirmation, and deterministic report generation through the same Foundation and Experiment Workflow Kit seams. The Biology slice may reshape provisional seams. Only after it passes do the Agent Foundation public SPI, Experiment Workflow Kit/Template contracts, and Domain Pack contract freeze; every migrated Chemistry slice must then pass again behind that frozen set before any production workflow can bind the new target or legacy L3 can retire.

The validation slice is not a production Biology launch and cannot require Portal, Lab Service, or BIC-shared-types changes.

### Domain Pack composition model

Domain Pack v1 uses a hybrid model: a versioned declarative manifest plus typed Python ports and factories.

One coherent Pack exposes two capability-limited behavior faces and may additionally provide a typed deterministic report contribution:

| Face | Consumer | Supplies | Must not own or receive |
|---|---|---|---|
| Domain Agent Definition | L3 Agent Foundation plus Experiment Workflow Kit L3 components | typed Domain Step Definitions, phase-scoped scientific capabilities, model-facing schemas, prompts, context contributors, classified tools, evidence interpretation, typed loop intent, and optional conversational closing narration | replacement macro topology, arbitrary compiled graphs or raw executable nodes; deterministic report facts, Workflow Facts, authorization, CAS, repositories, transactions, outbox, or raw command clients |
| Domain Proposal Policy | L2 Proposal adjudication | typed intent/action contracts, pure domain preconditions and decisions, deterministic transition-plan construction over an immutable current-fact view | model/graph execution, Agent State, persistence APIs, transaction handles, outbox executor, external clients |

The two faces may share versioned neutral domain contract types, but they neither import one another's layer implementation nor communicate through mutable runtime objects. The Experiment Workflow Kit supplies reusable contracts and components to the appropriate face without becoming a third face or runtime intermediary. A Pack may also register a typed deterministic report contributor through a neutral report contract consumed by the compatible report path; this component receives confirmed Workflow Facts and correlated Physical Execution Facts, not a model or mutable runtime. Generic L2 owns the mechanics that load/lock facts, check global capabilities, execute the selected policy decision under CAS, mutate aggregates, append Session Events, and create Outbox Commands. The Policy face supplies domain rules; it never becomes a second transaction or persistence authority.

The manifest declares:

- `domain_key` and pack version;
- compatible Agent Foundation SPI, Experiment Workflow Kit/Template, and Proposal contract version ranges;
- one Domain Agent Definition factory and one Domain Proposal Policy factory, plus neutral shared schemas/components and any typed deterministic report contributor that the Pack actually supplies;
- graph declarations selecting exactly one supported Model Capability Level (`light` or `complex`), plus required principal capabilities and external ports. The manifest cannot declare an arbitrary model-capability bag or additional levels.

The manifest is metadata for validation and composition, not a workflow execution language. Domain behavior stays in ordinary typed Python components. Packs are trusted, installed with the service, statically selected by the Composition Root, and validated before traffic is served.

Foundation and generic L2 orchestration/adjudication do not import concrete packs or maintain a closed domain/specialist enum. Enabling a domain changes trusted composition registration, not either neutral core. Runtime hot loading, arbitrary third-party code, and a general YAML/JSON workflow DSL are outside v1.

### Workflow-lifetime behavior version binding

An experimental workflow spans many stateless Turns and may outlive several Agent Service deployments. L2 therefore persists one immutable Workflow Behavior Binding when it creates the Experiment Workflow, before the first domain Agent invocation:

```text
authoritative Experiment Workflow
          |
          `-- immutable Workflow Behavior Binding
                 |-- exact domain identity
                 |-- exact Domain Pack Manifest/behavior version
                 |-- exact Experiment Workflow Template identity/version
                 `-- exact Behavior Target identity/version
                        `-- exact internal runtime implementation identity/version
                            (reviewed legacy compatibility target, or
                             Foundation + Experiment Workflow Kit + Pack target)
                                  |
                                  v
                         Composition Root exact lookup
                         |                       |
                         v                       v
               Domain Agent Definition   Domain Proposal Policy
                         \                       /
                          `-- same Pack version -'
```

Every Turn loads this binding from authoritative Workflow Facts. A Behavior Target is a reviewed, registered identity/version that immutably selects one exact internal runtime implementation. During coexistence, the catalog contains an explicit legacy Chemistry compatibility target as well as new Foundation + Experiment Workflow Kit + Domain Pack targets; legacy is not an absent value or deployment default. The Composition Root performs exact-version lookup and verifies that the target, Pack Agent and Policy faces, selected Workflow Template, Foundation contracts, and Proposal contracts are compatible. Manifest version ranges are admission checks for an installed exact version; they are not selectors that permit an existing workflow to drift to the newest compatible implementation.

New and old trusted targets and versions may coexist in one deployment. Configuration chooses the approved target only for a newly created workflow, and L2 persists that exact choice immediately. The binding never resolves through a mutable deployment mapping, per-Turn or per-Step branch rule, or fallback. A target or version still referenced by a workflow capable of receiving another Turn cannot be retired. If the exact target or dependency version is unavailable, execution fails closed before Foundation invocation or any behavior-dependent Proposal/transition; it never falls forward to another target or version. Any deterministic facts already committed by Input Admission remain valid, and the Turn reaches the applicable Turn Terminal Outcome rather than erasing its input.

V1 has no implicit or in-place behavior migration. Restart, canary routing, deployment, rollback, and default changes leave the binding byte-for-byte stable. Existing workflows complete or are explicitly abandoned under the original behavior. A future migration mechanism requires its own compatibility, history, in-flight Proposal/Command, and user-expectation design; no migration field or API is reserved here.

The binding is internal workflow-routing and audit data. It is not model-selectable and adds no Portal snapshot/SSE, Lab Service, or shared-types field in v1. Release/build metadata can be correlated in telemetry, but deployment routing is not a substitute for the persisted binding. Pre-existing workflows must receive a reviewed exact Chemistry Pack/Template plus legacy Behavior Target compatibility binding before exact-version dispatch is enabled; absence never means “legacy,” “new,” or “latest.” Exact storage columns and identifier syntax remain provisional.

Current main has no equivalent binding. `Experiment`, `Plan`, `Job`, and `Trial` persistence and their snapshots contain no domain, Pack, or Workflow Template behavior version. Application lifespan constructs one global `Runtime`, whose constructor compiles one concrete Chemistry graph once; the L2 orchestrator invokes that same instance for every Turn. A restart or deployment therefore silently replaces behavior for all unfinished workflows, and current Session Events do not make that selection authoritative or replayable. This is migration debt, not behavior to preserve.

### Graph-level model capability and Turn-correlated provenance

Workflow Behavior Binding fixes domain and workflow semantics, not a concrete LLM deployment. Foundation exposes exactly two provider-neutral Model Capability Levels in v1: `light` and `complex`. Every Foundation/Experiment Workflow Kit-hosted Agent graph declaration selects exactly one of them. This single level is the model requirement visible to the graph; there is no model-role taxonomy and no arbitrary bag of structured-output, tool-calling, streaming, vision, or context-limit requirements in graph declarations. Domain Packs cannot register additional levels.

```text
Workflow Behavior Binding
  -> exact Pack + Template + Behavior Target versions
       -> hosted Agent graph declaration
              -> one Model Capability Level
                           |
                           v
              Foundation level-to-model mapping
                           |
                           v
                  concrete model invocation
                           |
                           v
          Model Invocation Provenance -> Turn correlation
```

Foundation is the only model selector. When a hosted graph is invoked, Foundation resolves the graph's declared level through a trusted configuration mapping to one approved concrete model. A missing, unknown, or unmapped level fails closed. Portal/client data, prompts, model output, graph nodes, a Domain Pack, and a Skill cannot choose or change the level, provider, or model at runtime. A concrete model may change behind the same level without mutating Workflow Behavior Binding, but only after the tests and rollout gates required for that level pass. “Latest model” is not a mapping policy.

A Turn may invoke more than one hosted graph and may make more than one model call, so Foundation emits Model Invocation Provenance per actual call rather than writing one lossy `model` field on the Turn. Each entry is correlated to the Turn and identifies the hosted graph, declared Model Capability Level, concrete provider/model, and, as available, provider-reported revision, mapping-policy version, a safe fingerprint of behavior-affecting settings, timing, usage, and outcome. Missing provider revision remains explicitly unknown.

L2 retains a compact internal Turn-correlated audit record, while high-cardinality call detail can remain in telemetry. Exact durable fields and retention pass the same consumer-driven necessity discipline as terminal fields. Credentials, secret endpoint details, and raw prompts/responses are excluded unless separately approved; provenance is audit evidence, not Workflow Fact authority and not an input to Domain Proposal Policy. No Portal, SSE, snapshot, Lab, or shared-types field is added in v1.

Exact model lifecycle pinning is a separate Demand-Gated Capability for a domain with a concrete regulatory or reproducibility need. Such a policy must define availability, provider deprecation, artifact retention, failure, and rollback; Foundation does not infer it from a pinned Domain Pack or a Model Capability Level.

Current main implements neither capability-based selection nor durable model provenance. Lifespan may construct DashScope and vLLM clients, but application composition chooses `llm_commercial or llm_local` once and injects that single client into the global Runtime. Both the streaming and structured handles use the same configured model with hard-coded thinking/max-token behavior; all current graph builders receive that client. Failure retries the same model rather than failing over to the other configured provider. Optional token accounting writes usage to logs, and the persisted Turn root-span mapping stores feedback context rather than the selected model. This current provider-precedence rule is configuration behavior, not a target contract.

## Optional Agent capabilities

Long-term Memory, a general Skill runtime, general MCP activation, and durable Agent execution remain Demand-Gated Capabilities. The decision below fixes how an approved capability enters the architecture; it does not approve their production implementation in Foundation v1.

### Common admission, separate typed capability families

Memory, Skills, and MCP are different concepts: Memory retains scoped knowledge, a Skill contributes behavior, and MCP is an integration/transport mechanism. They share demand-gated admission, least-authority grants, provenance, auditing, and composition validation, but not a generic runtime interface.

```text
configured trusted providers + Domain/Skill requirements
                         |
                         v
                  Composition Root
       admission + contract validation + narrow grant
          |                  |                  |
          v                  v                  v
  Memory capability    Skill contributions   MCP operations
  typed read/write     prompt/context/tools  individually classified
          |                  |                  |
          +----------- existing typed seams --+
                         |
        Context / Pure Tool / Query / Proposal / Outbox
```

There is no `invoke(name, payload)` extension bus, raw provider registry, or generic service locator. The Composition Root resolves a configured provider, validates its contract and grant, and injects only the typed operation required by the narrowest Foundation, Workflow phase, Domain Step, or Skill consumer. Provider stores, sessions, credentials, clients, and transports stay behind L4 adapters.

### Domain-defined Skills

A trusted statically installed Domain Skill Definition is a behavior contribution, not a custom Agent graph or authorization source. It may contribute:

- domain instructions and prompt/context blocks;
- classified Pure, Query, or Proposal Tool definitions;
- bindings to declared domains, Step kinds, and workflow phases;
- explicit requirements for already admitted capabilities, including an MCP Operation Capability or Memory context.

The effective grant is the intersection of current Principal capabilities, Domain Pack declaration, provider grant, phase policy, and tool classification. A Skill cannot widen any of them, reclassify a tool, delegate a capability it did not receive, reorder Foundation middleware, replace the Workflow Template, implement Domain Proposal Policy, persist directly, or execute an External Command. Dynamic or untrusted Skill loading remains blocked until a separate isolation threat model approves a process or sandbox design.

### Domain-declared MCP operations

A Domain Pack or Skill may declare a typed MCP operation requirement and provide domain interpretation, but it never constructs an MCP connection or receives a generic `call_tool` function. Startup resolves the requirement against configured providers and validates each operation independently for stable identity, schema, source, domain/phase allowlist, capability, provenance, deadline, audit, and effect category.

| Admitted operation semantics | Architecture path |
|---|---|
| Read authoritative external state | Governed Query capability |
| Request a workflow or external mutation from model-controlled behavior | Proposal Tool producing typed intent only |
| Actually change externally owned state | Non-model-visible External Command adapter, callable only by the outbox executor after commit |

An MCP server is never trusted or declared read-only wholesale. MCP may be the transport behind an outbox adapter, but transport choice does not change effect authority.

### General Agent Memory

General Agent Memory is a future Foundation-governed capability family with its concrete Store behind an L4 port. Domain Packs and Skills may declare memory needs and contribute domain extraction, retrieval, or rendering semantics, but they do not receive the Store.

The read side returns typed Memory Context Contributions carrying scope, provenance, observation time, and freshness. Foundation ranks and deduplicates them under the normal context budget and protected-block rules. Memory is lower authority than Workflow Facts, Physical Execution Facts, permissions, and durable Turn/Plan/Trial lifecycles; a conflict cannot overwrite or demote those facts.

The write side distinguishes two authorities:

- a trusted deterministic lifecycle policy may update an approved derived summary under its declared scope;
- model-, Skill-, or Domain-selected durable memory requires a typed Memory Proposal and trusted adjudication of scope, permission, content policy, concurrency, provenance, and idempotency before a Store write.

Memory is neither a Workflow Fact store nor a durable LangGraph thread/checkpoint. Exact tenant, user, domain, Agent, Session, retention, and deletion fields remain unfrozen until a concrete use case passes the demand gate.

### V1 delivery depth

V1 ships only neutral governed seams that migrated Chemistry or the Biology validation slice must exercise before contract freeze:

- typed context contributions, protected-block assembly, and budgeting;
- classified Pure, Query, and Proposal Tool hosting;
- Manifest capability requirements and least-authority grants;
- default-deny Composition Root validation.

Those become production mechanisms only when that real validation exercises them; fixture-only abstractions do not qualify. V1 does not introduce or freeze feature-specific `MemoryProvider`, `SkillRegistry`, or `MCPGateway` contracts. Instead, architecture conformance work uses three non-production fixtures that adapt directly into the neutral seams:

| Fixture | Must prove | Must not imply |
|---|---|---|
| Static Biology-phase contribution shaped like a Domain Skill and adapted directly into neutral prompt/context/tool seams | prompt/context/tool composition; domain/phase binding; effective-grant intersection; inability to reorder middleware, replace topology, or execute an External Command | a frozen Domain Skill provider interface; Skill discovery, installation, registry, hot loading, sandboxing, or a production Skill feature |
| Allowlisted fake MCP read operation adapted to Query | per-operation schema/identity/source classification; Principal capability, deadline, audit, and provenance propagation; startup rejection of unclassified or effectful exposure | generic MCP discovery/gateway, server-level trust, dynamic activation, credential lifecycle, or a production MCP integration |
| In-memory memory-like context contributor | scope, observation time/freshness, provenance, ranking, budget handling, and protected Workflow Fact precedence | persistent/vector Memory, retention/deletion, a generic write path, or a frozen Memory provider API |

These Capability Conformance Fixtures are disposable test evidence. They do not satisfy a Demand-Gated Capability gate, are unreachable from production composition, and create no database, API, SSE, Portal, Lab Service, or shared-types contract. All production Memory, Skill, and MCP runtimes remain separate future work with feature-specific interfaces deliberately unfrozen.

### Current-code difference

Current main has no governed contribution system:

- `SessionContext` and its L2 loader are fixed structures that mix workflow snapshots, recent conversation, locale, and Chemistry-specific form state; prompt/context assembly is repeated across narration, admission, intent, and specialist middleware.
- recent conversation is the only production memory input. A rolling-summary fold exists in `app/session/conversation_summary.py`, but the production loader does not populate it and no producer completes the loop.
- `app/runtime/tools/registry.py` can wrap every operation returned by an MCP server as raw `StructuredTool`s, but production passes an empty list and the graph factory discards it. The wrapper has no per-operation effect classification or local allowlist.
- Query Agent uses a raw Lab protocol and hard-coded collectors rather than typed Query contributions, while Chemistry specialist tool factories closure-bind Mind, Lab, MinIO, and Persistence.
- no Agent Skill manifest, registry, or runtime exists; current `SkillType` occurrences refer to robot commands and are unrelated.

Useful existing pieces migrate behind the new seams: recent-history/budget mechanics into Foundation context assembly, workflow facts/forms into Kit contributions, domain prompts/evidence into Step Definitions, Lab collectors and safe MCP wrappers into Query definitions, and effectful specialist tools into Proposal definitions. The current raw `BaseTool` lists, clients, tool-name maps, and middleware ordering are not extension contracts.

## Agent Foundation v1

Foundation v1 is a narrow Agent execution kernel with a finite responsibility set:

| Capability | Foundation responsibility |
|---|---|
| Model integration | Expose exactly the graph-facing `light` and `complex` levels, map each level to an approved concrete model, verify internally that the mapped adapter supports Foundation-required mechanics, and record per-invocation provenance. No arbitrary model-capability bag crosses into graph or Pack declarations. |
| Invocation Context | Carry immutable principal, identity, locale, domain/version, workflow reference/version, execution policy, runtime dependency, and telemetry data for one invocation. It does not carry the L2 Domain Proposal Policy implementation. |
| Agent State | Store only lean serializable execution data; never embed an authoritative business aggregate or process-bound dependency. |
| Graph execution | Compile and invoke graphs through public LangGraph APIs with an injected transient checkpointer policy. |
| Context assembly | Rank typed context blocks, enforce budgets, preserve protected blocks, and fail closed rather than silently truncate protected facts. |
| Stream adaptation | Map supported public LangGraph message/update/custom streams to stable internal Agent outputs. |
| Execution lifecycle | Provide telemetry, deadline/cancellation propagation, Execution Closure, and one machine-readable Foundation Execution Outcome per invocation. The exact outcome fields and L2 mapping to a Turn Terminal Outcome remain detailed contract decisions. |
| Standard tools | Wrap `BaseTool` / `StructuredTool` only as needed to propagate Principal Context, classify side effects, normalize telemetry, and route effectful intent to Proposals. |

Foundation v1 explicitly excludes:

- workflow persistence, CAS, outbox, and external command execution;
- domain schemas, prompts, forms, workflows, reports, and concrete clients;
- Memory Store, general Skill registry, general MCP gateway, and durable checkpointer implementation.

Production code may not import `langgraph._internal` or depend on undocumented checkpoint namespace formats.

### Model-visible tool model

| Category | Model visible | Runtime behavior |
|---|---:|---|
| Pure Tool | yes | Execute inside the invocation with schema validation and telemetry. |
| Read-Only Query Tool | yes | Execute through the governed query wrapper using Principal Context, capability checks, deadlines, rate limits, audit, and source provenance. |
| Proposal Tool | yes | Produce only an Intent Payload for the trusted Proposal Factory. |
| External Command | no | Execute only through the outbox executor after an accepted Proposal transaction. |

Read-only is an explicit reviewed capability, not a property inferred from HTTP verbs or an adapter method name. A Query Result Snapshot carries source authority, source reference, observation time, and freshness. It can inform reasoning but cannot become a Workflow Fact or trigger mutation without a new Proposal.

Domain Packs provide domain-specific query and Proposal tools. Foundation provides only the standard execution wrapper and governance hooks. A future demand-gated read-only MCP integration must enter through the same category rather than a separate graph path.

## Vertical-slice migration and legacy retirement

The L3 redesign uses a strangler-style vertical migration around stable external contracts. It does not freeze a horizontally complete Foundation before product behavior exercises it, and it does not replace the current L3 in one big-bang release.

```text
recorded Chemistry compatibility baseline
                    |
                    v
production-shaped internal Chemistry happy-path slice
                    |
                    v
remaining Chemistry paths migrate in verified slices
                    |
                    v
non-production Biology portability slice
                    |
                    v
freeze Foundation SPI + Experiment Workflow Kit/Template + Pack contracts;
rerun all migrated Chemistry gates
                    |
                    v
eligible new workflows bind new L3; old bindings stay legacy
                    |
                    v
drain legacy bindings -> remove legacy routing and code
```

The first new path is vertically complete: Objective, confirmed Plan, ordered Chemistry Steps, applicable parameter design and confirmation, Lab dispatch and callback correlation, result analysis, Plan Completion, the existing deterministic ELN Summary Document, and the existing projections used by Portal and ELN. It is initially exercised through production-shaped internal contract, golden, and live-bench harnesses rather than arbitrary production workflow routing. The slice creates only the Foundation, Experiment Workflow Kit, Domain Pack, L2, L4, and compatibility-adapter surface needed to deliver that lifecycle. A partially built general platform with no end-to-end product path is not a migration milestone, but happy-path success alone is not a production cutover gate.

Old and new L3 may coexist across workflows, never within one workflow. Trusted L2 release policy chooses the exact registered Behavior Target when Workflow Behavior Binding commits before the first domain invocation; all later Turns and Steps stay on that exact target/version. The legacy path is a reviewed compatibility target, not an implicit fallback. Callback-, scheduler-, and reconciliation-created Turns reload the originating workflow's binding instead of using a deployment default. Routing cannot depend on model output, the later Plan shape, current Step, or a failure branch, and a new-bound workflow cannot fall back to legacy when it encounters unsupported behavior. Both paths remain subordinate to the same Workflow Fact authority; effectful shadow execution, dual Session Event or Workflow Fact writes, duplicate Proposal acceptance, and a second external-command pipeline are forbidden. Rollback restores availability of a bound target/version rather than silently rebinding an active workflow.

After the complete happy path passes, remaining baseline Chemistry branches and recovery behavior migrate as independently testable slices. Each slice records its compatibility baseline, gates, rollback target, and legacy removal condition, and may be deployed behind internal or disabled routing. No production cohort becomes eligible for a new-L3 Behavior Target until all four gates hold: every baseline behavior reachable by that cohort is supported and gated; the non-production Biology portability slice passes; the Agent Foundation public SPI, Experiment Workflow Kit/Template contracts, and Domain Pack contract are frozen; and **all** migrated Chemistry slices pass again against that frozen set. Eligibility uses trusted facts available when the binding commits, never a predicted future Plan or branch. Other new workflows and every existing legacy-bound workflow continue entirely on the legacy target. An unowned permanent compatibility flag is not an acceptable end state.

Coexistence-era persistence changes follow expand/migrate/contract. Every intermediate schema and durable-record representation must remain readable and writable by all old/new component versions that can run together. Destructive contraction waits until no legacy-bound workflow is queued, running, recoverable, or otherwise eligible for another Turn and legacy execution has been disabled. A deployable slice may remain behind internal or disabled routing; deployment alone never implies that arbitrary production workflows can bind to it.

The Biology slice follows the production-shaped Chemistry path rather than preceding all Chemistry implementation. Its purpose is still to detect Chemistry-shaped abstractions before contract freeze. If it changes a provisional seam, every migrated Chemistry slice reruns against that change. Legacy L3 retires only after Biology passes; the Agent Foundation public SPI, Experiment Workflow Kit/Template contracts, and Domain Pack contract freeze; every migrated Chemistry slice passes again; no eligible workflow remains bound to the legacy target; and external compatibility and rollback gates pass. The final migration act deletes legacy routing and code.

## External compatibility

Each core migration stage targets zero coordinated changes to existing Portal, Lab Service, and BIC-shared-types versions. Compatibility covers semantic REST, snapshot, SSE, replay, error, MQ/HTTP, identity, evidence, locale, confirmation, and ELN behavior. Byte-identical internals and unobservable timing are not frozen.

The explicitly approved user-cancellation feature is a separate additive Agent Service + Portal product slice. It does not weaken compatibility requirements for the core refactor and does not require Lab Service or BIC-shared-types changes under the current ownership model.

Because the current Portal drops unregistered named SSE kinds, rollout deploys hidden `turn_cancelled` handling first, then the Agent Service endpoint/event, then enables Stop. Reusing `turn_failed` is rejected: current Portal failure handling creates a failed bubble and can mark an awaiting analysis as failed. Mixed-version tabs are an explicit rollout test/gate rather than a reason to misclassify cancellation.

Production Biology cross-repo contracts require a separate roadmap.

## Candidate PR disposition

Neither PR #94 nor PR #136 is a merge unit. The implementation plan must contain a full adopt/adapt/drop matrix.

| Candidate | Current target disposition |
|---|---|
| #94 policy outcomes and stable reason codes | Adapt into the Chemistry Domain Proposal Policy and error translation |
| #94 admission/middleware checks | Retain only as non-authoritative preflight where they improve UX or defense in depth |
| #94 Chemistry action/stage taxonomy | Replace through the single versioned Proposal taxonomy |
| #136 derived Baton | Adapt as a non-authoritative Chemistry Workflow View, not a Foundation or persistence authority |
| #136 CAS/locking and engine mechanisms | Adapt into the single L2 Proposal transaction |
| #136 outbox repository/worker foundation | Adapt to executor-owned dispatch and per-command retry gates |
| #136 specialist registry/transition table | Move Chemistry behavior behind the Domain Pack contract; do not treat it as generic |
| #136 synchronous L3 Lab dispatch | Drop |
| Unapproved external additions from either PR | Drop by default or move to separate compatibility review |

## Evidence

- `research/source-inventory.md`
- `research/state-authority-and-legacy.md`
- `research/meta-structural-issues.md`
- `research/pr-94-136-150-evidence.md`
- `research/turn-lifecycle-evidence.md`
- `research/execution-isolation-evidence.md`
- `research/architecture-gate-evidence.md`
- `research/current-multi-effect-turn-behavior.md`
- `research/input-admission-evidence.md`
- `research/claim-fencing-evidence.md`
- `research/terminal-field-consumer-evidence.md`
- `research/user-turn-cancellation-evidence.md`
- `research/current-experiment-workflow-evidence.md`
- `research/current-extension-capability-evidence.md`
- `research/current-workflow-version-binding-evidence.md`
- `research/current-model-selection-provenance-evidence.md`

## Open decisions

Architecture review and detailed contract work must still resolve:

- the exact minimum component protocols and Python container shapes across Agent Foundation, the Experiment Workflow Kit, and the provisional Domain Pack manifest;
- the exact Foundation Execution Outcome schema and deterministic L2 mapping to a Turn Terminal Outcome;
- exact Turn Terminal Outcome fields and retention justified by named consumers in `turn-terminal-outcome-catalog.md`;
- final Proposal Outcome taxonomy and action-state transition graphs in `action-state-transition-catalog.md`;
- the exact typed Query Result and context-contribution contracts within the agreed governance boundary;
- exact Outbox Command lease, recovery, ambiguous-delivery, ordering, and idempotency protocols within the closed exclusive-executor boundary;
- exact durable admission, source-deduplication, claim-fencing, and terminal-storage fields within the closed lifecycle semantics;
- exact Workflow Behavior Binding and Behavior Target storage fields, identifier syntax, legacy backfill mechanics, and supported-version retention operations;
- concrete deadline, lease, heartbeat, and terminal-closure-reserve values, plus cooperative provider interruption and shutdown cleanup that cannot alter a committed closure;
- exact cancellation JSON spellings and mixed-version release mechanics within the closed authorization and first-commit-wins semantics.
