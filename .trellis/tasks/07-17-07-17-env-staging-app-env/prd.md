# Per-repo env staging (local/dev/prod) with APP_ENV fail-if-unset

## Problem / Goal

Each BIC service repo loads a single hardcoded `.env` today. There is no notion of a
deployment stage, and a service can start with whatever `.env` happens to be on disk. The
product owner wants explicit, per-repo staging: every service repo carries `local`, `dev`,
and `prod` env files, and starting a service from **its own repo** must **require** the
operator to pick a stage — there is no default, and an unset/invalid stage is a hard failure.

Goal: make the run-time stage an explicit, unmissable decision per service, backed by
stage-specific env files, without changing any product behavior.

## Scope

Four service repos, each of which has a runtime process:

- `BIC-agent-service` (FastAPI, pydantic-settings, `env_file=".env"`)
- `BIC-lab-service` (FastAPI, pydantic-settings, `env_file=".env"`)
- `BIC-agent-portal` (Vite; already has a `STAGE` concept in `src/lib/env.ts`)
- `mars_interface_mock` (asyncio MQ mock; plain `os.environ.get` with defaults)

Explicitly OUT of scope:

- `BIC-chem-service` — excluded by the product owner.
- `BIC-shared-types` — a pure types package, no runtime process, no env. Nothing to stage.

## Requirements

1. **Three stage env files per repo.** Each in-scope repo has `.env.local`, `.env.dev`,
   and `.env.prod` (portal uses Vite's `.env.<mode>` convention, same three modes).

2. **Stage selector is `APP_ENV`, fail-if-unset.** At startup each service reads a stage
   selector (`APP_ENV` for the Python services; the equivalent Vite `--mode` / `STAGE` for
   the portal). The value must be one of `local | dev | prod`. If it is unset or not one of
   those three, the service **exits non-zero with a clear error** before loading any config.
   There is NO default stage.

3. **`APP_ENV` is never stored in a stage env file.** The selector lives only in the launch
   command / process environment (inline `APP_ENV=local ...`, container `environment:`, k8s
   `env:`, systemd `Environment=`). Storing it in a `.env.<stage>` file would reintroduce a
   default and is prohibited.

4. **Stage selects which env file loads.** `APP_ENV=<stage>` causes the service to load
   `.env.<stage>` (and only that file) for its configuration. The old single `.env` is no
   longer the load target for a normal start.

5. **`local` captures today's working bench config verbatim.** The `local` stage reproduces
   the configuration the bench runs on now: AWS S3 (`aichemengine-release-bundles`,
   `cn-northwest-1`), AWS ChemEngine (`52.83.119.132:8003`), local Postgres / Redis /
   RabbitMQ / MinIO, Keycloak `:18080`, current ports. Starting with `APP_ENV=local` must
   yield the exact behavior the bench has today.

6. **`dev` and `prod` are scaffolded, not invented.** Their env files carry the same KEYS as
   `local` with clearly-marked placeholder values (`__FILL_ME__` / commented guidance). No
   real dev/prod endpoints or secrets are fabricated. The product owner fills them later.

7. **Started from each repo, not from BIC-meta.** The stage-gated start path must work when
   the operator runs the service from within its own repo directory (the existing per-repo
   `make dev` / start command), independent of the BIC-meta `make up` orchestrator.

8. **No product behavior change.** This is a configuration-loading and startup-gating change
   only. No API, workflow, or data behavior changes.

## Acceptance Criteria

- In each of the 4 repos, `.env.local`, `.env.dev`, `.env.prod` exist.
- Starting a service with `APP_ENV` unset fails fast with a non-zero exit and a message
  naming the required values — for all 4 services, from their own repo.
- Starting with an invalid `APP_ENV` (e.g. `staging`) fails the same way.
- Starting with `APP_ENV=local` loads `.env.local` and the bench behaves exactly as it does
  today (AWS S3 + AWS ChemEngine + local infra; a live ChemEngine material-parse call and an
  AWS S3 presign both still succeed).
- `APP_ENV=dev` / `APP_ENV=prod` load their respective files; with placeholder values the
  service either starts (if placeholders are syntactically valid) or fails loudly on the
  placeholder — never silently falls back to `local` or to the old `.env`.
- No `.env.<stage>` file contains an `APP_ENV` assignment.
- Secrets in `dev`/`prod` files are placeholders only; no fabricated credentials.
- `BIC-shared-types` and `BIC-chem-service` are untouched.

## Task Map (parent owns requirements; children are independently verifiable)

1. **`07-17-env-staging-repos`** — 4-repo APP_ENV gating + stage env files + `.example`
   templates. The foundation.
2. **`07-17-env-staging-tests`** — test harness obeys the universal fail-if-unset rule
   (no APP_ENV → pytest fails; `APP_ENV=local uv run pytest` runs). Depends on child 1.
3. **`07-17-env-staging-orchestrator`** — BIC-meta `make up` + `scripts/bic-env/*` +
   lab docker-compose migrate onto `APP_ENV=local` / `.env.local`. Depends on child 1;
   do last.

Ordering (written here, not implied by tree): 1 → (2, 3 in parallel), with 3 landing last so
the orchestrator migrates onto a finished per-repo contract.

## Resolved decisions (from planning)

- Git tracking: commit `.env.<stage>.example` templates (secrets scrubbed); real
  `.env.<stage>` stay gitignored (matches `.env*` ignore + `*.example` allow-list).
- Legacy `.env`: NOT kept as the load target. Legacy readers (`check_services.py` via the
  gated config import; lab docker-compose; `scripts/bic-env/*`) are migrated to
  `APP_ENV` / `.env.<stage>` in child 3.
- Test seam: universal rule — tests obey fail-if-unset too (child 2), no conftest bypass.
- `make up` / orchestrator: patched in the same overall task (child 3), not deferred.
