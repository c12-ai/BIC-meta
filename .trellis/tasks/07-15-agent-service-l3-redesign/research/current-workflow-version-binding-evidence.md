# Current workflow-version-binding evidence

## Scope

This note records the current Agent Service behavior-selection mechanism relevant to workflow-lifetime Domain Pack and Workflow Template version binding. Evidence is from `BIC-agent-service` `main` at commit `12a84f3238a9`; current code is migration evidence, not the target contract.

## No workflow entity carries a behavior binding

The authoritative hierarchy has no domain, Domain Pack, Workflow Template, or behavior-version field:

- `app/data/models.py:167-212` defines `Experiment` with identity, Session, Objective kind/name/payload, stage, and start time only.
- `app/data/models.py:215-269` defines `Plan` with Experiment identity, status, cursor, params, and creation time only.
- `app/data/models.py:272-321` defines `Job` with Plan identity, order, executor, title, outcome/review state, and creation time only.
- `app/data/models.py:324-405` defines `Trial` execution/analysis state without a workflow behavior binding.
- `app/repositories/experiments_repo.py:36-75` and `app/repositories/plans_repo.py:45-81` mirror those rows into strict snapshots without version metadata.

The current hierarchy can identify an Experiment, Plan, Step, and Trial, but cannot answer which scientific Agent/Policy behavior or shared Workflow Template should process the next Turn.

## One deployment-global Runtime selects behavior implicitly

Application lifespan constructs one concrete `Runtime` at `app/main.py:68-108`, stores it globally at `app/main.py:174-177`, and injects it into the single orchestrator. `Runtime.__init__` compiles one concrete graph once at `app/runtime/runtime.py:135-169`. The factory directly constructs the current Chemistry Objective, Plan, CC, RE, TLC, and FP graphs in `app/runtime/graphs/factory.py:345-451`.

For every Turn, the orchestrator loads current context and calls the same global instance at `app/session/orchestrator.py:350-365`. It does not load a domain or behavior binding before invocation.

Consequences:

1. Deploying or restarting with changed graph, prompt, Step, or policy code silently changes the behavior used by every unfinished workflow.
2. A canary/default route can select a process version but does not become an authoritative, replayable Workflow Fact.
3. A rollback cannot determine the required behavior from an Experiment row; operators must infer it from deployment history.
4. Session Events can replay user-visible progress but do not pin the Agent/Policy/Template implementation that should handle the next Turn.

## Target implication

This gap becomes a blocking production concern only when experiments must remain active across Agent Service releases. Current bench and field operations can finish or reset old-path workflows before the one-time cutover, so v1 does not add binding persistence, legacy backfill, cohort routing, or version retention. ADR-0035 must resolve immutable identity, retained versions, rollback, in-flight Proposal/Command behavior, migration, and history semantics before the first production deployment that requires cross-release workflow survival.
