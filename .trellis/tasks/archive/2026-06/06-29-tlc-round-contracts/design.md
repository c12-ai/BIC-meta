# Design — TLC round command contracts (child 1, shared-types)

> Contract-only changes in BIC-shared-types. Consumed by child 2 (lab) + child 3 (agent).
> Parent context: `../06-28-tlc-retry-loop-boundary/design.md` §2. All decisions below were
> resolved in the parent brainstorm + grill (Q1/Q2/Q4/Q5/Q6).

## 1. Surfaces changed (4)

| # | File | Change | Schema impact |
|---|---|---|---|
| S1 | `experiment_task/http/enums.py` | add `TaskStatus.AWAITING_CONFIRMATION = "awaiting_confirm"` | `export_ts_enums.py` |
| S2 | `experiment_task/http/tlc.py` | add `target_window: TLCRfGoal` to `CreateTLCTaskRequest` | `create-task` schema (via union) |
| S3 | `experiment_task/http/tlc.py` (new) | `AppendTLCRoundRequest { param: TLCParam }` + register in REGISTRY | new `append-tlc-round` schema |
| S4 | `experiment_task/mq/task_status.py` | add `image_url: FileUrl \| None = None` to `TaskStatusMsgPayload` | NONE (MQ not in REGISTRY — verified) |

## 2. Decisions (resolved — do not reopen)

- **S1 `AWAITING_CONFIRMATION`** — new shared `TaskStatus` value. Wire value MUST be ≤20 chars:
  use `"awaiting_confirm"` (16). The lab persists `tasks.status` as `String(20)`
  (`models/task.py:60`); `"awaiting_confirmation"` (21) would OVERFLOW the column. (Found in
  child-2 design §2.) Non-terminal, robot-free (parent §2.5). Consumers that bucket statuses must learn it: lab `_TERMINAL` must NOT include
  it (child 2); agent `NON_TERMINAL_STATUSES` MUST include it (child 3 — pinned in parent
  implement.md Phase 3). Those are consumer edits, not this child's; flagged so they're not missed.
- **S2 `target_window`** — reuse the EXISTING `TLCRfGoal` (`common/tlc.py`: `goal` + `range`,
  range-validated `0<=lo<hi<=1`). Field name `target_window` on the create request; type
  `TLCRfGoal`. **REQUIRED (Drake) — no default.** The retry loop compares product Rf against this
  window; a silent default `(0.2,0.8)` would mask a missing window and let the loop pass/fail on
  the wrong band. Every TLC create MUST carry an explicit window (child 3 chemist-edits 0.40/0.60).
  Update the existing `create-tlc-task` example to include an explicit `target_window`.
- **S3 append-round shape (grill Q6 → Option A)** — dedicated route `POST /tasks/{task_id}/rounds`
  with a typed body `AppendTLCRoundRequest { param: TLCParam }`. Mirrors the existing
  `/tasks/{task_id}/cancel` convention; typed (Rule 11); TLC-specific (no generic skill-append —
  YAGNI). Cleanup is a SEPARATE route `POST /tasks/{task_id}/cleanup` (no body, or `{}`) — cleanup
  is a distinct dispose skill and success-gating COMPLETED is cleaner as an explicit command.
  Per-round payload is ONLY `param` (tubes + window already on the Task from create).
- **S4 `image_url` on MQ** (grill Q2 verified) — `TaskStatusMsgPayload` is NOT in the
  `export_json_schema.py` REGISTRY (only `experiment_task/http/*` boundary models are), so this is
  a plain additive Pydantic field with NO schema-registry entry to update. Type `FileUrl | None`
  (the same alias `TLCPlateImage.rgb_url` uses), default `None`. CC/RE statuses omit it.

## 3. New OpenAPI paths (contracts/experiment_task/create-task.openapi.yaml)

Add two paths next to the existing `/tasks/{task_id}/cancel`:
- `POST /tasks/{task_id}/rounds` → `$ref` `AppendTLCRoundRequest`; 200 → `TaskSubmissionResponse`
  (or the existing task-mutation response shape — match `/cancel`).
- `POST /tasks/{task_id}/cleanup` → no body; 200 → same response shape.

## 4. Schema REGISTRY delta (scripts/export_json_schema.py)

- ADD `"experiment_task/http/append-tlc-round": AppendTLCRoundRequest` (the only NEW boundary model).
- S2 rides the existing `create-task` entry (`CreateTLCTaskRequest` is a union arm) — regenerates
  automatically.
- S4 needs NO entry (MQ not registered).

## 5. Compatibility

- All four changes are ADDITIVE → **minor** version bump (per `docs/compatibility-policy.md`).
  No deletion in this child (the old whole-task `CreateTLCTaskRequest` removal is parent Phase 3b).
- The intra-APEX override (grill Q1/Q2) means we are NOT obligated to deprecate-first here — but
  since every change is additive anyway, the question is moot for this child. The hard-swap/delete
  only bites in Phase 3b.

## 6. Validation (AGENTS.md gates)

1. Edit the 4 surfaces + add the new model to `__init__` exports.
2. `uv run python scripts/export_json_schema.py` → commit regenerated `schemas/`.
3. `uv run python scripts/export_ts_enums.py` → commit regenerated `ts/enums.ts` (S1).
4. Add an `examples/` entry for `AppendTLCRoundRequest` + register in `validate_examples.py`.
5. Update `contracts/experiment_task/create-task.openapi.yaml` (§3), `docs/contract-inventory.md`,
   `CHANGELOG.md`.
6. `--check` gates green: `export_json_schema.py --check`, `export_ts_enums.py --check`,
   `validate_examples.py`.
7. Bump version (minor); both consumer repos re-pin + smoke-import.

## 7. Risks

- **Miss-a-gate (AGENTS.md):** the model→__init__→REGISTRY→examples→openapi→inventory→CHANGELOG
  chain is long; one miss = red `--check`. Follow the checklist in §6 exactly.
- ~~`FileUrl` validation strictness~~ → CLEARED: `FileUrl` is `TypeAlias = str` with NO scheme
  constraint (`common/types.py:23`), so `mock://` / `s3://` / minio URLs all pass. No boundary
  trap. (If `FileUrl` later gains validation, re-check.)
