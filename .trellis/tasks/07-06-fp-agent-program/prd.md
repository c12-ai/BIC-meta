# FP Agent End-to-End — Parent PRD

## Status

- Owner: Drake
- Created: 2026-07-06
- Role: parent task — owns the requirement set, task map, and cross-child acceptance criteria. Implementation happens in the child tasks.

## Problem

The fixed workflow is TLC → CC → FP → RE, but the FP (fraction preparation / 组分收集) step has no agent: robot FP is classified `"stub"` (`BIC-agent-service/app/runtime/types/specialist.py:137`) and the dispatcher ends the turn with no trial, no form, no dispatch (`specialist_dispatcher.py:113`). The portal renders a placeholder param form and blocks FP from the material-prep dialog. Meanwhile the lab service is fully dispatch-ready for `fraction_preparation` (verified 2026-07-06: task creation, validation, resolver, robot mock, readiness rule, seed data, API tests).

## Requirements (decided by Drake, 2026-07-06)

### R1 — Container-based parameter model
- Execution params = `containers[]`, each `{id, type: flask|waste, name, tubes[]}`.
- Default containers: one flask named `烧瓶1` + one waste named `废液瓶`.
- User can add flasks; container names ≤ 5 characters.
- Multi-flask is supported by the model BY DEFAULT. The portal operator (Drake) will manually configure only ONE flask until the robot team confirms multi-flask capability (tracked in a BIC-lab-service GitHub issue — see Dependencies).

### R2 — Recommendation comes from upstream, no independent basis field
- The FP recommendation basis is the upstream CC analysis result, carried VERBATIM — FP adds no new information (Drake review 2026-07-06). The CC result contains multiple ranges with per-row status: several `product` rows are possible, plus `suspect` and `waste` rows (`CcEvidence.fractions: FractionRow[]` + per-well `rack: RackTube[]`).
- FP has no independent "recommendation basis" field; the agent pre-fills from well statuses: `product` wells → 烧瓶1, `suspect` + `waste` wells → 废液瓶, `idle` wells unassigned. The user can re-assign any well.
- No ChemEngine involvement anywhere in FP (no MindClient FP endpoint exists; result data is synthesized agent-side).

### R3 — Parameter Design FP tab layout (portal)
- Upper panel: read-only display of the upstream CC task analysis result.
- Lower panel: container configuration — select a container, then assign tubes to it.
- Tube-rack grid view: 96-well / custom layout; clicking a well circle adds/removes that tube from the currently selected container; live display of the selected tube list and total count.

### R4 — FP result evidence and volume math
- FP result = container → tube mapping table: which tubes went to each flask / waste, with peak classification (主峰 / 边缘峰 / 杂质).
- Volume is computed at 1 tube = 15 ml (e.g. 5 tubes collected = 75 ml, 3 discarded = 45 ml).
- Evidence carries actual combined liquid volume and the solvent system ratio so the downstream RE recommendation basis is auto-filled.
- A dedicated FP result card appears under the task result (result-review fanout), like other steps.
- The robot/lab report NO structured fraction result (terminal status + entity updates only, no images — verified). The agent synthesizes `FpEvidence` locally from the confirmed container config + CC fraction rows.

### R5 — RE dead-field migration (surfaced conflict, Rule 5)
- shared-types v1.2.0 moved `flasks`/`collect_config` from `CreateRETaskRequest` to `CreateFPTaskRequest`; RE dispatch already omits them (`specialists/tools.py:526`).
- But the RE form still collects them (`RELabLogistics`, `update_re_lab_logistics` tool, FE ReForm) — dead fields shown to the chemist.
- This program moves that responsibility into the FP form and removes it from RE (BE + FE), keeping the newer split pattern.

## Task map

| Child | Scope | Order |
|---|---|---|
| `07-06-fp-agent-specialist` | BE: fp subgraph, routing, tools, dispatch, evidence synthesis, RE lab-logistics removal | 1 — owns the FE↔BE contract |
| `07-06-fp-portal-surfaces` | FE: FP param form (upper/lower panels + rack grid), material-prep enablement, FP result card migration, ReForm cleanup | 2 — consumes the contract |
| `07-06-fp-e2e-docs` | E2E robot-chain spec, fix stale FP-skip assumptions, Production-PRD updates | 3 |

External (not a child): GitHub issue on BIC-lab-service for multi-flask robot capability + collect_config indexing semantics.

## Cross-child acceptance criteria

1. A robot-typed FP step produces a real specialist run: trial minted, params form emitted, user confirm → dispatch to lab service, terminal status consumed, FP result card rendered. The stub disposition is gone.
2. The FP params form shows upstream CC analysis (upper) and container/tube assignment (lower) with the rack grid; default containers 烧瓶1 + 废液瓶; names ≤ 5 chars; a tube belongs to at most one container.
3. Dispatch maps containers → `CreateFPTaskRequest` (`flasks[]` ordered, `collect_config` 0=discard / N=flask ordinal); with one flask configured, dispatch succeeds against the live lab service.
4. FP result card shows the mapping table with peak classification and 15 ml/tube volume math; totals (collected/discarded) and solvent system present; RE recommendation basis (volume + solvents/ratio) is auto-filled from FP evidence when RE follows.
5. RE form no longer collects flasks/collect_config anywhere (BE tool, form payload, FE form).
6. E2E: full robot chain TLC → CC → FP → RE passes; no spec still assumes FP is skipped.
7. Production-PRD: FP "out of scope until execution parameters are finalized" clause closed; FP interaction + result rules recorded.

## Out of scope

- Multi-flask dispatch against the real robot (blocked on the lab-service GitHub issue answer; model supports it, portal operator configures 1 flask).
- Any lab-service code change (verified zero-gap; readiness/API tests already exist).
- shared-types changes (contract v1.2.0 already complete).

## Dependencies / risks

- BIC-lab-service GitHub issue: robot multi-flask capability, max flask count, and exact `collect_config` indexing semantics vs rack positions. Portal single-flask convention de-risks execution until answered.
- Research base: memory `project_fp_agent_plan` + this session's verified findings (every load-bearing claim checked at file:line in-session).
