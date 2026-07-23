# Research: TLC Dispatch Contract — Solvent System Path

- **Query**: How does the target solvent system travel from the chemist's confirmed TLC parameters to the lab-service planner, and what would a developing-tank reuse change require?
- **Scope**: internal — BIC-shared-types, BIC-agent-service, BIC-lab-service
- **Date**: 2026-07-10

---

## Summary

The solvent system is carried as a **structured pair of parallel lists** (`solvents: list[Solvent]` + `solvent_ratio: list[PositiveInt]`) all the way from the form draft to the planner. There is NO free-string representation at any hop. The `Solvent` enum has four values (`PE`, `EA`, `DCM`, `MeOH`). The ratio is a list of positive integers (e.g. `[3, 1]` for 3:1).

The field that matters for tank-contents matching is `TLCParam` (the `param` field of `CreateTLCTaskRequest` and `AppendTLCRoundRequest`). Lab-service receives it, stores it in `task.params["rounds"]`, and at round-plan time splits a fixed 2000 µL total by ratio to produce per-solvent volumes — this is the only place absolute volumes are computed.

Agent-service does NOT need to change to support tank reuse. The `param` field already carries everything the planner needs to compare against a tank's stored contents. The change lives entirely inside lab-service's planner/allocator. Shared-types needs no change.

---

## Q1 — TLC Dispatch Payload: Schema and Solvent Fields

### `CreateTLCTaskRequest`
File: `/Users/drakezhou/Development/BIC/BIC-shared-types/bic_shared_types/experiment_task/http/tlc.py`

```python
class CreateTLCTaskRequest(CreateTaskRequestBase):
    task_type: Literal[TaskType.THIN_LAYER_CHROMATOGRAPHY]
    param: TLCParam                        # solvent system + ratio for round 1
    objects: list[ObjectLocation]          # 2–4 sample tubes (box_id, cell, tube_id)
    target_window: TLCRfGoal              # chemist's Rf acceptance window
```

### `AppendTLCRoundRequest`
File: `/Users/drakezhou/Development/BIC/BIC-shared-types/bic_shared_types/experiment_task/http/tlc.py:32`

```python
class AppendTLCRoundRequest(BaseModel):
    param: TLCParam    # round N's solvent system + ratio (tubes + window already on the Task)
```

### `TLCParam` (the solvent carrier)
File: `/Users/drakezhou/Development/BIC/BIC-shared-types/bic_shared_types/common/tlc.py:27`

```python
class TLCParam(BaseModel):
    solvents: list[Solvent]        # e.g. [Solvent.PE, Solvent.EA]
    solvent_ratio: list[PositiveInt]  # e.g. [3, 1]
    # invariant: len(solvent_ratio) == len(solvents)
```

### `Solvent` enum
File: `/Users/drakezhou/Development/BIC/BIC-shared-types/bic_shared_types/common/enums.py:21`

```python
class Solvent(StrEnum):
    PE   = "PE"    # 石油醚
    EA   = "EA"    # 乙酸乙酯
    DCM  = "DCM"   # 二氯甲烷
    MEOH = "MeOH"  # 甲醇
```

**Example payload** (PE:EA = 3:1):
```json
{
  "task_type": "thin_layer_chromatography",
  "task_id": "<uuid>",
  "param": { "solvents": ["PE", "EA"], "solvent_ratio": [3, 1] },
  "objects": [
    { "tube_id": "t1", "box_id": "box_a", "cell": { "row": "A", "col": 1 }, "object_type": "tube_2ml" },
    { "tube_id": "t2", "box_id": "box_a", "cell": { "row": "A", "col": 4 }, "object_type": "tube_2ml" }
  ],
  "target_window": { "goal": 0.5, "range": [0.2, 0.8] }
}
```

---

## Q2 — Agent-Service Side: Where Confirmed TLC Params Map into the Dispatch Payload

### Form model chain

1. **ChemEngine recommends** `TLCMixcaseResponse.recommendation.param: TLCParam`  
   (extracted at `tlc.py:194` via `extract_param=lambda response: response.recommendation.param`).

2. **Written into `TLCParamsForm.recommended: TLCParam | None`**  
   File: `/Users/drakezhou/Development/BIC/BIC-agent-service/app/events/form_payloads.py:409`

3. **At dispatch**, `_submit_l4` in  
   `/Users/drakezhou/Development/BIC/BIC-agent-service/app/runtime/graphs/specialists/tools.py:594–634`  
   reads `TLCParamsForm.model_validate(draft)` and builds:

```python
task_request = CreateTLCTaskRequest(
    task_id=task_uuid,
    param=tlc_form.recommended,   # ← the TLCParam from ChemEngine / chemist edits
    objects=[t.to_object_location() for t in sample_tubes],
    target_window=TLCRfGoal(goal=(low + high) / 2, range=target_window),
)
```

4. **Retry rounds** use `lab.append_round(trial.lab_task_id, AppendTLCRoundRequest(param=new_param))`  
   where `new_param` comes from a re-run of `recommend_tlc_mixcase` threading prior trials as history.  
   File: `/Users/drakezhou/Development/BIC/BIC-agent-service/app/runtime/graphs/specialists/tlc.py:1053–1130` (`_auto_retry_node`)

### Normalization along the way

- **No free-string formatting.** The solvent system travels as `list[Solvent]` + `list[int]` through every hop. There is no step that converts to or from a string like `"PE:EA=3:1"`.
- **Purity is stripped** at dispatch: `TLCTubeAssignment.to_object_location()` drops the `purity` field before building `CreateTLCTaskRequest.objects` (line 335–348 of form_payloads.py). Purity is agent-local only.
- `TLCParamsForm.from_user.solvents` / `from_user.solvent_ratio` are the chemist's context fields used to build the `TLCMixcaseRequest` (CC recommendation input); they are **not** what is dispatched. What is dispatched is always `form.recommended` — the Mind-produced `TLCParam`.

---

## Q3 — Ratio/Solvent Representation Consistency Across Hops

| Hop | Carrier | Shape |
|---|---|---|
| Portal form | `TLCParamsForm` JSON (SSE/REST) | `solvents: string[]`, `solvent_ratio: number[]` (Zod mirror) |
| Agent-service form state | `TLCParamsForm.recommended: TLCParam` | Pydantic: `list[Solvent]`, `list[PositiveInt]` |
| `CreateTLCTaskRequest` body (`POST /tasks/`) | JSON | `param.solvents: ["PE","EA"]`, `param.solvent_ratio: [3,1]` |
| `AppendTLCRoundRequest` body (`POST /tasks/{id}/rounds`) | JSON | same structure, `param` only |
| lab-service `task.params["rounds"]` (DB JSONB) | dict | stored as JSON from the request body |
| lab-service planner input (`TLCRoundSpec.solvents`) | `list[SolventDispense]` | volume computed from ratio at plan time: `volume[i] = 2000 * ratio[i] / sum(ratio)` |

The representation is **structured (list + list) at every hop** with no format ambiguity. A tank-contents matching rule can compare `param.solvents` and `param.solvent_ratio` directly against a tank's stored properties without any parsing.

**Volume derivation** (lab-service, the only place absolute volumes appear):  
File: `/Users/drakezhou/Development/BIC/BIC-lab-service/app/tlc/service.py:84,389`

```python
_TOTAL_DEVELOPING_VOLUME = 2000.0  # µL

volumes = _split_by_ratio(_TOTAL_DEVELOPING_VOLUME, round_param.solvent_ratio)
# e.g. ratio [3,1] → [1500.0, 500.0] µL
```

---

## Q4 — Spec Documents Covering the Agent↔Lab Dispatch Contract

### Agent-service specs

| File | Relevant section |
|---|---|
| `/Users/drakezhou/Development/BIC/BIC-agent-service/.trellis/spec/backend/L4/clients.md` | §LabClient — `submit_task`, `append_round`, `cleanup`; dispatch union (LOCAL CC\|RE\|TLC); error matrix |
| `/Users/drakezhou/Development/BIC/BIC-agent-service/.trellis/spec/backend/contracts.md` | §3 form-confirm contract; §TLC dispatch contract |
| `/Users/drakezhou/Development/BIC/BIC-agent-service/.trellis/spec/backend/L3/graphs.md` | TLC specialist subgraph wiring; `_auto_submit_node` dispatch seam |
| `/Users/drakezhou/Development/BIC/BIC-agent-service/.trellis/spec/backend/L3/specialist_tools.md` | `_submit_l4` contract; TLC arm |

### Lab-service specs

No `.trellis/spec/` in BIC-lab-service covers the `POST /tasks/` or `POST /tasks/{id}/rounds` request schema in spec-file form. The authoritative sources are:

- `/Users/drakezhou/Development/BIC/BIC-lab-service/docs/dataflow.md` — agent↔lab MQ and REST dataflow
- `/Users/drakezhou/Development/BIC/BIC-lab-service/docs/architecture.md` — service layer, task module, TASK_STEPS
- `/Users/drakezhou/Development/BIC/BIC-lab-service/app/tlc/planner.py` — TLCPlanner domain service (the place where a tank-reuse decision would live)
- `/Users/drakezhou/Development/BIC/BIC-lab-service/app/tlc/service.py` — TLCService orchestration (where `developing_tank_slot` is currently pinned to `binding.tank_slot`)

**Per rule 10 (respect the contract doc and spec):** a planner behavior change (reuse a tank vs always use a fresh one) that changes how the planner selects `developing_tank_slot` in `TLCRoundSpec` is a **lab-service-internal implementation change** — it does not change the shared-types schema, the `POST /tasks/` request body, or the `AppendTLCRoundRequest` body. No shared-types or agent-service spec update is required. The lab-service's own `docs/` and possibly a task-level design note are the right place to document it.

---

## Q5 — Does Agent-Service Surface Solvent-Prep Steps to the User?

### Step event shape

`TaskStepEvent` (file: `/Users/drakezhou/Development/BIC/BIC-shared-types/bic_shared_types/experiment_task/mq/task_status.py:26`) carries:

```python
class TaskStepEvent(BaseModel):
    event_id: str
    step_index: int
    skill_type: str      # e.g. "start_tlc", "end_tlc"
    status: str          # step_started | step_completed | step_failed | step_waiting
    occurred_at: datetime
    error_message: str | None = None
```

The `skill_type` values for TLC are `"start_tlc"` (one per round) and `"end_tlc"` (cleanup). There is **no sub-step event for solvent prep (配液)** — the solvent dispense is a sequence of ops INSIDE the `StartTLCLabParams.tlc_ops` program, not a separate `SkillType`. The agent and portal only see `START_TLC` (one per round) and `END_TLC`.

### What "skipping 配液" means at the step-event level

If lab-service reuses an existing developing tank (matching solvent system), the round's `_prepare_solvents` ops would be omitted or shortened from the `StartTLCLabParams.tlc_ops` program the planner emits. From the agent-service and portal's perspective, the step is still one `START_TLC` event — no new step event type is introduced, no existing event type changes. The agent does not surface 配液 as a named step; it only observes:

1. `task_status` MQ message with `step_events: [{skill_type: "start_tlc", status: "step_started"}, ...]`
2. Later: `{skill_type: "start_tlc", status: "step_completed"}` with `image_url` of the developed plate.

**No agent-service or portal change is required** if the only change is that the lab-service planner emits fewer ops inside the `tlc_ops` array for a reuse round. The external contract (MQ message shape, REST response shape, step-event types) stays identical.

---

## Caveats / Not Found

- **Tank stored-contents schema in lab-service**: I confirmed that lab-service currently pins `developing_tank_slot=binding.tank_slot` (from the prep-time allocation) and that the `TLCRoundSpec` carries `developing_tank_slot: int`. I did **not** verify whether lab-service currently persists solvent system properties on the developing tank's inventory record (the feature that would enable matching). That is a lab-service data model question (UNVERIFIED — would need to read `app/tlc/allocate.py` and the `inventory_items` / `locations` ORM model to confirm the property bag structure).
- **Shared-types `CreateTaskRequest` union is CC|RE only** (lab-service spec note line 316): the spec doc says TLC was intentionally excluded. However, the actual shared-types code I read shows `CreateTLCTaskRequest` IS in the shared-types package (`bic_shared_types/experiment_task/http/tlc.py`) and the `CreateTaskRequest` union in `bic_shared_types/experiment_task/http/__init__.py` may or may not include TLC. The spec doc says agent-service adds TLC locally. This is a potential spec/code drift — UNVERIFIED which is current.
- **Portal step display**: I confirmed the step-event wire shape (`skill_type` string) but did not read the portal's event-dispatcher or step-card components to confirm how it renders `"start_tlc"`. Any label change in the portal for a "reusing tank" UX hint would be a portal concern, not an agent-service or shared-types concern.
