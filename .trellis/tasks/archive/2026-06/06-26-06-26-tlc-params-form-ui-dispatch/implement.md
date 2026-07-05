# Implement — TLC ObjectLocation, parent execution plan

Parent owns ordering + cross-child integration. Each child is independently
verifiable; ordering below is a hard dependency chain (bottom-up), written here
(not implied by tree position) per the workflow guidance.

## Child map + ordering

| # | Child slug | Layer | Depends on | Deliverable |
|---|---|---|---|---|
| 1 | `…-st-objectlocation` | shared-types | — | `ObjectLocation`/`TubeCell` + `objects` on `CreateTLCTaskRequest` (TLC only), docstring fix, contract regen, commit on `feat/tlc-skill-protocol` |
| 2 | `…-lab-tube-placement` | lab-service | 1 | re-pin; request-driven placement write; `plan_from_request` uses chosen tubes; row/count/box validation (400) |
| 3 | `…-be-passthrough` | agent-service | 1, 2 | re-pin; `TLCLabLogistics` carries tubes; `_submit_l4` forwards `objects`; drop local widen |
| 4 | `…-fe-tlc-form` | portal | 3 | `TlcParamsForm` + 2–4 tube selector; un-placeholder TLC stage; confirm→dispatch |

Order is strict: a child cannot start until its deps are committed (each child's
`prd.md` restates its dependency + the exact upstream artifact it consumes).

## Per-child validation gates

### 1 — shared-types
- [ ] `ObjectLocation` + `TubeCell` defined; `objects` un-stubbed on TLC only (CC/RE stubs untouched).
- [ ] contract gate per `BIC-shared-types/AGENTS.md` (schemas/examples/OpenAPI/client regen) passes.
- [ ] package builds; `python -c "from bic_shared_types.experiment_task.http.tlc import CreateTLCTaskRequest, ObjectLocation"` works.
- [ ] commit on `feat/tlc-skill-protocol`; note the rev for downstream re-pin.

### 2 — lab-service
- [ ] `pyproject.toml` re-pinned; `uv sync`; `uv run python -c "import bic_shared_types; ..."` resolves the new field.
- [ ] new placement-write path: a TLC task with `objects` writes tube→box+cell into `tlc_inventory` before planning (idempotent, transactional).
- [ ] `plan_from_request` uses chosen `tube_id`s (ordered by `cell.col`), chosen box; no `_first_available` for the sample box.
- [ ] validation: count≠2–4, non-contiguous row, mixed/unknown box → clean 400, no partial persist (new tests).
- [ ] `ruff check`, `uv run pyright app/`, `uv run pytest` green.

### 3 — agent-service
- [ ] `pyproject.toml` re-pinned; imports resolve.
- [ ] `TLCLabLogistics` carries the 2–4 `ObjectLocation`s; `_submit_l4` TLC arm forwards `objects`.
- [ ] local TLC widen in `lab_client.py` removed (TLC dispatch uses the shared type — AC1).
- [ ] `ruff`/`pyright`/`pytest` (scenario scripts for TLC dispatch) green.

### 4 — portal
- [ ] TLC stage renders `TlcParamsForm` (not placeholder); footer + Confirm present.
- [ ] 2–4 tube selector (tube_id+box_id+cell); presence gate; `coerceTlcParamsForm`.
- [ ] `pnpm check`, `pnpm typecheck` green; targeted Playwright drives chat→Confirm Plan→TLC form→select tubes→Confirm.

## Parent integration gate (AC6 — the E2E the prior run could not assert)

After all 4 children commit, run a UI-driven TLC E2E (via `bic-e2e-runner`):
1. reset both services; robot idle; mock robot alive.
2. drive portal: chat → Confirm Plan → TLC params form → select 2–4 tubes → Confirm.
3. assert: lab task created from the UI action; dispatched `tlc_ops` spotting ops
   reference the **chemist-selected tubes' cells**; task reaches `completed`;
   robot returns idle.

## Rollback points

- Each child commits independently; revert is per-child.
- shared-types change is additive (new optional-at-parse-but-required field on TLC
  request only) — reverting the TLC `objects` line restores the stub.
- The lab placement-write is new code behind the `objects` field; absent `objects`
  the old auto-pick path is NOT removed until child 2's tests confirm the new path
  (keep both until green, then delete the dead sample-tube auto-pick).

## Spec updates (Rule 10 — done within each child, not deferred)

- 1: shared-types IS the contract (the change is the spec).
- 2: lab TLC backend spec — request `objects` + placement-write + validation.
- 3: BE `backend/L3/specialist_tools.md` — TLC dispatch carries `objects`.
- 4: FE `ui/L3/form.md` — TLC params has a tube selector, skips MaterialPreparation.
