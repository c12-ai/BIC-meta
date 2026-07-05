# BIC-shared-types Experiment Protocol Notes

Repository: `/Users/drakezhou/Development/BIC/BIC-shared-types`

Branch read: `origin/feat/mixcase-smiles-dict-protocol-v1.1.6a1`

Current local branch stayed on `main`; the remote branch was read with `git show` and `git diff`.

## Branch Summary

Latest branch commits:

* `0dc6e64` - fix CI formatting
* `d9c8874` - fix long TLC line wrap
* `c3346b4` - mixcase SMILES maps and `/api/protocol` paths v1.1.6a1

Diff versus main is mainly TLC/CC and canonical `/api/protocol/*` paths. The experiment objective models already exist in the model service protocol area and remain relevant for this task.

## Relevant Models

File on branch: `bic_shared_types/model_service/http/experiment.py`

### Request Models

`ExperimentMaterialParseRequest`

* `rxn: RxnSmiles`
* Purpose: parse user-provided reaction SMILES into a material table.

`ExperimentGoalConfirmRequest`

* `rxn: RxnSmiles`
* `feed_amount_mg: float` with `gt=0`
* `target_purity_pct: float` with `gt=0`, `le=100`
* `target_yield_pct: float` with `gt=0`, `le=100`
* `basis_material_hint: str | None`

### Response Models

`ExperimentMaterialParseResponse`

* `rendered_rxn_url: FileUrl`
* `materials: list[ExperimentParsedMaterial]`, min length 1

`ExperimentParsedMaterial`

* `role: substrate | reagent | product`
* `smiles: str`
* `name: str | None`
* `structure_url: FileUrl | None`

`ExperimentGoalConfirmResponse`

* `target_weight_mg: float`
* `rendered_rxn_url: FileUrl`
* `materials: list[ExperimentMaterial]`, min length 1

`ExperimentMaterial`

* `role: substrate | reagent`
* `smiles: str`
* `amount_mg: float`
* `equivalents: float`
* `is_baseline: bool`

## Mind Client Paths

File on branch: `bic_shared_types/clients/model_service/http/mind_client.py`

The typed wrapper exposes:

* `parse_experiment_materials(request)` -> POST `/api/protocol/experiment/material-parse`
* `confirm_experiment_goal(request)` -> POST `/api/protocol/experiment/goal-confirm`

The branch's changelog says model service paths moved to canonical `/api/protocol/*`.

## Implications for This Task

* The Feishu placeholder `experiment_object_stub` should not be the final contract if BIC-agent-service can consume these typed models.
* Portal should not import these Python models directly; BIC-agent-service should expose portal-facing DTOs and hide Mind transport.
* BIC-agent-service currently pins `bic-shared-types` to `v1.1.2a1`. Implementation must intentionally update that dependency before relying on `/api/protocol/*` client paths.
* Import paths should prefer `bic_shared_types.model_service.http.*`, not deprecated `bic_shared_types.mcp_protocol.*`.

## Non-Objective Changes on Branch

The branch also changes TLC and CC:

* TLC mixcase uses SMILES-keyed `observed_rf` and nested `recommendation.predicted_rf`.
* CC result request/response was redesigned around TLC result and peak match audit.
* `CCPeakProductRole` enum was added.

Those are not Experiment Objective requirements, but they may affect dependency upgrade blast radius.
