# Close lab-logistics maintenance gaps vs research

## Status

- Owner: Drake
- State: planning (parent task — owns the requirement set and integration review; no direct implementation)
- Source review: 2026-07-05 session — gap analysis of the shipped 07-05-lab-logistics-maintenance work against the reviewed research docs.

## Background / Source Requirements

The shipped TLC/CC lab-logistics work (portal `d4a32602`, lab-service `48eccf8`) is internally
consistent with the robot dispatch contract but diverges from the reviewed research:

- 交互文档-物料准备和耗材维护 (Feishu wiki `KS6kw4WLPiyIYbkn1f3c98SSn3b`; saved copy
  `~/Downloads/交互文档-物料准备和耗材维护.md`)
- 实验室信息维护配置表 (embedded wiki `AKmcweV5iiorPWkQTY1cBdWOnxc`; saved copy
  `~/Downloads/实验室信息维护配置表.md`)

Identified gaps:

1. **Specific-item stock has no maintenance surface.** The 配置表 places TLC 样品管盒 (有特殊性)
   on TLC Rack L1+L2 RIGHT (5 box slots per floor, 5×4 cells). The consumables page shows them
   read-only (correct — it maintains only 无特殊性); the Material Preparation popup maintenance was
   narrowed to `source=bench` only. Result: the shelf stock is editable nowhere.
2. **The bench dispatch box is not in the reviewed config source.** `tlc_tube_box_2ml_slot_{1..3}`
   exists only in the robot contract/implementation; the 配置表 has no row for it, violating the
   Production PRD rule that layout/material classification is driven by the reviewed source. There
   is also no explained relationship between shelf stock and the bench box in any surface.
3. **Assignment semantics inverted vs the interaction doc.** Doc: 分配槽位 = click an EMPTY slot
   (只能点击空位). Implementation (CC and TLC alike): select the FILLED/maintained item; empty
   slots are filled in maintenance mode. Recorded as a Production PRD open question, resolved in
   code without a closed product decision.
4. **Tube count contract.** Doc: 样品管 1-or-2 (demo passes one). Shipped contract: 2–4, one box,
   one row, contiguous, starting at column 1.

## Decisions (Drake, 2026-07-05)

- **D1**: The Material Preparation popup maintains BOTH shelf storage boxes and the bench dispatch
  box. Selection stays bench-only. The bench box is added to the reviewed 配置表.
- **D2**: Maintain-then-select stays. Assignment = selecting an already-maintained physical item;
  empty slots are filled in maintenance mode. PRD and interaction doc are updated to close the
  open question this way (applies to CC and TLC uniformly).
- **D3**: 2–4 tubes is CONFIRMED as the contract. The interaction doc's 1-or-2 is stale and gets
  updated. No relaxation work.
- **D4** (2026-07-05, supersedes D1's "selection stays bench-only"): TLC sample tubes are
  SELECTED from the SHELF box; the robot carries the box shelf→bench itself (protocol stage-1
  取料 carries 2ml box, 50ml box, and both tip boxes). Coordinates in the doc are examples — the
  service resolves real coordinates from the selected/allocated instances' inventory placement.
  Bench 2ml slots are robot-internal parking, not a chemist surface. Shelf maintenance from D1
  stands and becomes the primary surface; only the bench-selection premise is replaced. Child:
  `07-05-tlc-select-from-shelf`.

## Task Map

| Child | Repo(s) | Deliverable | Depends on |
|---|---|---|---|
| `07-05-prd-reconciliation` | root + portal docs | PRDs/doc updates codifying D1–D3, bench-box config row drafted | decisions only |
| `07-05-lab-shelf-tube-maintenance` | BIC-lab-service | cell maintenance generalized to shelf storage boxes, seed/config alignment | — |
| `07-05-portal-shelf-bench-maintenance` | BIC-agent-portal | popup maintenance shows shelf + bench groups; selection unchanged | lab child's endpoint |
| `07-05-tlc-select-from-shelf` | BIC-lab-service + BIC-agent-portal + PRDs | selection moves to shelf; coordinate resolution for all shelf-fetched materials; bench group removed from chemist popup | both code children |

## Cross-child Acceptance Criteria (integration review)

- [ ] Every 有特殊性 inventory listed in the 配置表 has exactly one maintenance surface: the
      Material Preparation popup. The consumables page maintains only 无特殊性 areas.
- [ ] The shelf-vs-bench split is visible and explained in the TLC popup; the robot's pick source
      is labeled.
- [ ] No PRD open question remains for assignment semantics or tube count; the interaction doc's
      stale statements are flagged or corrected at the source (Feishu) or explicitly superseded in
      the PRD.
- [ ] Focused portal + lab-service checks green; one live-bench TLC pass (bic-e2e-runner) after
      both code children land.

## Out of Scope

- Stock→bench transfer flow (rejected in D1 — two maintenance taps achieve the move).
- Any 1-tube dispatch support (rejected in D3).
- RE/FP special-item modules (unchanged scope from the shipped work).
