# BIC V2 field deployment (orin-tail, 192.168.12.150)

Self-contained package to deploy the BIC V2 stack (Keycloak · chem · lab · agent ·
portal) on orin-tail. After transfer, the field action collapses to
**`./deploy.sh init-env` → review `.env` → `./deploy.sh login` → `./deploy.sh up`**.
Everything provable off-machine has been proven (portal image smoke, full local
5-service rehearsal, deploy.sh pre-flight self-test) before this package shipped.

> **Do not run any of this until Wenlong approves the window runbook on
> BIC-meta PR#231.** V1 must be retired first (consumer mutex on
> `robot.exchange`), and the robot team must be told the bench is switching.

---

## What's in here

```
ops/field/
├── deploy.sh                 orchestrator (login/pull/preflight/init-env/init-data/up/down/status/logs)
├── .env.example              env template (keys+comments only; NO secrets)
├── scripts/preflight-selftest.sh   unit-test-like check of the port pre-flight
├── keycloak/  (docker-compose.yml + realm-bic.json + themes/bic)
├── chem-service/  lab-service/  agent-service/  portal/   (docker-compose.yml each)
```

All five services attach to the existing external `infra-net` and address the
shared infra by container name (`bic-postgres`, `bic-redis`, `bic-minio`,
`bic-rabbitmq`). Images come from `ghcr.io/c12-ai/<repo>:${IMAGE_TAG}` (portal:
`${PORTAL_IMAGE_TAG}` = the `field-<sha>` variant).

## Prerequisites on orin-tail

1. Shared infra containers up & healthy (postgres/redis/minio/rabbitmq) — unchanged from V1.
2. GHCR PAT (classic, **read:packages only**) at `~/.config/bic-v2/ghcr.token` (600),
   created by hand by the token owner (Wenlong). `deploy.sh preflight` fails loudly
   if it's missing and prints the create URL.
3. The V1 `~/bic/.env` present (init-env derives shared infra creds from it).

## Transfer to the field

From this repo root (rsync keeps it a one-liner; excludes are already gitignored):

```bash
rsync -avz --exclude='.env' ops/field/ wangwenlong@192.168.12.150:~/bic-v2/
```

(or `scp -r ops/field wangwenlong@192.168.12.150:~/bic-v2`). The realm JSON and
theme travel with the package — no BIC-infra checkout needed on the field.

## One-time setup (on orin-tail, in `~/bic-v2`)

```bash
./deploy.sh init-env        # writes .env (600): shared creds from ~/bic/.env + generated KC admin pw
$EDITOR .env                 # fill every __FILL_ME__: IMAGE_TAG, PORTAL_IMAGE_TAG, BE_LLM_*, MIND_HOST
./deploy.sh login            # docker login ghcr.io -u Valen-C12 (token from the 600 file; never echoed)
./deploy.sh pull             # optional: pre-pull all five images
```

---

## P2 — retire V1 + deploy V2 (the switch window)

Estimated **20–30 min** including health gates.

```bash
# 1. Retire V1 application containers (STOP, do NOT rm — images are the rollback). ~1 min
docker stop bic-agent-frontend bic-agent-copilot-bff bic-agent-backend bic-lab-service

# 2. Pre-flight: exclusive V2 ports free + shared infra alive + token present. ~5 s
./deploy.sh preflight        # ABORTS if any of 8192/8800/15173/8010/18080 is still occupied

# 3. Sequential, health-gated bring-up (keycloak→chem→lab→agent→portal). ~5–10 min
./deploy.sh up               # runs preflight + init-data itself, then each service with a health gate
```

`up` runs `init-data` first (idempotent): creates `talos_agent_db`, `labrun_v2_db`,
`keycloak_db` (coexisting with V1's dbs) and ensures the minio buckets. lab and agent
self-migrate on boot (`alembic upgrade head`).

## P3 — full-chain acceptance (binary checklist)

```bash
./deploy.sh status           # all five: container up + health green
```

- [ ] 5 ports answer health: keycloak `/realms/bic/.well-known/openid-configuration`,
      chem/lab/agent `/health`, portal `/` → 200.
- [ ] Keycloak issuer == `http://192.168.12.150:18080/realms/bic` (matches BE
      `KEYCLOAK_ISSUER_URL` and the portal's baked `VITE_OIDC_AUTHORITY`).
- [ ] Portal real login (self-register a chemist, or admin-create) → session opens.
- [ ] One TLC dispatch round-trip (portal → BE → lab → robot mock/real → result).
- [ ] **Mind real endpoint**: one parameter recommendation / result analysis over
      the real ChemEngine (`MIND_MOCK_MODE=false`) — must return a real result, not a stub.
- [ ] ELN report downloads (zh + en) from the final confirmed result surface.

## Rollback (minutes — images are all local)

```bash
./deploy.sh down             # stop V2 five containers (shared infra untouched)
cd ~/bic && ./bic-deploy.sh up   # V1 back up (its images never left the box)
```

V2's new dbs/buckets are harmless to leave; V1 keeps its own `labrun_db` /
`labassistant_db` intact (V2 used separate databases by design).

---

## Wenlong pre-actions (before the window)

1. Create the classic PAT (read:packages) and place it on orin at
   `~/.config/bic-v2/ghcr.token` (600). The token never enters git/chat/logs.
2. Book the switch window; tell the **robot team** the bench is switching (the
   robot bus has a single consumer — V1 and V2 lab cannot both run).
3. Confirm the field-only values before `up`: `MIND_HOST` (real ChemEngine
   endpoint), `BE_LLM_DEFAULT_MODEL` / `BE_LLM_API_KEY` (host :8000 model),
   and that the derived shared creds match the real `~/bic/.env` key names.
