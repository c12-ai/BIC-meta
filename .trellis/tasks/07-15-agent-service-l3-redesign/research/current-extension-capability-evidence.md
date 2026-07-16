# Current extension-capability evidence

## Scope

This note records the current Agent Service implementation evidence relevant to future Agent Memory, Domain Skills, MCP operations, context contribution, and tool-governance seams. It describes `BIC-agent-service` `main` at commit `12a84f3238a9`; the current code is migration evidence, not the target contract.

## Context and memory are fixed, not composable

The production context path is one hard-coded L2 loader and one fixed shared structure:

- `app/session/orchestrator.py:511-620` loads Session, Experiment, Plan, Jobs, Trials, decisions, recent conversation, locale, and the Chemistry form draft in one method.
- `app/core/context.py:30-35` imports repository snapshot types directly, and `app/core/context.py:138-183` defines the fixed `SessionContext`, including `ChemistFormDraft`.
- No `ContextContributor`, contribution registry, or composition contract exists under `app/`.

Current production “memory” is recent conversation history rather than a general memory capability:

- `app/repositories/session_events_repo.py:61-68,215-244` selects only conversational event kinds and returns at most the latest 50 events.
- specialist, Plan, and Objective rehydration rebuild the returned history independently in `app/runtime/graphs/specialists/rehydrate.py:27-40`, `app/runtime/graphs/plan/rehydrate.py:28-39`, and `app/runtime/graphs/specialists/rehydrate_objective.py:28-40`.
- token budgeting is implemented only by the narration assembler in `app/runtime/graphs/_rehydrate.py:92-124,158-230`.
- `app/session/conversation_summary.py:23-126` contains a structured rolling-summary fold, but `app/session/orchestrator.py:606-620` does not populate it and no production producer completes the loop. `docs/context-management-design.md:148-161` also records this integration as unfinished.

Prompt and context construction is spread across several paths: narration (`app/runtime/graphs/_rehydrate.py:158-230`), user admission (`app/runtime/graphs/nodes/user_admittance.py:111-135`), intent detection (`app/runtime/graphs/nodes/intent_detection.py:185-206`), and specialist middleware (`app/runtime/middleware/dynamic_prompts.py:825-1045`). The specialist middleware also imports and names Chemistry concepts directly at `app/runtime/middleware/dynamic_prompts.py:23-25,39-55`.

Existing logic suggests a target ownership split without freezing exact interfaces:

| Existing behavior | Candidate target owner |
|---|---|
| recent-history identity, deduplication, budgeting, protected blocks, locale handling | Agent Foundation context assembly |
| Objective, Plan, Step, Trial, confirmation, and cursor facts | Experiment Workflow Kit context contribution |
| domain draft, prior scientific facts, evidence rendering | Domain Step Definition context contribution |
| external Lab or provider facts | governed Query capability contribution |
| any future retained Agent knowledge | lower-authority Memory Context Contribution |

## MCP support exists as disconnected transport code

`app/runtime/tools/registry.py:43-101` converts an MCP descriptor into a LangChain `StructuredTool`, and `app/runtime/tools/registry.py:104-119` lists and wraps every operation returned by the server. `app/infrastructure/mcp_client.py:39-86` is a stateless transport adapter, and the application lifespan constructs it at `app/core/lifespan.py:165-166`.

This path is not active in production:

- `app/main.py:96-107` passes `intent_tools=[]`.
- `app/runtime/graphs/factory.py:345-368` discards the parameter.

The registry also lacks the target authority metadata: it has no local per-operation effect classification, allowlist, stable collision policy, capability declaration, provenance contract, or proof that a discovered operation is read-only. A server-level trust decision would therefore expose more authority than the target model permits.

The live Query Agent follows another path. `app/runtime/graphs/nodes/query_agent.py:187-260` binds `LabClientProtocol` directly and uses a hard-coded intent-to-collector tree; the same module mixes retrieval, filtering, aggregation, formatting, and LLM composition. `_safe_lab_method` uses string-based `getattr` at `app/runtime/graphs/nodes/query_agent.py:1758-1774`, so the consumer does not receive a statically narrow read capability.

## Agent Skills do not exist in the current runtime

There is no Agent Skill manifest, discovery mechanism, registry, or execution contract. Existing `SkillType` occurrences describe robot commands and are unrelated to Agent behavioral Skills.

The closest current extension mechanisms are global Chemistry catalogues and factories:

- `app/runtime/graphs/specialists/tools.py:177-229` maps phases to globally named Chemistry tools.
- `app/runtime/graphs/specialists/tools.py:1438-1457` closure-binds Mind, Lab, MinIO, and Persistence for CC, with separate bespoke catalogues for RE and FP.
- effectful paths such as `_submit_l4` combine external calls, event emission, and direct persistence at `app/runtime/graphs/specialists/tools.py:991-1124`.

These paths demonstrate why a future Skill must contribute only typed prompt, context, and classified tools under a granted capability set. They are not a Skill interface to preserve.

## Reusable middleware kernels exist, but composition is repeated

Several mechanisms are credible Agent Foundation inputs:

- bounded model retry: `app/runtime/middleware/llm_error_handling.py:41-143`;
- repeated-failure loop breaking: `app/runtime/middleware/loop_detection.py:133-232`;
- tool exception normalization: `app/runtime/middleware/tool_error_handling.py:49-110`;
- once-per-Turn terminal-tool fencing: `app/runtime/middleware/terminal_once.py:121-220`.

Other middleware mixes generic mechanics with concrete workflow or Chemistry behavior:

- `app/runtime/middleware/guardrail.py:44-101,120-186` knows concrete submit/cancel rules and `SpecialistState`;
- `app/runtime/middleware/after_tool.py:40-50,83-135,195-235` knows concrete graph states, Plan payloads, and Chemistry recommendation tool names;
- `app/runtime/middleware/dynamic_prompts.py` combines Foundation rules, Experiment Workflow language, Chemistry Steps, and context rendering.

Plan, Objective, CC, RE, TLC, and FP graphs each assemble the safety middleware sequence manually. This supports one Foundation-owned host and ordering invariant; a Domain Pack or Skill must not receive an arbitrary middleware hook that can omit or reorder it.

## Current extension blast radius

Adding a domain or Step currently requires edits to shared runtime modules:

- closed specialist kinds and executor mapping in `app/runtime/types/specialist.py:78-114`;
- the global phase/tool map in `app/runtime/graphs/specialists/tools.py:188-229`;
- fixed dispatcher routing in `app/runtime/graphs/nodes/specialist_dispatcher.py:64-80`;
- explicit specialist construction in `app/runtime/graphs/factory.py:377-451`;
- Chemistry names in `app/runtime/middleware/dynamic_prompts.py:46-55`;
- the common `SessionContext` and L2 loader.

The current extension mechanism is therefore “edit the shared runtime in several places,” not governed composition.

## Design implications

1. Memory, Skills, and MCP should adapt into existing typed context, Pure Tool, Query, Proposal, and Outbox seams rather than share a generic invocation bus.
2. Composition must default-deny and grant only declared operations; no consumer receives a raw Store, MCP client/session, credential, provider registry, repository, or general network client.
3. MCP trust and effect classification must be per operation, not per server. Discovery or transport does not confer read-only authority.
4. Agent Memory reads remain lower-authority context. The dormant conversation-summary code is useful migration evidence but is not a production general-memory implementation.
5. A Domain Skill is a typed static behavioral contribution under existing authority; it is not a graph, middleware, authorization, or command-execution plugin.
6. Foundation v1 validates the geometry through non-production Capability Conformance Fixtures while shipping only neutral seams that migrated Chemistry or the Biology validation slice exercises before contract freeze. The fixtures do not approve production Memory, Skill, or MCP runtimes or freeze feature-specific provider interfaces.
