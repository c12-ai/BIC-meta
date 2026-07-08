# Shared-types: step-event contract

Parent: `06-30-robot-execution-log`. **This child blocks the other three** — it defines
the typed wire contract every downstream hop consumes.

## Goal

Define the typed contract for a **step-level execution timeline** entry that crosses
Lab→Agent (MQ) and Agent→FE (SSE), in `BIC-shared-types`, **additively** (no breaking
removal), and ship all the generated artifacts the contract repo's gate requires.

## Context (real code)

- Existing MQ payload: `bic_shared_types/experiment_task/mq/task_status.py`
  - `TaskStatusStepPayload { step_index, skill_type, status, error_message? }` — a
    *current snapshot* per step, **no timestamp, no ordering-over-time**.
  - `TaskStatusMsgPayload { task_id, agent_side_task_id?, status, steps[], error_message?, image_url? }`.
- LabService source the timeline derives from: `EventLog` (`app/data/models/event.py`)
  has `STEP_STARTED / STEP_COMPLETED / STEP_FAILED / STEP_WAITING` with `created_at`
  (the timestamp the snapshot lacks) and `old_state/new_state` JSONB.
- This repo is **codegen-backed** (see `AGENTS.md`): editing a Pydantic model requires
  regenerating `schemas/`, possibly `ts/enums.ts`, examples, and passing a multi-gate.

## Requirements

- R1. Add a typed model for one timeline entry — working name `TaskStepEvent` — carrying
  at minimum: `step_index: int`, `skill_type: str`, `status: <step lifecycle>`,
  `occurred_at: datetime`, `error_message: str | None`. (Exact field set finalized in
  design; `occurred_at` is the new field vs. today's snapshot.)
- R2. Decide & encode how the timeline is transported (resolves parent **Q1**):
  either (a) a new field on `TaskStatusMsgPayload` (e.g. `step_events: list[TaskStepEvent]`)
  or (b) a new dedicated message payload type. **Additive either way** — do not change or
  remove existing `TaskStatusStepPayload` / `steps`.
- R3. If a new enum is introduced for step lifecycle status, prefer reusing the existing
  status vocabulary; only add an enum if no suitable one exists (constraint C1 below).
- R4. Regenerate **all** derived artifacts and pass the full gate (ruff, ruff format
  --check, validate_contracts, export_json_schema --check, validate_examples,
  export_ts_enums --check, pytest, pyright).
- R5. Update CHANGELOG + contract-inventory per `AGENTS.md` §3.1 if a boundary model is added.
- R6. Update the relevant `.trellis/spec/` contract doc for this boundary (Rule 10).

## Constraints

- C1. **Additive bump only.** History: a prior bump (v1.1.4a1) *dropped* a type and broke
  29 collect sites across consumers. Deprecate-don't-delete; keep existing types importable.
- C2. **Version bump discipline** — bump per the repo's policy; do not guess alpha vs minor,
  confirm during planning.
- C3. Reuse existing types/enums where possible (DRY); the new entry type should look like a
  natural sibling of `TaskStatusStepPayload`, not a parallel universe.

## Acceptance Criteria

- [ ] AC1. `TaskStepEvent` (or final name) exists, typed, exported from the package `__init__`.
- [ ] AC2. The transport decision (R2 a or b) is implemented additively; existing
      `TaskStatusMsgPayload.steps` / `TaskStatusStepPayload` are untouched and still importable.
- [ ] AC3. Full contract gate passes locally (all commands in `AGENTS.md`).
- [ ] AC4. **3-repo consume check**: after pinning the new version, BIC-lab-service and
      BIC-agent-service still import + `pytest --collect-only` green (no collect regression).
- [ ] AC5. `.trellis/spec/` doc for the Lab↔Agent / Agent↔FE step-event contract updated in
      this change set.
- [ ] AC6. CHANGELOG + contract-inventory updated.

## Resolved (see design.md)

- **R2 transport**: enrich `TaskStatusMsgPayload` with `step_events: list[TaskStepEvent] = []`
  (no new message type). [Drake, 2026-06-30]
- **Field set**: `event_id` (= EventLog UUID, for dedup/keying), `step_index`, `skill_type`,
  `status: str`, `occurred_at: datetime`, `error_message?`. `status` stays a string (no new
  cross-repo enum); EventLog `old_state/new_state` excluded (entity snapshots are out of MVP).
- **Payload mode**: full timeline each message; Agent dedups on `event_id`. [Drake, 2026-06-30]

## Open questions (resolve at implement time)

- Version bump level — design assumes alpha `1.1.9a1 → 1.1.10a1`; confirm with Drake (C2).

## Notes

- Contract task: design.md + implement.md required before `start` (the gate + 3-repo
  verification make it non-lightweight).
