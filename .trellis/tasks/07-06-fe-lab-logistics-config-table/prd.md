# FE lab-logistics config table drives the shared module

Parent: `07-05-lab-logistics-gap-remediation`. Portal-only refactor implementing portal project
PRD contract 4b (Drake, 2026-07-05). Complex enough to carry `design.md` + `implement.md`;
execution HELD until Drake releases it (loop directive 2026-07-06: refine the plan until stable).

> **RE-BASELINE REQUIRED (2026-07-09):** task `07-09-tlc-pure-crude-tube-properties` lands
> BEFORE this task and CHANGES the behavior this task is contracted to preserve — assignment is
> now select-empty = insert-and-assign (root PRD rule 8 reversal): TLC gains 添加纯品/添加粗品
> add-mode with per-tube purity properties, CC assigns via empty-slot insert, filled cells are
> read-only. The zero-behavior-change baseline, the `LAB_LOGISTICS_CONFIG` interface (needs a
> third add-mode interaction beyond selection/maintenance), and the Playwright case list must be
> re-derived from the post-07-09 tree before start.

## Goal

Every experiment's Lab Logistics button opens the ONE shared module component, and a single
FE-side per-experiment configuration table defines BOTH the left requirement list presentation
and the right physical panel wiring. Adding an experiment (RE/FP later) means adding one config
entry — never adding per-experiment conditional branches inside the shared component.

## Requirements

1. Introduce one FE configuration table (`LAB_LOGISTICS_CONFIG`) with one entry per experiment
   (`tlc`, `cc` now). Each entry declares:
   - data sources the right panel needs (rack layout / sample-tube boxes + source);
   - manual-selection behavior: satisfaction gate, shape-problem message, blocker text,
     selection summary, unassigned hint;
   - right-panel bodies: selection render and maintenance group adapters (both composing the
     existing shared grid primitives — no new page-specific grid components);
   - maintenance click → persistence action mapping;
   - static copy (titles, descriptions, hint text with its test id);
   - dispatch payload builder (`buildLabTaskParams` branch).
2. `MaterialPreparationPanel` contains exactly ONE experiment lookup
   (`LAB_LOGISTICS_CONFIG[executor]`) and afterwards reads only config fields. No
   `executor === '...'` comparisons remain in the shared component body (17 exist today).
3. Zero behavior change: DOM, network calls, gating, and copy identical before/after. The
   existing focused Playwright suite is the harness proving it.
4. Authority split preserved: the config table owns presentation wiring only; stock,
   availability, quantities, and physical state stay lab-service-driven (root PRD rules 5/10).

## Constraints

- React rules-of-hooks: hook calls stay unconditional in the shared body; config selects via
  `enabled` flags, never via per-experiment hooks (design §2).
- CC behavior byte-identical; TLC behavior byte-identical (post-shelf-cutover semantics).
- No lab-service changes; no shared-types changes.
- Do not conflict with the 07-02 session's files: this task touches only
  `MaterialPreparationPanel.tsx`, the new config module,
  `src/lib/material-preparation-adapter.ts` (its executor branches are absorbed into config
  entries), `ParameterDesignPanel.tsx` (the two experiment-specific sync callbacks generalize to
  one `onManualSelectionChange` prop — design §7), and
  `tests/material-preparation-layout.spec.ts` (+ fixtures only if strictly needed).

## Acceptance Criteria

- [ ] `rg "executor === '" src/components/workspace/material-preparation/MaterialPreparationPanel.tsx`
      returns 0 matches; the config lookup is the only experiment dispatch (structural check
      recorded in check.md).
- [ ] `LAB_LOGISTICS_CONFIG` has exactly `tlc` and `cc` entries typed by one shared interface.
- [ ] Focused Playwright (`material-preparation-layout.spec.ts`) passes UNMODIFIED except for an
      added structural/no-behavior-change note — the 7 existing cases prove zero drift.
- [ ] `pnpm typecheck && pnpm lint && pnpm test` green.
- [ ] Portal project PRD contract 4b acceptance line satisfied and referenced from check.md.

## Out of Scope

- RE/FP entries (added when their lab execution parameters are finalized — the payoff, not the
  task).
- Any change to lab-service requirements/readiness contracts.
- Consumables page and TLC Workspace view.
