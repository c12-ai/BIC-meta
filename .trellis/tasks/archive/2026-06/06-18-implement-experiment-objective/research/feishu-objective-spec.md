# Feishu Experiment Objective Spec Notes

Source: `https://carbon12.feishu.cn/wiki/SRChweKBRiPV29kh30zcoaldnW4`

Fetched through `lark-cli docs +fetch --api-version v2 --doc-format markdown` on 2026-06-17.

## Page Title

`Right Panel - Experiment Objective Interaction Notes`

## Layout

* Right panel has fixed top and bottom regions.
* Top fixed region includes Experiment Overview, Task Configuration / Result Confirmation tabs, and the setup step navigation.
* Bottom fixed region includes Save Draft and Confirm controls.
* Middle region is vertically scrollable.

## Setup Steps

Task Configuration contains three persistent steps:

1. Experiment Objective
2. Workflow Design
3. Parameter Design

The right-side close button closes the entire right panel.

## Execution Statuses

The page embeds a Feishu sheet for the five statuses. The sheet data was read from spreadsheet token `JSQxs2XZ2hqibptaguRcOVrmnwc`, sheet id `qIcJx0`.

| Status | Meaning | User view |
| --- | --- | --- |
| `configuring` | User is configuring task setup step 1/2/3. | I am filling the form. |
| `dispatching` | User clicked dispatch and waits for robot readiness. | Submitted, waiting for robot start. |
| `executing` | Robot is executing the current task. | Robot is running. |
| `awaiting_confirm` | Robot finished and waits for user result confirmation. | I need to review and confirm the result. |
| `all_completed` | All tasks have been confirmed. | Everything is finished. |

The Feishu page says the status field should come from the backend `jobs` table `status` field.

## Task Name

* Required.
* Source is noted as backend experiment table `name` field.
* Naming rule: short summary within 5 Chinese characters, date `yymmdd`, sequence suffix for duplicates.
* User can edit.
* If edited name duplicates another name in the current conversation/session, ask for a different name and suggest alternatives.

## Reaction Card

* Required.
* Left/top edit action opens a molecule drawing modal.
* Right/top copy action copies SMILES.
* The spec says reaction card and molecule drawing work already exists and should be reused.

## Reactant Table

* At least one reactant row.
* When there is one row, delete is disabled.
* If only one reactant exists, it is the baseline/reference row with `1 eq` and cannot change equivalents.
* Baseline means the `is baseline` switch is enabled.
* Baseline amount is required.
* Switching baseline should trigger backend protocol recalculation.
* Non-baseline rows can be deleted.
* Add Reactant appends a new empty row.

Fields:

* Structure: required once row exists.
* Compound name: required once row exists, user editable, max 50 Chinese characters.
* Molecular weight: not editable.
* Amount: baseline required, others optional, positive mg, 3 decimals.
* Equivalents: baseline fixed at 1, others optional, positive eq, 2 decimals.
* Baseline: exactly one true row.

## Targets

* Target purity: required, positive percent `(0, 100]`, 2 decimals.
* Target yield: required, positive percent `(0, 100]`, 2 decimals.
* Target weight: calculated from purity/yield/reactants through backend protocol, positive mg, 3 decimals.

The page references a BE Protocol stub named `experiment_object_stub` and draft route `/api/experiment/recognize-structure`, but marks final route/fields as pending Mind/Mars API contract finalization.

## Validation Copy

* Required: this field is required.
* Too long: field length should be less than `{x}` characters.
* Range: input range is `xx-xx`.

## Product/Contract Risks

* Feishu names `jobs.status`, but current portal status projection is not a one-to-one match.
* Feishu names `experiment.name`, but current BIC-agent-service model does not have that column.
* Feishu still references a placeholder stub; BIC-shared-types has stronger typed Mind protocol contracts that should supersede the placeholder where possible.
