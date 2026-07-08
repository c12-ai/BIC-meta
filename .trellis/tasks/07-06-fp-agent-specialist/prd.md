# FP specialist in agent service

Parent: `07-06-fp-agent-program` (requirements R1–R5 and DTOs live in the parent prd.md / design.md — this child implements the BE side and OWNS the FE↔BE contract).

## Goal

Replace the robot-FP `"stub"` disposition with a real FP specialist: params form (container model, deterministically pre-filled from CC evidence), user confirm, dispatch (`CreateFPTaskRequest`), terminal-status consumption, and agent-side `FpEvidence` synthesis. Remove RE's dead lab-logistics fields.

## Requirements

- Contract first: FP DTOs per parent design.md §2 in `app/events/form_payloads.py`; the old canned `FpEvidence`/`PoolMappingRow`/`FpSummaryRow` shape is replaced (no compat shims); MED005 fixture updated to the new shape.
- New `specialists/fp.py` subgraph, template `re.py`, NO MindClient dependency; `FPUpstreamContext` = verbatim `CcEvidence` subset (rack_cols/rack/fractions — multiple ranges with per-row status); pre-fill from well statuses: product → 烧瓶1, suspect + waste → 废液瓶, idle unassigned; defaults 烧瓶1 + 废液瓶.
- Routing: `SpecialistKind`/`executor_to_kind`/`classify_step_dispatch` (`runtime/types/specialist.py`), `_KIND_TO_SUBGRAPH`, `factory.py`, `specialists/__init__.py`; stub branch in `specialist_dispatcher.py:113` deleted.
- Dispatch follows the existing three-part convention (NO new builder pattern): `fp_params_form_problems()` + `map_containers_to_collect()` in form_payloads (single authority, pure, unit-tested), consumed by a new `_submit_l4` fp branch exactly parallel to cc/re/tlc (fail-loud RuntimeError on problems, inline `CreateFPTaskRequest`).
- `collect_config` semantics (RULED by Drake 2026-07-06 — follow the shared-types example `flasks=["500ml"], collect_config=[0,1,1,0]`): one element per rack tube (5×6 rack → 30 elements), element i = disposition of rack tube i, same flat order as `CcEvidence.rack`; 0=discard, N=flask ordinal. No dispatch gate; #81 ordering confirmation is a nice-to-have.
- Side change set in BIC-shared-types (contract-repo gate applies): add `create-fp-task.example.json`, strip the stale `flasks`/`collect_config` from `create-re-task.example.json` (v1.2.0 dropped them from `CreateRETaskRequest`), regenerate schemas/registries.
- On terminal `completed`: synthesize `FpEvidence` (mapping rows, 15 ml/tube math, collected/discarded totals, solvent system) and emit result_review.
- RE cleanup (parent R5): remove `RELabLogistics`, `update_re_lab_logistics`, and the stale "maps 1:1 onto CreateRETaskRequest" docstring.
- FP→RE bridge: RE pre-fills `volume_ml`/`solvents`/`solvent_ratio` from confirmed FpEvidence (replaces the MED005 bridge fixture as the live path).
- Rule 10: update `.trellis/spec/backend/L3/` + contracts docs in the same change set.

## Acceptance Criteria

- [ ] Robot fp step: trial minted, `FormRequestedEvent(params)` emitted with pre-filled `FPParamsForm`; no stub disposition remains in the codebase.
- [ ] Confirm → `CreateFPTaskRequest` accepted by live lab service (1-flask config); MQ terminal consumed; `FpEvidence` emitted with correct volume math (5 collected = 75 ml etc.).
- [ ] The pure functions (`prefill_containers` / `fp_params_form_problems` / `map_containers_to_collect` / `synthesize_fp_evidence`) pass the parent design.md §3 unit-test plan: partition + ordinal properties, volume math, mixed-class rows, precise failure messages, camelCase evidence round-trip.
- [ ] Params form emitted via the deterministic backstop on phase entry (no LLM tool call required to mint the decision); LLM tools cover chat-driven container edits only.
- [ ] RE form no longer carries flasks/collect_config; RE recommend basis auto-fills from FP evidence when present.
- [ ] Scenario/unit suites green; specs updated with the contract change.

## Notes

- Author design.md + implement.md at activation (complex task) — parent design.md §1–§5 is the design seed.
