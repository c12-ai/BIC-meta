# Design — Child 1: 4-repo APP_ENV gating + stage env files

See parent `design.md` for the shared mechanism. This narrows it to the 4 repos.

## The resolver (Python services — copied per repo, ~15 lines)

New module `app/core/stage.py` (agent + lab) / a `_bootstrap_stage()` at module top
(mock):

```python
import os, sys
_VALID = ("local", "dev", "prod")

def resolve_stage_env_file() -> str:
    stage = os.environ.get("APP_ENV")
    if stage not in _VALID:
        sys.stderr.write(
            f"FATAL: APP_ENV must be one of {_VALID}; got {stage!r}. "
            f"Start with e.g. APP_ENV=local ...\n"
        )
        raise SystemExit(2)
    path = f".env.{stage}"
    if not os.path.exists(path):
        sys.stderr.write(f"FATAL: APP_ENV={stage} but {path} not found.\n")
        raise SystemExit(2)
    return path
```

## Per-repo wiring

### BIC-agent-service
- `app/core/config.py:21`: `env_file=".env"` → `env_file=resolve_stage_env_file()`.
  Import `resolve_stage_env_file` from the new `app/core/stage.py`. The call runs at class-def
  time (module import), so importing `app.core.config` without APP_ENV exits(2) — covers
  `app.main`, `check_services.py`, all scripts.
- Move current `.env` → `.env.local` (already holds AWS values). Create `.env.dev` / `.env.prod`
  placeholders. Create the three `.example` templates.

### BIC-lab-service
- `app/core/config.py:20`: same edit. New `app/core/stage.py`.
- Move current `.env` → `.env.local`; create dev/prod + examples.

### BIC-agent-portal
- Vite loads `.env.[mode]` for `--mode`. `src/lib/env.ts` `resolveAppStage()` must THROW on a
  missing/invalid stage instead of defaulting.
- `package.json`: `"dev": "vite"` → require a mode. Add `"dev:local": "vite --mode local"`,
  `"dev:dev"`, `"dev:prod"`; make bare `"dev"` fail (e.g. `"dev": "node -e \"process.exit(1)\""`
  with a message, or a guard script). Same for `build`.
- **Vite `.env.local` collision:** Vite auto-loads `.env.local` in EVERY mode. To avoid
  `dev`/`prod` picking up local secrets, use mode files `.env.local` / `.env.dev` / `.env.prod`
  but VERIFY isolation, or set `envDir`/prefix so only the selected stage loads. Concrete check
  in implement: `pnpm dev:dev` must NOT read `.env.local` values.

### mars_interface_mock
- Config constants read `os.environ.get` at MODULE import (before `_cli`). Add a module-top
  `_bootstrap_stage()` that resolves APP_ENV + `load_dotenv(".env.<stage>")` BEFORE the
  constants are defined. Needs `python-dotenv` as a dep (add to `pyproject.toml`).
- Move nothing (no current `.env`); create `.env.local` from the values the mock runs on now
  (AWS S3 for the plate photos, MQ localhost), plus dev/prod + examples.

## Env file contents (the "today = local" mapping)

- agent `.env.local` = current agent `.env` (AWS S3 + AWS ChemEngine `52.83.119.132:8003`).
- lab `.env.local` = current lab `.env`.
- mock `.env.local` = the AWS S3 + MQ values the running mock uses now.
- portal `.env.local` = current portal `.env` / `.env.local` values.
- `*.dev.example` / `*.prod.example` = same keys, `__FILL_ME__`.
- `*.local.example` = local with SECRET values scrubbed to `__FILL_ME__`.

## gitignore
- Real `.env.local/.env.dev/.env.prod` already caught by `.env*`. Add allow-list:
  `!.env.local.example`, `!.env.dev.example`, `!.env.prod.example` in each repo's `.gitignore`.

## Verification (Child 1 done = )
- Each service: unset APP_ENV → exit 2; invalid → exit 2; `APP_ENV=local` → today's behavior.
- Live proof for local: agent health 200 + ChemEngine material-parse 200 + AWS presign OK;
  lab health 200; mock MQ-connected + AWS upload; portal loads.

## Weakest points (self-review)
1. Portal Vite `.env.local`-loads-in-all-modes is the trickiest; must prove `dev` mode does
   NOT leak `.env.local`.
2. Mock's import-time constants — the bootstrap MUST run before they're read; ordering bug
   risk. Keep the bootstrap literally first in the module.
3. Test import gate — deferred to Child 2, but Child 1's config edit is what triggers it;
   don't fix it here, just don't be surprised when `pytest` starts failing until Child 2.
