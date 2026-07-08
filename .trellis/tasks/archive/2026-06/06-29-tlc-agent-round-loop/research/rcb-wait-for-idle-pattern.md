# Research: RC-B wait-for-idle-then-submit pattern (lab-service)

- **Query**: Does BIC-lab-service already have an event-driven "wait until robot is idle, then submit the next step" mechanism that RC-B's TLC next-step submission can REUSE, instead of hard-failing when the single robot is momentarily WORKING?
- **Scope**: internal (BIC-lab-service)
- **Date**: 2026-06-30

## Verdict (lead)

**REFUTE.** There is **no** existing wait-for-idle-then-submit / robot-idle-event / queue / outbox-drainer / retry-on-busy machinery in the current tree. Submission of the next step is **purely synchronous** at `on_skill_completed` time. The only "re-submit later" path is **timer-driven** (`_delayed_submit_next`, RE evaporation), keyed on a clock deadline — **not** on a robot-idle state condition. The `outbox` table referenced in `CLAUDE.local.md` **does not exist** in the current migrations or codebase (stale note). CC/RE dodge RC-B **purely** via the `SKILL_ALLOWED_ROBOT_STATES` allow-list; START_TLC/END_TLC are **not** on it.

So the smallest correct fix is NOT "hook into an existing idle-event path" (none exists). It is one of two minimal options (§6).

## Findings

### Files Found

| File Path | Role in RC-B |
|---|---|
| `BIC-lab-service/app/services/task_service.py` | `_submit_next` (next-step dispatch + the hard-fail catch), `on_skill_completed` (synchronous advance), `_delayed_submit_next` (the ONLY re-submit-later path, timer-based), `_remaining_delay` (the timer source) |
| `BIC-lab-service/app/services/command_validator.py` | `validate_robot_available` (emits "No idle robots available"), `SKILL_ALLOWED_ROBOT_STATES` allow-list (CC/RE escape hatch) |
| `BIC-lab-service/app/services/skill_service.py` | `_exec_skill` (raises the HTTPExceptions `_submit_next` catches), `_resolve_robot` (the second, TOCTOU rejection site) |
| `BIC-lab-service/app/services/handlers/result_handler.py` | `process_result` clears robot → IDLE; `_advance_task` then runs the next step in a fresh session |
| `BIC-lab-service/app/services/handlers/heartbeat_handler.py` | robot state-change writer on heartbeat — does NOT react by submitting work |
| `BIC-lab-service/app/services/handlers/heartbeat_monitor.py` | only background asyncio loop; marks stale robots DISCONNECTED — no submit hook |
| `BIC-lab-service/app/repositories/robot.py` | `get_idle_robots`, `assign_skill` (re-checks IDLE, raises ValueError), `clear_skill`, `update_state` |
| `BIC-lab-service/app/core/lifespan.py` | startup wiring — confirms the only background task is `heartbeat_monitor` |

---

### Q1 — The robot idle-flip event path. Is a "couldn't submit (busy)" step ever re-submitted when the robot LATER goes idle?

**No. Submission is purely synchronous at `on_skill_completed` time.** Trace:

1. Robot result arrives → `handle_robot_result` (`result_handler.py:50`). Phase 1: `process_result` (`result_handler.py:125`) marks the skill COMPLETED and, at `result_handler.py:188-197`, **clears the robot**: `robot_repo.clear_skill(...)` (current_skill_id → NULL). Note: `process_result` clears `current_skill_id` but **does NOT itself set `state=IDLE`** here — see Q4/caveat.
2. Phase 2: `_advance_task` (`result_handler.py:398`) opens a **fresh session** and calls `TaskService.on_skill_completed` (`result_handler.py:409`).
3. `on_skill_completed` (`task_service.py:249`) on success releases the robot via `_release_robot_from_skill` (`task_service.py:308`), which sets `state=IDLE` (`task_service.py:837`), then immediately, **in the same call stack**, dispatches the next step:
   - timer branch: `WAITING` + `_delayed_submit_next` (`task_service.py:324-351`)
   - **immediate branch**: `await self._submit_next(task)` (`task_service.py:352-353`)
   - TLC park branch: `AWAITING_CONFIRMATION` (`task_service.py:354-377`)
   - terminal branch (`task_service.py:378-397`)

There is **no** place where a step that fails to submit (robot busy) is parked and re-tried when the robot later flips IDLE. The next step is submitted **once, synchronously**, and on rejection `_submit_next` goes straight to the hard-fail block (`task_service.py:704-769`): step FAILED, remaining CANCELLED, task FAILED. **Confirmed: no re-submit-on-idle path exists.**

The RC-B timing window: for TLC round/cleanup, the next step is appended and submitted via `_append_skill_and_resume` → `_submit_next` (`task_service.py:243`), an **agent-triggered** path (POST append), which is exactly when the robot may still be settling WORKING from the just-parked round.

---

### Q2 — Existing WAITING + re-submit machinery. Is `_delayed_submit_next` state-driven or timer-driven?

**Timer-driven only.** `_remaining_delay` (`task_service.py:847-881`) returns a positive value **only** for `END_EVAPORATION` (`task_service.py:855-856`): it computes `ceil(sum(air_pressure.duration_min)*60)` minus elapsed since `start_evaporation.finished_at`. Every other skill returns `0`.

When `remaining > 0` the task goes `WAITING` and schedules `asyncio.create_task(_delayed_submit_next(task.id, remaining))` (`task_service.py:351`). `_delayed_submit_next` (`task_service.py:906-939`) does `await asyncio.sleep(delay_seconds)` then `_submit_next`. It re-checks status (`!= WAITING` → skip, `task_service.py:932`) but the trigger is **the clock, not robot state**. It never inspects `robot.state` and has no idle condition. **Confirmed: this is the ONLY re-submit-later path, and it is purely a sleep timer. Nothing re-submits on a robot-idle state condition.**

---

### Q3 — Any queue / pending-submit / retry-on-busy / outbox drainer?

**None.**

- **Outbox: does not exist.** `grep -rni "outbox" .` over the entire repo (`*.py`, `*.sql`, excluding `.venv`) returns **zero hits**. `alembic/versions/` contains 11 migrations and **none** is an `add_outbox_table` migration (full list: `0001_init_schema`, `0002_seed_test_data`, `0b3e29d761ed_seed_tlc_slots_and_inventory`, `2d60ab0cf374_add_rack_and_inventory_tables`, `9f83d1f8d2b7_make_silica_areas_maintainable`, `b1813a458d3f_add_tlc_inventory_table_and_tlc_`, `c4e1a7f2b9d3_sample_tube_area_capacity_5`, `d5f2a8c41b67_seed_three_sample_tube_boxes`, `d7b3d83f9f77_add_agent_side_task_id_to_tasks`, `e7a3c9f1d28b_tlc_rack_box_slots_per_floor`, `0002`). The `CLAUDE.local.md` note ("Phase B: adds the transactional `outbox` table … `9d25dd2c3177_add_outbox_table.py`") is **STALE** — that migration is not present in this tree. **No outbox to drain or reuse.**
- **No robot-command queue.** Skills are created PENDING then published to MQ inline inside `_exec_skill` (`skill_service.py:156-182`). There is no staging table polled by a dispatcher; "PENDING" is a transient pre-publish status, not a queue (`get_pending_skills` at `skill_service.py:291` is an unused query helper, not a drainer).
- **No retry-on-busy.** The only `retry`/`drain`/`poll` matches in `app/services` + `app/infrastructure` are: a heartbeat-monitor log line ("will retry next cycle", `heartbeat_monitor.py:38`) and TLC planner phrasing ("retry round", `tlc/service.py:354`, `tlc/planner.py:439` — chemistry-round semantics, unrelated to robot-busy). No code retries a rejected submission.
- **No scheduler / idle-poller.** `lifespan.py` starts exactly one background asyncio task: `heartbeat_monitor.start()` (`lifespan.py:100`). It scans for **stale** robots and marks them DISCONNECTED; it has no submit hook (verified: no `submit`/`pending` references in its body).

**Confirmed: no queue, no outbox, no drainer, no idle-poller, no retry-on-busy anywhere.**

---

### Q4 — Does a robot heartbeat / idle-flip trigger pending work?

**No.** `heartbeat_handler.handle_robot_heartbeat` (`heartbeat_handler.py:28`) updates `robot.last_heartbeat_at` always (`:91`), and updates `robot.state`/`location` when changed (`:74-88`) — including IDLE transitions reported by the robot — then commits (`:93`). It emits **no event** that any submit path subscribes to; there is no "robot became idle → drain pending" handler anywhere. The state write is a dead-end w.r.t. task advancement.

There is **no robot-idle event** in the system that any submit logic listens to. The robot's return to IDLE after a skill is performed by the lab service itself in `_release_robot_from_skill` (`task_service.py:823-838`, sets `state=IDLE`) as a synchronous prelude to the single inline `_submit_next` — it is not a published/observable event that a parked step could await.

---

### Q5 — CC/RE comparison: why do they never hit RC-B?

**Purely the allow-list.** `CommandValidator.SKILL_ALLOWED_ROBOT_STATES` (`command_validator.py:127-138`) lists CC/RE handoff skills with `{IDLE, WORKING}`:

```
START_CC, TAKE_PHOTO, END_CC, COLLECT_CC_FRACTIONS,
START_EVAPORATION, END_EVAPORATION  → {IDLE, WORKING}
SETUP_CC_BINS, DISPOSE_CC_BINS, DISPOSE_CARTRIDGES, DISPOSE_TUBE_RACK → {IDLE}
```

`validate_robot_available` (`command_validator.py:144-186`) looks up the skill's allowed states (default `{IDLE}` for anything not listed, `:161-164`). For a **specific** `robot_id`, WORKING passes for the allow-listed skills (`:172`). When `robot_id is None`, it short-circuits to `get_idle_robots()` and emits **"No idle robots available"** (`:182-184`) regardless of allow-list — but the task path goes through `_exec_skill`'s `_resolve_robot`, which only hits that when no robot_id is provided.

**START_TLC and END_TLC are NOT in the allow-list** (verified: `grep "START_TLC|END_TLC"` in `command_validator.py` → no matches). They also have **no dedicated case** in `validate_command`'s match (`command_validator.py:787-832`) — they fall to the `_` default branch (`:830-832`) → `validate_robot_available(skill_name=START_TLC/END_TLC)` → not in the dict → **default `{IDLE}`**. So a TLC next step submitted while the robot is momentarily WORKING is rejected. That **is** RC-B.

**Is the allow-list the ONLY mechanism for "next step during robot handoff"? Yes.** There is no wait-for-idle alternative. CC/RE simply assert "it's fine to submit while WORKING" and let the robot/exchange queue it. RC-B is the gap where TLC was never granted that same assertion.

**Two distinct rejection sites** can produce the RC-B failure (both caught by `_submit_next` at `task_service.py:704`):
1. `validate_robot_available` → `validation_failed_error` (HTTP 400) with message **"No idle robots available"** (no robot_id) or **"Robot {id} state 'working' not allowed for {skill} (allowed: idle)"** (specific robot_id). (`command_validator.py:175-176, 184`; raised at `skill_service.py:145`.)
2. TOCTOU: validation passes, then `assign_skill` re-checks IDLE and raises `ValueError("Robot {id} is not idle …")` (`robot.py:115-117`) → caught at `skill_service.py:193` → re-raised as `bad_request_error` (HTTP 400) (`skill_service.py:203`).

The fix in §6 must recognize **both** message shapes as "robot busy → wait", and must NOT swallow genuine validation failures (no cartridge, no plate, etc.).

---

### Q6 — Verdict + smallest correct fix

**There is no ready wait-for-idle-then-submit pattern to reuse.** (REFUTE.) The cleanest fix is to add a minimal busy-aware retry on the TLC next-step path, reusing the **existing** WAITING + `_delayed_submit_next` timer machinery as a polling re-trigger — i.e. NOT new event machinery, but a new small hook into the one re-submit-later path that already exists.

Two candidate shapes (decision is the design agent's; both are minimal):

**Option A (recommended) — catch the busy-rejection in `_submit_next`, route to WAITING + timer re-poll.**
- In `_submit_next`'s except block (`task_service.py:704`), **before** the hard-fail, classify the error. If it is the robot-busy rejection (message contains "No idle robots available" OR "not idle" OR "not allowed for … (allowed: idle)"), do NOT fail the task. Instead set `task.status = WAITING`, emit `STEP_WAITING`, and `asyncio.create_task(_delayed_submit_next(task.id, <short retry, e.g. 2-5s>))` — the SAME re-submit path RE already uses. The robot is the single `talos.001`; within a few seconds `_release_robot_from_skill`/heartbeat has flipped it IDLE and the retry succeeds.
- Genuine validation failures (no cartridge, no plate, MQ publish error) do NOT match the busy classifier → fall through to the existing hard-fail (`task_service.py:730-769`) unchanged. This preserves Rule 9 / fail-loud for real errors.
- Bound the retry (max attempts or max elapsed) so a robot stuck WORKING forever still eventually fails loudly rather than spinning.
- Reuses: `WAITING` status, `STEP_WAITING` event, `_delayed_submit_next` (`task_service.py:906`). Net new: an error classifier + a bounded retry counter. `_remaining_delay` stays RE-only; the busy-retry passes its own short delay directly to `_delayed_submit_next`.

**Option B — add START_TLC/END_TLC to the allow-list (`{IDLE, WORKING}`), mirroring CC/RE.**
- One-line-ish change to `SKILL_ALLOWED_ROBOT_STATES` (`command_validator.py:127-138`). This makes TLC behave exactly like CC/RE: submit-while-WORKING is accepted and the command rides along.
- **Risk to verify before choosing B:** this only fixes the *validation* rejection (site 1). It does **NOT** fix the TOCTOU `assign_skill` `ValueError` (site 2, `robot.py:115`) — `assign_skill` hard-requires IDLE and would still raise if the robot is genuinely WORKING at assign time, because there is only ONE robot and a WORKING robot has no free slot to take a second concurrent command. CC/RE get away with the allow-list because their WORKING-handoff skills are issued when the robot is in a *watch/monitor* sub-state that the lab models as WORKING-but-assignable… **but `assign_skill` does not encode that** — it blanket-rejects non-IDLE. So Option B likely does not fully resolve RC-B for a single robot that is actually mid-skill; it only helps if the robot is already cleared/IDLE by assign time, which is the timing race we're trying to tolerate. **Option A (wait + retry) is the robust fix; Option B alone is insufficient and is the kind of allow-list-only change that masked, not solved, the handoff problem.**

**Recommendation:** Option A. It tolerates the timing race correctly (wait for the single robot to finish, then submit), reuses the existing timer re-submit path, and keeps genuine failures loud.

## Caveats / Not Found

- **Stale doc:** `CLAUDE.local.md` describes an `outbox` table + `9d25dd2c3177_add_outbox_table.py` migration "Phase B". Neither exists in the current tree (verified by full-repo grep and `alembic/versions/` listing). Any plan must not assume an outbox drainer is available to hook into.
- **Robot IDLE write split:** `process_result` clears `current_skill_id` (`result_handler.py:196`) but the `state=IDLE` write happens in `TaskService._release_robot_from_skill` (`task_service.py:837`) during Phase 2 `on_skill_completed`. Per `CLAUDE.local.md`, `result_handler` is documented as "sole writer of state=IDLE after a skill completes" — the actual code path routes the IDLE write through `_release_robot_from_skill`. This is a minor doc/code drift; not load-bearing for RC-B but worth flagging since the exact moment the single robot flips IDLE determines the retry window. (For non-task standalone skills there is no `on_skill_completed` advance, so the IDLE flip for those would rely on the next heartbeat — out of scope for RC-B which is task-driven.)
- I did not run the service or reproduce the race; all claims are from static reading of the cited file:line locations. The "few seconds is enough for the single robot to flip IDLE" assumption (Option A delay sizing) should be confirmed against live bench timing during implementation.
- Option A's error classification by message-substring is brittle if the rejection wording changes; a cleaner long-term form would raise a typed `RobotBusyError` from the validator/assign path and catch that. That is a slightly larger change than the minimal substring match; design agent to decide the altitude.
