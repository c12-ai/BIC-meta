# Child 2 — Test harness obeys APP_ENV fail-if-unset

Parent: `07-17-07-17-env-staging-app-env`. Read the parent + Child 1 first.

## Goal

Make the test suites obey the SAME universal rule (product-owner ruling: the rule is
universal — app AND tests). Running tests with no `APP_ENV` FAILS by design; to run tests the
operator sets `APP_ENV` explicitly. There is NO conftest auto-bypass that papers over the gate.

## Context

Child 1 puts the `APP_ENV` hard-exit in `app.core.config` import. `BIC-agent-service`
`tests/conftest.py:58` imports `app.main` → triggers the gate. `tests/fixtures/clients.py`
and `scripts/chat.py` already `load_dotenv(".env.test", override=True)` before app import.
`BIC-lab-service` tests likewise import app config.

## Requirements

1. **Tests obey fail-if-unset.** `uv run pytest` with no `APP_ENV` set exits non-zero at
   collection/import with the same clear message — not a confusing import traceback. This is
   the intended behavior, not a bug to hide.
2. **Explicit stage runs tests.** `APP_ENV=local uv run pytest` (and lab equivalent) collects
   and runs. `.env.test` still provides test-specific overrides via
   `load_dotenv(override=True)` layered over `.env.local`; test DB/infra targets are unchanged.
3. **Message quality.** The failure message tells the operator to set `APP_ENV` — the
   resolver's stderr line is enough; no silent exit(2) with no explanation during pytest.
4. **`.env.test` stays a test override, not a stage.** It is not added to the `local|dev|prod`
   set. Whether `APP_ENV=test`→`.env.test` becomes a first-class value is out of scope
   (product owner chose the 3-stage set); `.env.test` remains layered on top of a real stage.
5. **CI parity.** Any CI job that runs pytest must set `APP_ENV` (the CI mirror). Update the
   CI workflow / Makefile test targets so `make test` sets `APP_ENV=local` explicitly (visible,
   not hidden) — the rule is enforced, and the documented way to run tests carries the stage.

## Acceptance Criteria

- `uv run pytest` (no `APP_ENV`) in agent-service and lab-service exits non-zero with the
  resolver's stage message.
- `APP_ENV=local uv run pytest` runs green in both repos (same coverage as before this task).
- `make test` (or the documented test entrypoint) sets `APP_ENV` explicitly and is green.
- No conftest/fixture silently sets a default stage to bypass the gate.

## Ordering

Depends on Child 1 (the resolver must exist). Independent of Child 3.
