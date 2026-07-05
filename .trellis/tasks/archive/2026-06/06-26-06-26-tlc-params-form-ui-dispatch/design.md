# Design — TLC ObjectLocation contract + UI-to-lab dispatch

Implements the parent `prd.md`. Defines the cross-layer `ObjectLocation` contract
and the per-layer technical design. Grounded in `research/objectlocation-shape.md`
(Q1–Q5) and `research/cc-params-dispatch-pattern.md`.

## 1. The contract (`ObjectLocation`)

Model **B (declare placement)** is chosen, so the chemist's selection is a
placement assertion the lab must record. `ObjectLocation` therefore carries the
FULL address (not just `tube_id`), because in a real run the chosen tube may not
yet be in `tlc_inventory` with a cell, so the lab cannot rely on `where_is()`.

```python
# bic_shared_types/  (new type; placed beside TLCParam in common/tlc.py OR a new
# common/object_location.py — see §2 for placement decision)

class ObjectLocation(BaseModel):
    """One chemist-declared TLC sample tube placement.

    The chemist physically places a 2ml sample tube into a box cell and declares
    it here. The lab WRITES this placement into tlc_inventory before planning, then
    addresses the tube by its cell in the dispatched tlc_ops. rack_slot is DERIVED
    by the lab from box_id (where the box sits), not carried on the wire.
    """
    tube_id: str = Field(min_length=1)            # the 2ml sample tube id, e.g. "tube_2ml_017"
    box_id: str = Field(min_length=1)             # the tube box the tube sits in (parent_object_id)
    cell: TubeCell                                # which cell in the box (row letter + col number)
    object_type: Literal[ObjectType.TUBE_2ML] = ObjectType.TUBE_2ML  # typed guard, defaulted


class TubeCell(BaseModel):
    """A box-grid cell in PROTOCOL axes (matches the robot op + _place_tube_into_box)."""
    row: WellRow                                  # A–D for a 2ml box
    col: int = Field(ge=1, le=5)                  # 1–5 for a 2ml box


class CreateTLCTaskRequest(CreateTaskRequestBase):
    task_type: Literal[TaskType.THIN_LAYER_CHROMATOGRAPHY] = ...
    param: TLCParam
    objects: list[ObjectLocation] = Field(min_length=2, max_length=4)  # chemist's 2–4 sample tubes
```

Axis note (`research` §Q4): the DB stores `cell_col`=letter, `cell_row`=number
(swapped names vs protocol). The WIRE uses protocol axes (`row: WellRow` letter +
`col: 1..5` number) to match the robot op and `_place_tube_into_box`. The lab maps
wire→DB at the write boundary.

`rack_slot` is intentionally NOT on the wire: a box already sits on a known slot
(`box.location_id`), so the lab derives it. The chemist declares tube→box+cell;
the box→slot relationship is lab state.

### Validation (lab-side, returns clean 400 — AC3)

- `len(objects)` is 2–4 (also enforced by the Field constraint → 422 at parse).
- all `objects` share one `box_id` AND form **one contiguous row** (same `cell.row`,
  consecutive `cell.col`). The planner assumes one row at cols 1..n in list order
  (`planner.py:636-685`); non-contiguous picks would be mis-addressed.
- `box_id` resolves to a real tube box on a known rack-slot.

## 2. Layer designs

### 2a. shared-types (child: `st`)

- Define `ObjectLocation` + `TubeCell`. Placement: **new `common/object_location.py`**
  (it is cross-experiment by design — the stub exists in CC/RE/TLC — but we only
  WIRE it into TLC now; defining it standalone avoids coupling it to `tlc.py`).
- Un-stub `objects: list[ObjectLocation] = Field(min_length=2, max_length=4)` on
  `CreateTLCTaskRequest` ONLY (`experiment_task/http/tlc.py:19-20`). Leave CC/RE
  stubs untouched.
- Fix the misleading docstring (Nexus decomposes the task into SkillCommands, not
  the requester).
- Run the contract-repo gate per `BIC-shared-types/AGENTS.md` (schemas/examples/
  OpenAPI/client regen). Commit on `feat/tlc-skill-protocol`. No main rebase.

### 2b. lab-service (child: `lab`)

- Re-pin `pyproject.toml` to the new shared-types rev (`feat/tlc-skill-protocol` HEAD).
- **New request-driven placement write** (the gap — none exists today, only
  robot-`place`-driven `placement.py:103-140`): before planning, for each
  `ObjectLocation`, write tube→box+cell into `tlc_inventory` (reuse
  `TubeBox.insert` / `persist_box` / `_set_placement`, `inventory.py:119-152`).
  Idempotent: a re-declared placement updates in place.
- **`plan_from_request` (`service.py:159-211`)**: replace
  `_tube_ids(box2, count=1)` (line 175) with `[o.tube_id for o in req.objects]`,
  ordered by `cell.col`. Derive `box2` from the chosen tubes' shared `box_id`
  (via the declared placement) instead of `_first_available(TUBE_BOX_2ML)`
  (line 169 / `allocate_round_materials:98-99`). 50ml solvent box, plate, tip
  boxes stay auto-allocated.
- **Validation** (§1) at the API boundary (router/command_validator), clean 400.
- `_tube_ids` stays for the solvent path only (`count=n_solvents`, line 174).
- The `SpottingSpec.sample_tube_ids` bound (`planner.py:129` `1..5`) — align doc
  to the request's `2..4` where relevant; no planner logic rewrite (row-contiguity
  is validated upstream).

### 2c. agent-service (child: `be`)

- Re-pin `pyproject.toml` to the new shared-types rev.
- `app/events/form_payloads.py` — `TLCLabLogistics` gains the chemist tube
  selections (the 2–4 `ObjectLocation`s) so they ride the params form.
- `_submit_l4` TLC arm (`tools.py:543-559`) — pass `objects=<from form>` into
  `CreateTLCTaskRequest(task_id, param=…, objects=…)`.
- Drop the local TLC-inclusive widen in `lab_client.py` once shared-types has the
  field (no local override left for TLC dispatch — AC1).
- The TLC specialist (`specialists/tlc.py`) surfaces a tube-selection need (the
  form must collect 2–4 tubes); ensure the params-confirm payload includes them.

### 2d. portal (child: `fe`)

Mirror CC's params path (`research/cc-params-dispatch-pattern.md`):

- `ParameterDesignPanel.tsx:218` — drop `'tlc'` from `isPlaceholderStage` (keep `'fp'`).
- `:79`, `:208-214` — admit `'tlc'` to `Executor` / `hasExecutorForm` /
  `stageHasConfirmedRobotJob` so the real-form branch + footer render for TLC.
- New `forms/TlcParamsForm.tsx` (`forwardRef<DynamicFormHandle>` via
  `useParamsFormHandle({id:'workspace.params.tlc'})`): `rxn` (text, pre-filled),
  `target_window` (two number inputs lo/hi, [0,1]), editable `solvents`+ratio
  (reuse CC's Solvent-chip helpers), and a **2–4 sample-tube selector** (each row:
  tube_id + box_id + cell row/col). Presence gate: rxn non-empty, target_window
  both present, 2–4 tubes each with tube_id+box_id+cell, solvents+ratio present.
- `FORM_IDS` (`:81`) — add `'workspace.params.tlc'`.
- `params-coerce.ts` — `coerceTlcParamsForm`.
- Dispatch: TLC bypasses `MaterialPreparationPanel` (its `lab_logistics` is the
  tube list, not cartridge/flask staging) — `onConfirm` branches: `tlc` →
  `confirm('params', values)` directly; `cc`/`re` → `openPreparation(...)`.
  (Confirmed earlier: TLC has no prep dialog; the tube selector lives IN the form.)

## 3. Data flow (end to end)

```
FE TlcParamsForm (rxn, target_window, solvents/ratio, 2–4 tubes)
  → confirm('params', values)  → POST /sessions/{id}/forms/confirm
    → BE TLC specialist params-confirm dispatch → _submit_l4 TLC arm
      → CreateTLCTaskRequest{param, objects:[ObjectLocation×2–4]}
        → POST :8192/tasks/  (lab)
          → validate (count, one-row, box exists) — 400 on failure
          → WRITE declared placements into tlc_inventory
          → plan_from_request: sample_tube_ids = chosen, box = chosen box
            → tlc_ops spotting addresses chosen tubes' cells
              → publish start_thin_layer_chromatography → talos.001.cmd
                → mock robot ACK → END → task completed → robot idle
```

## 4. Rule-10 contract impact

- shared-types `CreateTLCTaskRequest` gains a field → **contract change** →
  shared-types is the spec; regen + commit (§2a).
- Lab `POST /tasks/` request shape changes (new `objects`) → reflected via the
  shared-types contract; lab spec `.trellis/spec/BIC-lab-service/...` TLC section
  updated in the `lab` child.
- BE→lab and FE→BE both carry `objects` → update the relevant FE
  (`ui/L3/form.md` note: TLC params has a tube selector, no MaterialPreparation)
  and BE (`backend/L3/specialist_tools.md`) specs in the respective children.

## 5. Risks / tradeoffs

- **New placement-write path in the lab** is the heaviest new surface; must be
  idempotent and transactional (write placement + plan in one transaction, roll
  back together on validation failure).
- **Planner left unchanged** relies on the row-contiguity validation holding; if a
  future need allows scattered tubes, the planner must learn per-tube cell
  addressing (`planner.py:636-685`) — explicitly deferred.
- **shared-types on a feature branch** (not main) — both services pin that branch;
  acceptable per owner decision, but the eventual main reconciliation (post #52
  revert) is tracked separately.
