# BIC V2 field deployment (orin (192.168.12.150, LAN direct))

Self-contained package to deploy the BIC V2 stack (Keycloak · chem · lab · agent ·
portal) on orin. After transfer, the field action collapses to
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

## Prerequisites on orin

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

## One-time setup (on orin, in `~/bic-v2`)

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

---

## Updating the deployment after code changes (routine redeploy)

One service changed (typical):

```bash
# 1. build the new image (from your Mac; repo = the changed service)
gh workflow run docker-build.yml --repo c12-ai/BIC-agent-service --ref main
gh run watch --repo c12-ai/BIC-agent-service   # wait for green
# portal needs the field build-args variant — pass the same inputs used for field-<sha>

# 2. on orin (or via ssh): pull + recreate ONLY the changed service
cd ~/bic-v2
./deploy.sh login
docker compose -f agent-service/docker-compose.yml --env-file .env pull
docker compose -f agent-service/docker-compose.yml --env-file .env up -d
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8800/health   # gate
```

Full-stack refresh: `./deploy.sh pull && ./deploy.sh down && ./deploy.sh up`
(Keycloak/DB state persists in `keycloak_db`; realm re-import is skipped.)

### Ready-to-paste Claude prompt (hand this to a Claude Code session)

> 现场更新部署：BIC V2 跑在 orin（ssh orin，~/bic-v2，方案与 runbook 见
> BIC-meta PR#231 与 ops/field/README.md）。请为 <REPO 名> 的最新 main 做一次滚动更新：
> ① gh workflow run docker-build.yml 构建镜像并等绿。portal 的 field 构建必须显式传全三个 URL：
> gh workflow run docker-build.yml --repo c12-ai/BIC-agent-portal --ref main -f image_variant=field \
>   -f vite_api_base_url=http://192.168.12.150:8800 -f vite_lab_api_base_url=http://192.168.12.150:8192 \
>   -f vite_oidc_authority=http://192.168.12.150:18080/realms/bic
> （漏传会被 CI 守卫直接打红——localhost 烘焙进 field 镜像会把浏览器送去操作员本机）；
> ② ssh 到 orin 在 ~/bic-v2 对该服务 pull + up -d 并 health-gate；
> ③ 只动目标服务，绝不碰共享基建（bic-postgres/redis/minio/rabbitmq）和其它 V2 容器；
> ④ 若 health 不过：docker logs 留证 → 回滚该服务到上一 tag（compose 里改 IMAGE_TAG
> 为上一个 sha- tag 再 up -d）→ 报告而不是重试到死。
> 完成后报：镜像 tag/digest、health 证据、变更前后容器 ID。

## Known operational notes (from the 2026-07-11 first deployment)

- **V1 containers are renamed, not removed**: `bic-*-v1` (stopped). V2 reuses the
  original container names; rollback recreates V1 by name from its untouched images.
- **preflight self-idempotency gap**: a HALF-deployed V2 (e.g. keycloak+chem up
  after an aborted `up`) makes preflight flag its own ports as occupied. Workaround:
  `./deploy.sh down && ./deploy.sh up`.
- **MIND_HOST is a bare host** (`192.168.12.104`), port goes in `MIND_PORT` (8002);
  BE builds `http://{host}:{port}` itself (config.py `mcp_address`).

## Mock robot (on-demand, mutually exclusive with the real robot)

`robot-mock/` runs `mars_interface_mock` as a container on the shared
`robot.exchange`. It is NOT part of `deploy.sh up` — start/stop it only via:

```bash
cd ~/bic-v2/robot-mock
./mock.sh up       # REFUSES if ${ROBOT_ID}.cmd already has a consumer (real robot live)
./mock.sh status   # container state + cmd-queue consumer count
./mock.sh down     # run this BEFORE the robot team brings up mars_interface
./mock.sh logs
```

Switching to the REAL robot = `./mock.sh down`, then the robot team starts
`mars_interface` (their `~/bic/robot_service` assets) against the same
`bic-rabbitmq`. Zero V2 changes; verify with
`docker exec bic-rabbitmq rabbitmqctl list_queues name consumers | grep cmd`.

Default TLC fixture is a single passing plate (`tlc_plate_med02.jpg`, Rf ≈0.481);
set `MOCK_TLC_FIXTURE_SEQUENCE=tlc_plate_fixture.png,tlc_plate_med02.jpg` in
`.env` for the fail→retry→pass demo.

### Known issue: V1-era MQ queue argument mismatch (auto-guarded since 2026-07-11)

RabbitMQ queue arguments are fixed at first declaration. On any site with V1
history, `agent.task.status` exists WITHOUT `x-dead-letter-exchange`; V2 BE's
redeclare then fails (`PRECONDITION_FAILED`) forever and the lab→BE task-status
channel is dead (experiments stick at 已下发 while BE retries every 30s).
`deploy.sh init-data` now detects V1-shaped queues with 0 consumers and deletes
them so BE recreates them with V2 args. If the guard reports the queue HAS
consumers, V1 is not actually retired — stop and check.
