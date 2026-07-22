# Child 1 — 4-repo APP_ENV gating + stage env files

Parent: `07-17-07-17-env-staging-app-env`. Read the parent `prd.md` + `design.md` first.

## Goal

Give each of the 4 service repos three stage env files (`local`/`dev`/`prod`) and make each
service's startup REQUIRE a valid `APP_ENV` (fail-if-unset, no default). `local` reproduces
today's working bench config; `dev`/`prod` are placeholder scaffolds.

## Scope

`BIC-agent-service`, `BIC-lab-service`, `BIC-agent-portal`, `mars_interface_mock`.
Excludes the test harness (Child 2) and the BIC-meta orchestrator (Child 3).

## Requirements

1. **Stage resolver, fail-if-unset.** Each Python service resolves `APP_ENV ∈ {local,dev,prod}`
   at startup and hard-exits (non-zero, clear stderr message) if unset or invalid, BEFORE
   loading config. Portal applies the same rule via Vite mode / `resolveAppStage()`.
2. **Stage → file.** `APP_ENV=<stage>` loads `.env.<stage>` (Python) / Vite `--mode <stage>`
   (portal). Plain `.env` is no longer the normal load target.
3. **`local` = today verbatim.** Starting with `APP_ENV=local` yields the exact current bench
   behavior (AWS S3 `aichemengine-release-bundles`/`cn-northwest-1`, AWS ChemEngine
   `52.83.119.132:8003`, local PG/Redis/MQ/MinIO, Keycloak `:18080`, current ports).
4. **`dev`/`prod` scaffolded, not invented.** Same keys as `local`, values `__FILL_ME__` /
   commented guidance. No fabricated endpoints or secrets.
5. **Committed as templates.** Commit `.env.local.example` / `.env.dev.example` /
   `.env.prod.example` (secrets scrubbed to `__FILL_ME__`); real `.env.<stage>` stay
   gitignored. Update each `.gitignore` allow-list.
6. **`APP_ENV` never in a stage file.** The selector lives only in the launch environment.

## Acceptance Criteria

- All 4 repos have `.env.local`/`.env.dev`/`.env.prod` (real, gitignored) and their
  `.example` templates (committed).
- For each of the 4 services, started from its own repo: `APP_ENV` unset → non-zero exit +
  message naming `local|dev|prod`; invalid `APP_ENV=staging` → same.
- `APP_ENV=local` boot reproduces today: agent BE health 200, a live ChemEngine
  material-parse call succeeds, an AWS S3 presign succeeds, lab `:8192` health 200, portal
  loads, mock connects to MQ and uploads to AWS S3.
- `APP_ENV=dev`/`prod` load their file and never silently fall back to `local` or plain
  `.env`.
- No `.env.<stage>` file contains `APP_ENV=`.
- `BIC-shared-types` and `BIC-chem-service` untouched.

## Ordering

This child is the foundation; Children 2 and 3 depend on the resolver + stage files landing
here first. No dependency on 2 or 3.
