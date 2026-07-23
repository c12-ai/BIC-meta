# Check record — TLC pure/crude tube assignment (2026-07-09)

All lanes implemented, checked, and live-verified. Nothing committed (Drake's call).

## Scope extension (2026-07-09 evening, blocks 4–5, portal-only)

- Maintenance mode REMOVED from the lab-logistics module: toggle, state, maintenance branch,
  `SpecialItemMaintenanceGrid` + helpers deleted (verified unreferenced; Consumable Maintenance
  page untouched), maintenance i18n keys pruned from both locales.
- Right panel scoped per job: TLC → shelf tube boxes only; CC → sample-cartridge area only
  (`filterRacksByAreaIds`); FP → `AutoPickOnlyBody` (requirements list, NO rack surface) + new
  Playwright case. The PRD's "rack filter control" was never implemented in this dialog —
  nothing to remove.
- `tests/helpers.ts` `declareBenchTubes` rewritten to the add-mode flow (was doubly stale:
  removed toggle + inert filled cells); five live chain specs depend on it; implementer
  reviewed the rewrite unchanged.
- Final gates: typecheck clean · lint 5 pre-existing warnings · vitest 283/283 · Playwright
  layout spec **10/10** (new: FP no-rack-surface case; maintenance cases replaced by
  no-toggle/scoping assertions).
- PRDs updated same change set: root rule 2 + right-panel scoping block (supersedes the 07-05
  selection-vs-maintenance consistency rule) + acceptance criteria + changelog; portal project
  PRD contracts 3/4/4a/5/8/9, layout, CC/TLC flows, criteria, changelog.
- OPEN QUESTION recorded in both PRDs: stale-stock cleanup (other experiments' leftover tubes,
  shelf-box add/remove) has NO chemist surface now; lab-service endpoints remain, nothing calls
  them from the UI.

## Gate results (final runs, verbatim tails)

- **BIC-lab-service**: `ruff format --check` + `ruff check` clean · `pyright app/` 0 errors ·
  `pytest` **447 passed** (check-lab agent, full chain). Migration `0437835e9eae` additive,
  revises `a7f3b2e1c9d5`, `alembic check` clean, applied to dev DB.
- **BIC-agent-service**: `ruff check` clean · `pyright` 0 errors · `pytest -m "not real_llm"`
  **1761 passed, 6 xfailed** (excluding `test_l4_e2e_turn` — proven environmental via
  stash-rerun on the unmodified tree: live lab DB had 0 sample cartridges pre-reset).
- **BIC-agent-portal**: `tsc -b` clean · Biome 5 pre-existing warnings (unrelated files) ·
  vitest **283/283** · Playwright `material-preparation-layout.spec.ts` **9/9**.
  `tlc-params-tube-selector.spec.ts` NOT run — pre-existing auth_required failure on this
  branch (verified pre-existing via stash-rerun; suite-level login-gate gap, out of scope).

## Live bench verification (verify-cdp agent, CDP-driven, 2 rounds)

- Visual checks 5a–5g ALL PASS: add buttons (`tlc-add-pure`/`tlc-add-crude`), empty cells
  clickable only when armed (`tube-empty-*`), 纯/粗 badges, undo + re-add, layout clean, zero
  console/network errors.
- Readiness PASS with NON-ADJACENT C1+C4 (columns-freed ruling exercised); Confirm Dispatch
  enabled.
- Round 1 exposed a REAL bug: `properties` persisted without `exp_id` — root cause
  `workspaceStore.experimentId` was written only by snapshot hydration, never in live flows
  (also silently affected the ELN download URL in reload-free sessions). Fixed: the
  `experiment_objective_confirmed` echo now writes it; pinned by a unit test in
  `workspaceStore.event-apply.test.ts`.
- Round 2 (fresh flow post-fix) PASS: both tubes persist
  `{exp_id: <uuid>, exp_name, purity}`; exp_id cross-checked EXACT-MATCH against
  `talos_agent_db.experiments`.

## Acceptance criteria verdicts (prd.md)

- Add buttons + empty-slot placement + shape/ordering validation — PASS (live + Playwright +
  unit).
- `tlc_inventory.properties` jsonb with exp_id/exp_name/purity; placement constraint intact —
  PASS (lab tests + live DB).
- CC empty-slot insert + assign; occupied slots read-only (undo on own assignment); no CC
  purity UI — PASS (Playwright 9/9 incl. two new CC cases).
- Portal purity badges — PASS (live 5d/5e).
- ELN renders pure/crude info, absent → omitted — PASS at unit level (8 aggregator/renderer
  tests, zh+en, legacy/malformed degradation). NOT verified on a full live experiment (would
  need an all-results-confirmed bench run); flagged as residual, low risk (aggregator is
  pure/no-IO).
- Production-PRD rule 8/9 + portal project PRD revised in same change set — PASS.
- No robot-protocol / shared-types / ChemEngine changes — PASS (dispatch payload proven
  unchanged by adapter test + BE strip test; shared-types tree untouched by us).
- Repo gates green — PASS (above).

## Check-agent findings resolved

- Spec home fixed: FE→BE confirm contract documented in
  `.trellis/spec/backend/L3/specialist_tools.md` (was mis-placed one-liner).
- Portal: 4 trivial cleanups self-fixed; CC occupied-slot gap fixed (three-case handler:
  insert / undo-own / no-op) + 2 new Playwright cases.
- Lab: no findings.

## Residual / follow-ups (not blocking)

1. Live spec `tlc-params-tube-selector.spec.ts` blocked by pre-existing branch-wide
   auth_required (login gate #7) — the live suite needs an auth fixture; separate fix.
2. ELN purity clause verified at unit level only (see above).
3. Stale lab spec flagged (NOT edited — entangled with Drake's labrun work):
   `tlc-placement.md` §6a still says the tube selector reads `source=bench` /
   "storage is maintenance-only", which predates the 07-05 shelf cutover.
4. `_reaction_monitored` omits the purity clause when observed_rf is absent (whole section 03
   omitted) — correct per omit-when-absent, noted for awareness.
