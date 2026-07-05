# Research: AWAITING_CONFIRMATION concurrency model (parked TLC = robot free?)

- **Query**: Is Drake's "a parked TLC task at AWAITING_CONFIRMATION frees the robot for other work" model feasible AND faithful (no physical plate/slot collision)?
- **Scope**: internal (BIC-lab-service primary, BIC-agent-service secondary)
- **Date**: 2026-06-29

---

## Verdict (decision-grade)

**FEASIBLE-WITH-GUARD.**

- Drake's premise that the **robot is physically idle** when a TLC task parks with no pending skill is **TRUE** in today's model — robot occupancy is driven by skill assignment / robot-reported state, not by task status. A parked task holds no robot. (Q1, Q2 ✅)
- BUT the **plate/slot/material reservation is NOT protected**. The TLC allocator picks instances by `state != "disposed"` and picks slots by row-existence occupancy, and the placement writer **never changes state** (parked plate stays `unused`). So a concurrent second TLC trial would re-pick the SAME silica plate / tube boxes the parked task already owns. The single-TLC-in-flight invariant is **documented but NOT enforced** anywhere. (Q3, Q4 ❌ — collision risk is real)
- Workstation collision with CC/RE is **not** a concern: TLC uses its own workstations + slot namespace. (Q3 ✅)
- Nothing reclaims a parked plate if the agent abandons the task. (Q5 ❌)

**Minimal guard needed:** keep the robot free, but enforce **"at most one active (non-terminal, including AWAITING_CONFIRMATION) TLC task"** at the TLC create boundary, OR reserve the plate/box instances (a non-`unused`/non-`disposed` allocator-visible state) for the lifetime of the parked task. The cheapest faithful guard is the single-active-TLC gate, because that is the exact assumption `cleanup_orphan_tip_boxes` and the plate-memory design already silently rely on.

---

## Findings

### Files found

| File Path | Role in this question |
|---|---|
| `BIC-lab-service/app/services/command_validator.py` | What validation gates on (robot state, not task status) |
| `BIC-lab-service/app/repositories/robot.py` | `assign_skill` / `clear_skill` / `get_idle_robots` — robot occupancy model |
| `BIC-lab-service/app/services/robot_service.py` | `is_robot_available`, `update_state` |
| `BIC-lab-service/app/services/skill_service.py` | `_exec_skill` — when robot gets `current_skill_id`; note it does NOT set WORKING |
| `BIC-lab-service/app/services/handlers/log_handler.py` | Sole writer of `robot.state = WORKING` (from robot's own update) |
| `BIC-lab-service/app/services/handlers/result_handler.py` | Clears `current_skill_id` on skill completion |
| `BIC-lab-service/app/services/handlers/heartbeat_monitor.py` | Stale detection — touches robots only, never tasks |
| `BIC-lab-service/app/tlc/allocate.py` | `_first_available`, `_pick_free_slot` — instance + slot allocation |
| `BIC-lab-service/app/tlc/inventory.py` | `what_at` occupancy = row existence; `_first_available` filter |
| `BIC-lab-service/app/tlc/placement.py` | Placement writer — writes `location_id` only, NEVER `state` |
| `BIC-lab-service/app/tlc/service.py` | `cleanup_orphan_tip_boxes` documents the single-robot-sequential invariant (lines 261-281) |
| `BIC-lab-service/app/services/task_service.py` | `create_task` (no single-TLC gate); `_submit_next` dispatch; `_release_robot_from_skill` |
| `BIC-lab-service/app/data/seed.py` | TLC workstations + 53 TLC slot rows, distinct namespace |
| `BIC-agent-service/app/scheduler/decision_expiry.py` | Agent-side reconciler — HITL decisions only, no lab/plate state |

---

### Q1 — Robot-occupancy model: is a parked task holding no robot? → **TRUE**

Robot busy/idle is governed by TWO independent signals, **neither of which is task status**:

1. **`robot.current_skill_id`** — set by `assign_skill` immediately before MQ publish:
   - `robot.py:119` `robot.current_skill_id = skill_id` (raises at `:115-117` if not IDLE).
   - Cleared on skill completion by the result handler: `result_handler.py:196` `await robot_repo.clear_skill(skill_record.robot_id)` (per the documented single-owner rule).
   - Also cleared on MQ-publish failure: `skill_service.py:209` `await self.robot_repo.clear_skill(resolved_robot_id)`.
   - Also cleared between task steps: `task_service.py:588` `await robot_repo.clear_skill(robot_id)`.

2. **`robot.state`** — `WORKING` is written **only** by the log handler from the robot's OWN reported state, not by skill assignment:
   - `log_handler.py:204` maps `"working" → RobotState.WORKING`, `:207-208` `update_state(...)`.
   - Note `assign_skill` does NOT set `state=WORKING` (`robot.py:94-122` only touches `current_skill_id`). The robot reports its own `working`/`idle` transitions on `#.log`.
   - `_release_robot_from_skill` resets to IDLE: `task_service.py:589` `update_state(robot_id, RobotState.IDLE)`.

**Conclusion:** When a TLC task parks with NO pending/in-flight skill, the just-completed skill's result handler has already run `clear_skill` (`result_handler.py:196`) and the robot has reported itself back to `idle`. So the robot has `current_skill_id IS NULL` and `state == IDLE`. **Drake's premise holds: a parked task holds no robot.** The proposed `AWAITING_CONFIRMATION` task status is purely a logical task-level placeholder; it has no representation in the robot row.

---

### Q2 — What does CommandValidator gate on? → **ROBOT state, NOT task status**

`validate_robot_available` is the only resource gate, and it checks the **robot** row:

- `command_validator.py:160-186`: resolves `allowed_states` per skill (default `{RobotState.IDLE}`, `:161`), then for a named robot checks `robot.state not in allowed_states` (`:172`); for auto-assign it calls `repo.get_idle_robots()` (`:182`).
- `get_idle_robots` filters purely on `state == RobotState.IDLE` (`robot.py:46-50`) — it does **not** consult `current_skill_id` and does **not** consult any task.
- `is_robot_available` (the stricter check) does AND both: `robot_service.py:227` `robot.state == RobotState.IDLE and robot.current_skill_id is None` — but this is NOT called in the validation/dispatch path; `_exec_skill` uses `validate_command` → `validate_robot_available` (`skill_service.py:143`).
- No validator anywhere references `TaskStatus` / a parked task. Searched `command_validator.py` — task status never appears.

**Conclusion:** Validation gates on robot idle, never on task status. **A parked TLC task (robot idle, no `current_skill_id`) would NOT block another task from validating or dispatching.** Confirmed — this is exactly the behavior Drake wants for "robot free for other work," and it already works that way. (Caveat: the dispatch path uses `validate_robot_available`, the laxer of the two checks, which only reads `state`; a robot that is IDLE-but-`current_skill_id`-set would still pass auto-assign's `get_idle_robots`. Not relevant to the parked case since the parked case has `current_skill_id` already cleared, but worth noting for the design.)

---

### Q3 — PHYSICAL collision risk → **REAL for plate/box/slot; NOT a risk for workstation**

**(a) Workstation: distinct, no collision.** TLC has its own workstations and its own slot-id namespace:
- TLC workstations: `seed.py:343-353` — `ws_bic_09_sa_004` (supply), `ws_bic_09_wb_001` (desk), `ws_bic_09_wb_002` (disposal). CC/RE use `ws_bic_09_fh_001/002` etc. (`seed.py:21-25`).
- TLC slots are a separate set of 53 rows (`seed.py:356-388`, e.g. `tlc_silica_plate` ×4, `tlc_tube_box_2ml` ×3, `tlc_developing_tank` ×3). They parse via `SlotId.parse`; non-TLC rows are skipped by the allocator (`allocate.py:176-179`). So CC/RE cannot grab a TLC slot and vice versa.

**(b) Plate / box / tube-box instances: NOT protected — collision risk.** The allocator picks an instance with a filter that a parked task's reserved-but-idle plate STILL satisfies:
- `allocate.py:144-153` `_first_available`: `WHERE object_type == X AND state != "disposed" ORDER BY id` → `.first()`. The ONLY exclusion is `disposed`.
- The placement writer that runs when START_TLC succeeds writes `location_id` **but explicitly never writes `state`**: `placement.py:13` "A `place` op updates ONLY `location_id` …, NEVER `state`"; `placement.py:155` `set_location(object_id, dest_slot.location_id)`. Materials "keep whatever state allocation gave them (`unused`)" (`placement.py:16-18`).
- Therefore a plate the parked task is mid-developing sits at its slot with `location_id` set but `state == "unused"`. A SECOND TLC trial's `_first_available(SILICA_PLATE)` would order by id and re-return that SAME plate row (seed has 4 plates `seed.py:383`, so it might pick a different one only by luck/ordering — there is no logic guaranteeing distinctness across tasks).

**(c) Slot occupancy is within-pass only.** `_pick_free_slot` (`allocate.py:155-166`) computes `occupied = await self._occupied_ids(all_slots) | self._reserved_slots`. `_occupied_ids` is row-existence at a `location_id` (`allocate.py:184-190`, `inventory.py:66-74` `what_at` = `WHERE location_id = :id`). `_reserved_slots` (`allocate.py:89`) is reset per `TLCAllocator` instance ("Construct one per round/run", `allocate.py:80-82`). So cross-task slot exclusion relies entirely on the parked task's objects already having a written `location_id` row at that slot — which IS true for placed objects (the placement writer wrote it), so two tasks would at least pick different *slots*. But they can still pick the same *instance* (point b), and an instance double-booked onto two different slots corrupts the plate-memory.

**Conclusion:** Workstation isolation is fine. Instance reservation (the silica plate especially, and the 2ml/50ml boxes) is **not** protected against a concurrent TLC task; the developing tank/plate physically owned by the parked task is allocator-visible as available.

---

### Q4 — Single-TLC-in-flight invariant: documented, NOT enforced

- The invariant is **documented** in `tlc/service.py:272-275` (`cleanup_orphan_tip_boxes` docstring): *"Safe only under the single-robot-sequential assumption (the documented placement-model invariant): with one TLC dispatch in flight at a time, every unplaced unused lab-minted tip box is an orphan of the just-failed attempt, never a concurrent task's in-flight material."*
- It is **NOT enforced** anywhere:
  - `create_task` (`task_service.py:74-128`) validates only param-shape (`validate_tlc_task_params`, `:103`) and material readiness (`validate_task_materials`, `:107`). It does **not** query for an existing active/parked TLC task. No "already in progress" / "active task" guard exists (grep for these terms in `task_service.py` returns nothing).
  - The invariant is therefore an **assumption**, not `IN_PROGRESS`-based nor robot-based enforcement.
- Consequence: **a SECOND TLC trial CAN be created while the first is parked**, and its allocation pass will re-run `_first_available` over the same `tlc_inventory`, able to grab the same plate slot/instance (Q3b). `cleanup_orphan_tip_boxes` (`task_service.py:497`) would also become unsafe — it deletes ALL unplaced unused lab-minted tip boxes, which under concurrency could be the OTHER task's freshly-minted in-flight material.

---

### Q5 — Agent-side reconciler / timeout: nothing reclaims a parked plate

- **Lab side:** `heartbeat_monitor.py` scans robots only and flips stale robots to `DISCONNECTED` (`heartbeat_monitor.py:55-81`); it never reads or fails `tasks`, never touches `tlc_inventory`. There is no task-level stale/timeout sweeper in lab-service. `TaskStatus.TIMEOUT` does not even exist (enum is `pending/in_progress/waiting/completed/failed/cancelled`, `bic_shared_types/experiment_task/http/enums.py:14-22`).
- **Agent side:** the only background reconciler is `DecisionExpiryScheduler` (`BIC-agent-service/app/scheduler/decision_expiry.py:21-66`), which by its own docstring "holds NO persistence, NO decision_id, NO business state" — it only ticks HITL decision expiry via `fast_path.tick_expired_decisions()`. It does not reclaim plates, fail lab tasks, or know about `tlc_inventory`.

**Conclusion:** If a parked TLC task is abandoned (agent crash, never appends the next round), **nothing reclaims the plate/tank or fails the task**. The plate stays at its slot, `state == unused`, indefinitely. Combined with the missing single-TLC gate (Q4), this is the worst case: an abandoned parked plate is silently allocatable to the next TLC trial.

---

### Q6 — Fidelity verdict

| Dimension | Today's reality | Drake's model |
|---|---|---|
| Robot free while parked | YES — `current_skill_id` cleared, `state` reported IDLE (Q1) | ✅ FAITHFUL |
| Other task can validate/dispatch | YES — validator gates on robot, not task status (Q2) | ✅ FEASIBLE |
| Plate/box instance reserved | NO — `_first_available` ignores reservation; state stays `unused` (Q3b) | ❌ NOT protected |
| Slot distinct across tasks | Partially — written `location_id` rows make slots distinct, but instances aren't (Q3c) | ⚠️ partial |
| Single-TLC-in-flight enforced | NO — assumption only (Q4) | ❌ NOT enforced |
| Abandoned-park recovery | NO — no reconciler touches tasks/plates (Q5) | ❌ none |

**"Robot free" = fine. "Workstation/plate slot free" = NOT fine.** Drake is right that the ROBOT can do other work while parked; the system already lets it. The danger is purely the **reserved physical materials** (silica plate mid-development in a tank, plus the 2ml/50ml tube boxes and their slots) that the allocator will happily hand to a concurrent or subsequent TLC task.

---

## Minimal guard (recommended)

**Free the robot (no change needed — it already is), but guard the plate.** Cheapest faithful option that matches the design's existing assumptions:

1. **Enforce single-active-TLC at the TLC create boundary** (`task_service.create_task`, TLC branch ~`:100`): reject a new TLC task if any TLC task is in a non-terminal status — and define `AWAITING_CONFIRMATION` as non-terminal for this check (add it to a "TLC occupies materials" set alongside `PENDING/IN_PROGRESS/WAITING`). This single gate simultaneously:
   - prevents plate/box double-allocation (Q3b),
   - makes the documented `cleanup_orphan_tip_boxes` invariant TRUE instead of assumed (Q4),
   - is the smallest change (no new instance-state machinery).

2. **(Heavier alternative, only if true concurrency is ever wanted)** give the allocator a reservation-aware state so `_first_available` excludes instances owned by an active/parked TLC task (e.g. a `reserved`/`using` state set at allocation and cleared on task terminal). This is more work and contradicts the placement writer's deliberate "location-only, never state" design (`placement.py:13-18`), so prefer option 1 for the MVP.

3. **Abandoned-park recovery (Q5)** is a separate gap — out of scope for the collision question, but flag it: with `AWAITING_CONFIRMATION` parked indefinitely and no reconciler, an abandoned plate is leaked. If single-active-TLC (option 1) is adopted, an abandoned parked task would also **block all future TLC** until manually failed, so a parked-task timeout/cancel path will be needed to make option 1 operable.

---

## Caveats / Not determined from code

- **`AWAITING_CONFIRMATION` does not exist yet** — it is not in `TaskStatus` (`bic_shared_types/.../enums.py:14-22`) nor referenced in either repo (grep returned nothing). All findings describe how today's code WOULD treat such a parked task, assuming it is modeled as a non-terminal `tasks.status`.
- The current TLC `TASK_STEPS` is a fixed 2-step `[start_thin_layer_chromatography, end_thin_layer_chromatography]` (`task.py:127-130`) with rounds interleaved out-of-band by lab-run (per the comment `task.py:121-126`). The "skills appended over time / one Task per trial" round-based redesign is NOT in the code yet; this research evaluates the concurrency consequences against the existing allocation + occupancy machinery, which the redesign would reuse.
- Whether two TLC tasks could ever be dispatched *truly simultaneously* (same instant) also depends on the single-robot deployment ("Typically only one robot exists per lab installation," `robot.py:17`). With one robot, two TLC START skills can't run at the same instant — but the parked-task scenario is exactly the case where the robot IS free, so a second TLC's START could dispatch while the first is parked. That is the collision window this research is about.
