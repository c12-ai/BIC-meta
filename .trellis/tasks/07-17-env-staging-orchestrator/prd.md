# Child 3 — BIC-meta orchestrator: single-stage, current-network-only

Parent: `07-17-07-17-env-staging-app-env`. Read the parent + Child 1 first.

## Goal

Migrate the BIC-meta orchestrator (`make up` + `scripts/bic-env/*`) onto the stage model, and
in the same pass **simplify it to one axis and one network**. After Child 1, each service is
configured entirely by its own `.env.<stage>` file. The orchestrator should therefore:

1. Launch every service with the chosen stage (`local`/`dev`/`prod`).
2. STOP owning service configuration — the stage file is the single source of truth.
3. Only ever touch the **current machine's network** — no reaching out to remote hosts.

## Product-owner rulings (2026-07-17) — the scope of this task

1. **Stage owns config; orchestrator stops rewriting `.env`.** Retire the seed / auth-self-heal
   / AWS-converge machinery in `up.sh` that rewrites `<repo>/.env`. The `.env.<stage>` file is
   authoritative. The orchestrator selects a stage and launches; it does not edit config.

2. **Kill `BIC_PROFILE` entirely.** The `aws` / `minimal` / `full-real` profile system is
   removed. The only axis is the stage: `local` / `dev` / `prod`. Wherever a profile decided
   behavior (which S3, which Mind, which mock target), that now lives in the stage file.

3. **Retire remote/SSH behavior — current-network-only.** Any machinery that reaches another
   host (orin MinIO forwarder, orin-tail route probing, cloud-Mind reachability convergence)
   is removed. A script run on this machine affects only this machine's network. To deploy to a
   server, the operator SSHes into that server and runs the script THERE, so it only ever
   touches that box's environment.

4. **Retire `mind.sh` entirely.** The mock-vs-real-Mind toggle is no longer a script. Real Mind
   = the developer sets `MIND_MOCK_MODE=false` / `MCP_HOST=...` in the repo's `.env.<stage>`.
   `make mind-status` / `mind-real` / `mind-mock` targets are removed.

5. **No `__FILL_ME__` placeholders.** Stage-file examples use real, sensible DEFAULT values
   (localhost hosts, example URLs, obvious placeholder-but-valid creds like `changeme`) so the
   files parse and read as working examples. (Applies to the Child-1 dev/prod scaffolds too —
   fix them in this task.)

## Requirements

1. **One stage selector.** `make up` (and `restart`, `down`, `doctor`, `status`) take the stage:
   `make up ENV=local|dev|prod`. Default is `local` (the bench convenience); a bad value fails.
   The stage is passed to every launched service inline (tmux `send-keys` shells do NOT inherit
   the orchestrator's env — Child-3 map finding).

2. **Launch commands carry the stage inline.** In `up.sh` `start_cmd_for`:
   - lab → `cd <lab> && make dev ENV=<stage>`
   - BE → `cd <be> && <proxy-unset> APP_ENV=<stage> uv run uvicorn app.main:app ...`
     (BE launches uvicorn directly, bypassing its Makefile — set `APP_ENV` inline)
   - portal → `cd <portal> && pnpm dev:<stage>` (localdev for local)
   - mock → `cd <mock> && APP_ENV=<stage> uv run mars-interface-mock`
     (mock reads S3/MQ from its own `.env.<stage>` now — DROP the inline S3_*/TLC_ env soup)
   - chem → out of scope (unchanged).

3. **Orchestrator stops writing `.env`.** Remove from `up.sh`: the `.env`-from-`.env.example`
   seed (section 6), `ensure_env_key` auth self-heal, and the entire `converge_env_kv` AWS
   block. Config lives in the stage file the developer maintains.

4. **`BIC_PROFILE` removed** from `common.sh`, `up.sh`, `doctor.sh`, `status.sh`, `Makefile`.
   Replace any profile-gated branch with stage-gated or stage-file-driven behavior.

5. **`mind.sh` deleted**; `make mind-*` targets removed; `up.sh` section 8 (mind converge)
   removed; `be_mind_mock` reads become either stage-file reads or are dropped where they only
   fed profile logic.

6. **Remote machinery removed.** orin MinIO forwarder (`minio-forward.py` bridge, `minio_fwd`),
   orin-tail route checks, AWS/orin host convergence — all removed from `up.sh`/`common.sh`/
   `doctor.sh`. Infra (`docker start bic-*`, keycloak seed, DB create) stays — that is local.

7. **`.env` reads point at `.env.<stage>`.** Read-only consumers that still legitimately read a
   repo env value (e.g. `doctor.sh` KEYCLOAK/S3 consistency checks, `common.sh app_pg_port`)
   read `<repo>/.env.<stage>`. Portal's file is `.env.localdev` for the local stage.

8. **Infra + keycloak + DB self-heal preserved** — these are local-network actions and stay.
   Health gates and idempotency preserved.

## Acceptance Criteria

- `make up ENV=local` brings the bench green; each service's process carries the right stage
  (`APP_ENV=local` for BE/lab/mock; portal on `--mode localdev`).
- `make up` with no ENV defaults to `local`; `make up ENV=bogus` fails loudly.
- No orchestrator script reads or writes a plain `<repo>/.env` (all go through `.env.<stage>`),
  and no script writes `APP_ENV=` into a stage file.
- `mind.sh` is gone; `make mind-*` targets are gone; nothing references orin/forwarder/
  BIC_PROFILE/AWS-converge.
- `make doctor` / `make status` run stage-aware and green on `local`, with no profile card and
  no remote-Mind/forwarder legs.
- No stage-file value is `__FILL_ME__` — examples carry real default values.
- `grep -rE 'BIC_PROFILE|minio_fwd|orin|mind\.sh|converge_env_kv' scripts/ Makefile` returns
  nothing.

## Non-goals / preserved

- Local infra bring-up (docker start, keycloak seed, DB create, migrations) stays.
- `ops/field/*` (the real field-deploy scripts) are OUT of scope — untouched.
- lab `docker-compose*.yaml` staging is a follow-up unless trivially covered here (flag it).

## Ordering

Depends on Child 1. Do last. This is a larger rewrite than originally scoped (profile removal +
SSH/remote retirement + mind.sh deletion), captured here per the 2026-07-17 rulings.
