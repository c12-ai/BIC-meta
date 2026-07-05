# shared-types: TLC ObjectLocation type + objects field

> Child 1 of parent `06-26-06-26-tlc-params-form-ui-dispatch`. **No upstream
> dependency** — this is the bottom of the chain. Children 2–4 (lab, BE, FE)
> depend on the rev this child commits. See the parent `design.md` §1 + §2a for
> the contract; `research/objectlocation-shape.md` for the derivation.

## Goal

Add the `ObjectLocation` contract to BIC-shared-types so a TLC task request can
carry the chemist's 2–4 chosen sample tubes, and wire `CreateTLCTaskRequest` fully
into the contract pipeline (it is currently absent from the schema/example/client
registry).

## Requirements

- **New types** (Model B — declare placement; full address on the wire):
  ```python
  class TubeCell(BaseModel):       # protocol axes (match robot op + _place_tube_into_box)
      row: WellRow                 # A–D for a 2ml box
      col: int = Field(ge=1, le=5) # 1–5 for a 2ml box

  class ObjectLocation(BaseModel):
      tube_id: str = Field(min_length=1)
      box_id: str = Field(min_length=1)
      cell: TubeCell
      object_type: Literal[ObjectType.TUBE_2ML] = ObjectType.TUBE_2ML
  ```
  Place in a new `common/object_location.py` (cross-experiment by design; only
  WIRED into TLC now). `WellRow` from `pipetting_robot_protocol.enums`,
  `ObjectType` from `robot_protocol.skills.tlc_ops`.
- **Un-stub on TLC ONLY** (`experiment_task/http/tlc.py:19-20`):
  `objects: list[ObjectLocation] = Field(min_length=2, max_length=4)`. Leave the
  CC/RE `ObjectLocation` stubs untouched.
- **Register `CreateTLCTaskRequest` into the contract pipeline** — it is missing
  today (no `create-tlc-task.example.json`, not in `export_json_schema.py`,
  unlike CC/RE). Add: schema registry entry, `examples/experiment_task/http/
  create-tlc-task.example.json`, OpenAPI `$ref`, client wrapper + MockTransport
  test, `docs/contract-inventory.md` + `CHANGELOG.md` (per `AGENTS.md`).
- **Docstring fix**: `CreateTLCTaskRequest` doc "由 Apex 拆解为 SkillCommand 后下发"
  → name the actual component (Nexus/lab decomposes the task into SkillCommands;
  the requester does not). Keep it factual and short.
- **Branch/commit**: work on `feat/tlc-skill-protocol`; commit there. No main
  rebase (owner decision — main reverted the TLC op protocol this branch depends
  on). Record the resulting rev for children 2–4 to re-pin.

## Constraints

- Contract repo: Pydantic models are the only handwritten source; `schemas/`,
  `ts/enums.ts`, OpenAPI, clients are DERIVED — never hand-edit generated files.
- This is a contract change (Rule 10): the shared-types models ARE the spec.

## Acceptance Criteria

- [ ] `ObjectLocation` + `TubeCell` defined in `common/object_location.py`, exported in `__init__`.
- [ ] `CreateTLCTaskRequest.objects: list[ObjectLocation]` (len 2–4); CC/RE stubs untouched.
- [ ] `from bic_shared_types.experiment_task.http.tlc import CreateTLCTaskRequest, ObjectLocation` imports cleanly.
- [ ] `create-tlc-task.example.json` exists with a valid 2–4-tube example; CreateTLCTaskRequest in the schema + client registries.
- [ ] Docstring corrected (no misleading "Apex 拆解" claim).
- [ ] Full gate green: `ruff check`, `ruff format --check`, `validate_contracts.py`,
      `export_json_schema.py --check`, `validate_examples.py`, `export_ts_enums.py --check`, `pytest`.
- [ ] Committed on `feat/tlc-skill-protocol`; rev noted in this task's notes for downstream re-pin.

## Out of scope

- CC/RE `objects` adoption (their stubs stay).
- Any lab/BE/FE consumption of the field (children 2–4).

## Notes

- Committed on `feat/tlc-skill-protocol`.
- rev for downstream re-pin: 72f4882dca1e581bfcedc87cc62c0f3dd15388a9
- Surprise vs plan: there was NO per-type `create-cc-task.schema.json` /
  schema-registry entry to mirror — CC/RE reach the schema only via the
  `CreateTaskRequest` union, which previously EXCLUDED TLC ("intentionally out
  of scope", 1.1.6a1). Full pipeline wiring therefore required adding
  `CreateTLCTaskRequest` to the union; that single edit pulls TLC into the
  exported `create-task.schema.json`, the `POST /tasks/` OpenAPI `$ref`, and the
  typed `LabClient.submit_task` (no separate per-type schema/wrapper exists).
  The OpenAPI uses one union `$ref` (no `oneOf`/discriminator listing TLC in the
  yaml — the discriminator lives in the generated schema). Not pushed.
