# Agent must not fabricate lab_logistics.sample_tubes (clarify not hallucinate)

## Goal

The TLC specialist must NEVER pre-fill `lab_logistics.sample_tubes` with invented
box/tube ids. Missing tube selection is the chemist's to make (or clarify) — fabricating it
violates the "missing param → clarify, never fabricate" contract and dispatches garbage.

## Evidence (bench run 5b, 2026-07-02, task 07-02)

The TLC specialist pre-filled `lab_logistics.sample_tubes` with placeholders
`box_id: "box_01"`, tubes `t001..t004` — present in both `trials.params` AND the confirm's
`form_values` (session_events seq 79). `box_01` is not a dispatchable slot, so the lab's
`POST /tasks/` correctly 400'd ("TLC sample-tube box 'box_01' is not on a known dispatchable
slot") and the turn failed (seq 83). Repo: BIC-agent-service. Related contract:
[[project_missing_param_clarify_not_default]].

Secondary observation from the same run (own finding, may fold here or separate): the
manual-TLC plan path seeded CC's `from_user` with a CANNED `tlc_result` (fixture spot ids
`…5001`, 2025-07-09 URL) — fabricated evidence surfacing in a live flow.

## Decision (Drake, 2026-07-02): LEAVE EMPTY — chemist fills

The TLC specialist never invents tube ids. `sample_tubes` stays unset; the chemist selects
via the material dialog, exactly like CC's `sample_cartridge_location`. If genuinely blocked,
the agent clarifies — it does not fabricate. (No live-inventory recommendation tool — that
was the rejected larger-scope option.)

## Requirements

- R1: Locate where the TLC specialist populates `lab_logistics.sample_tubes` (prompt
  instruction and/or a tool default) and stop it — leave the field empty/unset, mirroring
  CC's handling of `sample_cartridge_location`.
- R2: Missing tube selection required to proceed → agent CLARIFIES, never invents.
- R3: Regression: a TLC params draft emitted by the specialist never contains agent-authored
  tube ids (empty until the chemist/material-dialog fills it).

## Acceptance Criteria

- [x] A TLC specialist turn that reaches params draft leaves `sample_tubes` empty (no
  `box_01`/`t00x` placeholders).
- [x] BE test suite green; a test pins the empty-default behavior.

## Verification (2026-07-03, sonnet research-agent pass)

RESOLVED — shipped on BIC-agent-service main via PR #34 squash `7d2b1ba` (pre-squash `9ce7889`).
R1/R2: `_LAB_LOGISTICS_NO_FABRICATE_RULE` (`app/runtime/middleware/dynamic_prompts.py:80-86`)
injected into all three specialists' collecting_params blocks; `update_tlc_params` docstring
says leave EMPTY / NEVER invent (`tools.py:1316-1318`); clarify-not-fabricate wording included.
R3: prompt-level regression pins in `tests/unit/test_dynamic_prompts_chemist_draft.py:288,312`
(asserts guard text in all 3 prompts, no `box_01`); dispatch-gate test in
`test_specialists_tlc.py:673`. Spec I-ST-F copilot fill contract documented at
`.trellis/spec/backend/L3/specialist_tools.md:200` referencing this task. Known gap (low-risk,
accepted): no state-level test driving a live specialist turn and asserting the emitted draft —
prompt-guard test covers by proxy.
