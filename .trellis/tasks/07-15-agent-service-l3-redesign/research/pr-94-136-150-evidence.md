# Agent Service PR #94, #136, and #150 evidence

Checked against live GitHub and `origin/main @ 12a84f3`; PR #150 status refreshed on 2026-07-16.

## Current status

| PR | Status | Scope |
|---|---|---|
| [#94](https://github.com/c12-ai/BIC-agent-service/pull/94) | Open, conflicting, review required; head `4d86c17`; 78 files | Input admission plus action-specific, state-aware authorization. |
| [#136](https://github.com/c12-ai/BIC-agent-service/pull/136) | Open, conflicting, review required; head `4e77442`; 95 files | Derived WorkflowBaton, WorkflowEngine, CAS, outbox, narration guard, specialist registry. |
| [#150](https://github.com/c12-ai/BIC-agent-service/pull/150) | Closed 2026-07-16, docs-only; head `62ae747`; superseded by BIC-meta #327 | Historical Agent Foundation / Proposal Layer / Domain Pack proposal and three-round Claude × Codex review record. |

#94 and #136 are not stacked. They share 26 modified files and evolved from different baselines. The historical #150 design treated #136 as a candidate implementation and did not define how #94 converged into the proposal; BIC-meta #327 now owns that cross-repo disposition.

## PR #94

Confirmed value:

- Separates message admission from authorization of a resolved action.
- Defines typed actions, policy outcomes, stable reason codes, HTTP 409 behavior, and telemetry.
- Adds checks at tool runtime, service/CAS, and API layers.
- Review iterations found and repaired bypasses and dead policy branches.

Confirmed limits:

- The central policy file is 1331 lines and imports Chemistry-specific decision, job, trial, specialist, and verdict types.
- Its action/stage/reason taxonomy is a closed Chemistry workflow vocabulary.
- It intentionally reads caller-provided snapshots rather than owning a transaction.
- Policy evaluation and final CAS/apply can occur in different transactions.

Conclusion: valuable defense-in-depth and explainable policy surface, but not the unique transactional workflow authority.

Evidence: [module intent](https://github.com/c12-ai/BIC-agent-service/blob/4d86c178f747aa1da2054e2cbc7dfaf0f97c4be8/app/runtime/workflow_action_authorization.py#L1-L24), [action model](https://github.com/c12-ai/BIC-agent-service/blob/4d86c178f747aa1da2054e2cbc7dfaf0f97c4be8/app/runtime/workflow_action_authorization.py#L26-L220), and [service transaction split](https://github.com/c12-ai/BIC-agent-service/blob/4d86c178f747aa1da2054e2cbc7dfaf0f97c4be8/app/session/service.py#L503-L509).

## PR #136

Confirmed value:

- Derives an immutable WorkflowBaton instead of persisting a second authority.
- Introduces typed WorkflowEngine proposal/effect facades, active-decision/form-version guards, CAS/row locking, stable dispatch command identity, durable outbox records, narration guards, and a specialist registry.
- Establishes a durable command record before the external call.

Confirmed limits:

- The current primary dispatch path still commits the outbox record and then synchronously calls Lab from L3; the background worker is disabled by default.
- The outbox provides at-least-once recovery and depends on Lab honoring the same idempotency key.
- Baton stages, transitions, specialist kinds, and graph composition remain hard-coded to objective -> plan -> TLC -> CC -> FP -> RE.
- The graph factory still wires every specialist explicitly rather than composing from a domain contract.

Conclusion: a serious Chemistry workflow-authority consolidation, not yet a cross-domain platform or final Proposal Layer.

Evidence: [Baton](https://github.com/c12-ai/BIC-agent-service/blob/4e7744268a2069f998b4c73e0b7f67bf7e787422/app/workflow/baton.py#L21-L199), [Engine](https://github.com/c12-ai/BIC-agent-service/blob/4e7744268a2069f998b4c73e0b7f67bf7e787422/app/workflow/engine.py#L327-L402), [dispatch path](https://github.com/c12-ai/BIC-agent-service/blob/4e7744268a2069f998b4c73e0b7f67bf7e787422/app/runtime/graphs/specialists/tools.py#L960-L1051), and [registry](https://github.com/c12-ai/BIC-agent-service/blob/4e7744268a2069f998b4c73e0b7f67bf7e787422/app/workflow/specialist_registry.py#L13-L124).

## PR #150 historical proposal

The proposal separates:

- Agent Foundation: reusable execution, context, streaming, telemetry, and governed extension seams.
- Proposal Layer: the deterministic boundary from probabilistic output to authorized/CAS/idempotent/transactional change.
- Domain Pack: versioned domain schemas, workflows, specialists, prompts, forms, policies, adapters, evidence, and reports.

Its strongest retained decisions are the authority hierarchy, no business snapshots in checkpoints, effectful outputs becoming typed proposals, the Framework Ruling at `62ae747`, and the rolling-summary produce/load commitment.

Wenlong closed #150 on 2026-07-16 with a pointer to BIC-meta #327. The canonical cross-repo design supersedes #150; its branch remains historical evidence of the three-round Claude × Codex convergence. #327 inherits only the ruled Framework Ruling and rolling-summary commitment explicitly, not #150's earlier Biology-first order or broader Foundation scope.

Evidence: [closed PR and supersession comment](https://github.com/c12-ai/BIC-agent-service/pull/150#issuecomment-4989438269), [retained branch head](https://github.com/c12-ai/BIC-agent-service/blob/62ae7471d703bf85957c12e348b236f3f78cfc05/docs/agent-foundation-refactor-design.md), and the Feishu documents listed in `source-inventory.md`.
