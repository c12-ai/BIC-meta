# Implement — TLC round command contracts (child 1, shared-types)

> Contract-only, BIC-shared-types. Ordered to satisfy the AGENTS.md gate chain
> (model → __init__ → REGISTRY → examples → openapi → inventory → CHANGELOG → version).
> Miss one link and a `--check` gate goes red. Design: `design.md` §1–§6.

## Ordered checklist

1. [ ] **S1 enum** — add `AWAITING_CONFIRMATION = "awaiting_confirm"` to `TaskStatus`
   (`bic_shared_types/experiment_task/http/enums.py`). Non-terminal value. ⚠️ Value MUST be
   ≤20 chars — the lab persists `tasks.status` as `String(20)`; `"awaiting_confirmation"` (21)
   overflows. Use `"awaiting_confirm"` (16). (Cross-child constraint from child-2 design §2.)
2. [ ] **S2 create field** — add `target_window: TLCRfGoal` to `CreateTLCTaskRequest`
   (`experiment_task/http/tlc.py`); import `TLCRfGoal` from `common/tlc.py`.
3. [ ] **S3 append model** — define `AppendTLCRoundRequest { param: TLCParam }` in
   `experiment_task/http/tlc.py`; export it from the package `__init__`.
4. [ ] **S4 MQ field** — add `image_url: FileUrl | None = None` to `TaskStatusMsgPayload`
   (`experiment_task/mq/task_status.py`); import `FileUrl` from `common/types.py`. (No REGISTRY
   entry — MQ types are not registered; verified design §2/S4.)
5. [ ] **REGISTRY** — add `"experiment_task/http/append-tlc-round": AppendTLCRoundRequest` to
   `scripts/export_json_schema.py`. (S2 rides the existing `create-task` union entry.)
6. [ ] **Schemas** — `uv run python scripts/export_json_schema.py` → commit regenerated `schemas/`.
7. [ ] **TS enums** — `uv run python scripts/export_ts_enums.py` → commit regenerated `ts/enums.ts` (S1).
8. [ ] **Examples** — add an `examples/` payload for `AppendTLCRoundRequest`; register it in
   `scripts/validate_examples.py`.
9. [ ] **OpenAPI** — add `POST /tasks/{task_id}/rounds` (`$ref` AppendTLCRoundRequest) and
   `POST /tasks/{task_id}/cleanup` (no body) to `contracts/experiment_task/create-task.openapi.yaml`,
   next to the existing `/tasks/{task_id}/cancel`.
10. [ ] **Docs** — update `docs/contract-inventory.md` + `CHANGELOG.md` (additive entries).
11. [ ] **Version** — bump minor (additive). Per shared-types versioning; both consumer repos re-pin.

## Validation (all must be green before done)

- [ ] `uv run python scripts/export_json_schema.py --check`
- [ ] `uv run python scripts/export_ts_enums.py --check`
- [ ] `uv run python scripts/validate_examples.py`
- [ ] Whatever lint/type gate the repo runs (per AGENTS.md / CONTRIBUTING).
- [ ] Smoke: both consumer repos resolve the new pin + import the new symbols
  (`AppendTLCRoundRequest`, `TaskStatus.AWAITING_CONFIRMATION`, `TaskStatusMsgPayload.image_url`).

## Risky points / rollback

- The gate chain (step 5–10) is the failure-prone part — a missing examples/openapi/inventory link
  reads as a red `--check`, not a runtime bug. Work it top-to-bottom; re-run `--check` after each.
- All changes additive → rollback = revert the version bump + the model edits as one commit; no
  downstream consumer can have hard-depended on the new symbols yet (children 2/3 not started).

## Cross-child reminders (NOT this child's work — flag so they're not lost)

- Child 2 (lab): `_TERMINAL` must NOT include `AWAITING_CONFIRMATION`; add the append-round +
  cleanup route handlers; mark plate/tank/box occupied for the validation-based collision guard.
- Child 3 (agent): add `AWAITING_CONFIRMATION` to `NON_TERMINAL_STATUSES` (`event_ingress.py:40`)
  — pinned in parent implement.md Phase 3; without it the loop silently breaks.
