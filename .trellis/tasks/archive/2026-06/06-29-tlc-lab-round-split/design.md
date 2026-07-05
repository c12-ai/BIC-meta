# Design — Lab-side TLC round split (child 2, lab-service)

> SECOND in the chain. Consumes child-1 contracts. Carries the heaviest risk (open-Task
> engine edit + plate-memory + occupancy). Parent `design.md` §2.1/§2.4/§2.5 is authority.

## 1. The state machine (the keystone — grill Q7; CORRECTED at impl §IMPL-1)

**IMPL-1 divergence (accepted):** there is NO separate no-op "prep skill". The existing
`START_TLC` skill already bundles pickup(round-1-gated)+spot+develop, and
`CreateTLCTaskRequest.param` carries round-1's chemistry. So **create = round 1**
(`TASK_STEPS[TLC] = [START_TLC]`); appends run rounds 2..N; cleanup appends `END_TLC`. This
honors "no robot-protocol change" — a standalone prep skill would have needed one.

```
PENDING ─(create: round-1 START_TLC done)─→ AWAITING_CONFIRMATION
  ─(POST /rounds: append START_TLC)────────→ IN_PROGRESS ─(round done)→ AWAITING_CONFIRMATION ←┐
                                                                              └────── loop ────┘
  ─(POST /cleanup: append END_TLC skill)───→ IN_PROGRESS ─(END_TLC done)→ COMPLETED
```

- **Terminal detection** (`task_service.py:249-266` edit): when a skill completes with NO pending
  step → if `last_completed.skill_type == SkillType.END_TLC` (`"end_thin_layer_chromatography"`)
  → `COMPLETED`; else → park `AWAITING_CONFIRMATION`. (Today: unconditional `COMPLETED`.)
- **Append gate:** `/rounds` + `/cleanup` accept ONLY `task.status == AWAITING_CONFIRMATION`;
  else 409. The sole state the agent grows the task from — prevents append-to-busy/terminal.
- **Robot-free park:** `AWAITING_CONFIRMATION` is NOT in `_TERMINAL`; the parked task holds no
  pending skill so the robot is already idle (`result_handler` cleared it). CC/RE may run meanwhile.

## 2. The `String(20)` blocker (found during design — MUST resolve in child 1 OR here)

`tasks.status` is `mapped_column(String(20))` (`models/task.py:60`). The proposed value
`"awaiting_confirmation"` is **21 chars — it will not fit.** Two options:
- **(A, recommended)** child 1 uses a ≤20-char enum value, e.g. `AWAITING_CONFIRMATION =
  "awaiting_confirm"` (16). No migration; cleanest.
- **(B)** widen the column to `String(32)` via an Alembic migration here in child 2.
**Decision: (A)** — pick a ≤20-char wire value in child 1 (update child-1 design S1 accordingly).
This is a cross-child constraint: FLAG to child 1 before it implements the enum.

## 3. Append seam (Q1 resolved)

- `create_task` builds steps as `TaskStep(step_index=i, skill_type=...)` and mutates via
  `steps.append` + `flag_modified(task, "steps")` then `_submit_next` (`task_service.py:115,198,
  248,440`). The append routes follow the SAME pattern: append one `TaskStep` (round → START_TLC;
  cleanup → END_TLC), `flag_modified`, flip `IN_PROGRESS`, `_submit_next`.
- `_resolve_tlc_step` (`task_resolver.py:216`) builds `lab_params` via
  `TLCService.plan_from_request`. The round skill's `lab_params` must resolve from the round's
  ratio + the stored `session_binding`. So `plan_from_request` (or a new round-aware variant)
  READS `task.params.session_binding` + `task.params["rounds"][n]` instead of re-allocating.

## 4. Plate-memory (parent §2.4) — `task.params.session_binding`

```
task.params: { session_binding: {plate_slot, tank_slot, box_slots}, rounds: [{ratio}, ...] }
```
- PREP allocates plate/tank/boxes ONCE (existing `_slot_index`/allocate path) → writes
  `session_binding`. Pin `tank_slot` explicitly (else `plan_round` defaults it to `round_index`,
  `planner.py:160-163`, drifting round 2 to tank 2).
- ROUND/CLEANUP op-build reads `session_binding` → feed exact `silica_plate_slot` /
  `developing_tank_slot` into `plan_round` (planner already accepts them, `planner.py:131,145` —
  no planner change). Replaces the `_first_available` calls (`allocate.py:144`).

## 5. Occupancy guard (parent §2.5) — validation, not reservation

- PREP marks the bound plate/tank/box state OCCUPIED (mirror CC's consumable `using`/`used`);
  the placement writer currently never sets `state` (`placement.py:13,155`) — this is the gap.
- Add a TLC prep validator (mirror `validate_setup_cartridges`, `command_validator.py:192`) that
  rejects if the target plate/tank/box slot is occupied. So a second TLC over an abandoned plate
  fails loudly; chemist resets. No reservation/scheduler.

## 6. Photo URL (R6)

When a round skill completes, the round's `SkillResult.captured_images` already holds the robot's
uploaded photo URL (`repositories/skill.py:240`). Surface the first/primary URL onto
`TaskStatusMsgPayload.image_url` (child-1 field) in `_build_status_message`
(`task_service.py:411-433`). Only for round skills; prep/cleanup statuses omit it.

## 7. Observe/photo wiring (R7)

`observe_view`/`observe_uv`/`take_photo` are defined but never called (`planner.py:326-372`). Wire
them into the round skill's op program (after `_immerse_and_aim`) so a round actually photographs
the developed plate. No robot-protocol change — they already return existing `*LabParams`.

## 8. Risks

- **The terminal-detection edit is the single riskiest line** — a wrong branch either auto-completes
  a task mid-loop (loses the trial) or never completes (hangs). Needs focused unit tests for all
  three transitions (prep→park, round→park, END_TLC→complete).
- **Concurrency:** the append commits while `on_skill_completed` may still be finishing — the
  append-gate (`AWAITING_CONFIRMATION` only) + the single-session result handling
  (CLAUDE.local.md) are the guards; test an append racing a just-parked task.
- **`flag_modified` discipline:** every `task.steps` / `task.params` mutation needs
  `flag_modified` or JSONB won't persist (existing pattern — match it).
