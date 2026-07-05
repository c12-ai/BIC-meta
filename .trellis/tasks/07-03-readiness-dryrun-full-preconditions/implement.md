# Implementation plan

## Order

### 1. Lab BE — shared chain (BIC-lab-service)
- [ ] Add `CommandValidator.validate_task_preconditions(task_type, params)` — per-type check
      then materials, short-circuit, identical order to today's `create_task`.
- [ ] Refactor `TaskService.create_task` (task_service.py:104-127) to call it; identical
      `validation_failed_error` raise; `KeyError` for unknown type untouched.
- [ ] Point `POST /preparations/validate` at the shared method; extend
      `ValidatePreparationResponse` with `errors: list[str] = []`; fix the now-true
      "same logic as task creation" docstrings.
- [ ] Tests (pytest, alongside existing validator/router tests):
      - occupied silica plate → dry-run `valid=false`, occupancy message in `errors`,
        and `create_task` raises with the SAME message (same-chain proof).
      - bad tube placement (col start ≠ 1) → dry-run `valid=false` + placement error.
      - RE malformed params → dry-run fails like create.
      - happy path → `valid=true, errors=[]`, rest of response unchanged.
      - dry-run writes nothing (no task rows after call).

### 2. Portal FE (BIC-agent-portal)
- [ ] `lab-service-client.ts`: add `errors: string[]` to `ValidatePreparationResponse`.
- [ ] `MaterialPreparationPanel.tsx`: render `errors` as blocking items next to
      `missing_materials`.
- [ ] `tlc-params-draft.ts` `tubeSelectionProblem`: add start-at-column-1 rule; unit test in
      `tlc-params-draft.test.ts` (B2–B4 rejected, A1–A3 accepted).

### 3. Spec (Rule 10)
- [ ] Write `/preparations/validate` contract doc under `.trellis/spec/BIC-lab-service/backend/`
      and add it to that index.md.

## Validation commands (re-run FULL chain after any fix)

- Lab: `cd BIC-lab-service && make ci` (falls back to `uv run ruff check . && uv run pytest -q`
  if no ci target — check Makefile first).
- Portal: `cd BIC-agent-portal && pnpm lint && pnpm test` (unit only; no Playwright needed —
  change is panel-local rendering + pure draft-gate function).
- Live smoke (services already up): occupy the plate via a dispatched TLC, hit
  `curl --noproxy '*' -s -X POST http://127.0.0.1:8192/preparations/validate ...` → expect
  `valid=false` + occupancy error. Reset bench afterwards.

## Rollback

Single commit per repo; revert lab commit restores old create_task inline block (pure
extract-method), portal commit is additive rendering — both revert clean.
