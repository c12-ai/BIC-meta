# Repair RE dispatch after shared-types drops CreateRETaskRequest.flasks

## Goal

RE dispatch and its test/spec still assume the OLD `CreateRETaskRequest` shape (with
`flasks`/`collect_config`). A shared-types bump (bic-shared-types v1.2.0, pulled in by 07-01)
removed those fields, so RE dispatch is broken and one test hard-fails. Reconcile the RE
dispatch path to the new contract.

## Evidence (2026-07-02, surfaced during task 07-02 bench runs)

- `uv run pytest` in BIC-agent-service:
  `tests/unit/test_specialists_tools.py::test_submit_l4_execution_re_payload_carries_flasks_and_collect_config`
  fails: `'CreateRETaskRequest' object has no attribute 'flasks'`.
- pyright on `app/runtime/graphs/specialists/tools.py:538-543` (the RE `_submit_l4` arm):
  2 errors — the code composes `CreateRETaskRequest(param=..., flasks=..., collect_config=...)`
  against a model that no longer has those params.
- Root: the shared-types version bump lives in 07-01's uncommitted `pyproject.toml`/`uv.lock`
  (off-limits during 07-02); this task owns reconciling RE code to it. NOT caused by 07-02.

## Ruling (Drake, 2026-07-03) — FP materializes; RE = evaporation only

Shared-types v1.2.0 moved `flasks`/`collect_config` to the NEW `CreateFPTaskRequest`: the
fixed workflow's FP (Fraction Pool) step becomes a real task type owning fraction collection;
`CreateRETaskRequest` is evaporation-only. Fix: slim the RE dispatch (`_submit_l4` RE arm) to
the new request shape — drop `flasks`/`collect_config` from the RE payload AND from RE's
dispatch-time missing-field gate. KEEP the RE lab_logistics collection path (chemist still
sets flasks/collect_config; the future FP specialist consumes them). FP specialist/dispatch
itself is LATER work, not this task.

## Evidence correction (2026-07-03 PR gate)

The break is in the COMMITTED state of feat/tlc-objectlocation-passthrough (not merely the
dirty tree as first recorded): committed `uv.lock` pins shared-types 99763dc (v1.2.0 line,
no flasks on CreateRETaskRequest) while committed `tools.py` still passes them. Caught by the
raise-pr clean-worktree gate — blocks the agent-service PR.

## Requirements (draft)

- R1: `_submit_l4`'s RE arm composes a VALID `CreateRETaskRequest` per v1.2.0.
- R2: `test_submit_l4_execution_re_payload_carries_flasks_and_collect_config` updated to the
  new contract (or replaced if the concept moved).
- R3: Spec (`specialist_tools.md` RE dispatch rows + any lab-contract doc) reconciled — Rule 10.
- R4: Coordinate with 07-01: the shared-types bump must be committed for this to build; this
  task should land WITH or AFTER 07-01's dependency commit, not before.

## Acceptance Criteria

- [x] R1: RE arm of `_submit_l4` composes `CreateRETaskRequest(task_id=..., param=...)` only
  (evaporation-only per v1.2.0); flasks/collect_config dropped from payload AND dispatch gate.
- [x] R2: test renamed to `test_submit_l4_execution_re_payload_is_evaporation_only`; asserts
  `not hasattr(req, "flasks")` — moved-to-FP contract encoded.
- [x] R3: spec reconciled — `specialist_tools.md` rows 43/49/198 carry the v1.2.0
  evaporation-only ruling with task 07-03 references; RE lab_logistics kept as FP-bound.
- [x] R4: shared-types v1.2.0 pin committed (`pyproject.toml`/`uv.lock` on main).

## Verification (2026-07-03, closing pass)

Shipped in PR #34 squash-merge (`7d2b1ba` on main; pre-squash original `2621690` on
feat/tlc-objectlocation-passthrough — branch now redundant for this task).
Verified on main: `uv run pytest tests/unit/test_specialists_tools.py` → 47 passed;
`uv run pyright app/runtime/graphs/specialists/tools.py` → 0 errors.
