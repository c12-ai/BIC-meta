# Implement — Lab-side TLC round split (child 2, lab-service)

> SECOND in the chain (after child-1 contracts land + are pinned). Heaviest child.
> Validate per `.claude/rules`: `ruff check && uv run pyright app/ && uv run pytest`.
> Design: `design.md`. Match existing `flag_modified` + single-session result patterns.

## Pre-flight

- [ ] Child 1 landed + new shared-types version pinned in this repo's `pyproject.toml`
  (`AppendTLCRoundRequest`, `TaskStatus.AWAITING_CONFIRMATION="awaiting_confirm"`,
  `TaskStatusMsgPayload.image_url`).
- [ ] Confirm NO migration needed for the status value (≤20 chars fits `String(20)` — design §2).

## Ordered checklist

1. [ ] **Plate-memory at PREP** (R4) — in the TLC create path: allocate plate/tank/boxes ONCE,
   write `task.params.session_binding {plate_slot, tank_slot, box_slots}`; pin `tank_slot`
   explicitly. Mark those plate/tank/box states OCCUPIED (R5).
2. [ ] **Round/cleanup op-build reads the binding** (R4) — replace the `_first_available` plate/
   tank/box calls (`allocate.py:144` path via `plan_from_request`) with reads of
   `session_binding`; feed exact slots into `plan_round` (`planner.py:131,145`).
3. [ ] **Append-round route + service** (R1) — `POST /tasks/{task_id}/rounds` (`AppendTLCRoundRequest`):
   gate `status == AWAITING_CONFIRMATION` (else 409); append a `TaskStep(skill_type=START_TLC)`;
   record ratio on `task.params["rounds"]`; `flag_modified`; `IN_PROGRESS`; `_submit_next`.
4. [ ] **Cleanup route + service** (R2) — `POST /tasks/{task_id}/cleanup`: same gate; append
   `TaskStep(skill_type=END_TLC)`; `flag_modified`; `IN_PROGRESS`; `_submit_next`.
5. [ ] **Terminal-detection edit** (R3, `task_service.py:249-266`) — no pending step + last
   completed `skill_type == END_TLC` → `COMPLETED`; else → park `AWAITING_CONFIRMATION`.
6. [ ] **TLC prep validator** (R5) — mirror `validate_setup_cartridges`
   (`command_validator.py:192`): reject if target plate/tank/box slot occupied.
7. [ ] **Photo URL on status** (R6) — in `_build_status_message` (`task_service.py:411-433`),
   set `image_url` from the round skill's `SkillResult.captured_images` (round skills only).
8. [ ] **Wire observe/photo into the round op program** (R7) — call
   `observe_view`/`observe_uv`/`take_photo` after `_immerse_and_aim` in `plan_round`.
9. [ ] **Round-skill `lab_params` resolution** (Q1) — make `plan_from_request` (or a round-aware
   variant) read `session_binding` + `task.params["rounds"][n]` instead of re-allocating.
10. [ ] **Spec docs** (R8, Rule 10) — update the lab TLC contract/spec docs for the new routes +
    state machine + plate-memory + occupancy.

## Tests (R8 / AC1–AC4) — the riskiest paths get focused unit tests

- [ ] State machine: prep→park, round→park, END_TLC→complete (the §8 keystone-risk edit).
- [ ] Append gate: 409 on append to `IN_PROGRESS` / `COMPLETED` / `FAILED`.
- [ ] Plate-memory: two rounds reuse the SAME plate/tank (assert `session_binding` stable).
- [ ] Occupancy: second TLC over an occupied slot → validation failure; passes after reset.
- [ ] `image_url` populated on a round-skill status; omitted on prep/cleanup.
- [ ] Append racing a just-parked task (concurrency — design §8).

## Validation

- [ ] `ruff check` · `uv run pyright app/` · `uv run pytest` all green.
- [ ] Manual bench: create → /rounds → /rounds → /cleanup; assert AC1 (one task, one fetch,
  shared plate, one dispose, park-between, complete-only-after-END_TLC).

## Risky points / rollback

- Terminal-detection edit (step 5) — focused tests first; revert it alone if it misfires.
- The `_first_available` → `session_binding` swap (step 2) — keep it localized to the TLC
  op-build path; CC/RE allocation untouched.
- Append routes are net-new — additive, safe to revert as a unit.

## Cross-child constraint raised by this child

- ⚠️ Child 1's `AWAITING_CONFIRMATION` wire value MUST be ≤20 chars (`"awaiting_confirm"`) — the
  `tasks.status` column is `String(20)`. Already fed back into child-1 design/implement.
