# Implement — Child 1: 4-repo APP_ENV gating + stage env files

Ordered checklist. Each repo is independently verifiable; do agent-service first (proves the
pattern), then lab, mock, portal. Do NOT commit (no git ops without explicit go).

## 0. Pre-dev
- [ ] Read parent + this task's prd/design. Load `.trellis/spec` for the layer being touched
      (agent/lab L4 config, portal env).
- [ ] Snapshot current working `.env` of agent/lab and the mock's running env (already
      captured in session: agent AWS S3 + MCP 8003; mock AWS S3).

## 1. BIC-agent-service
- [ ] Add `app/core/stage.py` with `resolve_stage_env_file()` (design snippet).
- [ ] `app/core/config.py`: `env_file=".env"` → `env_file=resolve_stage_env_file()`.
- [ ] `cp .env .env.local` (keeps AWS values). Create `.env.dev`, `.env.prod` (placeholders).
- [ ] Create `.env.local.example` (secrets scrubbed), `.env.dev.example`, `.env.prod.example`.
- [ ] `.gitignore`: add `!.env.local.example` `!.env.dev.example` `!.env.prod.example`.
- [ ] Verify: `unset APP_ENV; uv run python -c "import app.core.config"` → exits 2 w/ message.
- [ ] Verify: `APP_ENV=staging uv run python -c "import app.core.config"` → exits 2.
- [ ] Verify: `APP_ENV=local` → config loads; re-run the session's live proofs (BE health 200,
      ChemEngine material-parse 200, AWS presign OK).

## 2. BIC-lab-service
- [ ] Mirror: `app/core/stage.py`, `config.py:20` edit, `.env`→`.env.local`, dev/prod, examples,
      gitignore.
- [ ] Verify: unset/invalid APP_ENV → exit 2; `APP_ENV=local` → lab health 200.

## 3. mars_interface_mock
- [ ] Add `python-dotenv` to `pyproject.toml` deps; `uv sync`.
- [ ] Add module-top `_bootstrap_stage()` (resolve APP_ENV + load `.env.<stage>`) BEFORE the
      `os.environ.get` config constants. Confirm ordering (constants read after bootstrap).
- [ ] Create `.env.local` (AWS S3 + MQ localhost values the mock runs on now), dev/prod,
      examples, gitignore allow-list.
- [ ] Verify: unset/invalid → exit 2; `APP_ENV=local uv run mars-interface-mock` → MQ up +
      AWS upload path intact (drive one observe via a VALID SkillCommand, or check the
      S3 env + fixture resolution as in session).

## 4. BIC-agent-portal
- [ ] `src/lib/env.ts`: `resolveAppStage()` throws on missing/invalid stage (no default).
- [ ] `package.json`: add `dev:local`/`dev:dev`/`dev:prod` (`vite --mode <stage>`); make bare
      `dev` and `build` fail without a stage.
- [ ] Create `.env.local`/`.env.dev`/`.env.prod` (+ `.example`), gitignore.
- [ ] **Resolve Vite `.env.local`-in-all-modes:** confirm `pnpm dev:dev` does NOT read
      `.env.local` values (test with a distinct marker var). Adjust naming/`envDir` if it leaks.
- [ ] Verify: `pnpm dev` (no mode) fails; `pnpm dev:local` serves the portal and it loads.

## 5. Full-scope check (2.2)
- [ ] Run `trellis-check` scope for each repo touched.
- [ ] Re-run the local live-proof matrix end-to-end with everything on `APP_ENV=local`.
- [ ] Confirm `BIC-shared-types` + `BIC-chem-service` untouched (`git status` clean there).
- [ ] Note: agent/lab `pytest` will now FAIL without APP_ENV — that's expected and is fixed in
      Child 2. Do not "fix" it here; record it as the handoff to Child 2.

## Validation commands
- Gate (per Python repo): `unset APP_ENV; uv run python -c "import app.core.config"; echo $?`
  (expect 2) — then `APP_ENV=local uv run python -c "import app.core.config"; echo $?` (expect 0).
- Live local proof: reuse the session's ChemEngine material-parse + AWS presign probes.

## Rollback
- Each repo's change is isolated: revert `config.py`/`stage.py`/`package.json`/`env.ts` and
  restore plain `.env` to un-gate. No data migration, no schema change — safe to revert per repo.
