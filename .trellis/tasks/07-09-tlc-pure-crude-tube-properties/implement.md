# Implement — TLC pure/crude tube assignment with inventory properties

Ordered checklist. Lane order is **contract-driven** (design §8): lab-service provides the
column/API → agent-service ACCEPTS `purity` → portal starts SENDING it. Landing the portal
before the agent would silently drop purity (`ObjectLocation` extra=ignore), so lanes 2 and 3
must not be swapped. Validation commands per lane; re-run full gate chains from the top after
any fix (gate chains short-circuit).

Post-rebase note (2026-07-09): anchors re-verified against the rebased trees; drifted anchors
are already corrected in design.md (`_require_slot_editable_area:1065`; `tlc-params-draft.ts`
gained Recommend helpers — `tubeSelectionProblem` untouched).

## Lane 1 — BIC-lab-service (contract provider)

- [ ] 1.1 ORM: `tlc_inventory.properties: Mapped[dict | None]` (JSONB) in
      `app/data/models/tlc_inventory.py`.
- [ ] 1.2 Alembic revision (autogenerate, verify additive `add_column` only); `alembic upgrade
      head` against dev DB.
- [ ] 1.3 Schemas: `TlcInventoryCreate`/`TlcInventoryRead` += `properties`
      (`app/data/schemas/tlc_inventory.py`); `SampleTubeCellMaintenanceRequest` +=
      `properties: dict | None`; `SampleTubeCellView` += `properties`
      (`app/data/schemas/preparation.py`).
- [ ] 1.4 Repo: `_upsert` accepts `properties`, writes on create, never clears on
      placement-only update; `persist_box` untouched semantics verified
      (`app/tlc/inventory.py`).
- [ ] 1.5 Service: insert branch of `update_sample_tube_cell` passes
      `properties=request.properties` (`app/services/preparation_service.py:540` ff); read
      path `get_sample_tube_boxes` (`:439` ff) maps `tube.properties` into the cell view.
- [ ] 1.6 Tests: insert-with-properties persists & reads back; placement update preserves
      properties; occupied=false removal; seed reset unaffected.
- [ ] 1.7 Gate: `uv run ruff check . && uv run pyright app/ && uv run pytest` (full chain, one
      shot).
- Rollback point: lane is additive; `alembic downgrade -1` + revert commit.

## Lane 2 — BIC-agent-service (accept purity + ELN) — BEFORE portal

- [ ] 2.1 `form_payloads.py:311` ff: TLC `sample_tubes` item type → agent-local enriched model
      (`ObjectLocation` fields + `purity: Literal["pure","crude"] | None = None`).
      Shared-types untouched.
- [ ] 2.2 Parse-point audit (design §8): `rg "TLCLabLogistics|sample_tubes"` across
      `app/runtime/` + `app/events/` — every normalization of TLC `lab_logistics` (entry
      pipeline draft merge, `specialists/tlc.py`, Recommend payload path) must preserve
      `purity`. Add a cross-turn re-entry test: confirm-with-purity → draft reseed → purity
      still present in `trial.params`.
- [ ] 2.3 `_apply_tlc` (`app/eln/aggregator.py:189`): also read
      `trial.params["lab_logistics"]["sample_tubes"]`; `ReportContext.tlc_sample_tubes`
      (`None` default).
- [ ] 2.4 Renderer section 03 (`renderer.py:502`): bilingual clause/table (cell → 纯品/粗品)
      via `_pick`; `None` → omitted (omit-never-fabricate).
- [ ] 2.5 Tests: aggregator params-present / params-absent / legacy-no-purity; renderer zh+en;
      the 2.2 re-entry test.
- [ ] 2.6 Gate: repo's standard full chain (ruff/pyright/pytest per its CLAUDE.md).
- Rollback point: revert commit; accepting purity with no producer is a no-op.

## Lane 3 — BIC-agent-portal (interaction + send purity)

- [ ] 3.1 `lab-service-client.ts`: `SampleTubeCellView` += `properties`;
      `updateSampleTubeCell` body += optional `properties`.
- [ ] 3.2 TLC add-mode: `addMode` state + 添加纯品/添加粗品 buttons (`tlc-add-pure` /
      `tlc-add-crude`) in `TlcPreparationBody`; `TubeSelectorGrid` `addMode`/`onInsert` props;
      empty cells clickable only when armed, testid `tube-empty-{boxId}-{row}{col}`; filled
      cells inert + purity badge from `cell.properties.purity`.
- [ ] 3.3 Insert flow: empty-cell click → PUT with `{occupied: true, properties: {exp_id,
      exp_name, purity}}` → resolve `tube_id` from refreshed response → append
      `{...ObjectLocation, purity}` to draft `lab_logistics.sample_tubes`. Undo: click a
      draft-selected tube → PUT `{occupied: false}` + drop from draft. Draft layer unchanged
      (pass-through verified, design D3.5).
- [ ] 3.4 Validation: extend `tubeSelectionProblem` (`tlc-params-draft.ts:82`) — shape rule
      kept; NEW: ≥1 pure AND ≥1 crude; pure block strictly left of crude block.
- [ ] 3.5 Dispatch: `buildLabTaskParams` (tlc) strips `purity` → plain `ObjectLocation[]`;
      assert payload shape identical to today (adapter test). Confirm/Recommend payloads keep
      `purity` (agent already accepts it after lane 2).
- [ ] 3.6 CC: selection-view empty-slot click in allowed area → `updatePreparationSlot`
      `{occupied: true, material_key}` + `withSampleCartridgeLocation`; re-pick clears the
      previous session-inserted slot first; occupied slots no longer selection targets.
- [ ] 3.7 Specs: rewrite TLC selection case + `toHaveCount(0)` assertion
      (`material-preparation-layout.spec.ts`); CC insert case; new cases: ordering validation,
      purity badge, undo; rewrite tube acquisition in `tlc-params-tube-selector.spec.ts`.
- [ ] 3.8 Gate: `pnpm typecheck && pnpm lint && pnpm test` (full chain), then focused
      Playwright: `material-preparation-layout.spec.ts`, `tlc-params-tube-selector.spec.ts`
      (services via tmux `bic-services` only).
- Rollback point: revert portal commit; lanes 1–2 are inert without it.

## Lane 4 — PRD + spec (same change set, rule-10)

- [ ] 4.1 `Production-PRD.md`: rule 8 replaced (select-empty = insert-and-assign, TLC + CC,
      dated 2026-07-09); rule 9 + purity ordering; rule 10 TLC row note; acceptance criteria
      swap; UI Interaction Requirements add-buttons flow; Change Log entry.
- [ ] 4.2 Note in `.trellis/tasks/07-06-fe-lab-logistics-config-table/prd.md`: re-baseline
      needed (third interaction mode; lands after 07-09).
- [ ] 4.3 `.trellis/spec` touch-ups where the old maintain-then-select contract is written
      (lab-service/portal spec indexes — check via trellis-update-spec).

## Review gates

- After lane 1: contract review (schemas + migration) before lanes 2–3 consume it.
- After lanes 2+3: cross-repo E2E sanity on live bench (dispatch one TLC with 1p+1c, export
  ELN, see the clause) — via bic-e2e-runner if a full pass is wanted.
- Lane 4 in the final commit set of each repo touched (spec update never trails code).
