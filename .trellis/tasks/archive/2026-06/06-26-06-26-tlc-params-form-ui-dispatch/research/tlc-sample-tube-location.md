# Research: Does TLC require a chemist-specified sample tube location? (3-layer truth)

- **Query**: Drake says "user needs to specify sample tube location" for TLC. Earlier research claimed TLC `lab_logistics` is empty and `CreateTLCTaskRequest` carries only solvents+ratio. Resolve the contradiction end-to-end.
- **Scope**: mixed (lab-service + agent-service + shared-types contract)
- **Date**: 2026-06-26

## VERDICT — **(A)** The lab AUTO-ALLOCATES the sample tube. No chemist input needed. The FE TLC form needs NO tube-location field and NO MaterialPreparation arm. Drake's mental model is ahead of (or predates) the current contract; the wire has no field to carry a tube location even if the FE collected one.

If a chemist-chosen sample tube is genuinely desired, that is verdict **(C)** territory — a multi-layer contract change (shared-types `CreateTLCTaskRequest` + lab `plan_from_request` + agent BE `TLCParamsForm`/`_submit_l4` + FE) — NOT an FE-only fix, and NOT what today's code supports. The shared-types file literally carries a `# TODO ... 暂不实现` (not yet implemented) comment for the object-location concept. See "If Drake still wants chemist control" below.

The earlier research (`tlc-params-gap.md`, `contract-spec-and-objective-bug.md`) was **CORRECT**: `TLCLabLogistics` is empty, `CreateTLCTaskRequest` carries only `{task_id, param: TLCParam}`, and `TLCParam` is `{solvents, solvent_ratio}` only. This investigation independently re-verified each claim against the installed runtime code and adds the Layer-1 lab evidence the earlier research did not cover.

---

## Layer 1 — Lab service: what does it ACTUALLY need to fire a TLC experiment?

**Bottom line: NO chemist-specified sample tube location. The lab auto-allocates the sample tube box + sources the tube id from the box's seeded contents (with a synthetic fallback). The chemist never chooses a slot or tube.**

### The dispatch entry point sources the tube id from the ALLOCATED box, not the request

`BIC-lab-service/app/tlc/service.py:159-211` (`plan_from_request`) — the task-path entry called when a `CreateTLCTaskRequest` arrives:

```python
async def plan_from_request(self, req: CreateTLCTaskRequest) -> TLCPlan:
    allocator = TLCAllocator(self.inventory)
    allocations = await self.allocate_round_materials(allocator)   # <-- allocator picks the box

    n_solvents = len(req.param.solvents)
    box50 = allocations["tube_box_50ml"]
    box2 = allocations["tube_box_2ml"]
    solvent_tube_ids = await self._tube_ids(box50.object_id, count=n_solvents)
    sample_tube_ids = await self._tube_ids(box2.object_id, count=1)   # <-- sample tube id is DERIVED
```

The docstring (`:159-166`) is explicit: *"The thin request carries only the solvent system + ratio, so this allocates the round's tracked instances + tip boxes, **sources the solvent / sample tube ids from the allocated boxes' contents**."* The request (`req`) is read ONLY for `req.param.solvents` and `req.param.solvent_ratio`. Nothing tube-location-shaped is read from the request because there is no such field (see Layer-1 contract below).

### The allocator is allocator-driven, NOT chemist-driven

`BIC-lab-service/app/tlc/allocate.py:93-103` (`allocate_tracked`):

```python
async def allocate_tracked(self, object_type: ObjectType, slot_kind: LocationKind) -> Allocation:
    instance = await self._first_available(object_type)   # deterministic: first non-disposed by id
    if instance is None:
        raise ValueError(f"no available {object_type.value} instance in tlc_inventory")
    slot = await self._pick_free_slot(slot_kind)
    return Allocation(object_type=object_type, object_id=instance.id, slot=slot, tracked=True)
```

`_first_available` (`allocate.py:144-153`) is `SELECT ... WHERE object_type = :t AND state != 'disposed' ORDER BY id LIMIT 1`. The box, the slot, and (downstream) the tube are all chosen by the allocator from seeded inventory. There is no parameter, hook, or branch that lets a request name a specific box, slot, or tube.

### The `_tube_ids` synthetic fallback — what it really means for a real run

`BIC-lab-service/app/tlc/service.py:235-246`:

```python
async def _tube_ids(self, box_id: str, *, count: int) -> list[str]:
    """The first ``count`` tube ids inside ``box_id``, ordered deterministically by id.
    ... Until the round's tube inventory is seeded (Step 6), a box may hold no tubes;
    this falls back to deterministic synthetic ids derived from the box id ...
    """
    tubes = sorted(t.id for t in await self.inventory.contents(box_id))
    if len(tubes) >= count:
        return tubes[:count]
    synthetic = [f"{box_id}_tube_{i + 1:02d}" for i in range(count - len(tubes))]
    return tubes + synthetic
```

Interpretation: `inventory.contents(box_id)` (`inventory.py:76-80`) returns the box's children via `parent_object_id`. **The tube inventory IS now seeded** (see seed evidence below) — so for a real run against seeded data, `_tube_ids(box2, count=1)` returns the FIRST real seeded sample tube (`tube_2ml_001`), NOT a synthetic id. The synthetic fallback only fires if the box has no seeded tubes, which is not the case after the current seed. Either way, the id is derived from the allocated box; it is never supplied by the chemist.

### The sample tube IS seeded as real inventory (the lab auto-allocates from it)

`BIC-lab-service/app/data/seed.py:428-434`:

```python
# 2ml sample tube box at slot 1, with 5 sample tubes in column A (rows 1..5).
("tube_box_2ml_001", "tube_box_2ml", "tlc_tube_box_2ml_slot_1", None, None, None),
("tube_2ml_001", "tube_2ml", None, "tube_box_2ml_001", "A", 1),
("tube_2ml_002", "tube_2ml", None, "tube_box_2ml_001", "A", 2),
("tube_2ml_003", "tube_2ml", None, "tube_box_2ml_001", "A", 3),
("tube_2ml_004", "tube_2ml", None, "tube_box_2ml_001", "A", 4),
("tube_2ml_005", "tube_2ml", None, "tube_box_2ml_001", "A", 5),
```

So `_first_available(TUBE_BOX_2ML)` → `tube_box_2ml_001` (placed at `tlc_tube_box_2ml_slot_1`), and `_tube_ids(box2, count=1)` → `tube_2ml_001`. Fully allocator/seed-driven.

### The TLC slot locations (commit 5a09bcc) are allocator targets, not chemist choices

`seed.py:375-384` (`_TLC_SLOT_INDEXED`) seeds indexed slot rows: `tlc_tube_box_2ml` ×3, `tlc_tube_box_50ml` ×3, `tlc_tip_box` ×3, `tlc_developing_tank` ×3, `tlc_silica_plate` ×4, etc.; plus `_TLC_SLOT_FIXED` (`:363-371`) and `_TLC_SLOT_EXPLICIT` (`:388-393`). These are the deck slots `PlacementPolicy.pick_free_slot` chooses among (`allocate.py:155-166`). The slot is picked by occupancy (row existence), not by the chemist. There is **no notion anywhere of the chemist choosing a slot/tube** — `_pick_free_slot` takes only `slot_kind` + current occupancy.

### Readiness gate confirms tube is treated as auto-managed inventory

`seed.py:282` material rule: `("thin_layer_chromatography", "sample_tube", "Sample Tube", "manual_slot", 1, 2, 2, "tlc_inventory")`. The sample tube is a readiness-counted `tlc_inventory` material (min/target/max), surfaced on the maintenance page (`inventory.py:82-98` `available_of_type`). It is lab stock the allocator draws from — not a per-task chemist input.

### Layer-1 contract: the wire request has NO tube-location field

`bic_shared_types/experiment_task/http/tlc.py` (installed in lab venv, **diff-identical to the `BIC-shared-types` source repo**):

```python
class CreateTLCTaskRequest(CreateTaskRequestBase):
    task_type: Literal[TaskType.THIN_LAYER_CHROMATOGRAPHY] = TaskType.THIN_LAYER_CHROMATOGRAPHY
    param: TLCParam
    # TODO: ObjectLocation 数据结构与流程待设计，暂不实现
    # objects: list[ObjectLocation]
```

`TLCParam` (`bic_shared_types/common/tlc.py:27-38`): `solvents: list[Solvent]` + `solvent_ratio: list[PositiveInt]` only. `CreateTaskRequestBase` carries `task_id` + `task_type`. **There is definitively no sample-tube-location / tube-id / box-location field in the TLC request contract.** The commented-out `objects: list[ObjectLocation]` is the design placeholder for exactly this concept — and `ObjectLocation` does not exist anywhere in `BIC-shared-types` (grep returned nothing). It is explicitly "暂不实现" (not yet implemented).

> Version note: lab venv ships `bic_shared_types==1.1.6a1`, agent venv `1.1.6a2`. The `CreateTLCTaskRequest` + `TLCParam` definitions are byte-identical across both and the source repo (verified by `diff`), so the version skew does not affect this contract.

**Layer 1 answer: To fire a real TLC task, does the lab need a chemist-specified sample tube location? NO.** The sample tube box is auto-allocated by `TLCAllocator._first_available(TUBE_BOX_2ML)` from seeded inventory; the tube id is derived via `_tube_ids` from the box's seeded contents (`tube_2ml_001`), with a synthetic-id fallback only if no tubes are seeded. The request contract has no field to carry a tube location.

---

## Layer 2 — Agent BE: what does the TLC params form payload contain?

**Bottom line: there is NO field in the agent BE's TLC form or dispatch path to carry a sample tube location. `TLCLabLogistics` is empty. `_submit_l4` builds `CreateTLCTaskRequest(task_id, param=recommended)` only. Even if the FE collected a tube location, it would have nowhere to go — this is the CONTRACT GAP.**

### `TLCLabLogistics` — empty (vs `CCLabLogistics` which has `sample_cartridge_location`)

`BIC-agent-service/app/events/form_payloads.py:294-304`:

```python
class TLCLabLogistics(BaseModel):
    """TLC lab-only logistics — never sent to Mind.
    ``CreateTLCTaskRequest`` carries only ``param: TLCParam`` (plus the base
    ``task_id``); there are no cartridge / flask logistics for a TLC plate task.
    This empty-but-present model preserves the three-sub-model shape parity ...
    """
    model_config = ConfigDict(extra="forbid")
    # (NO fields)
```

Contrast — `CCLabLogistics` (`form_payloads.py:116-128`) DOES have the analogous field:

```python
class CCLabLogistics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_cartridge_location: CCSampleCartridgeLocation | None = Field(
        default=None, description="Sample cartridge location for the CC robot task.")
```

So CC has a per-task chemist-routed location (`sample_cartridge_location`); **TLC has nothing analogous.** This is the precise field Drake's "sample tube location" would map to — and it is absent on the TLC side, by design (`extra="forbid"` means you can't even smuggle one in).

### `TLCFromUserFields` — only `rxn` + `target_window` are chemist inputs

`form_payloads.py:255-291`: `rxn`, `target_window` (chemist), plus the recognition carry trio `tlc_file_key` / `tlc_result` / `product_rf` (written by the Phase-4 retry loop, not the form). No tube/location field.

### `TLCParamsForm` — three sub-models, none carry a tube location

`form_payloads.py:327-343`: `from_user: TLCFromUserFields`, `recommended: TLCParam | None`, `lab_logistics: TLCLabLogistics` (empty). `extra="forbid"` everywhere.

### `update_tlc_params` tool — chemist/agent can only write `from_user` + (empty) `lab_logistics`

`TLCParamsUpdate` (`form_payloads.py:307-324`): `from_user: TLCFromUserFields | None` + `lab_logistics: TLCLabLogistics | None` (empty). The tool signature `def update_tlc_params(fields: TLCParamsUpdate, ...)` (`specialists/tools.py`) accepts nothing tube-shaped. There is **no** `recommended` member (only Mind writes that), and no tube/slot member at all.

### `_submit_l4` TLC arm — dispatches `recommended` only

`BIC-agent-service/app/runtime/graphs/specialists/tools.py:543-559`:

```python
elif state.specialist_kind == "tlc":
    # TLC has NO lab-logistics (CreateTLCTaskRequest needs only task_id + param),
    # so the dispatch gate is completeness alone — no cartridge / flask check.
    tlc_form = TLCParamsForm.model_validate(draft)
    tlc_problems = tlc_params_form_problems(tlc_form)
    if tlc_problems or tlc_form.recommended is None:
        raise RuntimeError(...)
    task_request = CreateTLCTaskRequest(
        task_id=task_uuid,
        param=tlc_form.recommended,    # ONLY the solvent system + ratio
    )
```

Compare the CC arm (`tools.py:~510-521`) which passes `sample_cartridge_location=cartridge`, and the RE arm (`:522-542`) which passes `flasks` + `collect_config`. The TLC arm passes **only `param`** — there is no parameter slot for a tube location, and `CreateTLCTaskRequest` has no field to accept one.

### TLC specialist (`tlc.py`) never touches tube location

Grep for `tube` / `location` / `sample_cartridge` / `lab_logistics` across `specialists/tlc.py` returned **nothing**. `recommend_tlc_params` builds the Mind request from `rxn` + `target_window` (`tlc.py:293-294`); the eval loop uses `target_window` + `product_rf`. No tube-location handling exists. (The only `tube_id` in the whole BE — `form_payloads.py:799` `TubeReportRow.tube_id` — is a CC/RE per-tube ANALYSIS report row, unrelated to TLC dispatch.)

**Layer 2 answer: Is there a field in the agent BE's TLC form/dispatch path to carry a sample tube location to the lab? NO.** `TLCLabLogistics` is empty; `_submit_l4` sends only `param`. If the FE collected a tube location, it would have nowhere to go — **CONTRACT GAP**.

---

## Layer 3 — Reconcile

### Is Drake's statement supported by the current contract?

**No.** "User needs to specify sample tube location" is NOT supported anywhere in the live contract:
- Lab: auto-allocates the tube box + derives the tube id; no request field reads a tube location (`service.py:159-211`, contract `CreateTLCTaskRequest` has no such field).
- Agent BE: `TLCLabLogistics` empty, `_submit_l4` sends `param` only, no tool input for tube location.
- Shared-types: the `objects: list[ObjectLocation]` field that would carry it is commented out / "暂不实现", and `ObjectLocation` doesn't exist.

### Which verdict the evidence supports: **(A)**

- **(A) ✅** Lab auto-allocates the sample tube; no chemist input needed; the FE form needs NO tube-location field; Drake's mental model predates / is ahead of the current auto-allocation contract. **(FE-only task, bypass MaterialPreparation.)** — THIS ONE.
- (B) ❌ Rejected — there is NO existing field anywhere (lab request, BE `TLCLabLogistics`, shared-types) for a chemist tube-location override. `extra="forbid"` on every TLC model rules out an overlooked field. We did not "miss" a field; it genuinely does not exist.
- (C) — Only applies IF Drake insists on chemist control. Then it is a real multi-layer contract change (see below), not the current state.

### What the FE TLC form must collect (verdict A)

| FE collects | Wire field that carries it | Layer-below change? |
|---|---|---|
| `from_user.rxn` (reaction SMILES) | → `TLCMixcaseRequest.rxn` (Mind recommend only; not dispatched) | None |
| `from_user.target_window` (lo, hi Rf) | → `TLCMixcaseRequest.target_window` (Mind recommend only) | None |
| `recommended.solvents` + `recommended.solvent_ratio` (editable Mind output) | → `CreateTLCTaskRequest.param` (the ONLY thing dispatched to the lab) | None |
| ~~sample tube location~~ | **NONE — do not add a field** | None |

`lab_logistics` is `{}`. **No layer below the FE changes.** TLC Confirm calls `confirm('params', values)` directly — skip `MaterialPreparationPanel` (there's no TLC logistics and no TLC prep executor). This matches the earlier research's Implementation shape (`contract-spec-and-objective-bug.md` §Implementation shape).

### If Drake still wants chemist-chosen sample tube location → this is verdict (C), a bigger task

This would be a Rule-10 multi-layer contract change, NOT part of the FE TLC params form task:
1. **shared-types**: define `ObjectLocation` (or a `sample_tube_location` field) and add it to `CreateTLCTaskRequest` (uncomment/implement the TODO at `experiment_task/http/tlc.py:19-20`). Bump version, propagate to both venvs.
2. **lab `plan_from_request`** (`service.py:159-211`): read the supplied tube location instead of (or as an override to) `_first_available` + `_tube_ids`; validate it against seeded `tlc_inventory`.
3. **agent BE**: add the field to `TLCLabLogistics` (mirroring `CCLabLogistics.sample_cartridge_location`), wire it through `_submit_l4` into `CreateTLCTaskRequest`, and expose it in `update_tlc_params` / `TLCParamsUpdate`.
4. **FE**: add the select to the TLC form + (likely) a MaterialPreparation arm.

Recommend confirming with Drake which world he wants before any FE work begins: ship **(A)** now (matches all current code), or scope **(C)** as a separate multi-layer task.

## Caveats

- Did not run a live dispatch to observe the actual tube id used; the conclusion is from static code + seed data, which is unambiguous (`plan_from_request` reads only `req.param`; the tube id is derived from the allocated box).
- The lab↔agent shared-types version skew (`1.1.6a1` vs `1.1.6a2`) does not affect the TLC contract (definitions diff-identical), but a future bump touching `CreateTLCTaskRequest` would need both venvs re-synced.
- Whether Drake's "specify sample tube location" refers to a future requirement vs the current build is a product question — flag to Drake. The code truth (verdict A) is certain.
