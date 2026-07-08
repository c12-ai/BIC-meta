# FP specialist — child design

Authoritative design lives in the parent: `../07-06-fp-agent-program/design.md` (§1 architecture, §2 DTOs incl. python-expert refinements, §3 dispatch mapping + unit-test plan, §4 FP→RE bridge, §5 RE dead-field removal, §6 data flow). This file only fixes child-local execution decisions.

## Repo / branch

`BIC-agent-service`, branch `feat/fp_agent` (checked out by Drake 2026-07-06).

## Stage boundaries (each independently green)

1. **S1 Contract**: `form_payloads.py` — FP DTO family (FPContainer/FPUpstreamContext/FPFromUserFields/FPParamsForm/FPParamsConfirmAction; FpRowClass/FpMappingRow/FpEvidence/FpResultReviewAction), casing split per ADR #1 (forms snake_case, evidence camel), `fp_params_form_problems()`, `map_containers_to_collect()`, `prefill_containers()`, discriminator wiring for the new actions, `__all__` updates, PoolMappingRow/FpSummaryRow removal, MED005 fixture migration. Unit tests per parent §3 plan.
2. **S2 Subgraph + routing**: `specialists/fp.py` (template `re.py`; deterministic-first form emission on phase entry; LLM tool `update_fp_containers` for chat edits; no MindClient), `SpecialistKind`/`executor_to_kind`/`classify_step_dispatch`, `_KIND_TO_SUBGRAPH`, `factory.py`, `specialists/__init__.py`, stub branch removal in `specialist_dispatcher.py`. Upstream CC evidence loading for `FPUpstreamContext` (from the experiment's confirmed CC result; loader mechanism = whatever cc/re use to read prior-step evidence — discover in S2, document in the spec update).
3. **S3 Dispatch + evidence**: `_submit_l4` fp branch; terminal-status handling in the fp subgraph conducting phase; `synthesize_fp_evidence()` (+ `TUBE_VOLUME_ML=15` in the fp domain module); result_review emission; FP→RE bridge (RE pre-fill from confirmed FpEvidence).
4. **S4 RE cleanup + specs**: remove `RELabLogistics`/`update_re_lab_logistics` + stale docstrings; update `.trellis/spec/backend/L3/specialist_tools.md`, `graphs.md`, `contracts.md` (Rule 10); scenario sanity via scripts/chat or unit-level graph tests.

Side change set (rides S1, separate repo BIC-shared-types): `create-fp-task.example.json` + strip stale fields from `create-re-task.example.json` + registry/regen per contract-repo gate.

## Non-goals (child)

Portal changes (child B); e2e specs and Production-PRD updates (child D); multi-flask live dispatch (single-flask operating convention until #81 answers).

## Gate

`uv run pytest` green on the repo suite (663-collect baseline must not regress) + `uv run ruff check` + `uv run pyright` (match the repo's existing gate chain; re-run the WHOLE chain after any fix).
