# Design — shared precondition chain for create + dry-run

## Shape

One new method on `CommandValidator` (BIC-lab-service `app/services/command_validator.py`):

```python
async def validate_task_preconditions(self, task_type: TaskType, params: dict) -> ValidationResult:
    """The FULL create-side precondition chain, shared by create_task and the dry-run.

    Order (identical to today's create_task, short-circuit on first failure):
      1. per-type param check — RE / FP / TLC (TLC = solvents + tube placement + prep occupancy)
      2. material readiness — validate_task_materials
    """
```

- Runs the per-type branch exactly as `TaskService.create_task` does today
  (task_service.py:104-120), then `validate_task_materials`, returning the FIRST failing
  `ValidationResult` (short-circuit) — preserving today's 400 messages and the
  "missing_materials only populated when the materials step is reached" behavior.
- `ValidationResult` already carries `errors` / `warnings` / `missing_materials` /
  `robot_busy` — no schema work needed on the result type.

## Callers

1. **`TaskService.create_task`** — replace its inline per-type + materials block with one call;
   on `not result.valid` raise `validation_failed_error(result.errors, result.warnings,
   missing_materials=...)` exactly as today. `TASK_STEPS` unknown-type `KeyError` stays where
   it is (before the chain).
2. **`POST /preparations/validate`** (`app/api/routers/preparations.py:150`) — call the shared
   method instead of `validate_task_materials`; map the `ValidationResult` onto the response.
   Still zero writes (all chain members are read-only queries).

## Contract change (FE ↔ Lab)

`ValidatePreparationResponse` (`app/data/schemas/preparation.py:463`) gains:

```python
errors: list[str] = []   # blocking, human-readable; valid=false whenever non-empty
```

Additive only. FE mirror in `BIC-agent-portal/src/lib/lab-service-client.ts:187`.
Docstring fix: the endpoint docstring / schema docstring currently say "same logic as task
creation" — after this change that becomes true again; reword to name the shared method.

## FE

- `MaterialPreparationPanel.tsx`: render `snapshot.response.errors` as blocking items in the
  same visual slot as `missing_materials` (dispatch already gated on `valid`).
- `tlc-params-draft.ts` `tubeSelectionProblem`: add `cols[0] !== 1` →
  `'Sample tubes must start at column 1.'` (mirrors command_validator rule (3)).

## Spec (Rule 10)

No existing spec doc mentions `/preparations/validate`. Add the contract to
`.trellis/spec/BIC-lab-service/backend/` (new `preparations-readiness.md` or the closest
existing doc — decide when writing; index it) covering: request/response shape, the
same-chain-as-create guarantee, additive-`errors` rationale.

## Rejected alternatives

- **Duplicating the per-type calls in the router** — that's the drift that caused this bug.
- **Reusing `warnings` for blocking reasons** — lies about severity; FE gates on `valid` but
  users read `warnings` as non-blocking.
- **Making create_task call the dry-run endpoint logic via HTTP** — pointless indirection,
  same process.

## Risk

Low. create_task path is a pure extract-method refactor (same order, same exceptions);
dry-run gets strictly more checks (fail-closed direction); response change is additive.
