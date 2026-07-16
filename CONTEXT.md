# BIC Architecture Language

Canonical language for reasoning about BIC workflow, laboratory execution, user-visible progress, and Agent execution without conflating their authorities.

## Language

**Workflow Fact**:
The canonical current product state of an experiment workflow, including its plan, tasks, trials, and decisions.
_Avoid_: Session state, event-sourced state

**Physical Execution Fact**:
The canonical record of what the laboratory, equipment, or robot has actually executed or observed.
_Avoid_: Agent execution state, projected progress

**Session Event**:
An append-only record of a user- or system-visible occurrence used for audit and progress replay. It reflects workflow or execution facts but does not authorize or replace them.
_Avoid_: Workflow source of truth, business aggregate

**Agent Execution State**:
The non-authoritative working state needed while an Agent task is executing or being resumed.
_Avoid_: Workflow state, experiment state

**Event-Projected Progress**:
User-visible progress reconstructed from ordered Session Events while Workflow Facts and Physical Execution Facts retain their own authority.
_Avoid_: Event-sourced workflow

**L1 Access Layer**:
The protocol boundary that translates external inputs and outputs without owning workflow facts or bypassing the application boundary.
_Avoid_: Workflow service, business logic layer

**L2 Workflow Host**:
The application boundary that owns cross-turn coordination and the deterministic path for changing Workflow Facts.
_Avoid_: Agent runtime, transport adapter

**L3 Agent Runtime**:
The turn-scoped probabilistic execution boundary that produces typed intents or proposals without owning workflow persistence or physical command execution.
_Avoid_: Workflow authority, persistence layer

**L4 Infrastructure Adapter**:
A technical I/O implementation behind an explicit port that does not contain workflow transition policy.
_Avoid_: Domain service, workflow reducer

**Architecture Topology**:
The current physical arrangement of modules, graphs, and specialist wiring. It may change while the L1-L4 responsibility boundaries remain stable.
_Avoid_: L1-L4 contract

**Agent Foundation**:
The domain-neutral kernel inside L3 that provides reusable, turn-scoped Agent execution capabilities through explicit ports.
_Avoid_: Workflow engine, platform layer

**Experiment Workflow Kit**:
The cross-domain body of reusable experimental-product behavior shared by Chemistry, Biology, and later experimental domains without becoming a new layer or workflow authority.
_Avoid_: Agent Foundation, Base Domain Pack, workflow DSL

**Experiment Workflow Template**:
The v1 cross-domain lifecycle from an Experiment Objective through an ordered serial Experiment Plan to Plan completion and a Summary Document.
_Avoid_: Domain graph, arbitrary workflow topology

**Workflow Behavior Binding (deferred)**:
A future immutable association between one Experiment Workflow and its exact behavior identity and component versions. ADR-0035 must define it before the first production deployment where experiments survive Agent Service releases; it is not part of the v1 bench/field cutover.
_Avoid_: Current migration requirement, disabled internal route, deployment cohort, mutable runtime default

**Behavior Target (deferred)**:
The future exact runtime-implementation identity referenced by a Workflow Behavior Binding after ADR-0035 approves its lifecycle and retention semantics.
_Avoid_: V1 route flag, per-Turn selection, branch fallback, online-coexistence mechanism

**Model Capability Level**:
Either `light` or `complex`, the two centrally governed, provider-neutral v1 model tiers that a hosted Agent graph may declare and Foundation maps to an approved concrete model.
_Avoid_: Arbitrary capability bag, model role, provider/model name, exact model pin

**Model Invocation Provenance**:
The Turn-correlated audit evidence identifying the hosted graph, its declared Model Capability Level, and the concrete model actually used for one model call.
_Avoid_: Workflow Behavior Binding, model selector, raw prompt archive

**Experiment Objective**:
The user-confirmed scientific aim that one Experiment Plan is intended to satisfy.
_Avoid_: Prompt, Turn goal

**Experiment Plan**:
An ordered serial sequence of domain-defined Experiment Steps intended to satisfy one Experiment Objective.
_Avoid_: Agent graph, unordered task collection

**Confirmed Plan**:
An Experiment Plan whose ordered Step structure has been accepted and is thereafter immutable while its authorized progression continues.
_Avoid_: Editable plan draft, current cursor

**Experiment Step**:
A domain-defined unit of planned scientific work that follows the shared Step Cycle while retaining domain-specific parameter, execution, evidence, and analysis semantics.
_Avoid_: Agent node, Turn, external Task

**Domain Step Definition**:
The coherent typed description of one domain Step's scientific capabilities within the fixed Experiment Workflow Template, paired with but isolated from its L2 domain policy.
_Avoid_: Custom workflow graph, specialist subgraph, phase registry

**Step Capability**:
A phase-scoped piece of domain behavior used for Parameter Design, Execution Intent, or Result Analysis, including typed scientific loop intent without owning the shared Step lifecycle.
_Avoid_: Arbitrary callback, service plugin

**Step Loop Policy**:
A pure L2-facing domain rule that decides whether a typed scientific loop intent may keep the current Experiment Step open for another Trial without changing Plan topology or advancing another Step.
_Avoid_: Plan router, Turn retry

**Trial**:
One execution-and-analysis instance of an Experiment Step, allowing rework or re-execution without changing the Confirmed Plan's Step structure.
_Avoid_: Turn Attempt, duplicate planned Step

**Step Cycle**:
The shared progression of one Experiment Step through Preparation/Parameter Design, any confirmation required for an execution-bearing design, Experiment Execution, and Result Analysis before plan progression. A manual Step with no system-generated parameters returns a typed `not_required` preparation result and introduces no synthetic form or confirmation surface.
_Avoid_: Agent loop, model turn

**Summary Document**:
The deterministic end-of-Plan report artifact. In Chemistry v1 it is the existing AI-free ELN, gated and orchestrated by the Experiment Workflow Kit from confirmed Workflow Facts, Physical Execution Facts, and typed deterministic Domain Pack report contributions.
_Avoid_: Agent finale narration, model-generated report facts, raw event log

**Domain Pack**:
A coherent versioned module spanning the L2/L3 extension boundary through a Domain Agent Definition for L3 and a Domain Proposal Policy for L2, without becoming a new layer or runtime intermediary.
_Avoid_: L3-only plugin, Foundation plugin, specialist registry

**Domain Agent Definition**:
The L3-facing Domain Pack contract that defines a domain's probabilistic Agent composition, model-facing language, governed tools, context, evidence interpretation, and output contributions.
_Avoid_: Domain policy, workflow authority

**Proposal**:
An immutable, typed request describing a desired workflow change or external effect. It is neither proof that the change is allowed nor evidence that the effect occurred.
_Avoid_: Command receipt, persisted event

**Proposal Boundary**:
The sole effect-governance boundary between probabilistic L3 output and deterministic L2 workflow change. L3 produces Proposals; L2 adjudicates and applies them against current Workflow Facts.
_Avoid_: Proposal Layer, second mutation pipeline

**Agent Runtime Port**:
The sole domain-neutral L2-to-L3 execution contract for one Turn, hiding Domain Agent, graph, prompt, and tool topology from L2.
_Avoid_: Domain Pack boundary, specialist router, Proposal Port

**Demand-Gated Capability**:
An optional platform capability that is implemented only after a named consumer, concrete use case, measurable benefit, and authority or safety conditions have been agreed.
_Avoid_: Future-proofing, platform prerequisite

**Extension Seam**:
A narrow supported contract through which an approved capability can be added without changing unrelated domain behavior. It is not an unused implementation or speculative abstraction.
_Avoid_: Placeholder framework, empty registry

**Capability Conformance Fixture**:
A non-production test contribution that exercises a governed Extension Seam without approving a product capability or freezing a feature-specific provider contract.
_Avoid_: Demo feature, production provider, capability approval

**Capability Grant**:
The least-authority set of typed operations that the Composition Root makes available to one approved Foundation, workflow-phase, Domain, or Skill consumer.
_Avoid_: Service container, provider registry, inherited permission

**Domain Skill Definition**:
A trusted domain behavioral contribution composed from typed instructions, context, and classified tools that operates only with its declared Capability Grant.
_Avoid_: Custom Agent graph, arbitrary middleware plugin, authorization policy

**MCP Operation Capability**:
One individually admitted and effect-classified operation resolved from a configured MCP provider and exposed through an existing typed capability seam.
_Avoid_: Trusted MCP server, raw MCP client, generic call-tool function

**Agent Memory**:
Scoped durable knowledge retained to assist later Agent reasoning without becoming authoritative workflow, physical-execution, permission, or lifecycle state.
_Avoid_: Workflow Fact, Agent checkpoint, event log

**Memory Context Contribution**:
A provenance-bearing, time-aware Agent Memory read admitted into context under Foundation protection, ranking, and budget rules.
_Avoid_: Authoritative fact, hidden prompt injection

**Memory Proposal**:
A typed request from model-controlled behavior to persist or change Agent Memory, requiring trusted scope, permission, content, concurrency, provenance, and idempotency adjudication.
_Avoid_: Direct Store write, Workflow Proposal without memory semantics

**Domain Validation Slice**:
A minimal, runnable second-domain workflow used to discover and verify an extension contract before that contract is frozen. It is architectural evidence, not a production domain launch.
_Avoid_: Demo plugin, production Biology feature

**Contract Freeze**:
The point after which a versioned extension contract may change only through explicit compatibility rules rather than incidental needs discovered during extraction.
_Avoid_: First draft, interface creation

**Compatibility Baseline**:
The selected, recorded set of externally observable Chemistry contracts and behaviors against which a migration slice is evaluated.
_Avoid_: Latest main, assumed current behavior

**Vertical Migration Slice**:
An independently deployable and verifiable end-to-end subset that carries one coherent product behavior through the required L1-L4 path in the new architecture.
_Avoid_: Horizontal platform scaffold, effectful shadow run, big-bang cutover

**External Compatibility**:
The property that existing Portal, Lab Service, and shared-contract consumers require no coordinated change and observe semantically equivalent product behavior after an Agent Service migration.
_Avoid_: Byte identity, unchanged internals

**External Command**:
A request that asks another system to change physical or externally owned state.
_Avoid_: Proposal, workflow transition

**Outbox Command**:
The durable, precommitted instruction that authorizes the outbox executor to perform one External Command with a stable identity.
_Avoid_: Recovery note, synchronous call marker

**Command Receipt**:
The durable record of an External Command attempt and its correlated external outcome or stable task identity.
_Avoid_: Workflow Fact, Session Event

**Idempotency Gate**:
The per-command-type proof that a receiving system persists and honors the same stable command key, permitting safe automatic retry.
_Avoid_: Best-effort deduplication, global retry flag

**Admission Check**:
A non-authoritative early screen used for routing, safety feedback, or user experience before a concrete Proposal is adjudicated against current facts.
_Avoid_: Authorization, workflow guard of record

**Domain Proposal Policy**:
A pure L2-facing Domain Pack rule set that evaluates typed domain intent against an immutable current-fact view without owning persistence, transactions, or workflow authority.
_Avoid_: Global workflow engine, middleware policy

**Workflow View**:
A derived, non-authoritative representation that helps an Agent or Domain Proposal Policy reason about the current workflow.
_Avoid_: Persisted baton, workflow source of truth

**Invocation Context**:
The immutable identities, capabilities, references, policies, and runtime dependencies supplied for one Agent invocation and recreated for a later invocation or recovery.
_Avoid_: Agent State, checkpoint payload

**Agent State**:
The lean, serializable working data needed to execute or resume an Agent task without carrying authoritative Workflow Facts or Physical Execution Facts.
_Avoid_: Session Context, workflow snapshot

**Foundation Execution Outcome**:
The single machine-readable result returned by one Agent Foundation invocation before L2 performs durable Turn closure. Its exact variants and fields are not yet frozen.
_Avoid_: Turn Terminal Outcome, final narration, process exit

**Turn Terminal Outcome**:
The unique typed durable L2 lifecycle result for one admitted logical Turn, orthogonal to Proposal, Outbox Command, and external Task outcomes.
_Avoid_: Foundation Execution Outcome, workflow result, external Task result

**Execution Closure**:
The point at which a started Foundation invocation has produced its Foundation Execution Outcome and completed its own cleanup.
_Avoid_: Durable Turn terminal, external Task completion

**Persistence Closure**:
The point at which L2 has durably and idempotently recorded the unique Turn Terminal Outcome for an admitted Turn.
_Avoid_: Iterator exhaustion, best-effort terminal event

**Domain Pack Manifest**:
The versioned declaration that binds a Domain Pack's identity, compatible Domain Agent Definition and Domain Proposal Policy, provided components, required capabilities, permissions, and external ports.
_Avoid_: Workflow DSL, executable plugin script

**Composition Root**:
The application boundary that validates each configured trusted Domain Pack, Workflow Template, Domain Agent Definition, Domain Proposal Policy, and Foundation adapter composition without placing concrete-domain knowledge in either neutral core.
_Avoid_: Domain registry inside Foundation, runtime plugin loader

**Intent Payload**:
The typed domain content of a desired action that an Agent is allowed to propose, excluding identity, authority, target, concurrency, and idempotency claims.
_Avoid_: Proposal Envelope, external command

**Proposal Envelope**:
The trusted request formed by binding an Intent Payload to actual principal, target, lifecycle, version, provenance, and idempotency context for L2 adjudication.
_Avoid_: Model tool arguments, authorization result

**Proposal Factory**:
The trusted runtime component that constructs a Proposal Envelope from an Intent Payload and authoritative invocation references without deciding whether the Proposal is accepted.
_Avoid_: LLM tool, Workflow Engine

**Pure Tool**:
A model-visible operation whose result depends only on its inputs and that does not read or change externally owned state.
_Avoid_: External query, workflow helper

**Read-Only Query Tool**:
A model-visible, capability-governed operation that observes an authoritative external source without changing that source or Workflow Facts.
_Avoid_: GET endpoint, ungoverned client method

**Proposal Tool**:
A model-visible operation that converts domain intent into an Intent Payload for trusted Proposal construction without applying the requested change.
_Avoid_: Command tool, workflow mutation

**Query Result Snapshot**:
A sourced, time-bounded observation returned by a Read-Only Query Tool for Agent reasoning. It remains non-authoritative even when its source is authoritative.
_Avoid_: Workflow Fact, persisted Lab truth

**Proposal Identity**:
The stable trusted identity of one logical proposed action across execution attempts, distinct from the Proposal payload and from later External Command identities.
_Avoid_: Payload hash, attempt ID

**Transition Provenance**:
The durable internal link from an accepted workflow transition and its effects back to the Proposal that requested them.
_Avoid_: Proposal aggregate, UI event kind

**Proposal Outcome**:
The typed result of adjudicating a Proposal against current facts, capabilities, policy, and concurrency conditions. Its exact taxonomy is defined by the reviewed action-state transition catalog.
_Avoid_: LLM narration, HTTP status alone

**Action-State Transition Catalog**:
The exhaustive design record that maps each workflow action and eligible current state to preconditions, Proposal Outcomes, authoritative changes, events, commands, and replay behavior.
_Avoid_: Action enum, happy-path flowchart

**Turn**:
One bounded L2 execution of a single normalized input, beginning when that input is dequeued and ending when L2 durably records its terminal lifecycle result.
_Avoid_: LLM call, conversation, experiment run

**Turn Initiator**:
The authenticated Session member whose admitted user input created a user-triggered Turn, distinct from the Session owner and the current collaboration focus holder.
_Avoid_: Turn owner, current user, focus holder

**User-Triggered Turn**:
A Turn admitted from an explicit authenticated user interaction and associated with a Turn Initiator.
_Avoid_: Any Turn with user-visible output, system callback Turn

**System-Triggered Turn**:
A Turn admitted from MQ, scheduler, reconciliation, or another trusted system stimulus rather than an interactive user action.
_Avoid_: Background thread, user-triggered continuation

**Turn Cancellation**:
An explicit user request to stop further Agent work and output for one identified admitted Turn and close that Turn durably. It is not an SSE disconnect and does not cancel an already committed Outbox Command or Lab/Nexus Task.
_Avoid_: Stop streaming, cancel current session, Lab Task cancellation

**Cancellation Actor**:
The authenticated Principal whose authorized request durably closes a Turn as cancelled, distinct from the Turn Initiator who created that Turn.
_Avoid_: Turn owner, current user, last modifier

**Turn Input**:
The normalized user, system, callback, scheduler, or reconciliation stimulus that is queued with a new Turn identity.
_Avoid_: Prompt, Agent thread

**External Execution Lifecycle**:
The independent lifecycle of an Outbox Command or Lab/Nexus Task after the originating Turn has committed its request.
_Avoid_: Long-running Turn, resumed Turn

**In-Process Contract Isolation**:
A hard capability boundary enforced inside one service process through narrow injected ports, forbidden dependency edges, object-graph validation, and default-deny runtime registration.
_Avoid_: Convention-only layering, process sandbox

**Proposal Port**:
The typed request-response contract through which an active Agent invocation submits a trusted Proposal Envelope for L2 adjudication and receives a typed outcome without accessing L2 implementation or persistence.
_Avoid_: Repository callback, external command client

**Architecture Gate**:
A required automated check that rejects a forbidden dependency, injected capability, object-graph edge, or runtime registration before deployment.
_Avoid_: Design guideline, optional lint warning

**Turn Effect Slot**:
The durable L2-owned single-acceptance guard that allows at most one effectful business Proposal to commit for a Turn while permitting rejected candidate correction before acceptance.
_Avoid_: Prompt instruction, process-local lock

**Business Action Proposal**:
An action-level Proposal that may atomically produce multiple Workflow Fact changes, ordered Session Events, and correlated Outbox Commands without exposing row-level mutations to the Agent.
_Avoid_: One database write, arbitrary batch of independent actions

**Input Admission**:
The L2 transaction that durably validates and accepts one normalized input, records its deterministic fact/receipt consequences, and creates the queued Turn before acknowledging the producer.
_Avoid_: In-memory enqueue, Agent execution

**Admission Receipt**:
The transport acknowledgement returned only after Input Admission commits, correlating the accepted input with its stable Turn without describing the Turn's later execution result.
_Avoid_: Turn result, enqueue acknowledgement

**Admitted Turn**:
A Turn whose immutable input and queued lifecycle have committed and must eventually receive one durable terminal result.
_Avoid_: Rejected request, transient coroutine

**Claim Generation**:
The monotonic internal fencing token on a durable Turn row that grants one current worker authority to submit Proposals, persist outputs, broadcast, and close the Turn.
_Avoid_: Attempt aggregate, public run ID

**Stale Claim**:
A former Turn claimant whose generation is no longer current and therefore has no effect, persistence, terminal, or narration authority.
_Avoid_: Recoverable command, active worker

**Turn Operational State**:
The minimal durable scheduling phase of an admitted Turn: queued, running, or terminal. Success, failure, timeout, and cancellation belong to terminal outcome data instead.
_Avoid_: Workflow status, external Task status

**Outcome Orthogonality**:
The rule that Turn, Proposal, Outbox Command, and external Task outcomes answer separate lifecycle questions and remain correlated without being collapsed into one total status.
_Avoid_: Overall success, cascading status overwrite

**Field Necessity Record**:
The mandatory evidence record for a proposed contract field, naming its consumer, changed decision, information gap, compatibility exposure, and cross-domain/topology stability before schema acceptance.
_Avoid_: Might be useful, speculative metadata

**Turn Execution Deadline**:
The immutable absolute time fixed at first claim by which the logical Turn must stop component work and enter durable L2 closure, shared across all claim generations and internal retries.
_Avoid_: Per-attempt timeout, queue expiry, Lab Task deadline
