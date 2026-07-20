# Design — Child 3: single-stage, current-network-only orchestrator

Based on the Child-3 map (up.sh is the sole launcher via tmux send-keys; profile/mind/AWS
machinery spans common.sh/up.sh/mind.sh/doctor.sh/status.sh/Makefile — ~217 refs).

## The one new concept: `BIC_STAGE`

Add to `common.sh`:
```sh
BIC_STAGE="${BIC_STAGE:-local}"   # local | dev | prod ; default local for bench convenience
case "$BIC_STAGE" in local|dev|prod) ;; *) echo "FATAL: BIC_STAGE must be local|dev|prod" >&2; exit 2;; esac
export BIC_STAGE
env_file() { printf '%s/%s\n' "$(repo_dir "$1")" ".env.${BIC_STAGE}"; }   # portal special-cased
```
Portal's local file is `.env.localdev` (Vite), not `.env.local` — `env_file` maps
`portal + local → .env.localdev`.

`Makefile`: `make up ENV=local` sets `BIC_STAGE=$(ENV)` (default local). Same for
restart/down/doctor/status.

## Edits per file

### common.sh
- Add `BIC_STAGE` + `env_file()` (above).
- REMOVE `BIC_PROFILE` (line 78) and every `AWS_*` / `MIND_LAB_IP` / `MIND_PORT` /
  `minio_fwd` / forwarder var + helper.
- `be_mind_mock()` (113): it only fed profile/mind logic — DELETE it (mind is now stage-file
  owned, not script-reported). Any caller that printed a Mind card drops that card.
- `app_pg_port()` (271): read `env_file(BIC-agent-service)` / `env_file(BIC-lab-service)`
  instead of `<repo>/.env`; keep `.env.example` fallback? No — stage file is authoritative;
  fall back to a hard default (5432) if absent.

### up.sh — the big one
- DELETE section 6 config machinery: the `.env`-from-example seed (243-248), `ensure_env_key`
  (253-273), the whole `converge_env_kv` AWS block (275-331). The stage file is the config.
- DELETE section 8 (mind converge, 362-370).
- `start_cmd_for` (378-398): rewrite each per PRD req 2 — inline stage, drop the mock S3_* soup
  (mock reads its own `.env.<stage>`). Keep chem as-is.
- Infra/keycloak/DB/migrations sections (1–5, 7) STAY — local actions. Remove any
  profile-gated branch inside them (e.g. the `bic-minio` skip logic keyed on `BIC_PROFILE=aws`
  / `be_mind_mock` at 73-82 → simplify: start bic-minio if it exists; the stage file decides
  whether the service uses it).
- Done-banner (462-472): drop the MIND MOCK/REAL + profile line; print the stage instead.

### DELETE 4 scripts entirely (2026-07-17 ruling)
- `mind.sh` — mock/real Mind is a stage-file value now.
- `status.sh` — redundant with doctor.sh (quick UP/DOWN is a subset of the deep check).
- `bootstrap.sh` — first-clone-only repo cloning; becomes a README step.
- `reset-demo.sh` — thin wrapper over lab reset API; becomes a documented curl / make reset.
Survivors: common.sh (shared lib — KEEP, everything sources it), up.sh, down.sh, restart.sh,
doctor.sh, get-token.sh. Makefile: drop targets for the 4 deleted scripts.

### doctor.sh
- REMOVE the profile card, the aws-口径 S3 check keyed on profile, and any orin/forwarder/
  Mind-reachability leg.
- The KEYCLOAK/S3 consistency reads (191, 193, 262-263, 364-365) → read `env_file(...)`; portal
  → `.env.localdev`.
- Keep the local service health + auth probes.

### status.sh
- Drop the `be_mind_mock` Mind lines (63, 80); keep UP/DOWN/WHITE probes.

### Makefile
- `up/restart-*/down/doctor/status`: accept `ENV=`, pass `BIC_STAGE`.
- DELETE `mind-status/mind-real/mind-mock` targets (72-74) + their help lines (39-41) + the
  header comment block describing BIC_PROFILE (7-8).
- `export` line (21): drop `BIC_PROFILE`, add `BIC_STAGE`.

### Child-1 scaffold fix (no __FILL_ME__)
- Replace every `__FILL_ME__` in all repos' `.env.dev`/`.env.prod`(+examples) with real example
  defaults: hosts→`localhost`/example host, URLs→`https://dev.example.com/...`, secrets→
  `changeme`, buckets→a sample name. Files parse and read as fill-in examples.

## Risks / weakest points (self-review)

1. **up.sh is load-bearing and I'm deleting ~40% of it.** Mitigation: keep infra/keycloak/DB
   sections byte-for-byte; only excise config-rewrite + mind + profile. Verify `make up
   ENV=local` end-to-end on THIS bench after.
2. **Removing `.env` self-heal means a fresh clone has no `.env.local`.** New behavior: the
   operator copies `.env.local.example` → `.env.local` themselves (the stage gate tells them
   to). Document in the done-banner / a WARN if the stage file is missing. This is intended
   (stage owns config), but must fail LOUD, not silently.
3. **be_mind_mock deletion**: confirm no surviving caller needs it (grep). status/doctor cards
   that used it are removed with it.
4. **Portal `.env.localdev` special case** must be handled in `env_file()` and every doctor
   read — easy to miss one.
5. **Bench is live on this machine** — every edit is validated by re-running `make up ENV=local`
   and confirming the 4 services stay green.

## Verification
- `make up ENV=local` → 4 services green, each on the right stage (check process env + Vite
  mode).
- `make up ENV=bogus` → fails. `make up` (no ENV) → defaults local.
- `make doctor` / `make status` → green, no profile/mind/orin content.
- `grep -rE 'BIC_PROFILE|minio_fwd|orin|mind\.sh|converge_env_kv|__FILL_ME__' scripts/ Makefile`
  → empty.
