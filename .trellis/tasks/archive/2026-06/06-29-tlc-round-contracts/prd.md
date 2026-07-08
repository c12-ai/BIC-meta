# TLC round command contracts + photo URL on MQ

> Child 1 of parent **06-28-tlc-retry-loop-boundary**. Head of the dependency chain —
> lands FIRST; child 2 (lab) and child 3 (agent) consume these types. Contract-only
> (BIC-shared-types). Read the parent `design.md` §2 before changing anything (Rule 10).

## Goal

Define the shared-types contract surface for the aggregator-Task TLC round model: one lab
Task per trial, grown by appending round skills, parked between rounds in a new status, with
the per-round plate photo URL flowing on the existing MQ status payload.

## Confirmed facts / decisions inherited from the parent (do not re-litigate)

- **Domain model:** 1 Agent trial = 1 Lab Task; prep/round/cleanup are SKILLS appended to the
  ONE Task. No `tlc_session` id/table — the single `task_id` IS the correlation. (parent §2.1)
- **Back-compat:** intra-APEX (agent↔lab) → hard-swap allowed; the shared-types deprecate-first
  policy is overridden for these intra-APEX task types. The old `CreateTLCTaskRequest` whole-task
  shape is deleted LAST (parent Phase 3b), NOT in this child. (grill Q1/Q2)
- **No robot-facing change:** prep/round/cleanup are TASK-level concepts the lab decomposes into
  EXISTING robot skills (`START_TLC`/`END_TLC` are lab-level). The robot protocol is untouched.
- **`AWAITING_CONFIRMATION` is non-terminal but ROBOT-FREE** — a routing/progress state, not a
  bench-busy flag. (grill Q4/Q5, parent §2.5)
- **Mock-in-L4-only** does not touch shared-types (no mocks here).

## Requirements

- **R1 — `TaskStatus.AWAITING_CONFIRMATION`.** Add the value to the shared `TaskStatus` StrEnum
  (`experiment_task/http/enums.py`). Semantics: a non-final skill completed and the Task has no
  closure yet — it parks awaiting the agent's verdict. Non-terminal.
- **R2 — `target_window` on TLC create.** Attach the EXISTING `TLCRfGoal` (`common/tlc.py` — has
  `goal` + `range`, validated) to the TLC create request so the chemist's acceptance window is on
  the contract. (Today `CreateTLCTaskRequest` has no Rf goal.)
- **R3 — Append-round request shape.** Define the wire shape for "append a round skill to an
  existing TLC Task" carrying the round's `TLCParam` (solvent ratio). Exact shape (new request
  model vs. a field on an append route body) is the design decision (§ design.md). Sample tubes
  + target_window are NOT repeated here (sent once at create — R5 of parent).
- **R4 — `image_url` on `TaskStatusMsgPayload`.** Add an optional captured-image S3 URL field
  (`experiment_task/mq/task_status.py`). Additive; CC/RE statuses omit it.
- **R5 — Regenerate derived artifacts + version.** Per AGENTS.md: run `export_json_schema.py`
  (and `export_ts_enums.py` for the enum change), update OpenAPI/CHANGELOG/contract-inventory,
  register any NEW boundary model in the schema REGISTRY, bump the version (additive = minor).

## Acceptance criteria

- [ ] **AC1** `TaskStatus.AWAITING_CONFIRMATION` exists; `export_ts_enums.py --check` green.
- [ ] **AC2** TLC create request carries `target_window: TLCRfGoal`; append-round shape carries the
  per-round `TLCParam`; both validate (round/window constraints enforced by the existing models).
- [ ] **AC3** `TaskStatusMsgPayload` has the optional `image_url`; CC/RE payloads still validate
  with it omitted.
- [ ] **AC4** `export_json_schema.py --check` + `export_ts_enums.py --check` green; schemas/openapi/
  CHANGELOG/contract-inventory regenerated and committed; version bumped (minor).
- [ ] **AC5** Both consumer repos resolve the new pin (smoke import; full integration is children 2/3).

## Out of scope

- Deleting the old single-shot `CreateTLCTaskRequest` (parent Phase 3b, after children 2/3 land).
- Any robot-protocol / SkillType change (not needed — see Confirmed facts).
- The lab append-route impl + agent ingress edit (children 2/3) — this child only defines the types.

## Open questions

- Q1 (design-level): append-round wire shape — a dedicated `AppendTLCRoundRequest` model on a new
  route, vs. extending an existing task-update body. Resolve in design.md.
- Q2: does `TaskStatusMsgPayload` need its own schema-REGISTRY entry, or is it already exported via
  an MQ-envelope schema? Verify during design (the REGISTRY currently shows http boundary models).
