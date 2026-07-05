# Lab-side TLC prep/run-round/cleanup split + photo URL

> Child 2 of parent **06-28-tlc-retry-loop-boundary**. SECOND in the chain (after child 1
> contracts; before child 3 agent). Carries ~80% of the redesign risk: the open-Task engine
> edit + plate-memory + occupancy. Read parent `design.md` §2.1/§2.4/§2.5 + the research files
> before coding. Rule 10: any contract touch updates the spec.

## Goal

Turn the lab's single-shot TLC task into an aggregator Task the agent grows by appending skills:
one Task per trial; prep allocates the plate/tank/boxes ONCE and stores the binding; each
appended round reuses that binding to develop + photograph + return the photo URL; cleanup
disposes once. The Task parks in `AWAITING_CONFIRMATION` between rounds (robot free).

## Confirmed facts / decisions (from parent + grill — do not re-litigate)

- **1 trial = 1 Task; rounds = appended skills.** No `tlc_session` table; plate memory is
  `task.params.session_binding` on the ONE Task.
- **State machine (grill Q7, CONFIRMED):**
  ```
  PENDING ─(prep done)→ AWAITING_CONFIRMATION
    ─(append round)→ IN_PROGRESS ─(round skill done)→ AWAITING_CONFIRMATION   ← loop
    ─(append cleanup)→ IN_PROGRESS ─(END_TLC done)→ COMPLETED
  ```
- **Terminal detection by `skill_type`:** last completed skill == `SkillType.END_TLC`
  (`"end_thin_layer_chromatography"`) → `COMPLETED`; any other skill done with no PENDING step
  → park `AWAITING_CONFIRMATION`. No extra intent flag.
- **Append gate:** append-round + cleanup routes accept ONLY a task in `AWAITING_CONFIRMATION`
  (reject 409 if `IN_PROGRESS` / terminal). This is the only state the agent grows the task from.
- **`AWAITING_CONFIRMATION` is robot-free** (parent §2.5): a parked task holds no pending skill,
  robot already idle. Do NOT add it to `_TERMINAL`. Do NOT mark the bench busy.
- **Collision guard = validation + material state** (NOT reservation): TLC prep must MARK its
  plate/tank/box occupied so the next TLC prep's validation fails if a slot is still occupied
  by an abandoned plate. Mirror CC's `state != UNUSED` pattern. Manual reset is the chemist's job.
- **No robot-protocol change:** reuse existing `START_TLC` / `END_TLC` skills + the `plan_*`
  planner surface. Wire the dead `observe_view`/`observe_uv`/`take_photo` ops into the round skill.

## Requirements

- **R1 — Append-round route + service.** `POST /tasks/{task_id}/rounds` (`AppendTLCRoundRequest`,
  from child 1): gate on `AWAITING_CONFIRMATION`; append a round skill to `task.steps`; record the
  round's ratio on `task.params["rounds"]`; flip `IN_PROGRESS`; `_submit_next`. No append path
  exists today — this is net-new.
- **R2 — Cleanup route + service.** `POST /tasks/{task_id}/cleanup`: gate on `AWAITING_CONFIRMATION`;
  append the `END_TLC` dispose skill; flip `IN_PROGRESS`; `_submit_next`.
- **R3 — Terminal-detection edit** (`task_service.py:249-266`): replace unconditional
  auto-complete-when-no-PENDING with the `skill_type == END_TLC ? COMPLETED : park
  AWAITING_CONFIRMATION` rule.
- **R4 — Plate-memory.** TLC create allocates plate/tank/boxes ONCE → write
  `task.params.session_binding {plate_slot, tank_slot, box_slots}`. Round/cleanup op-build READS
  it (replace the `_first_available` calls). Pin `tank_slot` explicitly (don't let it default to
  `round_index`).
- **R5 — Occupancy marking + TLC validator.** Mark the bound plate/tank/box state occupied at prep;
  add a TLC prep validator that rejects if the target slots are occupied (mirror CC validators).
- **R6 — Photo URL on status.** When a round skill completes, surface its
  `SkillResult.captured_images` URL on `TaskStatusMsgPayload.image_url` (child-1 field).
- **R7 — Wire observe/photo into the round skill program** (currently dead `plan_*` ops).
- **R8 — Spec + tests (Rule 10).** Update the lab TLC spec/contract docs; lab pytest green.

## Acceptance criteria

- [ ] **AC1** Create → append round → append round → cleanup against the bench: ONE Task / one
  `task_id`; one material fetch; both rounds reuse the SAME plate/tank (assert `session_binding`);
  one dispose; Task parks `AWAITING_CONFIRMATION` between rounds; `COMPLETED` only after END_TLC.
- [ ] **AC2** Append to a non-`AWAITING_CONFIRMATION` task → 409 (busy/terminal rejected).
- [ ] **AC3** `image_url` present on the status when a round skill completes.
- [ ] **AC4** A second TLC prep while a plate slot is still occupied → validation failure (collision
  guard works); after `reset-to-test-data` it succeeds.
- [ ] **AC5** `ruff check` + `uv run pyright app/` + `uv run pytest` green; spec docs updated.

## Out of scope

- Agent-side loop + ingress edit (child 3); shared-types definitions (child 1).
- Orphan auto-recovery / parked-task timeout (by design: chemist manual reset — parent §2.5).
- Old single-shot path deletion (parent Phase 3b).

## Open questions

- Q1: does the append happen as a NEW Skill row appended to `task.steps`, and does
  `task_resolver` resolve the round skill's `lab_params` from `task.params["rounds"][n]`? Confirm
  the resolver seam in design.
- Q2: migration for `AWAITING_CONFIRMATION` — is it a `String(20)` status column (no DB enum), so
  no migration needed? Verify (`models/task.py` uses `String(20)`).
