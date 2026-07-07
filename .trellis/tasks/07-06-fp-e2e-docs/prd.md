# FP e2e coverage and PRD updates

Parent: `07-06-fp-agent-program`. Runs after both sibling children land.

## Status (2026-07-07) — ALL GREEN, uncommitted

Both E2E specs PASS clean solo on the live bench:
- `fp-chain-flow.spec.ts` (FP feature: params → dispatch → result card → RE prefill): PASS 7.2m.
- `cc-re-chained-flow.spec.ts` (full TLC→CC→FP→RE, 5 task_created): PASS 5.4m.

Gates green all three repos: BIC-agent-service (ruff/pyright 0/pytest 1030), BIC-agent-portal (tsc/biome 6 pre-existing warnings/vitest 100), BIC-shared-types (ruff/examples 21/pytest 261).

Bugs found+fixed getting here (all invisible to unit tests, only the live chain caught them): (1)+(2) L2 service.py + reception_node.py kind-maps missing fp arm (params confirm 422); (3) fp conducting had no query_l4_status tool → LLM hang; (4) fp instant-terminal MQ NACK-drop race → durable lab_task_id persist in _submit_l4; (5) R5's RE dead-field removal left RE zero material requirements → MaterialPreparationPanel conflated zero-req with load-failure → RE validate stuck (fixed via requirementsResolved). Production-PRD rule 11 + FP UI/result rules added.

Remaining: commit (awaiting Drake's authorization) across BIC-agent-service (feat/fp_agent), BIC-agent-portal, BIC-shared-types; external non-blocker BIC-lab-service issue #81 (multi-flask cap).

## Goal

Prove the full robot chain TLC → CC → FP → RE end-to-end, remove stale FP-skip assumptions from existing specs, and record the FP product rules in the Production PRD.

## Requirements

- New Playwright spec: full robot chain including FP params confirm (1-flask config), dispatch, and FP result card acceptance; run against the live bench per the `bic-e2e-runner` playbook.
- Fix stale assumptions: `cc-re-chained-flow.spec.ts` documents/asserts a CC→RE jump because the FP stub was skipped — update to the real CC→FP→RE flow.
- Production-PRD (use the `prd` skill): close the rule-10 clause "RE and FP … surfaces remain out of scope until their execution parameters are finalized" for FP; add FP interaction rules (container model, upper/lower panels, rack grid) and result rules (mapping table, 15 ml/tube volume math, FP→RE basis handoff); change-log entry.
- Verify no other spec or fixture still encodes FP-as-skipped (grep pass).

## Acceptance Criteria

- [ ] Full-chain robot spec green on the bench; FE suite green (LLM specs --workers=1).
- [ ] No spec/fixture asserts FP is skipped.
- [ ] Production-PRD updated with FP rules + change log; `prd` skill routing respected.

## Notes

- Lightweight: PRD-only is acceptable for this child.
