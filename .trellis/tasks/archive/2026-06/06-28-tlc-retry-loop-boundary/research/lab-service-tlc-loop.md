# Research: Lab-Service (Nexus) TLC retry-loop model

- **Query**: Confirm/refute the domain expert's per-round TLC loop model against BIC-lab-service code; answer who can own the loop (Q5).
- **Scope**: internal (BIC-lab-service)
- **Date**: 2026-06-28

---

## TL;DR verdict

**The expert's real-world model is REFUTED *as a description of what the lab code does today*** — but it is a faithful description of what the *physical* process is. The gap is the whole point of this task:

- The lab today dispatches a **single TLC task = exactly 2 skills: `START_TLC` → `END_TLC`** (one START = one whole round, including prep), with **NO round loop, NO Rf recognition, NO per-round photo handover, and END unconditional**. (`task.py:127-130`, `planner.py:393-423`, `task_service.py:220-266`)
- The planner *can* model multiple rounds (`plan_run` loops over `rounds`, `round_index` 1-vs-≥2 branches, fresh `tank_slot` per round), but **nothing ever feeds it more than one round** — `plan_from_request` hard-codes `round_index=1` with a single round. (`service.py:231`, `service.py:252`)
- Several expert steps (per-round tank prep, dispose-on-success) ARE present in code; several (the loop, photo→recognize→re-dispatch, observe/take_photo ops) are **NOT wired** — `observe_view`/`observe_uv`/`take_photo` are defined but never called anywhere in `app/`.

**Q5 answer**: The lab **cannot own the loop today**. It runs at most one round per `START_TLC` and has no recognition/decision seam between rounds. **The agent must own the loop** (re-dispatch per round) unless the lab is extended — OR the planner's latent multi-round capability is activated and a recognition callback is built. See "Q5 — Loop owner" below.

---

## Findings

### Q1 — The exact op program a TLC task produces

There are **two layers** of "program":

#### (a) Task-step level (what actually gets dispatched to the robot)

`TASK_STEPS[THIN_LAYER_CHROMATOGRAPHY]` is a **fixed 2-element list** (`app/data/schemas/task.py:127-130`):

```python
TaskType.THIN_LAYER_CHROMATOGRAPHY: [
    "start_thin_layer_chromatography",
    "end_thin_layer_chromatography",
],
```

So a dispatched TLC task is exactly two skills: one `START_TLC`, then one `END_TLC`. Each step's `lab_params` (a `tlc_ops` `Step` program) is resolved on demand by `_resolve_tlc_step` → `TLCService.plan_from_request` (`task_resolver.py:216-246`, `service.py:186`).

#### (b) Op level (inside one `START_TLC` program — `TLCPlanner.plan_round`, `planner.py:297-322`)

`plan_round` emits, in order, for ONE round:

| Real-world step (expert) | Planner code | Once vs per-round |
|---|---|---|
| (3-way reset) | `ResetTalosOp`/`ResetCapOp`/`CommonResetOp` (`planner.py:302-304`) | every START (so per-round) |
| **PREP** (initial setup: fetch boxes/tips from shelf) | `_pickup_materials` (`planner.py:532-577`) | **round 1 ONLY** — gated `if is_first` (`planner.py:306-308`) |
| (dispose previous plate) | `_dispose_previous` (`planner.py:579-596`) | **round ≥2 ONLY** — the `else` branch (`planner.py:309-310`) |
| **aspirate + prepare developing tank** (new solvent ratio) | `_prepare_solvents` → `TlcCentrifugeTubeAspirateOp` + `TlcDevelopingTankDispenseOp` (`planner.py:598-634`, ops at `:616-625`) | **EVERY round** (`planner.py:312-313`) |
| **spot** (sip + drop dot on silica plate) | `_spot_plate` → `TlcCentrifugeTubeAspirateOp` (2ml) + `TlcSilicaPlateDispenseOp` (`planner.py:636-685`, ops at `:655-670`) | EVERY round (`planner.py:315-317`) |
| **immerse plate into tank + aim camera** (develop) | `_immerse_and_aim` → tank lid off, plate→tank, lid on, `AimCameraOp` (`planner.py:687-744`) | EVERY round (`planner.py:319-320`) |
| **develop/observe (RGB+UV)** | `observe_view` / `observe_uv` (`planner.py:326-367`) | **DEFINED, NEVER CALLED** — see below |
| **take photo** | `take_photo` (static, `planner.py:369-372`) | **DEFINED, NEVER CALLED** — see below |
| **CLEANUP / dispose plate** | `end_tlc` → pick plate from view stand, place to disposal bin, tip eject, 3-way reset (`planner.py:374-389`) | ONCE at end (its own `END_TLC` skill) |

**Critical dead-code finding**: `observe_view`, `observe_uv`, and `take_photo` are defined on `TLCPlanner` but are **never invoked anywhere under `app/`** (grep for call-sites returns nothing — only the `def`s and docstrings). `plan_run` itself documents this: *"Observation/photo requests are interleaved by lab-run between rounds and are NOT part of this skeletal program"* (`planner.py:396-399`). So the lab program as-dispatched contains **no observe and no take_photo op** — the photo step the expert describes has no producer in the lab today.

**`plan_run` (the multi-round skeleton, `planner.py:393-423`)** loops over `rounds`, emitting one `START_TLC` per round plus a single final `END_TLC` (`planner.py:405-422`). It DOES structurally model N rounds in ONE command program. BUT:

- `round_index` 1-vs-≥2 only changes prep-vs-dispose (`planner.py:306-310`); both still re-prep the tank and re-spot.
- "one plate per round": `SpottingSpec` is `min_length=1, max_length=1` (`planner.py:144`) — each round has exactly one plate.
- `tank_slot` defaults to `round_index` — "a fresh tank each round" (`planner.py:160-163`).

So **the planner CAN model multiple rounds in a single program** — but it is **never fed more than one round**. `TLCService.plan_from_request` builds **exactly one `TLCRoundSpec(round_index=1)`** and calls `self.plan([spec], ...)` (`service.py:231-252`). The 2-step `TASK_STEPS` list mirrors this: it only has room for one START + one END. So in practice **each dispatched TLC task = ONE round** (the multi-round path in `plan_run` is latent/unreached).

### Q2 — Is developing-tank prep per-round or one-time?

**PER-ROUND. Confirmed, matches the expert.** `plan_round` calls `_prepare_solvents` unconditionally on every round (`planner.py:312-313`), AFTER the `is_first` prep/dispose branch. `_prepare_solvents` (`planner.py:598-634`) opens each 50ml solvent tube, aspirates, and `TlcDevelopingTankDispenseOp` into the tank — fresh fill every round. Tank slot is also per-round (`tank_slot` = `round_index`, `planner.py:160-163`). What is round-1-only is the *material pickup from the supply shelf* (`_pickup_materials`, `planner.py:532-577`), i.e. fetching the boxes/tips — NOT the tank prep. This is exactly the expert's revised model (initial fetch once; tank prep each round).

### Q3 — Is CLEANUP / END_TLC gated on success?

**It is NOT gated on success per se — it is the next pending step, submitted unconditionally when START_TLC *succeeds*.** Two facts:

1. `plan_run` always appends one `END_TLC` after the rounds (`planner.py:415-422`) — unconditional in the program.
2. In `TaskService.on_skill_completed`: when a step succeeds, it finds `next_pending` and calls `_submit_next` (`task_service.py:220-248`). When the LAST step (END_TLC) succeeds, task → `COMPLETED` (`task_service.py:249-266`). When a step **FAILS**, `_cancel_remaining_steps` cancels the rest and the task → `FAILED` (`task_service.py:267-271`) — so END_TLC is **NOT** run after a failed START.

Net: END_TLC runs **iff START_TLC succeeded** (generic step-advance), but it is **NOT conditioned on any Rf/in-window recognition** — it always runs the cleanup after a successful single round. There is **no "only on success [of separation goal]"** semantics; "success" here means "the START skill returned code 200", not "product Rf is in window". This is a divergence from the expert model, where cleanup is gated on the *chemistry* succeeding.

### Q4 — How the lab notifies the agent after a photo (robot → S3 → lab → MQ → agent)

- **S3 upload is the ROBOT's job, not the lab's.** `CapturedImage.url` is *"图片存储路径 (如 minio URL)"* — the robot uploads the photo and ships the URL in its result (`bic_shared_types/robot_protocol/shared_models.py:21-34`). The lab's `s3_client` is only `connect`/`disconnect` in lifespan (`lifespan.py:104,147`); **nothing in `app/` uploads images to S3** (grep for `upload_file`/`put_object`/`presigned` over `app/` returns only the s3_client module itself). The lab merely records image metadata: `store_captured_images` logs an `image_captured` event with the URL (`log_handler.py:138-154`).
- **Image arrival channels**: images ride on robot messages. Intermediate images come on `#.log` (`EntityUpdateService.store_captured_images`, `log_handler.py:496-498`); final images on `#.result` (`ResultHandler.process_result`, `result_handler.py:174-184`).
- **Notification to agent**: the lab → agent message is `publish_task_status` → `agent.exchange` / `{task_id}.task.status` (`mq_producer.py:132-151`). Its payload is `TaskStatusMsgPayload`: `task_id`, `status`, and per-step `{step_index, skill_type, status, error_message}` (`task_service.py:411-433`). **It carries NO image URL and NO photo payload** — the agent learns a step completed, not "here is a photo".

- **One terminal message per task, NOT a mid-task photo-ready handover.** Task status is published on step transitions: `step_completed`/`waiting` and the terminal `task_completed`/`task_failed` (`task_service.py:227,256`; `on_skill_completed`). There is **no "round complete / photo ready" inter-round message type** — `ApexMessageType.TASK_STATUS` is the only thing produced for the task. The expert's "take photo → robot uploads → notifies Lab Service → (hand back for recognition)" has **no corresponding mid-task lab→agent signal**: the lab cannot tell the agent "photo N is ready, decide the next ratio".

### Q5 — Does the lab run the FULL multi-round loop internally, or one round per dispatched task?

**Authoritative answer: ONE round per dispatched TLC task. The lab does NOT run a multi-round loop and has no recognition seam between rounds.**

Evidence chain:

1. **`TASK_STEPS` has room for exactly one round** — `[start_thin_layer_chromatography, end_thin_layer_chromatography]` (`task.py:127-130`). The generic step engine (`on_skill_completed`/`_submit_next`, `task_service.py:147-271, 440+`) just walks pending steps in order; it has **no round counter, no re-queue, no Rf branch** (grep for `round|retry|loop|recogni` in `task_service.py` returns nothing).
2. **`plan_from_request` builds a single round** — `round_index=1`, one `TLCRoundSpec`, `self.plan([spec], ...)` (`service.py:231-252`). The thin request (`CreateTLCTaskRequest`) carries no round count and no per-round ratios — only one `solvent_ratio` (`tlc.py:17-26`, `TLCParam` at `common/tlc.py`).
3. **The multi-round capability is latent** — `plan_run` *would* emit N STARTs + 1 END (`planner.py:393-423`), but no caller passes >1 round, and `TASK_STEPS` could not hold the extra STARTs anyway.
4. **No recognition / no decision point in the lab** — `observe_view`/`observe_uv`/`take_photo` are never called (Q1); the lab never computes Rf, never compares to a target window, and the `TLCRfGoal` type (`common/tlc.py`: `goal`, `range`) exists in shared-types but is **not even a field on `CreateTLCTaskRequest`** (`tlc.py:24-26` — only `param: TLCParam` + `objects`). The lab has no input for the acceptance window and no code that evaluates it.
5. **Loop exit is deterministic auto-recognition (expert)** — there is **no auto-recognition anywhere in the lab**. Whatever decides "Rf in window → stop, else new ratio → next round" must live OUTSIDE the lab (the agent / Mind), because the lab has neither the photo-analysis nor the target window.

So: to do N rounds today, **the agent must dispatch N separate TLC tasks** (each its own START→END), OR the lab must be extended to (a) accept rounds/target-window, (b) call `plan_run` with multiple rounds, (c) wire `observe_view`/`observe_uv`/`take_photo` between immerse and END, and (d) gain a recognition + inter-round handover. None of (a)–(d) exists today.

**Who can own the loop, given current lab capabilities:**

- **Agent (today's only viable owner):** the agent re-dispatches a fresh single-round TLC task per ratio, runs recognition on the returned photo URL itself (or via Mind), and stops when Rf is in window. The lab needs no change. Caveat: each re-dispatch re-runs round-1 prep (`_pickup_materials`) and `END_TLC` cleanup, because every dispatched task is `round_index=1` + END — i.e. **the per-task program disposes the plate at the end and re-fetches materials at the start**, which does NOT match the expert's "prep once / cleanup once" envelope. A per-round task would prep+spot+develop+dispose every round.
- **Lab (only if extended):** the planner ALREADY has the multi-round skeleton (`plan_run`, `round_index` branching, fresh tank per round, dispose-previous-plate on round ≥2). To make the lab own the loop you would: feed `plan_run` real N rounds, expand `TASK_STEPS`/step engine to N STARTs + END (or add an inter-round "observe+photo+recognize" step), and add a recognition callback + acceptance-window input. This is real work, not a config flip.

### Q6 — Relevant spec under `.trellis/spec/BIC-lab-service/`

- **`backend/tlc-placement.md`** — the TLC cross-layer contract. Confirms the round semantics indirectly:
  - "`plan_run` ... `plan_round`/`observe_view`/`observe_uv`/`take_photo`/`end_tlc`/`plan_run`. Reimplements the `tlc-op-builder` recipe" (line 149) — observe/take_photo are part of the *planner surface* but the spec never describes them being dispatched.
  - §5 "`TLC_OP_SKILLS = {START_TLC, END_TLC}`" (lines 205-206) — only these two op-skills are recognized by the placement writer. There is **no observe/photo skill in the dispatch set**.
  - §7 "single-robot-sequential execution" assumption (lines 420-424) — the occupancy model assumes one TLC dispatch in flight at a time; relevant if the agent re-dispatches rounds back-to-back.
  - §8 "current single-round flow does NOT consume them" (line 455) — the spec explicitly calls the live flow the **"single-round flow"**, confirming Q5.
  - The spec documents **no round/loop contract, no Rf-recognition contract, and no inter-round handover** — it treats TLC as a single START→END placement-authoring exercise.

There is **no spec describing a multi-round TLC loop, a target-Rf-window acceptance, or a photo-ready inter-round signal.** That contract does not exist yet.

---

## Caveats / Not Found

- **`observe_view`/`observe_uv`/`take_photo` are dead code** w.r.t. the dispatched flow — defined on `TLCPlanner` (`planner.py:326-372`) but with zero call-sites in `app/`. They were built for a between-rounds observation step that was never wired. Flag for the design decision: if the lab is to own the loop, these are the building blocks already present.
- **Expert model vs code divergences to flag:**
  - Expert "PREP once at start" → code: only *material fetch* is round-1-only; **tank prep + spot + immerse repeat every round** (correct), but **plate is disposed at the end of EVERY dispatched task** (`END_TLC` per task), so a per-task re-dispatch does NOT give "cleanup once at end".
  - Expert "take photo → notify Lab Service" → **no observe/take_photo op is dispatched and no mid-task photo-ready lab→agent message exists** (`task_service.py:411-433` payload has no image).
  - Expert "loop exit = deterministic auto-recognition of in-window Rf" → **no Rf recognition, no target-window input in the lab** (`CreateTLCTaskRequest` has no `TLCRfGoal`; `tlc.py:24-26`).
  - Expert "cleanup ONLY on success" → code: END runs on START-skill success (code 200), **not** on chemistry/Rf success (`task_service.py:220-271`).
- **`TLCRfGoal` exists in shared-types** (`common/tlc.py`) with `goal`/`range`, and `TLCPlateImage`/`TLCExperimentData` exist for photo data — so the *types* for a recognition loop are partly defined cross-team, but the lab does not consume them. Whether the agent already uses these is an agent-side question (out of scope here).
- I did not trace the agent side (BIC-agent-service) — by scope. The Q5 "agent owns the loop today" conclusion is inferred from the lab having no loop capability, not from confirming the agent currently does re-dispatch.
