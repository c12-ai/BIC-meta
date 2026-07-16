# Current experiment-workflow evidence

## Finding

Current Agent Service already implements most of the agreed v1 product skeleton:

```text
Objective
  -> Plan
  -> [Parameter Design -> Confirmation -> Execution -> Result Analysis -> Result Confirmation]
       across serial Chemistry Steps
  -> workflow finale / ELN eligibility
```

The redesign is not introducing this lifecycle from nothing. It is separating an existing but interwoven combination of reusable experiment progression, Chemistry policy, Agent execution mechanics, persistence, and external execution. Current code is migration evidence, not a contract to promote wholesale.

## Existing lifecycle mapping

| Target concept | Current implementation evidence | Target reuse owner |
|---|---|---|
| Objective | Objective draft/propose/confirmation graph; confirmation advances `experiment_objective -> workflow_design` (`app/runtime/graphs/specialists/objective.py:468-499`, `app/events/bypass_emitted.py:152-209`) | Experiment Workflow Kit lifecycle; Chemistry owns reaction schema and ChemEngine behavior |
| Plan | Plan propose/confirm; confirmation freezes the payload, materializes Jobs, and advances `workflow_design -> parameter_design` (`app/events/runtime_emitted.py:460-574`) | Kit owns ordered Step identities, Plan freeze, and progression; Chemistry owns the Step catalog |
| Parameter Design | Shared recommend/draft/form prototype (`app/runtime/graphs/specialists/_entry_pipeline.py:1-25,91-245`) | Kit owns the lifecycle; Domain Pack owns schemas, recommendation, and validation |
| Confirmation | L2 form reduction is the authoritative parameter write and Trial-phase advance (`app/events/runtime_emitted.py:823-853`) | Kit supplies confirmation semantics; L2 owns facts/transactions; Domain Pack supplies typed payload/policy |
| Execution | Similar specialist submit shells call Lab and persistence directly (`app/runtime/graphs/specialists/tools.py:913-953,1063-1065,1113-1118`) | Kit supplies Step-execution lifecycle; Domain Pack supplies intent and command payload policy; L2/outbox owns effects |
| Result Analysis | Shared CC/RE mechanisms plus TLC/FP variants, followed by result-review confirmation | Kit supplies analysis/review lifecycle; Domain Pack owns evidence meaning, analyzer, and scientific verdict |
| Serial progression | `SessionContext.current_job` / `next_job` and result-review acceptance advance one Plan cursor (`app/core/context.py:193-244`, `app/events/runtime_emitted.py:855-913`) | L2-authoritative Experiment Workflow Kit component |
| Plan completion | Exhaustion is inferred from `next_job is None` and routes to a finale (`app/runtime/graphs/nodes/specialist_dispatcher.py:272-305`) | Target requires an explicit authoritative Plan-completion fact/transition |
| Summary | Finale narration plus a read-only, on-demand ELN projection (`app/eln/service.py:1-7,55-87,163-172`) | Kit supplies summary eligibility/orchestration; Chemistry supplies ELN content; exact durable-artifact model remains separate |

The durable hierarchy is already `session -> experiment -> plan -> jobs -> trials` (`app/core/context.py:137-157`). Specialist working phases are already shared as `collecting_params -> rts -> conducting -> done` (`app/runtime/types/specialist.py:156-166`). These shapes are useful evidence, but their names and current persistence placement are not automatically frozen contracts.

## Existing confirmation and freeze behavior

- Objective confirmation is required before workflow design.
- Plan confirmation is required before parameter design. Proposed Plans have no executable Jobs; confirmation writes the confirmed payload and materializes Jobs.
- Parameter confirmation is the authoritative write that allows execution.
- Result-review rejection does not advance the Step; acceptance is the only path that terminalizes the reviewed execution and advances the Plan cursor (`app/events/runtime_emitted.py:803-913`).
- A confirmed Plan is semantically frozen while its progression cursor remains mutable. Re-confirmation returns before writes and new proposals supersede only recommended/proposed Plans (`app/events/runtime_emitted.py:490-523`, `app/repositories/plans_repo.py:178-225`).
- The freeze is not yet a complete repository/database invariant: generic Plan update methods do not consistently predicate writes on `status != confirmed`. Target L2 policy/CAS must enforce immutability structurally rather than relying on call discipline.
- Job mutation is also insufficiently fenced: the current reconcile/insert repository surfaces can change Job rows without proving the parent Plan remains editable, and cursor advancement does not structurally prove same-Plan membership, monotonic movement, confirmed status, or an expected prior cursor (`app/repositories/jobs_repo.py:202,340`, `app/repositories/plans_repo.py:212-225`).
- Trial reruns already preserve history under one Job by allocating the next `attempt` and enforcing uniqueness on `(job_id, attempt)` (`app/repositories/trials_repo.py:258-329`, `app/data/models.py:405`). This is migration evidence for same-Step Trial rework, not for a Turn Attempt aggregate.
- Multiple Plans per Experiment are technically possible, but current selection and ELN aggregation do not define Revision semantics consistently (`app/session/orchestrator.py:702`, `app/eln/service.py:63`). V1 therefore adds no Revision feature or fields; this evidence only explains why a future product slice must design Revision explicitly instead of inferring it from the current rows.

## Structural gaps to remove during migration

1. **Closed Chemistry catalog.** Plan schemas, prompts, dispatch types, dispatcher branches, and graph factory directly name TLC/CC/FP/RE (`app/runtime/types/plan.py:15-71`, `app/runtime/types/specialist.py:78-153`, `app/runtime/graphs/nodes/specialist_dispatcher.py`, `app/runtime/graphs/factory.py`). Neutral Foundation and the Kit cannot inherit this catalog.
2. **Duplicated graph shells.** Specialist model loops, compilation, stream relay, submit/form/failure nodes, and routing repeat across graphs even though `_entry_pipeline.py` and `_narrate_pipeline.py` have begun extracting shared behavior.
3. **Effect-boundary violation.** L3 submit code captures raw Lab and Persistence dependencies, calls the external command, and writes in transactions. Target Domain code produces typed intent; L2 commits an Outbox Command; only the outbox executor calls Lab/Nexus.
4. **Manual Steps disappear from progression.** Plan confirmation materializes only `type == "robot"` Steps as Jobs (`app/events/runtime_emitted.py:476-483,536-553`), while progression iterates persisted Jobs. Manual Steps therefore cannot participate in the same authoritative Step lifecycle even though the Production PRD requires them.
5. **Implicit Plan completion.** Plan status stops at `confirmed`; exhaustion is inferred from a missing next Job. Target design needs an explicit Plan-completion transition and a clear Summary eligibility rule.
6. **Domain retry leakage.** TLC's bounded Rf retry loop is Chemistry policy. The common Kit may support repeated executions or attempts only after their semantics are separately agreed; it must not standardize TLC's retry count or verdict rules.

## Design implication

The migration should preserve externally visible behavior while extracting two deep common modules: Agent Foundation for execution mechanics and the Experiment Workflow Kit for L2-authoritative serial experiment progression plus reusable L3 phase components. Chemistry supplies Step definitions and scientific policies through its Domain Pack. The Biology validation slice proves the common seams before they freeze.
