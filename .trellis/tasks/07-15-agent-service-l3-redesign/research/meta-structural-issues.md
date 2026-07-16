# Meta structural-issue evidence

## Structural families

The evidence does not show a single directory-layout problem. It shows missing or unenforced invariants across several families:

| Evidence | Failure mode |
|---|---|
| [Meta #131](https://github.com/c12-ai/BIC-meta/issues/131) | Umbrella review groups 124 issues into state ontology, Mind boundaries, evidence flow, parameter provenance, turn outcomes, cross-service lifecycle, form runtime, conversation expectations, and live/snapshot projection. |
| [Meta #128](https://github.com/c12-ai/BIC-meta/issues/128) | Lab Task, Agent trial, execution result, analysis verdict, and workflow outcome have been conflated, producing live/snapshot and progress contradictions. |
| [Meta #138](https://github.com/c12-ai/BIC-meta/issues/138) | A missing single-active-decision/supersede invariant permits stale confirmation and duplicate trials/forms. |
| [Meta #48](https://github.com/c12-ai/BIC-meta/issues/48) | Several event reducers are not idempotent and fail under duplicate application. |
| [Meta #49](https://github.com/c12-ai/BIC-meta/issues/49) | An MCP call can emit duplicate tool results, violating tool-call/result 1:1. |
| [Meta #46](https://github.com/c12-ai/BIC-meta/issues/46) | Live form-confirm events can omit accept/reject semantics and disagree with the later snapshot. |
| [Meta #115](https://github.com/c12-ai/BIC-meta/issues/115) | Evidence propagation depends on per-field cross-repo allowlists, causing CC images to disappear before analysis. |
| [Meta #109](https://github.com/c12-ai/BIC-meta/issues/109) | A stalled LLM turn has no structural watchdog or guaranteed typed terminal outcome. |
| [Meta #261](https://github.com/c12-ai/BIC-meta/issues/261) | SSE cursor and replay-too-old recovery semantics remain incomplete. |
| [Meta #194](https://github.com/c12-ai/BIC-meta/issues/194), [#281](https://github.com/c12-ai/BIC-meta/issues/281) | Narration and context assembly have multiple mirrored paths, so new specialists pay a governance-copy tax. |

## External product constraints

`Production-PRD.md` makes the following behavior higher authority than internal graph topology:

- Portal owns the user surface; Agent Service owns copilot/orchestration; Lab owns LIMS and physical orchestration (`Production-PRD.md:11-17`).
- Objective, workflow, and execution parameters require human confirmation (`:43-55`).
- Workflow order remains objective -> plan -> parameters -> logistics -> dispatch (`:192-210`).
- Nexus/Lab owns physical status; Agent output cannot fabricate it (`:57-64`).
- Workflow/session/task identifiers remain correlated across Portal, Agent, and Lab (`:66-73`).
- Evidence remains explicit, visible, and traceable; missing data cannot become placeholder fact (`:52-69`).
- Locale propagates while machine keys, IDs, SMILES, units, and protocol identifiers remain stable (`:125-140`).
- ELN export is gated on confirmed results and is a deterministic aggregation (`:98-123`).
- Shared cross-repo protocols are governed in BIC-shared-types, not changed unilaterally by Agent Service (`:513-517`).

## Design implications, not yet decisions

- Retaining L1-L4 names alone will not resolve structural problems; dependency and authority rules must become enforceable contracts.
- External compatibility includes REST, SSE live/snapshot/replay, MQ/HTTP with Lab, shared schemas, identity correlation, and artifact propagation.
- Memory, Skill, or MCP extensions must not introduce new mutation, event, or narration bypasses.
- A future Biology product will require separate external domain-contract work even if this internal refactor remains wire-compatible for the current Chemistry product.
