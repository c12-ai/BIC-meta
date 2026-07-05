# Research: BIC-shared-types TLC op/skill contract — plate-memory MVP depth

- **Query**: Enumerate the TLC op/skill vocabulary in BIC-shared-types; determine whether a specific silica plate / developing tank / tube box can be NAMED and reused across the 3-command split (TLC_PREP / TLC_RUN_ROUND / TLC_CLEANUP), to choose plate-memory MVP depth (thin session→plate mapping vs full durable aggregate).
- **Scope**: internal (BIC-shared-types only, READ-ONLY)
- **Date**: 2026-06-29
- **shared-types version**: `1.1.6a1` (`BIC-shared-types/pyproject.toml:version`)

---

## TL;DR (decision-grade)

1. **There is NO multi-command session / round / attempt / correlation concept in shared-types today.** The only correlation keys are `task_id` (per CreateTaskRequest) and `skill_id` (per SkillCommand). No `session`, `round_index`, `attempt`, `correlation` field exists anywhere in `experiment_task`, `robot_protocol`, or `common`. (See Q6.)

2. **Q5 answer — a specific plate CANNOT be named/reused via the op contract today.** The op models address physical TLC fixtures (silica plate, developing tank, tip/tube boxes) by **slot index** (`slot_from_left`, 1-based) on the work-station, NOT by a stable plate/tank id. The only id-carrying handle is `ObjectRef{type,id?}`, and even there `id` is `None`-able and described as "lab-run provided," not chemist/agent-named. **Run-time `_first_available` is not in the contract either** — the contract simply doesn't model plate identity. Whoever fills the op sequence (lab-run) decides which slot. So "name a plate and reuse it across 3 commands" is **not expressible in the current contract**; it would have to live in lab-side state (tlc_inventory) keyed by something the agent does NOT send. (See Q5.)

3. **Recommendation: thin session→plate mapping, lab-side, leaning on the single-robot-one-TLC-in-flight invariant. Do NOT build a full durable session aggregate, and do NOT push plate identity into shared-types.** The op contract gives the agent zero levers to name a plate, so a heavy shared-types session aggregate would be contract bloat the agent can't drive. The natural seam already exists: `ObjectLocation`/`tlc_inventory` is "lab writes a placement keyed off chemist declaration, then addresses ops by slot." Extend that same lab-internal table with a `task_id → {silica_plate_slot, tank_slot, tube_box_slots}` row created at PREP and read at RUN_ROUND/CLEANUP. Single-TLC-in-flight makes a slot-level binding unambiguous. (See Recommendation.)

---

## Findings

### Files Found

| File Path | Description |
|---|---|
| `BIC-shared-types/bic_shared_types/robot_protocol/skills/tlc_ops.py` | The full TLC op vocabulary: `OpTarget`, op-name enums, `Location` discriminated union, `ObjectRef`, all `*Op` models, `Step`/`ParallelStep`. THE authoritative op contract. |
| `BIC-shared-types/bic_shared_types/robot_protocol/skills/tlc.py` | Skill-layer TLC commands: `StartTLCSkillCommand` (`START_TLC`) + `EndTLCSkillCommand` (`END_TLC`); both wrap a flat `tlc_ops: list[Step]`. |
| `BIC-shared-types/bic_shared_types/robot_protocol/skills/skill_commands.py` | `SkillType` enum, `SkillCommandBase` (`skill_id`/`work_station`), generic `TakePhotoSkillCommand`, `AdvanceCommandSkillCommand`, and `SkillResult` (images + `failed_op_id`). |
| `BIC-shared-types/bic_shared_types/robot_protocol/skills/ops_rules.py` | `AdvanceControl` (`reset` / `force_set_state`), `Fluent`-based world-state model, `OpsConstraintViolation`. Relevant to "how lab tracks state" but it's robot↔lab-run, not agent↔lab. |
| `BIC-shared-types/bic_shared_types/pipetting_robot_protocol/tlc.py` | The 4 pipetting-robot TLC request bodies that the `Tlc*Op` op models inherit (aspirate/dispense), all slot/row/col addressed. |
| `BIC-shared-types/bic_shared_types/common/tlc.py` | `TLCParam` (solvents+ratio — the PER-ROUND varying input), `TLCRfGoal` (goal/range — session-fixed), `TLCPlateImage`, `TLCExperimentData`. |
| `BIC-shared-types/bic_shared_types/common/object_location.py` | `ObjectLocation` (chemist-declared 2ml sample-tube placement) + `TubeCell`. The session-fixed sample list. Docstring explicitly describes the `tlc_inventory` lab-side seam. |
| `BIC-shared-types/bic_shared_types/experiment_task/http/tlc.py` | `CreateTLCTaskRequest` = `param: TLCParam` + `objects: list[ObjectLocation]` (min 2, max 4). The current single-task Agent↔Lab create contract. |
| `BIC-shared-types/bic_shared_types/experiment_task/http/_base.py` | `CreateTaskRequestBase`: `task_id: UUID`, `task_type: TaskType`. The only correlation key on create. |
| `BIC-shared-types/bic_shared_types/experiment_task/http/enums.py` | `TaskType` (CC / RE / **THIN_LAYER_CHROMATOGRAPHY** — a SINGLE TLC type today, no prep/round/cleanup siblings) + `TaskStatus`. |
| `BIC-shared-types/bic_shared_types/experiment_task/mq/task_status.py` | `TaskStatusMsgPayload` / `TaskStatusStepPayload` — the MQ status surface. **Carries NO image url today.** |
| `BIC-shared-types/bic_shared_types/robot_protocol/shared_models.py` | `CapturedImage` (work_station/camera/url/create_time) — image evidence lives on `SkillResult.images`, NOT on the task-status MQ payload. |
| `BIC-shared-types/bic_shared_types/robot_protocol/entity_updates.py` | `EntityUpdate` union. Note: **no silica-plate / developing-tank / tube-box entity types exist** — only Robot, Cartridges, TubeRack, RBFlask, CC/Evaporator devices. |

---

## Q1 — Full TLC `tlc_ops` vocabulary and the physical objects each op addresses

The vocabulary is a **nested discriminated union**: outer discriminator `target` (`tlc_ops.py:694`), inner discriminator `op`. Three targets (`OpTarget`, `tlc_ops.py:120-125`): `talos`, `cap_station`, `pipetting_robot`.

#### talos ops (`TalosOpName`, `tlc_ops.py:139-149`; models `tlc_ops.py:510-573`)

| Op model | op name | Physical objects referenced (via `Location` / `ObjectRef`) |
|---|---|---|
| `ResetTalosOp` (`:510`) | `reset` | none |
| `AgvMoveOp` (`:515`) | `agv_move` | `station: WorkStation` |
| `PickOp` (`:521`) | `pick` | `object: ObjectRef`, `source: Location`, `arm_count` |
| `PlaceOp` (`:531`) | `place` | `object: ObjectRef`, `to: Location`, `arm_count` |
| `MoveOp` (`:539`) | `move` | `to: Location` (no grab/release) |
| `PourOp` (`:546`) | `pour` | `object: ObjectRef`, `over: Location` (reserved for waste-liquid pour) |
| `AimCameraOp` (`:554`) | `aim_camera` | `camera` (LEFT/RIGHT arm RGB), `aim_at: Location` |
| `UvAimOp` (`:562`) | `uv_aim` | `aim_at: Location`, `wavelength: UVWavelength` (254/365nm); "only illuminates, does not capture — photo comes via TAKE_PHOTO" (`:563`) |

#### cap_station ops (`CapStationOpName`, `tlc_ops.py:152-161`; models `:579-622`)
`reset` / `clamp` / `unclamp` / `open_lid` / `close_lid` / `lid_to_tray` / `lid_from_tray`. All except `reset` take only `tube_type: CentrifugeTubeType`. These operate the cap-open/close mechanism on centrifuge tubes (solvent/sample tubes), not on plates/tanks.

#### pipetting_robot ops (`PipettingRobotOpName`, `tlc_ops.py:164-176`; models `:628-691`)
These **inherit the Allen pipetting-robot request bodies** from `pipetting_robot_protocol/tlc.py` (pass-through, `tlc_ops.py:31-36`, 659-676):

| Op model | op name | Inherited request | Physical addressing |
|---|---|---|---|
| `CommonResetOp` (`:628`) | `common_reset` | `CommonResetRequest` | none |
| `CommonMoveToPositionOp` (`:633`) | `common_move_to_position` | `CommonMoveToPositionRequest` | (x,y,z); "DMPK reserved, TLC unused" |
| `CommonTipBoxReplaceOp` (`:639`) | `common_tip_box_replace` | `TipBoxReplaceRequest` | tip box |
| `CommonPipetteReplaceOp` (`:644`) | `common_pipette_replace` | `PipetteReplaceRequest` | pipette (single/6-ch) |
| `CommonTipMountOp` (`:649`) | `common_tip_mount` | `MountTipRequest` | tip |
| `CommonTipEjectOp` (`:654`) | `common_tip_eject` | `EjectTipRequest` | tip |
| `TlcTubeRackAspirateOp` (`:659`) | `tlc_tube_rack_aspirate` | `TLCTubeRackAspirateRequest` (`pipetting_robot_protocol/tlc.py:21`) | tube **rack** by `row: int (1-15)` + volume + spacing (post-CC TLC) |
| `TlcSilicaPlateDispenseOp` (`:664`) | `tlc_silica_plate_dispense` | `TLCSilicaPlateDispenseRequest` (`tlc.py:29`) | silica plate — **only `volume` + `spacing`, NO plate id/slot** |
| `TlcCentrifugeTubeAspirateOp` (`:669`) | `tlc_centrifuge_tube_aspirate` | `TLCCentrifugeTubeAspirateRequest` (`tlc.py:36`) | tube box by `tube_type` + `row`(WellRow) + `col` |
| `TlcDevelopingTankDispenseOp` (`:674`) | `tlc_developing_tank_dispense` | `TLCDevelopingTankDispenseRequest` (`tlc.py:70`) | developing tank — **only `volume`, NO tank id/slot** |

**Key observation for plate-memory:** the pipetting-robot dispense/aspirate ops do NOT name the plate or tank at all — they are "dispense N µL to *the* silica plate / *the* tank." Which physical plate/tank is implied entirely by the talos `pick`/`place`/`aim_camera` ops that staged it, addressed by slot `Location`. So plate identity is never a first-class field; it is positional/contextual.

#### `Step` structure (`tlc_ops.py:702-714`)
A `Step` is either a single `Op` (default, no `logic_type`) or a `ParallelStep` (`logic_type=parallel`, nested `parallel_ops: list[list[Step]]`). `planning_unit` was removed (`:135-136`, `:711-712`). Ops carry a global 0-based `op_id` (`_OpBase`, `:496-499`).

---

## Q2 — Mapping the vocabulary to PREP / ROUND / CLEANUP

shared-types does **not** split TLC into prep/round/cleanup. It defines exactly **two** skills (`tlc.py`): `START_TLC` and `END_TLC`, each a flat `tlc_ops: list[Step]`. The op→phase mapping below is what the START/END docstrings describe, mapped onto the task's intended 3-command split. **No model enforces this split — it is purely how lab-run composes the op list.**

- **PREP (fetch/setup, once)** — `START_TLC` scope opener, "取料(首轮)" / fetch materials (`tlc.py:8`, `:38`): `AgvMove` (`:515`), `Pick`/`Place` of tube boxes, tip boxes, silica plate, developing tank from `TlcSupplyShelfLoc` (`:413`) to work-station slots (`SilicaPlateSlotLoc :392`, `DevelopingTankSlotLoc :376`, `TubeBox2mlSlotLoc :361`, `TipBoxSlotLoc :371`).
- **ROUND (tank-prep + spot + develop + photo, repeated)** — the body of `START_TLC` (`tlc.py:8`): solvent dosing (`TlcCentrifugeTubeAspirate` → `TlcDevelopingTankDispense`), spotting (`TlcCentrifugeTubeAspirate`/`TlcTubeRackAspirate` → `TlcSilicaPlateDispense`), develop (`Place` plate into tank, `aim_camera` at `DevelopingTankSlotLoc`), then UV observe + photo. **Critically, `tlc.py:8-9` states the develop-monitor photo / plate-UV-observe / success-or-retry are issued as INDEPENDENT lab-run requests AFTER `START_TLC`** — i.e. observe/photo is already conceptually a separate command, which aligns with the task's RUN_ROUND boundary.
- **CLEANUP (dispose, once)** — `END_TLC` (`tlc.py:53-69`): dispose used materials to disposal bins (`DisposalBinSlotLoc :399` — slot 1 waste-plate bin, slot 2 reserved waste-liquid), return imager/plate-view-stand items, robot to idle. `EndTLCLabParams.tlc_ops` is "same shape as START_TLC, op templates provided by LabRun, not hard-coded in shared-types" (`tlc.py:54-58`).

**Flag (makes the 3-command split harder than expected):** The task wants 3 sibling `TaskType`s correlated by a session id, but shared-types only has (a) ONE `TaskType.THIN_LAYER_CHROMATOGRAPHY` (`enums.py:11`) and (b) TWO skills (START/END), where START already bundles prep+round and END is cleanup. There is **no `TLC_RUN_ROUND` skill or task type**, and observe/photo is not a TLC-specific skill — it's the generic `TAKE_PHOTO` (Q3). Introducing prep/round/cleanup siblings is net-new contract work in `experiment_task/http/enums.py` + new CreateTaskRequest models + (optionally) new SkillTypes.

---

## Q3 — TLC SkillType(s); is observe/take_photo first-class?

`SkillType` enum (`skill_commands.py:25-42`). TLC-relevant members:
- `START_TLC = "start_thin_layer_chromatography"` (`:36`)
- `END_TLC = "end_thin_layer_chromatography"` (`:37`)
- `TAKE_PHOTO = "take_photo"` (`:38`) — **generic, task-agnostic**, not TLC-specific.
- `ADVANCE_COMMAND = "advance_command"` (`:42`) — reset / force_set_state control.

**Answer:** There is NO TLC-specific observe/photo SkillType. Photo capture is the generic `TakePhotoSkillCommand` (`skill_commands.py:84-89`) whose `lab_params.cameras: list[CameraType]` (`:67-81`) picks 1-4 arm cameras; "robot does not move, captures in place." UV illumination is an **op inside the program** (`UvAimOp`, `tlc_ops.py:562`) — it only illuminates; the actual photo is a separate `TAKE_PHOTO` skill (`tlc_ops.py:563`). So observe = `uv_aim` op + `take_photo` skill, not a first-class TLC skill. The START_TLC docstring confirms photo/observe/retry are independent post-START_TLC requests (`tlc.py:8`).

---

## Q4 — Per-round varying vs session-fixed inputs

| Input | Model + file:line | Per-round varying or session-fixed |
|---|---|---|
| Solvent system + ratio | `TLCParam{solvents: list[Solvent], solvent_ratio: list[PositiveInt]}` (`common/tlc.py:27-38`) | **PER-ROUND varying** (each retry adjusts the mix; this is what `recommend_tlc_mixcase` adapts per design.md §1) |
| Sample tubes (2-4) | `objects: list[ObjectLocation]` min 2 max 4 (`experiment_task/http/tlc.py:26`); each `ObjectLocation{tube_id, box_id, cell:TubeCell, object_type=TUBE_2ML}` (`object_location.py:24-35`) | **SESSION-FIXED** (same tubes spotted every round) |
| Target Rf window / goal | `TLCRfGoal{goal: float=0.5, range: tuple=(0.2,0.8)}` (`common/tlc.py:12-24`) | **SESSION-FIXED** (the accept window; note: NOT currently a field on `CreateTLCTaskRequest` — see flag) |

**Flag:** `TLCRfGoal` exists in `common/tlc.py` but is **NOT wired into `CreateTLCTaskRequest`** (`http/tlc.py:17-26` only has `param` + `objects`). The target window the design's `_evaluate_route` needs is defined but not yet on the create contract. Adding the prep command is a natural place to introduce `target_window: TLCRfGoal`.

---

## Q5 — Object IDENTITY (the crux): can a specific plate/tank/box be NAMED and reused, or run-time chosen?

**Two addressing mechanisms exist, neither lets the agent name a reusable plate:**

1. **Slot-index `Location`** (the dominant one). Physical TLC fixtures are addressed by 1-based slot on the work-station, NOT by id:
   - `SilicaPlateSlotLoc.slot_from_left: int (ge=1, le=4)` (`tlc_ops.py:392-396`) — "4 slots on the desk holding silica-plate boxes."
   - `DevelopingTankSlotLoc.slot_from_left: int (ge=1, le=3)` (`tlc_ops.py:376-380`).
   - `TubeBox2mlSlotLoc` / `TubeBox50mlSlotLoc` / `TipBoxSlotLoc`: `slot_from_left (ge=1, le=3)` (`tlc_ops.py:361-373`).
   - `PipettingAgvSlotLoc.slot: PipettingAgvSlot` (semantic enum, `tlc_ops.py:179-191`, `337-341`).
   The dispense/aspirate ops carry **no plate/tank handle at all** (`pipetting_robot_protocol/tlc.py:29-33` silica = volume+spacing only; `:70-73` tank = volume only).

2. **`ObjectRef{type: ObjectType, id: str | None = None}`** (`tlc_ops.py:276-284`) — the only id-bearing handle, used by `pick`/`place`/`pour` (`object: ObjectRef`). Its docstring is decisive (`tlc_ops.py:277-281`):
   > `id` 由 lab-run 提供、同一实体跨 op 复用同一 id ... 离心管盒/离心管都带 id；枪头盒/盖子等不带。
   ("`id` is **provided by lab-run**; same entity reuses same id across ops ... tube boxes/tubes carry id; tip boxes/lids do not.")
   `ObjectType` (`tlc_ops.py:200-218`) includes `SILICA_PLATE`, `DEVELOPING_TANK`, `DEVELOPING_TANK_LID`, `TUBE_BOX_2ML`, etc.

**Answer to Q5:** The contract does **NOT** let the agent (or even lab at the create boundary) NAME a specific silica plate / tank to reuse across commands:
- The `ObjectRef.id` that *could* tag a plate is explicitly **"provided by lab-run,"** is `None`-able, and is scoped to "same id across ops" *within a single op program* — not a cross-command durable name the agent supplies. The agent never sends `ObjectRef`; it sends `CreateTLCTaskRequest` (just `param` + `objects`), and lab-run composes the ops.
- It is also **NOT** literally "`_first_available` at run time" in the type system — the contract simply does not model plate selection. The choice of slot/id is made by whatever fills `tlc_ops` (lab-run), and shared-types stays silent.
- The ONLY thing the agent declares about physical objects is the sample-tube placement via `ObjectLocation` (`object_location.py:24-35`), and even that is "lab writes it into `tlc_inventory`, then addresses ops by slot; `rack_slot` is derived by Lab Service from `box_id` and NOT put on the wire" (`object_location.py:26-30, 33-35`).

So: **plate identity is a lab-internal concern. The agent has no contract field to name or pin a plate across PREP/ROUND/CLEANUP.** Any "remember this plate" must be lab-side state keyed off something the agent already sends — and the only stable agent-supplied key is `task_id` (per the chosen session).

---

## Q6 — Any existing multi-command session / correlation beyond task_id?

**None.** Grep over `experiment_task` + `robot_protocol` + `common` for `session|round_index|round|attempt|correlation` returns only false positives (`ROUND_BOTTOM_FLASK`, `RoundBottomFlask*`, and a doc comment) — no session/round/attempt construct. Evidence:
- `CreateTaskRequestBase`: only `task_id: UUID` + `task_type` (`experiment_task/http/_base.py:13-20`). `task_id` doc: "由 Apex 生成，串联本次任务的所有数据对象" (ties together one task's data objects).
- `SkillCommandBase`: only `skill_id` + `skill_type` + `work_station` (`skill_commands.py:50-59`). `skill_id` correlates a skill call to its result.
- `TaskStatusMsgPayload`: `task_id` + `agent_side_task_id` ("echoed back for correlation," `mq/task_status.py:23-37`).
- `SkillResult`: `skill_id` correlates result→call (`skill_commands.py:114-125`).

**Implication:** A "session" correlating PREP/ROUND×n/CLEANUP does not exist as a type. The task must either (a) reuse `task_id` as the session id across 3 sibling commands, or (b) introduce a new `session_id`/`correlation_id` field on the new create requests. shared-types offers no off-the-shelf field.

---

## Q7 — MQ result/status side: per-op/skill captured-image URL?

- **`SkillResult.images: list[CapturedImage] | None`** (`skill_commands.py:121`) — yes, the **skill result** carries images. `CapturedImage{work_station, camera, device?, component?, url, create_time}` (`shared_models.py:21-35`); `url` = MinIO path (`:33`). `SkillResult` also has `failed_op_id: int | None` for op-program failures (`skill_commands.py:123-125`).
- **`TLCPlateImage{uv_url?, rgb_url}`** (`common/tlc.py:41-48`) and `TLCExperimentData.plates: list[TLCPlateImage]` (`:50-53`) — TLC-domain image bundle (UV + RGB), used in the recognition path.
- **GAP — `TaskStatusMsgPayload` carries NO image url.** `mq/task_status.py:14-38`: `TaskStatusStepPayload{step_index, skill_type, status, error_message?}` and `TaskStatusMsgPayload{task_id, agent_side_task_id?, status, steps, error_message?}`. **No url / image field on the task-status MQ message.**

**Implication for the design's "publish task.status + image_url" arrow (design.md §1):** the image url is NOT currently expressible on `TaskStatusMsgPayload`. Either the lab surfaces the photo via `SkillResult.images` on a different MQ message, or `TaskStatusMsgPayload`/`TaskStatusStepPayload` must gain an `image_url`/`images` field. This is a contract change to flag.

---

## Recommendation — plate-memory MVP depth

**Choose: thin, lab-side session→slot mapping keyed by the session's `task_id`, leaning on the single-robot-one-TLC-in-flight invariant. Do NOT build a full durable session aggregate, and do NOT add plate-identity fields to shared-types.**

Justification grounded in the contract:

1. **The op contract gives the agent zero levers to name a plate (Q5).** Dispense/aspirate ops are plate-anonymous (volume/spacing only); the only id handle (`ObjectRef.id`) is explicitly lab-run-owned and op-scoped. A heavy shared-types session aggregate that carries `silica_plate_id`/`tank_id` would be fields the agent cannot meaningfully populate and the robot ops never read — pure contract bloat. The memory belongs where identity already lives: lab-side.

2. **The seam already exists and is documented.** `ObjectLocation`'s docstring (`object_location.py:26-30`) describes exactly the pattern to extend: "Lab Service writes the placement into `tlc_inventory`, then addresses ops by slot; `rack_slot` is derived from `box_id` and not put on the wire." A thin `task_id → {silica_plate_slot, tank_slot, tube_box_slots, tip_box_slot}` row, created during PREP op-composition and read during RUN_ROUND/CLEANUP op-composition, is the minimal extension of an already-blessed mechanism.

3. **Single-TLC-in-flight makes slot-level binding unambiguous.** Because the contract addresses fixtures by `slot_from_left` on one work-station (Q5) and only one TLC session runs at a time, a per-`task_id` slot map cannot be confused with another session's plate. You don't need a globally-unique durable plate aggregate to disambiguate — the invariant does it for free.

4. **Correlation key is already available.** `task_id` (`http/_base.py:19`) is the only stable agent-supplied identifier and is explicitly meant to "tie together all of this task's data objects." Reusing it as the session id for the 3 sibling commands avoids inventing a new `session_id` field, keeping the create-contract change minimal.

5. **What a thin mapping does NOT need (and why full aggregate is over-build):** no plate lifecycle state machine in shared-types, no `EntityUpdate` type for silica plate/tank (none exists today — `entity_updates.py:222-231`), no durable cross-session plate registry. Those only pay off with concurrent sessions or plate reuse across tasks, neither of which the locked design or the contract supports.

### Net-new contract work this implies (flag for the implementers)
Independent of memory depth, the 3-command split requires shared-types additions the current contract lacks:
- **TaskType / CreateTaskRequest siblings** for prep / run_round / cleanup (today only one `THIN_LAYER_CHROMATOGRAPHY`, `enums.py:11`) — OR model the 3 commands as new `SkillType`s rather than `TaskType`s. Decide which layer the split lives on.
- A **session/correlation field** if `task_id` is not reused (Q6 — none exists).
- **`target_window: TLCRfGoal`** onto the prep request (Q4 flag — `TLCRfGoal` defined but unwired).
- **An image-url field on the task-status MQ payload** OR a decision to surface the round photo via `SkillResult.images` instead (Q7 flag — `TaskStatusMsgPayload` has no url today).

## Caveats / Not Found
- I researched ONLY BIC-shared-types (per scope). I did NOT inspect the lab-service `tlc_inventory` implementation, so the *current* lab-side memory behavior is asserted from the `ObjectLocation` docstring, not from lab code. If the implementer needs the actual `tlc_inventory` schema, that's a follow-up read in BIC-lab-service.
- The prep/round/cleanup→op mapping (Q2) is reconstructed from the START_TLC/END_TLC docstrings; shared-types does not encode the phase split, so treat the mapping as intent, not a typed contract.
- No `TLC_RUN_ROUND` skill or observe-specific TLC skill exists; "round" today is the body of START_TLC plus independent post-START_TLC TAKE_PHOTO requests.
