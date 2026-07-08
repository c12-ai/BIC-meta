# Research: Lab-service — ONE open Task that grows rounds-as-appended-skills

- **Query**: Design 2–3 concrete ways to make ONE lab `Task` stay OPEN across TLC rounds, growing by appended round-skills, agent-owned loop, open-until-cleanup.
- **Scope**: internal (BIC-lab-service step engine). READ-ONLY.
- **Date**: 2026-06-29
- **Locked model (given, not challenged)**: 1 agent trial = 1 lab Task; a round = 1 (or few) skills appended to that Task; Task stays OPEN until agent sends cleanup; agent owns the loop and picks each next ratio; photos already land per-skill on `skill_results.captured_images`; plate-memory reused across rounds within the one Task.

---

## ⚠️ CONFLICT TO SURFACE FIRST (Rule 5)

This task's locked model **directly contradicts the already-written `design.md` + `prd.md` in this same task dir.**

- **design.md / prd.md (RESOLVED there)**: Agent dispatches **THREE separate lab Tasks** —
  `TLC_PREP` / `TLC_RUN_ROUND` / `TLC_CLEANUP` as **three sibling `TaskType` arms**, correlated
  by a shared session id, plus a NET-NEW `tlc_session` table holding `{plate_slot, tank_slot,
  box_slots}` (design.md §2.1, §2.4; prd.md Q-A "RESOLVED: Agent owns the loop via a
  finer-grained per-round Agent↔Lab command surface"). Each `tlc_run_round` is its **own Task**.
- **THIS task's locked model**: ONE lab Task for the whole trial (prep + ALL rounds + cleanup);
  rounds are **appended skills inside that single open Task**; correlation is
  `agent Trial.lab_task_id ↔ one lab Task` (NOT a session id spanning 3 tasks).

These are mutually exclusive at the contract level: "1 trial = 1 Task" vs "1 trial = 3 Tasks". I designed **within the locked model** as instructed, but the integration `design.md` must be reconciled before implementation (it currently encodes the 3-Task model end-to-end, including the agent loop and the `tlc_session` table). **Pick one; do not blend.** My recommendation at the end argues which is the smaller engine change.

---

## Engine facts (grounded, file:line)

### Fact 1 — Steps are FIXED at create from a static template
- `create_task` reads `TASK_STEPS.get(task_type)` and builds `steps` **once**:
  `steps = [TaskStep(step_index=i, skill_type=...) for i, skill_type in enumerate(step_types)]`
  (`task_service.py:85`, `:115`). TLC template = `["start_thin_layer_chromatography",
  "end_thin_layer_chromatography"]` (`task.py` / `schemas/task.py:127-130`).
- There is **no append path** anywhere: the only writers of `task.steps` are `create_task`
  (`:121`), `on_skill_completed` (`:198`, `:271`), `cancel_task` (`:319`), and `_submit_next`
  (`:503`, `:539`) — all mutate-in-place of the EXISTING list, none **grows** it.

### Fact 2 — Auto-complete the instant no PENDING step remains (the terminal guard)
- In `on_skill_completed`, after a step succeeds: `next_pending = next((s for s in steps if
  s.status == SkillStatus.PENDING), None)` (`task_service.py:220`). If `next_pending` is falsy →
  the `else` branch sets `task.status = TaskStatus.COMPLETED` + `finished_at` + publishes
  (`:249-266`). **This is the exact edit point** for "do not auto-complete after a round."

### Fact 3 — The only non-terminal "idle between work" state is WAITING, and it is RE-timer-only
- `TaskStatus.WAITING` is entered ONLY when `next_pending` exists AND `_remaining_delay(...) > 0`
  (`task_service.py:221-246`). `_remaining_delay` returns `0` unless the next step is
  `END_EVAPORATION` (`task_service.py:599-608`). So WAITING means "a pending step exists but a
  timer must elapse first" — it is **not** "the Task is parked waiting for the agent to append
  more work." There is no such state today.

### Fact 4 — `TaskStatus` is a SHARED type (cross-team, Rule 10)
- `app/data/models/task.py:10`: `from bic_shared_types.experiment_task.http import TaskStatus, TaskType`.
- Definition: `bic_shared_types/experiment_task/http/enums.py:14-22` — `PENDING, IN_PROGRESS,
  WAITING, COMPLETED, FAILED, CANCELLED` (6 values, `StrEnum`).
- It is also re-exported through `app/data/schemas/task.py:33` and rides on the MQ payload
  `TaskStatusMsgPayload.status: TaskStatus` (`bic_shared_types/experiment_task/mq/task_status.py:23-37`).
- **Consequence**: ANY new TaskStatus value (e.g. `AWAITING_NEXT_ROUND`) is a **shared-types
  change** → regenerate `schemas/` + `ts/enums.ts`, bump version, both repos re-pin
  (shared-types AGENTS.md gate). The lab cannot add it locally without forking the contract.

### Fact 5 — TaskStep has NO params field
- `TaskStep` (`task.py:21-30`) = `step_index, skill_type, skill_id, status, error_message,
  started_at, finished_at`. **No per-step params.** The per-round ratio cannot live on a
  TaskStep as-is.
- Per-step params are resolved at dispatch from `task.params` (the task-level JSONB):
  `_submit_next` calls `resolve_params(skill_name, task.params, task.task_type, self.db)`
  (`task_service.py:466`). For TLC, `resolve_params` → `_resolve_tlc_step` →
  `TLCService.plan_from_request(req)` where `req` is hydrated from `task.params`
  (`task_resolver.py:344`, `:355`, `:216-246`; `tlc/service.py:186`).

### Fact 6 — `plan_from_request` re-allocates + re-writes placements EVERY call (plate-memory hazard)
- `plan_from_request` hard-codes `round_index=1`, calls `write_declared_placements` (rewrites
  sample-tube cells) and `TLCAllocator.allocate_tracked(...)` for the 50ml box / silica plate /
  tip boxes EVERY time (`tlc/service.py:199-252`). Allocation picks `_first_available`. So if the
  same Task's params drove two dispatches, **each would pick a possibly-different plate/tank/box**
  unless slots are pinned. This is the plate-memory problem.

### Fact 7 — The planner already supports rounds; the developing-tank slot defaults to round_index
- `TLCPlanner.plan_round(spec)` is per-round; `plan_run(rounds)` loops over rounds (one
  `START_TLC` per round + one final `END_TLC`) (`planner.py:297-322`, `:393-423`).
- `round_index` branches: round 1 → `_pickup_materials` (fetch boxes/tips ONCE); round ≥2 →
  `_dispose_previous` (dispose prior plate) (`planner.py:306-310`, `:532-596`).
- `_prepare_solvents` (new ratio into the tank) + `_spot_plate` + `_immerse_and_aim` run EVERY
  round (`planner.py:312-320`).
- **Pinnable slot fields exist on the spec**: `silica_plate_slot` (`planner.py:131`),
  `developing_tank_slot` (`planner.py:145`), `tube_box_2ml_slot`/`tube_box_50ml_slot`/
  `tip_box_*_slot`. `TLCRoundSpec.tank_slot` **defaults to `round_index`**
  (`planner.py:160-163`) — so across rounds the tank slot WALKS unless `developing_tank_slot` is
  pinned explicitly. Plate-memory MUST pin all of these.

### Fact 8 — Photos already land per-skill; URL not yet on the MQ payload
- `result_handler.process_result` stores `captured_images` on the SkillResult per skill
  (`result_handler.py:174-186`) and logs an `image_captured` event. The robot uploads to S3 and
  ships only the URL (`CapturedImage.url`); the lab never uploads.
- The MQ `TaskStatusMsgPayload` carries `task_id / agent_side_task_id / status / steps[] /
  error_message` — **no image_url** (`task_service.py:411-431`; shared `task_status.py:23-37`).
  Surfacing the round photo URL = additive field on `TaskStatusMsgPayload` (shared-types change,
  already agreed in prd.md Q-B / R8).

### Fact 9 — Append + flag_modified pattern already exists; dispatch via _submit_next
- The JSONB list mutation pattern is `task.steps = steps; flag_modified(task, "steps")`
  (`task_service.py:198-199`, repeated `:271`, `:320`, `:503-504`, `:539-540`). An append is just
  `steps.append(TaskStep(...))` before that pattern.
- Dispatch of the next PENDING step is `_submit_next(task)` (`task_service.py:440-573`): finds the
  first PENDING step, resolves params, `_exec_skill`, marks IN_PROGRESS, transitions
  PENDING/WAITING → IN_PROGRESS (`:544-548`).

### Fact 10 — Idempotency / orphan seams that already exist
- `on_skill_completed` is idempotent on terminal: `if task.status in _TERMINAL: return`
  (`task_service.py:164-170`). But there is NO dedupe for "append the same round twice."
- `_submit_next` failure branch marks the step FAILED, cancels remaining, FAILS the task, and
  (TLC-only) calls `TLCService.cleanup_orphan_tip_boxes()` (`task_service.py:490-521`).
- An agent that dies mid-loop leaves the Task non-terminal forever (no watchdog). prd.md Out-of-
  scope: "Orphan/abandoned-session handling — MVP relies on bench reset" — same posture applies.

---

## The 8-point design, three options

Each option keeps: 1 trial = 1 Task, agent owns the loop, Task open until cleanup.

### OPTION A — "Append route + AWAITING_NEXT_ROUND non-terminal state" (explicit park-and-resume)

The faithful implementation of the locked model. The Task parks in a new non-terminal state after each round's skill finishes; the agent appends the next round or appends cleanup.

1. **TaskStatus**: NEW value `AWAITING_NEXT_ROUND` (non-terminal). **SHARED-TYPE change** (Fact 4)
   — add to `bic_shared_types/experiment_task/http/enums.py:14`, regenerate `schemas/` +
   `ts/enums.ts`, bump version, both repos re-pin. Add to lab `_TERMINAL`? **No** — it is
   explicitly non-terminal; but add it to the `_submit_next` "resume" set alongside
   `{PENDING, WAITING}` at `task_service.py:544`.
2. **Routes / methods**:
   - `POST /tasks/{task_id}/rounds` body `{ ratio: TLCParam }` → `TaskService.append_round(task_id,
     ratio)`. Guards: task not terminal; task currently `AWAITING_NEXT_ROUND` or `PENDING`
     (first round). Appends a `START_TLC` step, persists, calls `_submit_next`.
   - `POST /tasks/{task_id}/cleanup` → `TaskService.append_cleanup(task_id)`. Appends an `END_TLC`
     step, persists, `_submit_next`. After this END_TLC finishes, the Task is ALLOWED to complete.
   - Both in `app/api/routers/tasks.py` (thin) + `task_service.py` (logic), mirroring
     `cancel_task` (`tasks.py:116`, `task_service.py:293`).
3. **Append mechanics**: `steps = list(task.steps); steps.append(TaskStep(step_index=len(steps),
   skill_type="start_thin_layer_chromatography")); task.steps = steps; flag_modified(task,
   "steps")` then `await self._submit_next(task)` (Fact 9). Cleanup appends `end_thin_layer_chromatography`.
4. **Per-round ratio**: TaskStep has no params (Fact 5). Two sub-choices:
   - **A1 (recommended sub-choice)**: store rounds on `task.params` as an appended list, e.g.
     `task.params["rounds"] = [...; {ratio, round_index}]` mutated per append + `flag_modified(task,
     "params")`. Then `resolve_params`/`plan_from_request` builds the CURRENT round's spec from the
     LAST entry. Requires `plan_from_request` to read the current round (not hard-code
     `round_index=1`) and to read the pinned slots from `task.params["session_binding"]` (point 7).
   - A2: add a `params: dict | None` field to `TaskStep` (lab-local model change, `task.py:21`),
     carry the ratio there. Cleaner per-step but is a TaskStep schema change + every
     read/serialize site (`TaskStepListType`, `TaskStepRead`, `TaskStatusStepPayload`). Heavier.
5. **Terminal detection**: the auto-complete edit is at `task_service.py:249-266`. Change so a
   finished round-skill does NOT complete the Task. Cleanest: when the just-completed step is a
   `START_TLC` (a round) and no PENDING remains → set `task.status = AWAITING_NEXT_ROUND`
   (park), publish status, RETURN (do not COMPLETE). Only when the completed step is `END_TLC`
   (cleanup) → fall through to the existing COMPLETED branch. Concretely: replace the bare `else`
   at `:249` with `elif current.skill_type == END_TLC: <complete>` and add `else: <park
   AWAITING_NEXT_ROUND>`.
6. **Failure / idempotency**:
   - Duplicate append: guard in `append_round` — reject if task already has a PENDING/IN_PROGRESS
     round step (return 409), so a double-POST cannot stack two STARTs.
   - Agent dies mid-loop: Task sits in `AWAITING_NEXT_ROUND` forever (orphan). MVP: bench reset
     (matches prd.md Out-of-scope). Optional later: a stale-AWAITING watchdog.
   - Round skill fails: existing `on_skill_completed` failure branch (`:267-291`) FAILS the whole
     Task and cancels remaining — correct (a failed develop kills the trial). No change needed.
7. **Plate-memory**: at the FIRST round's prep (round_index 1, `_pickup_materials`), write the
   chosen slots to `task.params["session_binding"] = {plate_slot, tank_slot, box_2ml_slot,
   box_50ml_slot, tip_*_slot}` (+ `flag_modified`). On each appended round, `plan_from_request`
   READS `session_binding` and passes the pinned indices into `TLCRoundSpec`
   (`silica_plate_slot`, `developing_tank_slot`, the box/tip slots — `planner.py:131,145,155-158`)
   instead of re-allocating. **Critical**: pin `developing_tank_slot` explicitly — else
   `tank_slot` walks with `round_index` (Fact 7, `planner.py:160-163`). This replaces the
   `_first_available`/`allocate_tracked` calls in `plan_from_request` (`tlc/service.py:206-214`)
   with read-back for rounds ≥2 (round 1 still allocates, then persists the binding).
8. **Effort / risk / blast radius**:
   - Effort: MEDIUM-HIGH. Shared-types (new enum) + 2 routes + 2 service methods + terminal-guard
     edit + plate-memory pin + `plan_from_request` round-aware rewrite.
   - Risk: MEDIUM. The terminal-guard edit is surgical; the shared enum touches both repos + the
     MQ payload + agent event mapping. `plan_from_request` round-awareness is the same real work
     called out in design.md §2.4.
   - Blast radius: shared-types (cross-team gate), lab `task_service`/`tasks.py`/`tlc/service.py`,
     agent (must drive the new routes + handle the new status), MQ status consumers.

### OPTION B — "Append route, NO new TaskStatus; park as WAITING-with-no-pending (reuse IN_PROGRESS hold)"

Same append routes as A, but avoid the shared-enum change by keeping the parked Task in an
EXISTING status. The Task simply has no PENDING step between rounds; the engine is taught not to
complete a TLC Task that has not yet seen its cleanup.

1. **TaskStatus**: **NO new value.** Between rounds the Task stays `IN_PROGRESS` (or transitions to
   `WAITING`) with zero PENDING steps. Avoids the cross-team Rule 10 change. The "is this Task
   awaiting a round?" signal is **derived**: `task_type == TLC AND status not terminal AND no
   END_TLC step has completed`. (No durable enum state — the predicate is the truth.)
2. **Routes / methods**: identical to A — `POST /tasks/{id}/rounds`, `POST /tasks/{id}/cleanup`.
3. **Append mechanics**: identical to A (append a step + flag_modified + `_submit_next`). Note
   `_submit_next` transitions to IN_PROGRESS only from `{PENDING, WAITING}` (`:544`); if the Task
   is parked as IN_PROGRESS with no pending, the new appended PENDING step is picked up and the
   status stays IN_PROGRESS — fine.
4. **Per-round ratio**: identical to A1 (`task.params["rounds"]`) — same constraint (Fact 5).
5. **Terminal detection**: the edit at `task_service.py:249-266` becomes a **TLC-aware guard**:
   in the no-`next_pending` branch, if `task.task_type == THIN_LAYER_CHROMATOGRAPHY` AND the
   just-completed step is NOT `END_TLC` → DO NOT complete; leave status IN_PROGRESS (parked),
   publish, return. Only complete when the completed step is `END_TLC` (or task_type is CC/RE,
   unchanged). This is the minimal behavioral change and needs no enum.
6. **Failure / idempotency**: same as A. Extra subtlety: because the parked status is the generic
   IN_PROGRESS, a `GET /tasks` consumer cannot visually distinguish "robot actively running a
   round" from "parked between rounds" — only the steps list reveals it. Acceptable for MVP;
   surfaced as a UX cost.
7. **Plate-memory**: identical to A (`task.params["session_binding"]`, pin tank slot).
8. **Effort / risk / blast radius**:
   - Effort: MEDIUM. Drops the shared-enum work; the rest equals A.
   - Risk: MEDIUM-LOW for the engine, but the "parked == IN_PROGRESS" ambiguity is a real
     observability smell and the terminal guard becomes task-type-special-cased (a slight SOLID
     ding vs A's explicit state).
   - Blast radius: lab-only for the status (no cross-team enum); still touches agent (drive routes)
     + the additive `image_url` on the MQ payload (shared, but already agreed).

### OPTION C — "Single open Task, ONE growing START_TLC program rebuilt per append (no per-round skill rows)"

Keep the Task's `steps` essentially `[START_TLC (open), END_TLC]` but make each round APPEND ops
to the SAME running START program by re-dispatching an extended `tlc_ops` program — i.e. the round
is a NEW skill that REPLACES the in-flight START with a longer program. Rejected-leaning, documented
for completeness.

1. **TaskStatus**: needs a park state too (same as A or B) — buys nothing over them on this axis.
2. **Routes**: `POST /tasks/{id}/rounds` would re-resolve the WHOLE program with N rounds via
   `plan_run(rounds)` (`planner.py:393`) — the planner already supports it (Fact 7). But the step
   engine dispatches ONE skill per step; a growing single START skill does not fit "one round = one
   skill appended." It fights the engine (`_submit_next` is one-pending-at-a-time).
3. **Append mechanics**: would require re-issuing/replacing an in-flight skill — there is no
   "extend a SENT skill" path; skills are immutable once published. Dead end without a new skill
   each round, at which point it collapses into A/B.
4–7. Same constraints as A/B but with worse fit.
8. **Effort / risk**: HIGH risk, no payoff. The planner's `plan_run` multi-round skeleton is built
   for "one command program with N STARTs" — but the engine cannot hold N STARTs in flight, and
   `TASK_STEPS` is built once (Fact 1). **Rejected.**

---

## Does the planner's round_index branching HELP or HURT?

**HELPS — strongly, and is the reason the append model is cheap on the planner side.**
- `plan_round` already does the right per-round thing: round 1 fetches materials, round ≥2 disposes
  the previous plate, every round re-preps the tank + re-spots + re-immerses
  (`planner.py:306-320`). An appended round-skill can call `plan_round(spec)` per round with the
  correct `round_index`, reusing this branching verbatim.
- `plan_run(rounds)` (the all-at-once skeleton) does NOT fit the append model (it wants the full
  round list up front, which the agent-owned loop does not have — rounds are decided one photo at a
  time). So: **reuse `plan_round` per appended round; do NOT use `plan_run`.**
- The one HURT: `tank_slot` defaults to `round_index` (`planner.py:160-163`), so without pinning
  `developing_tank_slot` the tank walks per round — plate-memory MUST override it (point 7). The
  `is_first` gate on material pickup also means round 1's skill must be the prep-bearing one
  (round_index=1), so the append sequence must track round_index in `task.params`.

---

## RECOMMENDATION

**Option A (append route + explicit `AWAITING_NEXT_ROUND` non-terminal status), with ratio on
`task.params["rounds"]` (sub-choice A1) and plate-memory on `task.params["session_binding"]`.**

Why A over B:
- **Honesty of state (Rule 9 / observability)**: B parks the Task in a generic `IN_PROGRESS` with
  no pending step — indistinguishable from "robot actively developing." A's explicit state makes
  "the lab is waiting for the agent's next ratio" a first-class, queryable fact, which the agent's
  loop and any monitor read directly. B forces a derived predicate at every read site.
- **Cleaner terminal guard**: A's guard keys off "completed step is END_TLC vs a round" (a clear
  intent), while B special-cases task_type inside the generic completion branch (a SOLID smell).

The honest minimal-change truth (as asked):
- **No option avoids an append route + a service method pair.** The engine has zero append path
  (Fact 1) and zero "park between work" non-terminal state for TLC (Fact 3). Growing one Task across
  rounds is structurally new behavior; it cannot be a config flip.
- **The single avoidable piece is the new TaskStatus** (that is the only thing B saves). If the
  cross-team shared-enum churn is judged too costly for MVP, B is the smaller-blast fallback — but
  it trades a clean state for a derived predicate + an observability gap.
- **Plate-memory is unavoidable in BOTH** and is ~80% of the lab work/risk (design.md §2.4): the
  `task.params["session_binding"]` pin + `plan_from_request` round-awareness + the explicit
  `developing_tank_slot` pin (Fact 7). This is identical whether rounds are appended-skills (A/B) or
  separate tasks (design.md). So choosing A/B over the 3-Task design does NOT add plate-memory cost;
  it MOVES the session record from a NEW `tlc_session` table INTO `task.params` of the one Task —
  which is **strictly less schema** (no new table, no migration) and naturally scoped/cleaned by the
  one Task's lifecycle. That is the concrete argument that the locked "1 trial = 1 Task" model is the
  smaller engine change than the design.md "3 Tasks + tlc_session table" model.

**True minimal change set for Option A:**
1. shared-types: add `AWAITING_NEXT_ROUND` to `TaskStatus` (+ regenerate, version bump, re-pin)
   AND add optional `image_url` to `TaskStatusMsgPayload` (already in scope, prd.md R8).
2. lab `tasks.py`: 2 thin routes (`/rounds`, `/cleanup`) mirroring `cancel_task`.
3. lab `task_service.py`: `append_round` / `append_cleanup` (append step + flag_modified +
   `_submit_next`); edit the terminal guard at `:249-266` (round → park; END_TLC → complete);
   add `AWAITING_NEXT_ROUND` to the `_submit_next` resume set at `:544`.
4. lab `tlc/service.py`: make `plan_from_request` round-aware — read the current round's ratio +
   the pinned `session_binding` slots from `task.params`; write the binding at round 1.
5. agent: drive the new routes; consume `AWAITING_NEXT_ROUND` + `image_url`.

**Reconcile with `design.md` BEFORE coding** — it currently encodes the contradictory 3-Task /
`tlc_session`-table model end-to-end (Rule 5 + Rule 10). One model must win and the spec rewritten.
