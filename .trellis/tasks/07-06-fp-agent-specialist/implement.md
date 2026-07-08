# FP specialist — execution checklist

Work on `BIC-agent-service` branch `feat/fp_agent`. Stages from design.md; each stage ends with the full gate chain green before the next starts. NO git commits by subagents (main session controls commits; Drake approves).

## S1 Contract (form_payloads + tests)

- [ ] FP DTO family per parent design §2 (exact ConfigDict split: forms `extra="forbid"` snake_case; evidence adds `alias_generator=to_camel, populate_by_name=True`)
- [ ] `fp_params_form_problems`, `map_containers_to_collect`, `prefill_containers` (pure; index-keyed mapping)
- [ ] Wire `FPParamsConfirmAction`/`FpResultReviewAction` into the action discriminator (`_action_discriminator`) + `__all__`
- [ ] Remove `PoolMappingRow`/`FpSummaryRow`; migrate `med005_fixture.py` FP evidence to the new shape
- [ ] Unit tests: parent design §3 plan (partition/ordinal properties, volume math, mixed rows, failure messages, camel round-trip)
- [ ] Gate chain green

## S2 Subgraph + routing

- [ ] `specialists/fp.py` (template re.py; deterministic-first emission; `update_fp_containers` tool)
- [ ] Upstream loader: populate `FPUpstreamContext` from the confirmed CC evidence (reuse the existing prior-step evidence mechanism; document it)
- [ ] `runtime/types/specialist.py`: Kind += "fp"; executor_to_kind; classify_step_dispatch robot fp → specialist (stub disposition removed)
- [ ] `specialist_dispatcher.py`: `_KIND_TO_SUBGRAPH["fp"]`; delete stub branch + its NodeCompletedEvent shape
- [ ] `factory.py` fp_subgraph_node; `specialists/__init__.py` export
- [ ] Graph-level tests: robot fp step mints trial + emits params form; manual fp still skipped
- [ ] Gate chain green

## S3 Dispatch + evidence

- [ ] `_submit_l4` fp branch (problems → fail-loud → map_containers_to_collect → CreateFPTaskRequest)
- [ ] Conducting phase: consume terminal task status; `synthesize_fp_evidence` (+ TUBE_VOLUME_ML in fp domain); emit result_review with typed FpEvidence
- [ ] FP→RE bridge: RE pre-fills volume_ml/solvents/solvent_ratio from confirmed FpEvidence
- [ ] Tests: dispatch payload shape vs `CreateFPTaskRequest`; evidence synthesis cases; RE pre-fill
- [ ] Gate chain green

## S4 RE cleanup + specs + shared-types examples

- [ ] Remove `RELabLogistics` + `update_re_lab_logistics` + stale docstring; fix affected RE tests
- [ ] Spec updates (Rule 10): L3 specialist_tools.md / graphs.md / backend contracts.md
- [ ] BIC-shared-types: add `create-fp-task.example.json`, strip stale RE example fields, run full contract-repo gate
- [ ] Full gate chain green in both repos

## Validation commands (BIC-agent-service)

```bash
uv run ruff check app/ tests/ && uv run pyright && uv run pytest
```
(Re-run the whole chain after any fix — gate chains short-circuit.)
