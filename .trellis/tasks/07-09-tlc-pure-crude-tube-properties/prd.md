# TLC lab logistics: pure/crude tube assignment with inventory properties

Standalone task (Drake, 2026-07-09). Cross-repo: BIC-lab-service (schema + API), BIC-agent-portal
(TLC Lab Logistic panel + CC assignment semantics), BIC-agent-service (ELN report only). No
robot-protocol / shared-types change; no ChemEngine involvement.

## Goal

In the TLC Lab Logistic panel the chemist declares which sample tubes hold 纯品 (pure) and 粗品
(crude) and exactly where they sit in the shelf sample-tube box. Lab-service persists per-tube
experiment properties so the portal can display them and the ELN report can include them.
Assignment semantics change from maintain-then-select to **select = insert** — for BOTH TLC sample
tubes and the CC sample column (Drake, 2026-07-09).

## Requirements

1. **Portal — TLC Lab Logistic panel interaction (new assignment model)**
   - Two add actions: 添加纯品 and 添加粗品. After clicking one, the user clicks an EMPTY
     ("white") slot in the shelf sample-tube box grid to place that tube there.
   - **Select = insert.** Clicking an empty slot inserts the tube inventory row AND assigns it to
     the current experiment in one act. No separate maintain-then-select step.
   - Any mix of 纯品/粗品 counts is allowed (Drake, 2026-07-09: "we don't care how many").
   - Shape rules validating the final placement (root PRD rule 9, as revised mid-task by the
     2026-07-09 columns-freed ruling): 2–4 tubes total, ONE box, one row, any DISTINCT cells.
     The contiguous-from-column-1 rule was removed by Drake's ruling (labrun v5 reference);
     the lab-service validator was relaxed in Drake's parallel labrun session.
   - Ordering: direction left → right, 1st tube = 纯品, last tube = 粗品. **Assumption (flag at
     review):** interpreted as pure tubes occupy the leading (left) columns and crude tubes the
     trailing (right) columns — no interleaving.

2. **Portal — CC sample column switches semantics too**
   - CC sample-column assignment also becomes select-empty-cell = insert + assign (Q1 answer).
   - Semantics switch only: CC gets NO purity labels; persistence follows CC's existing
     sample-column model.

3. **Lab-service — inventory model + API**
   - `tlc_inventory` gains a nullable jsonb column `properties`, written when the tube row is
     inserted, holding at least: `exp_id`, `exp_name`, `purity` (纯品/粗品). The column is a
     property bag — more fields may be added later without migration.
   - Insert/assignment API accepts these properties; existing read APIs expose them so the portal
     can render purity labels.
   - Alembic migration; `seed.py` / `0002_seed_test_data.py` stay in sync (seed tubes carry no
     properties).

4. **Agent-service — ELN report**
   - The exported ELN report includes the pure/crude tube information for the TLC stage.
     Missing data is omitted, never fabricated (root PRD requirement 10 pattern).

5. **Production PRD revision (rule-10 compliance — same change set)**
   - Rule 8 ("maintain-then-select; selection must never create inventory") is REVERSED for both
     CC and TLC: revise it plus the matching acceptance criteria ("Selecting an item for a task
     never creates inventory; empty slots/cells change only in maintenance mode").
   - The TLC Lab Logistic UI requirements section gains the pure/crude add-button interaction.
   - Rule 9's shape rule stays; add the purity-ordering rule next to it.

## Scope Extension (Drake, 2026-07-09 evening)

6. **Right panel scoped to the job's specific-item surface only.**
   - TLC → the 2ml shelf sample-tube boxes; CC → the sample-cartridge slot area; FP → no right
     panel (its card is auto-pick-only, root PRD rule 10). No other rack areas render.
   - If the header rack-filter control becomes a no-op after scoping, remove it from this
     module (report what was done).
7. **Remove the "Enter Maintenance" button from the lab-logistics module.**
   - Select-empty = insert is the ONLY add path; undo (click own assignment) is the only
     removal path in this module. All maintenance-mode UI paths inside the module are removed.
   - The Consumable Maintenance page's own maintenance mode is UNAFFECTED (root PRD rule 1).
   - OPEN QUESTION (flagged, not blocking): stale-stock cleanup (other experiments' leftover
     tubes; shelf-box add/remove) now has NO chemist surface anywhere — the lab-service
     endpoints remain but nothing calls them from the UI. Needs a future product decision.

## Resolved Decisions (Drake, 2026-07-09)

- **Q1 — reversal scope:** CC switches too. Select-empty-slot = insert applies to TLC sample
  tubes AND the CC sample column.
- **Q2 — counts/shape:** no constraint on how many 纯品 vs 粗品; rule-9 shape validation still
  applies. NOTE: mid-task (2026-07-09, labrun v5 ruling in Drake's parallel session) the shape
  rule itself was relaxed to "2–4 total, one box, one row, any distinct cells" — the
  contiguous-from-column-1 requirement no longer exists anywhere (lab validator relaxed there;
  portal follows in this task).

## Open Points (defaults proposed in design.md, confirm at review)

- **Q3 — lifecycle/undo.** Proposed default: while the selection is unconfirmed, clicking a tube
  this session inserted removes it (undo); tubes left over from other experiments are handled by
  existing maintenance/disposal flows.
- **Q4 — identifier source.** Proposed default: `exp_id` / `exp_name` are the agent-side
  experiment id and display name, passed through by the portal at insert; lab-service treats them
  as opaque strings.

## Acceptance Criteria

- [ ] TLC Lab Logistic panel offers 添加纯品 / 添加粗品; clicking an empty slot afterwards places
      that tube; shape rule (2–4, one box, one row, distinct cells — columns freed 2026-07-09)
      and ordering rule (pure block left, crude block right) are enforced before confirm.
- [ ] The inserted `tlc_inventory` row carries `properties` jsonb with `exp_id`, `exp_name`,
      `purity`; rows still satisfy the placement check constraint (location or parent present).
- [ ] CC sample-column assignment inserts + assigns on empty-cell click; no purity labels for CC.
- [ ] Portal shows the purity label on assigned tubes in the Lab Logistic panel.
- [ ] ELN report renders the pure/crude tube info for TLC; absent data is omitted.
- [ ] Production-PRD rule 8 + matching acceptance criteria revised in the same change set.
- [ ] No changes to robot dispatch payloads, shared-types robot protocol, or ChemEngine calls.
- [ ] Lab-service: `ruff` + `pyright` + `pytest` green; portal: `pnpm typecheck && pnpm lint &&
      pnpm test` green; focused Playwright for the TLC lab-logistic flow updated and green.

## Out of Scope

- Purity labels for CC / RE / FP (semantics switch only for CC).
- ChemEngine lane-identity analysis input (explicitly excluded by Drake, 2026-07-09).
- Robot protocol changes.

## Notes

- Complex task: `design.md` + `implement.md` required before `task.py start`.
- Related held task `07-06-fe-lab-logistics-config-table` is FE-only, zero-behavior-change, and
  constrained to "no lab-service changes" — this task must not be merged into it. If 07-06 lands
  first, the panel work here goes through its `LAB_LOGISTICS_CONFIG` entry. This task changes
  behavior 07-06 is contracted to preserve — sequencing decision needed at review.
- If design reveals the CC lane is large, propose splitting CC into its own task before start.
