# agent-BE: forward chemist sample-tube selections to the lab

> Child 3 of parent `06-26-06-26-tlc-params-form-ui-dispatch`.
> **Depends on child 1** (shared-types `ObjectLocation`) rev
> `398e8f4` on `feat/tlc-skill-protocol`, and conceptually on child 2 (lab now
> accepts `objects`). Re-pin to `398e8f4` before coding.
> See parent `design.md` §2c.

## Goal

Carry the chemist's 2–4 selected sample tubes (`ObjectLocation`) through the TLC
params form and forward them on dispatch, so `CreateTLCTaskRequest.objects` reaches
the lab. Today `_submit_l4`'s TLC arm builds `CreateTLCTaskRequest(task_id, param)`
only — `objects` is dropped because the form has nowhere to hold the tubes.

## Requirements

- **Re-pin** `pyproject.toml` `bic-shared-types` to rev `398e8f4` (dev-local
  `file://` pin, mirroring child 2 — the GitHub branch is not pushed). Current
  pin is `v1.1.6a2` (no `ObjectLocation`). `uv sync`; confirm
  `from bic_shared_types.common.object_location import ObjectLocation` resolves.
- **`TLCLabLogistics` carries the tubes** (`app/events/form_payloads.py:294`):
  add `sample_tubes: list[ObjectLocation]` (the chemist's 2–4 selections). Update
  the now-stale "empty / no lab logistics for TLC" docstrings on
  `TLCLabLogistics` and `TLCParamsUpdate.lab_logistics`. (The 2–4 bound is the
  wire contract on `CreateTLCTaskRequest.objects`; the form field can hold 0..n
  as a draft and the dispatch gate enforces 2–4 — mirror how CC/RE gate logistics.)
- **`_submit_l4` TLC arm forwards them** (`app/runtime/graphs/specialists/tools.py:~542`):
  `CreateTLCTaskRequest(task_id=…, param=tlc_form.recommended, objects=tlc_form.lab_logistics.sample_tubes)`.
- **Dispatch gate** (`tlc_params_form_problems` / `_from_values`,
  `form_payloads.py:543,564`): add a problem when `sample_tubes` count is not
  2–4 (so an incomplete tube selection blocks dispatch with a clear message,
  same shape as CC/RE logistics gating).
- **Drop the local TLC widen** in `app/infrastructure/lab_client.py` if it still
  locally widens the dispatch union for TLC — now that shared-types carries
  `objects`, TLC dispatch uses the shared `CreateTLCTaskRequest` (AC1). Verify
  whether the widen is still needed for anything else before removing.
- **Spec update (Rule 10)**: `backend/L3/specialist_tools.md` — TLC dispatch now
  carries `objects`; the TLC form's `lab_logistics.sample_tubes`.

## Constraints

- Agent conventions: match existing CC/RE patterns (Rule 8) — the tube
  selections are the TLC analog of CC's `sample_cartridge_location` logistics.
- FE (child 4) is the contract authority for the form's field NAMES — pick a
  clear name (`sample_tubes`) and child 4 mirrors it.

## Acceptance Criteria

- [ ] Re-pinned to `398e8f4`; `ObjectLocation` importable in the agent venv.
- [ ] `TLCLabLogistics.sample_tubes: list[ObjectLocation]` added; stale "empty
      logistics" docstrings corrected.
- [ ] `_submit_l4` TLC arm passes `objects=` into `CreateTLCTaskRequest`.
- [ ] Dispatch gate blocks when tube count ∉ [2,4] with a clear problem string.
- [ ] Local TLC widen removed (or its continued need documented).
- [ ] Gate green: ruff, pyright, and the TLC scenario/scripts that exercise
      dispatch (e.g. scripts under `BIC-agent-service/scripts`, plus any unit
      tests for `_submit_l4` / form payloads).
- [ ] `specialist_tools.md` spec updated.

## Out of scope

- shared-types (child 1) / lab (child 2).
- The FE form + tube selector UI (child 4).
- Mind recommendation logic (solvents/ratio) — unchanged.
