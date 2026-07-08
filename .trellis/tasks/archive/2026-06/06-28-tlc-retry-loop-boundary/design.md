# Design — TLC Rf-retry loop (round-based, agent-owned)

Parent integration design. Each child task gets its own focused `design.md`; this
document owns the cross-service contracts, the end-to-end data flow, the child
sequencing, and the integration acceptance.

## 1. Architecture & boundaries

The agent owns the loop; the lab executes one round per command; recognition and
the deterministic Rf decision stay in the agent (L3) calling L4 stubs. The lab
gains a finer-grained command surface so prep and cleanup are separated from the
repeatable develop-a-round step.

**Domain model (the keystone — CORRECTED grill Q9):**
`1 TLC job = N attempts (= N agent Trials) = 1 Lab Task (1 task_id) = N skills.`
The lab Task is the AGGREGATOR for the whole run; prep / round×N / cleanup are SKILLS
appended under that ONE Task (existing `Task → 1..N Skill → SkillResult` ER reused — each
round's photo lands on its round-skill's `SkillResult.captured_images`). On the AGENT side
the run is still N `Trial` rows (one per attempt/round — the existing `ctx.trials[job_id]`
attempt-ordered history + `_evaluate_route(attempt)` + `_build_retry_mixcase_request`
machinery is REUSED UNCHANGED). All N agent trials SHARE the one `lab_task_id = T`
(many-to-one — NOT 1:1; the earlier "1 trial = 1 task" framing was wrong). Because rounds are
sequential and only one trial is live at a time, the agent's MQ→trial resolution
(`resolve_trial_id`) maps `lab_task_id = T` → the MAX(attempt) trial (the live round); older
trials are historical-only (`ctx.trials[job_id][-1]`). See child-3 design for that seam.

The Task stays OPEN across rounds via a new shared TaskStatus **`AWAITING_CONFIRMATION`**:
the round-skill finishes cleanly, but the TASK has no closure yet — it parks awaiting the
agent's verdict. (Named for the task-level "no closure, awaiting confirm" condition, NOT a
"round" — the lab doesn't presume another round is coming.)

```
Agent (L3 TLC subgraph)                 Lab-service (ONE Task, task_id=T)      Robot
──────────────────────                  ─────────────────────────────────     ─────
create TLC Task(tubes, target_window) ─► create Task T; allocate plate/tank ─► prep skill
   (= 1 trial = 1 Task)                    ONCE → store binding on task.params
                                           prep skill done → park: AWAITING_CONFIRMATION
                                           publish task.status ◄──────────────── result
  ── per round, ratio_n ──┐
append round skill(ratio_n)┼──────────►  append skill to task.steps → IN_PROGRESS ► round skill
                          │              reuse stored plate/tank → tank-prep+spot+develop+photo
                          │              robot uploads photo→S3
                          │              round skill done → park: AWAITING_CONFIRMATION
                          │              publish task.status + image_url ◄──────── result(url)
recognize_tlc_plate(url)  │  (L4 stub: round 1→0.25 OUT, round 2→0.51 IN)
_evaluate_route(rf,window)│
  ├─ out & attempt<cap ──►│ recommend_tlc_mixcase(trials) (L4 stub: adapt ratio)
  │                       └─► append round skill(ratio_{n+1})   ← loop (same Task T)
  └─ in-window ───────────►  cleanup skill ──────────────────► dispose plate (ONCE)
                              last skill done → Task T COMPLETED   result_review(SUCCESS) → accept
```

**Loop ownership:** Agent. Rejected: activating the lab's latent `plan_run`
multi-round program (would require moving Rf recognition + target-window into the
lab and inventing a stateful pause/resume MQ handover — see PRD Q-A).

**Mock boundary (load-bearing, R7):** L3 is production-real and calls `mind.*`
exactly as against live ChemEngine. ALL fakery lives in `mind_client` L4 stubs.
`recognize_tlc_plate` and `recommend_tlc_mixcase` stubs are INDEPENDENT
(recognition keys off round index; mixcase adapts from observed-Rf history).

## 2. Contracts (the cross-layer surfaces — Rule 10)

Owned by child **06-29-tlc-round-contracts** (shared-types), consumed by the other two.

### 2.1 Agent↔Lab command surface — ONE aggregator Task, skills appended per round

**RESOLVED (Drake, after the trial↔task correction + open-task research):** the wire
shape is **ONE lab Task per trial** that the agent grows by appending skills, NOT three
sibling tasks. This supersedes the earlier 3-sibling-`TaskType` resolution AND the
`tlc_session` table — both are DROPPED.

**Why the reversal:** the locked domain invariant is **1 TLC job = 1 Lab Task** (one
`task_id` for the whole run; the N agent Trials of the job all SHARE that `lab_task_id` —
many-to-one, CORRECTED grill Q9). Three sibling tasks would mint 3 lab tasks for one job,
breaking it. The aggregator-Task model honors it, reuses the existing `Task → Skill →
SkillResult` ER unchanged, and makes plate-memory just `task.params` on the one Task (no
cross-task binding, no aggregation problem — the Task IS the aggregation).

**The command surface:**
- **Create TLC Task** — carries the FIXED `sample_tubes` (2–4 `ObjectLocation`) +
  `target_window`. Creates the Task, allocates plate/tank/boxes ONCE, stores the binding
  on `task.params` (§2.4), runs the prep skill, then parks `AWAITING_CONFIRMATION`.
- **Append round skill(ratio)** — a NEW lab route/service method that appends a round
  skill (tank-prep + spot + develop + photo) to the SAME Task's `task.steps`, with the
  round's `TLCParam` (solvent ratio) carried on `task.params["rounds"]` (the round-skill's
  params are resolved from there — `TaskStep` has no params field). Reuses the same plate/
  tank from the stored binding. Task → IN_PROGRESS, then back to `AWAITING_CONFIRMATION`.
- **Cleanup / finish** — appends the final dispose skill; its completion is the ONLY path
  to `COMPLETED` (success-gated — fixes the PRD divergence where `END_TLC` was unconditional).

**New shared TaskStatus `AWAITING_CONFIRMATION`** (the "task lacks closure, awaiting agent
verdict" state — task-level, not round-level):
- ENTER: a non-final skill completes AND no cleanup yet → Task parks.
- EXIT A: agent appends a round skill → IN_PROGRESS.
- EXIT B: agent sends cleanup → final skill runs → COMPLETED.
- ORPHAN (agent never returns): stays parked; MVP relies on bench reset (deferred).
`TaskStatus` is a SHARED type (`bic_shared_types/.../http/enums.py`), so adding this value
is a cross-team change (Rule 10: regen + version bump + re-pin both repos).

**Engine work this requires (from `research/lab-open-task-round-append.md`, all unavoidable
for an open Task):** an **append-skill route + service method** (the engine has zero append
path today); mutate `task.steps` via the existing `steps.append` + `flag_modified` pattern
(`task_service.py:198-199`) then `_submit_next`; and the **terminal-detection edit** at
`task_service.py:249-266` — "last completed skill was the cleanup/END skill → COMPLETED;
else → park `AWAITING_CONFIRMATION`" (instead of today's unconditional auto-complete when no
PENDING step remains). Reuse `plan_round`'s `round_index` branching per appended round
(`planner.py:306-310` — HELPS); do NOT use `plan_run` (it wants all rounds up front).

**Loop-ownership (unchanged):** Agent owns the cross-round loop (judge photo, decide next
ratio, count attempts via `_evaluate_route`); Lab owns within-round robot steps + the plate
binding on `task.params`.

**Contract gaps to fill (from `research/sharedtypes-tlc-ops.md`):** `TAKE_PHOTO` is a generic
skill (wire observe/photo into the round skill program); `TLCRfGoal` (target window) is
defined but NOT on the create request — add it; `TaskStatusMsgPayload` has no image field —
add `image_url` (§2.2). No session/correlation type needed — the one `task_id` IS the link.

### 2.2 Lab→Agent MQ — `TaskStatusMsgPayload` gains the photo URL (R8, Q-B)

Add the round's captured-image S3 URL to `TaskStatusMsgPayload` (already published on
`agent.exchange`/`{task_id}.task.status`). The agent reads it off the status message when
the round skill completes (Task → `AWAITING_CONFIRMATION`) and calls `recognize_tlc_plate(url)`.
No new message type; no REST GET.

**RESOLVED:** chose extending `TaskStatusMsgPayload` over the alternative the research
surfaced (reuse the existing `SkillResult.images` field). Reason: the agent already
consumes the MQ status message per round terminal; putting the URL there is one channel
and no extra per-round `SkillResult` fetch/correlation. Additive optional field
(`image_url`); CC/RE statuses omit it.

### 2.3 Agent↔Mind — `TLCMixcaseRequest`/`Response` (no shape change)

Already round-aware (`trials` observed-Rf history). Only the L4 stub impl changes
(history-aware). `recognize_tlc_plate` stays scripted-by-round in L4.

### 2.4 Lab plate-memory — on the ONE Task's `task.params` (no new table)

Today the lab picks `_first_available` plate/tank/box per call (`allocate.py:99`) and
`plan_from_request` re-allocates every call (`service.py:206`) — so without a binding, a
later round would grab a DIFFERENT plate. With the aggregator-Task model the fix is trivial
and needs NO new table and NO cross-task lookup: the binding lives on the ONE Task's
existing `task.params` JSONB (the Task IS the session).

```
task.params (the one TLC Task)
  session_binding: { plate_slot: 1, tank_slot: 1, box_slots: [2, 3] }
  rounds:          [ {ratio: "2:1"}, {ratio: "3:1"} ]   # per-round params (TaskStep has none)
  # sample_tubes + target_window also arrive on the create request
```

Flow (all within ONE Task):
- **Create / prep skill** → allocate free slots ONCE (capture indices via the existing
  `_slot_index()` helper) → WRITE `session_binding` to `task.params` → robot fetches materials.
- **Append round skill(ratio)** → READ `task.params.session_binding` → feed those EXACT slot
  indices into `plan_round` (planner already accepts explicit `silica_plate_slot` /
  `developing_tank_slot`, `planner.py:131,145` — no planner change) → develop+photo.
- **Cleanup skill** → READ the binding → dispose that plate.

Code seam: in the round/cleanup op-build path, replace the `_first_available` plate/tank/box
calls with reads of `task.params.session_binding`. Small + localized.

**Gotcha (research):** the developing TANK is not allocated today — `tank_slot` defaults to
`round_index` (`planner.py:160-163`). PREP MUST pin `tank_slot` into `session_binding`
explicitly, or round 2 would drift to tank 2 (only 2 tanks seeded).

### 2.5 Concurrency & occupancy — `AWAITING_CONFIRMATION` is robot-free, NOT reserved
(RESOLVED — grill Q4/Q5 + `research/awaiting-confirmation-concurrency.md`)

One robot, serialized by nature — so NO reservation system, NO scheduler, NO
"single-TLC-in-flight" gate, NO agent-side abandon timeout. All withdrawn as
over-engineering for a one-robot bench. Specifically:

- **`AWAITING_CONFIRMATION` is NON-terminal but ROBOT-FREE.** A parked task holds no
  pending skill, so `result_handler.py:196` has already cleared `robot.current_skill_id`;
  the validator gates on `robot.state == IDLE` (`command_validator.py:172`, `robot.py:46-50`),
  NOT on task status. So the robot is free to run other work (CC/RE) while a TLC parks.
  Agent ingress must route the status as "round done → recognize" (add to
  `NON_TERMINAL_STATUSES`, `event_ingress.py:40`) — this is about the loop PROGRESSING,
  NOT about marking the bench busy.
- **Collision is prevented by VALIDATION + material state, the same way CC does it** — NOT
  by reservation. CC validators reject occupied resources (`sample.state != UNUSED`
  `command_validator.py:229`; `cc.state != IDLE` `:335`). The next TLC prep must likewise
  FAIL validation if its target plate/tank/box slot is still occupied. An abandoned parked
  plate occupying a slot → the next TLC naturally fails "slot occupied" — correct, honest
  behavior that mirrors the physical bench.
- **GAP child-2 MUST close:** today TLC allocation (`_first_available`, `allocate.py:144-153`)
  only filters `state != "disposed"` and the placement writer NEVER sets `state`
  (`placement.py:13,155`) — so a parked plate stays `unused` and silently re-allocatable.
  To make the validation-based model REAL, TLC prep must (a) MARK its plate/tank/box state as
  occupied (mirror CC's `using`/`used`), and (b) a TLC prep validator must CHECK slot
  occupancy. Without (a)+(b), validation will not catch the collision the model relies on.

**Orphan handling: by design, the chemist's responsibility (NOT auto-recovered).** An
abandoned parked plate is a PHYSICAL lab condition — a human must clear the physical plate,
so requiring a manual `POST /admin/reset-to-test-data` to clear the DB state MIRRORS reality.
No agent-side timeout / auto-cleanup escape valve (rejected — it would paper over a physical
condition that genuinely needs human intervention). The collision surfaces loudly as a
validation failure on the next TLC until the chemist resets. This is part of child
**06-29-tlc-lab-round-split**.

## 3. End-to-end data flow (success-after-one-retry, ONE Task `T`)

1. Chemist confirms TLC params (tubes + window + first ratio).
2. Agent **creates TLC Task `T`** (tubes, window) → lab allocates plate/tank/boxes ONCE,
   writes `session_binding` to `T.params`, runs prep skill → `T` parks `AWAITING_CONFIRMATION`.
3. Agent **appends round skill(ratio_1)** to `T` → lab reuses bound plate → develops +
   photographs → `task.status{image_url=u1}` → `T` parks `AWAITING_CONFIRMATION`.
4. Agent `recognize_tlc_plate(u1)` → L4 stub round 1 → `product_rf=0.25` → OUT.
5. `_evaluate_route(OUT, attempt=1<cap)` → `recommend_tlc_mixcase(trials=[r1])` →
   L4 stub adapts ratio (0.25 below window → more polar) → `ratio_2`.
6. Agent **appends round skill(ratio_2)** to `T` → `task.status{image_url=u2}`.
7. `recognize_tlc_plate(u2)` → L4 stub round 2 → `product_rf=0.51` → IN-window.
8. `_evaluate_route(IN)` → emit `result_review(SUCCESS)` AND **append cleanup skill** to `T`
   → cleanup skill completes → `T` → COMPLETED.
9. Chemist accepts → "Confirmed result review." No `turn_failed`.

Note: steps 2/3/6/8 are all the SAME lab Task `T` (one `task_id`, agent `Trial.lab_task_id=T`).

## 4. Child decomposition & sequencing

Ordering is a hard dependency chain (write it in each child's artifacts, not implied
by tree position):

1. **06-29-tlc-round-contracts** (shared-types) — FIRST. Adds: `AWAITING_CONFIRMATION` to
   the shared `TaskStatus` enum; `target_window` (`TLCRfGoal`) on the TLC create request;
   `image_url` on `TaskStatusMsgPayload`; the append-round request shape. Regenerate contract
   artifacts. Both downstream children depend on these.
2. **06-29-tlc-lab-round-split** (lab-service) — SECOND. The aggregator-Task engine work:
   the append-skill route + service method; the terminal-detection edit (park
   `AWAITING_CONFIRMATION` vs. complete-on-cleanup, `task_service.py:249`); plate-memory on
   `task.params` (pin `tank_slot`); reuse `plan_round` per appended round; wire the dead
   `observe`/`take_photo` ops into the round skill; surface `image_url` on the status payload.
   Verifiable with lab pytest + a manual create→append→append→cleanup dispatch.
3. **06-29-tlc-agent-round-loop** (agent-service) — THIRD. Rebuild the L3 loop: create Task →
   append round per attempt → read photo URL off MQ → recognize/decide → append cleanup on
   success; L4 history-aware mixcase stub + scripted-by-round recognition stub; rewrite
   `tlc-retry-flow.spec.ts` + migrate `tlc-e2e-final-chain.spec.ts` to the new shape (AC1–AC3).
   Verifiable with agent pytest + the E2E.

## 5. Compatibility / migration

- **Back-compat scope (RESOLVED — grill Q1/Q2).** The shared-types compatibility policy
  (`docs/compatibility-policy.md`, AGENTS.md:36 — expand-contract, deprecate one minor cycle
  before deleting) protects EXTERNAL teams. The TLC task-request types are **intra-APEX**
  (agent↔lab, both this team), so the service-repo "no back-compat scaffolding" convention
  OVERRIDES the contract repo's deprecate-first rule for these types — hard-swap, no shim.
  - **Verified the override is safe (no external blast radius):** the round split needs ZERO
    robot-facing changes. `START_TLC`/`END_TLC` are LAB-LEVEL skills (`skills/tlc.py:4-8`);
    photo / observe / fail-retry are explicitly "independent requests issued by lab-run AFTER
    START_TLC". The lab `plan_*` surface already returns the existing
    `StartTLCLabParams`/`TakePhotoLabParams`/`EndTLCLabParams` — `tlc_prep`/`run_round`/
    `cleanup` are TASK-level (agent↔lab) concepts the lab decomposes into EXISTING robot
    skills. The robot protocol (a separate team's surface) is untouched, so the contract
    policy is not engaged for any robot-facing type.
- The old single-shot `CreateTLCTaskRequest` behavior (one `THIN_LAYER_CHROMATOGRAPHY` task =
  fixed `START_TLC`→`END_TLC`, auto-completing) is REPLACED by the aggregator-Task + append
  model — no back-compat scaffolding (repo convention, both CLAUDE.md). The single-shot
  behavior is referenced in ~16 source + ~10 test files across all 3 repos. **Removal/rework
  is STAGED LAST** (not up front): build the new append path → migrate the TLC tests → THEN
  delete the old single-shot code paths + dead tests as the final step. One short red window;
  clean end state. CC/RE are untouched (separate request arms / TaskTypes).
- **`tlc-e2e-final-chain.spec.ts` is MIGRATED** (not retired) to the aggregator-Task flow — it
  keeps the tube-selection → lab-execution chain-of-custody DB assertions, which the new
  `tlc-retry-flow.spec.ts` does not duplicate. Both specs survive under the new shape.
- The `TaskStatusMsgPayload` field is additive (optional `image_url`) — CC/RE statuses
  simply omit it; the agent only reads it on the TLC round path.
- The clobber bug is dissolved (tubes sent once at prep, never re-validated per round).
  CC's `sample_cartridge_location` clobber risk is NOT addressed here (out of scope;
  follow-up).

## 6. Trade-offs & risks

- **More MQ round-trips** (one create + N appended rounds + cleanup, vs. today's single
  dispatch). Acceptable — the lab spec assumes single-in-flight TLC dispatch; robot occupancy
  is unaffected. All round-trips are against the SAME Task (`task_id`).
- **New `AWAITING_CONFIRMATION` shared TaskStatus + append-skill engine path** is the real
  cost — it touches the engine's most load-bearing branch (terminal detection,
  `task_service.py:249`) and a cross-team enum. Mitigated by landing it in the lab child with
  focused tests for the park/append/complete transitions.
- **Orphan: a parked Task with no agent return** stays open until bench reset (MVP-deferred).
- **External dependency parked:** live ChemEngine routes stay L4 stubs. The loop is real;
  only the two L4 methods are fake. Going live later edits only `mind_client.py`.
- **Cross-repo contract drift risk:** mitigated by landing shared-types first and
  updating every spec doc in the same change set (AC4 / Rule 10).

## 7. Integration acceptance (parent-owned)

The parent is DONE when all five PRD acceptance criteria hold together:
AC1 (round-based E2E green), AC2 (prep-once/cleanup-once proven), AC3 (ratio adapts),
AC4 (specs updated for every changed surface), AC5 (both BE suites green). No child is
"done" in isolation until the E2E in child 3 passes end-to-end against the real bench.
