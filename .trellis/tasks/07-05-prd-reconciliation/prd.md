# Reconcile PRDs and research docs with shipped lab-logistics model

Parent: `07-05-lab-logistics-gap-remediation` (decisions D1–D3 recorded there). Lightweight,
doc-only — PRD-only planning is sufficient.

## Goal

Close the two recorded Production PRD open questions and codify the shelf/bench inventory model so
the PRDs, the interaction doc, and the shipped implementation agree.

## Requirements

1. **Root `Production-PRD.md`**
   - Codify the two-class material model: 有特殊性 (specific) / 无特殊性 (non-specific); note
     "unique" is the retired name for specific — there is no third tier.
   - Introduce the **bench dispatch box** as a product concept: the robot picks TLC sample tubes
     only from the Workspace bench 2ml box slots; TLC Rack shelf boxes are maintained stock. The
     Material Preparation popup maintains both; selection/dispatch uses bench only (D1).
   - Close open question "assign slot semantics": assignment = selecting an already-maintained
     item; empty slots are filled in maintenance mode; applies to CC and TLC uniformly (D2).
   - Close open question "TLC tube quantity": 2–4 in one box, one row, contiguous, starting at
     column 1 is the confirmed contract; remove the 1-or-2 caveat (D3).
   - Update the affected Acceptance Criteria and Change Log.
2. **Portal `docs/project-prd.md`**: mirror the shelf/bench split and the two closed decisions at
   the portal-owned level of detail (surfaces, gating, labels).
3. **Reviewed config source (配置表)**: draft the bench-dispatch-box row (location naming, slot
   count 3, box grid 5×4, 有特殊性, workspace area) for Drake to submit to the Feishu table;
   record in the PRD that the config source now covers it. The draft lives in this task's
   `research/` until submitted.
4. **Interaction doc staleness**: list the superseded statements (1-or-2 tubes; click-empty-slot
   assignment) in the Production PRD so the Feishu doc can be corrected at source; do not silently
   diverge.

## Constraints

- Follow the `prd` skill for placement decisions (root vs child PRD).
- No code changes in this task.

## Acceptance Criteria

- [ ] Production PRD has no open question for assignment semantics or tube count.
- [ ] Production PRD defines the bench dispatch box and the shelf-stock relationship; the
      integrity rules section still holds (no placeless records).
- [ ] Portal project PRD matches the root PRD (no contradiction between the two).
- [ ] Bench-box 配置表 row drafted and stored under `research/`.
- [ ] Change Logs updated in both PRDs with date and decision references.
