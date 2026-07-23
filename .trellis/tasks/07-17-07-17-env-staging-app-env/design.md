# Design — Per-repo env staging with APP_ENV fail-if-unset

## Decisions carried in from planning

- Selector: `APP_ENV ∈ {local, dev, prod}`, **fail-if-unset** (no default). Read from the
  process environment only; never from a `.env.<stage>` file.
- `local` = today's working bench config verbatim (AWS S3, AWS ChemEngine `52.83.119.132:8003`,
  local infra). `dev` / `prod` = same keys, placeholder values, no fabricated secrets.
- Git: commit `.env.<stage>.example` templates (placeholder-only); real `.env.<stage>` stays
  gitignored (matches existing `.env*` ignore + `*.example` allow-list).
- Legacy `.env` readers (`check_services.py`, lab docker-compose) are pointed at the
  `APP_ENV` / `.env.<stage>` path too; plain `.env` stops being the normal load target.

## Shared mechanism: a stage resolver

All three Python services share ONE tiny helper (copied per repo, ~15 lines — the repos do
not share a runtime package, so a shared module would add a cross-repo dependency we don't
want for config bootstrap). The helper:

1. Reads `APP_ENV` from `os.environ`.
2. If missing or not in `{local, dev, prod}` → print a one-line error to stderr and
   `sys.exit(2)` (non-zero, before any config import).
3. Returns `f".env.{stage}"` (validated to exist; missing file → same hard exit with a
   message naming the expected path).

Fail-BEFORE-config-import is essential for the two pydantic services: `Settings()` reads the
env file at construction, so the resolver must run and set the target filename before the
`Settings` class is instantiated.

## Per-repo application

### BIC-agent-service (pydantic-settings)

- `app/core/config.py:21` currently: `SettingsConfigDict(env_file=".env", ...)`.
- Change to resolve the stage file at import: compute `env_file=_resolve_stage_env_file()`
  (the shared helper) instead of the literal `".env"`.
- `_resolve_stage_env_file()` lives in a new `app/core/stage.py` and is called from
  `config.py` at module load. Hard-exit on unset/invalid APP_ENV happens here — so importing
  `app.core.config` with no APP_ENV already fails loud, which covers every entrypoint
  (`app.main`, `check_services.py`, scripts).
- **Test path unaffected:** `tests/fixtures/clients.py` and `scripts/chat.py` explicitly
  `load_dotenv(".env.test")` BEFORE importing `app.*`. They must set `APP_ENV` first (e.g.
  `APP_ENV=local`) OR the stage resolver must treat an already-loaded test env as satisfying
  config. Simplest: those test entrypoints export `APP_ENV=local` before importing app — the
  `.env.test` values already loaded win via `override=True`, and `.env.local` fills the rest.
  Decide the exact test seam in implement; keep `pytest` green as a gate.

### BIC-lab-service (pydantic-settings)

- Identical change to `app/core/config.py:20` (`env_file=".env"` → resolved stage file) via a
  new `app/core/stage.py`.
- **docker-compose**: `docker-compose.yml` and `docker-compose.cloud.yaml` hardcode
  `env_file: .env`. Update these to pass `APP_ENV` into the container `environment:` and set
  `env_file: .env.${APP_ENV}` (compose interpolates `${APP_ENV}` from the shell), so a
  compose start also requires APP_ENV. `docker-compose.standalone.yaml` uses `.env.standalone`
  — that is a separate self-contained profile; leave it unless the product owner wants it
  staged (flag as follow-up, do not silently change).
- `scripts/check_services.py` imports `app.core.config` → inherits the gate for free.

### BIC-agent-portal (Vite)

- Vite already loads `.env.<mode>` natively for `--mode <mode>` and `src/lib/env.ts` already
  has `STAGE` + `resolveAppStage()`.
- `package.json` `"dev": "vite"` has no mode → currently defaults to `development`. Change so
  the dev/build scripts REQUIRE a mode: make `"dev"` fail without a stage, and add explicit
  `dev:local` / `dev:dev` / `dev:prod` that pass `--mode local|dev|prod`. A bare `pnpm dev`
  must error, not default.
- `resolveAppStage()` must reject a missing/invalid stage (throw at startup) instead of
  defaulting — the fail-if-unset rule applies to the browser bundle too.
- Vite modes map to `.env.local` / `.env.dev` / `.env.prod` (Vite loads `.env.[mode]`).
  Note Vite's own precedence: `.env.local` is ALSO loaded for every mode by Vite convention —
  a collision with our `local` stage. Resolve in implement (likely name the portal stage
  files `.env.local` is fine but be aware `.env.local` loads in all modes; may need
  `.env.development`-style names or `--mode local` with `envDir`). This is the one portal
  subtlety to nail down.

### mars_interface_mock (plain os.environ)

- Entry is `tlc_mock_interface:_cli`. Today every config is `os.environ.get(name, default)`
  with defaults — no dotenv load at all.
- Add: at the TOP of `_cli()` (before the module-level config constants are used), call the
  shared stage resolver, `load_dotenv(".env.<stage>")`, then proceed. BUT the config
  constants (`HOST`, `S3_ENDPOINT`, …) are read at MODULE IMPORT time, before `_cli` runs — so
  either (a) move the dotenv load to module top-level guarded by APP_ENV, or (b) defer the
  constants into `_cli`. Cleanest: a module-top `_bootstrap_stage()` that runs on import,
  resolves APP_ENV, loads the file — mirrors the Python services. Implement decides (a) vs a
  small refactor; (a) is smaller and matches the others.

## Env file content strategy

- For each repo, `.env.local` = the current real `.env` content (agent-service already has
  AWS values; lab/mock get their current working values). This is the "today = local" mapping.
- `.env.dev.example` / `.env.prod.example` = same keys as local, values replaced with
  `__FILL_ME__` (or commented guidance for endpoints). Committed.
- `.env.local.example` = local with SECRETS scrubbed to `__FILL_ME__` (so the template is
  safe to commit), real values kept for non-secret local defaults (ports, localhost hosts).
- `.gitignore`: real `.env.local/.env.dev/.env.prod` already covered by `.env*`; add
  `!.env.local.example`, `!.env.dev.example`, `!.env.prod.example` to the allow-list.

## Boundaries / compatibility

- No product/API/workflow behavior changes; this is config-load + startup-gating only.
- The BIC-meta `make up` orchestrator is out of scope for the requirement, but it currently
  starts services expecting the old `.env`. It will break unless it passes `APP_ENV`. Flag as
  a REQUIRED follow-up (or in-scope patch) — surface loudly; do not let `make up` silently
  regress. Decide in implement whether to patch `make up` in the same change or as a tracked
  follow-up.
- `.env.test` (agent-service) stays as the test-only env; not a stage. Untouched except for
  ensuring the test entrypoints set `APP_ENV` so the gated `app.core.config` import succeeds.

## Risks / weakest points (self-review)

1. **Import-time gate vs test harness.** The hard-exit lives in `app.core.config` import.
   Any test or script that imports app modules without `APP_ENV` set will now exit(2). This
   is a wide blast radius — every pytest run, every script. Mitigation: test conftest sets
   `APP_ENV=local` (or a dedicated `test` value) before app import. MUST verify `pytest`
   still green; this is the highest-risk seam.
2. **Portal `.env.local` Vite collision.** Vite auto-loads `.env.local` in ALL modes. Our
   `local` stage naming may double-load. Needs a concrete test: `pnpm dev:dev` must NOT pick
   up `.env.local` values. Resolve naming before finalizing.
3. **make up regression.** Must not silently break the one-command bench. Explicit decision
   needed.
