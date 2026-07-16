# BIC V2 field deployment (orin 192.168.12.150 · a1 192.168.12.239)

Two sites share this package. The body below is written against **orin** (the
original site); **a1** differs only by the knobs in the "Site: a1" section.

Self-contained package to deploy the BIC V2 stack (Keycloak · chem · lab · agent ·
portal) on orin. After transfer, the field action collapses to
**`./deploy.sh init-env` → review `.env` → `./deploy.sh login` → `./deploy.sh up`**.
Everything provable off-machine has been proven (portal image smoke, full local
5-service rehearsal, deploy.sh pre-flight self-test) before this package shipped.

> **Do not run any of this until the product owner approves the window runbook on
> BIC-meta PR#231.** V1 must be retired first (consumer mutex on
> `robot.exchange`), and the robot team must be told the bench is switching.

---

## What's in here

```
ops/field/
├── deploy.sh                 orchestrator (login/pull/preflight/init-env/init-data/up/down/status/logs)
├── .env.example              env template (keys+comments only; NO secrets)
├── scripts/preflight-selftest.sh   unit-test-like check of the port pre-flight
├── scripts/reset.sh          bench reset ON the field box: BE /reset (DB truncate+MQ purge,
│                             no-auth dev endpoint) → lab reset-to-test-data (service-account
│                             Bearer minted from the on-box Keycloak). `reset.sh [all|be|lab]`
├── keycloak/  (docker-compose.yml + realm-bic.json + themes/bic)
├── chem-service/  lab-service/  agent-service/  portal/   (docker-compose.yml each)
```

All five services attach to the existing external `infra-net` and address the
shared infra by container name (`bic-postgres`, `bic-redis`, `bic-minio`,
`bic-rabbitmq`). Images come from `ghcr.io/c12-ai/<repo>:${IMAGE_TAG}` (portal:
`${PORTAL_IMAGE_TAG}` — shared tags `latest` / `sha-<full sha>` since
BIC-agent-portal#86; backend/issuer URLs are runtime config via `/env.js`, no
per-site build variants).

## Prerequisites on orin

1. Shared infra containers up & healthy (postgres/redis/minio/rabbitmq) — unchanged from V1.
2. GHCR PAT (classic, **read:packages only**) at `~/.config/bic-v2/ghcr.token` (600),
   created by hand by the token owner (the product owner). `deploy.sh preflight` fails loudly
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
      `KEYCLOAK_ISSUER_URL` and the portal's runtime `OIDC_AUTHORITY` — check
      `curl http://192.168.12.150:15173/env.js`).
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

## Product-owner pre-actions (before the window)

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
# portal builds the same way since #86 — no variant, no build-args

# 2. on orin (or via ssh): pull + recreate ONLY the changed service
cd ~/bic-v2
./deploy.sh login
docker compose -f agent-service/docker-compose.yml --env-file .env pull
docker compose -f agent-service/docker-compose.yml --env-file .env up -d
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8800/health   # gate
```

Full-stack refresh: `./deploy.sh pull && ./deploy.sh down && ./deploy.sh up`
(Keycloak/DB state persists in `keycloak_db`; realm re-import is skipped.)

### Portal runtime config — ONE-TIME migration per site (after BIC-agent-portal#87)

The portal image is site-agnostic since #86/#87: URLs live in compose env →
`/env.js`, tags are `latest` / `sha-<full sha>`. A site still running a
pre-#86 `field-*` image needs one manual hop (its old image has no OCI
revision label, so `update.sh` survey reports portal "unknown" until then):

```bash
# 0. sync this package to the site first (portal compose gains the env keys)
gh workflow run docker-build.yml --repo c12-ai/BIC-agent-portal --ref main   # no args
gh run watch --repo c12-ai/BIC-agent-portal                                  # wait for green
ssh <site> "cd ~/bic-v2 && sed -i 's|^PORTAL_IMAGE_TAG=.*|PORTAL_IMAGE_TAG=latest|' .env \
  && docker compose -f portal/docker-compose.yml --env-file .env pull -q \
  && docker compose -f portal/docker-compose.yml --env-file .env up -d"
curl -s http://<site-ip>:15173/env.js    # must show the site's OIDC_AUTHORITY + API_BASE_URL
```

Then do one real login in a browser. From here `update.sh` handles portal like
any backend (survey via image label, pin `sha-<full sha>` on roll). The old
`field-*` tags stay in GHCR as emergency anchors but are no longer built.
DANGER: rolling a pre-#86 site to the new image WITHOUT the synced compose
gives an empty `/env.js` → the SPA boots with no OIDC authority (fail-loud by
design) while `/health` stays green — always sync the package first.

### Ready-to-paste Claude prompt (hand this to a Claude Code session)

> # 任务：BIC V2 现场（orin）例行更新到各仓 main 最新
>
> ## 环境事实
> - 现场机：orin（ssh 别名 `orin`=LAN / `orin-tail`=tailscale，先测哪个通用哪个），部署目录 ~/bic-v2
> - 五服务：bic-keycloak(:18080)/bic-chem-service(:8010)/bic-lab-service(:8192)/bic-agent-service(:8800)/bic-agent-portal(:15173)
> - 镜像 ghcr.io/c12-ai/<repo>，现场已 docker login（~/.config/bic-v2/ghcr.token）
> - 权威文档：本 README + BIC-meta PR#231 部署台账
>
> ## 铁律
> - 绝不动共享基建（bic-postgres/redis/minio/rabbitmq/phoenix/日志栈）与 bic-sa-*、bic-*-v1
> - 不跑 lab reset、不删数据；.env 只按 .env.example 新增 key 补值，绝不回显秘密
> - 每步有证据（sha/digest/health 码）；失败如实报并停下，不重试到死
>
> ## 步骤
> 1. 盘点：五仓 git fetch 后比较现场运行版本 vs origin/main；PR 合并通知≠进 main（gh pr view --json baseRefName 核对）；纯 CI/docs 变更跳过。
> 2. 兼容性预检（lab/shared-types 变更时必做）：mock 的 shared-types pin 与新技能 handler 先适配再滚 lab；diff compose 与 .env.example，新增 env knob 先定值。
> 3. 构建：变更仓 gh workflow run docker-build.yml --ref main 等绿；portal 自 #86 起免参数（共享镜像，runtime config，无 variant/无 vite 输入）。
> 4. 滚更：逐服务 pull + up -d（portal 先改 .env PORTAL_IMAGE_TAG=sha-<新全长sha>），每服务 health-gate（40×2s 内 200）；全栈才用 deploy.sh down && up。
> 5. 验证：deploy.sh status 全 healthy；BE 滚更后 rabbitmqctl 确认 agent.task.status/results/hb 消费者归位（启动见 lab_task_lost absorbed WARN 属正常自愈）；portal 滚更后断言 /env.js 含现场 OIDC_AUTHORITY 与 API_BASE_URL（curl :15173/env.js）；关键修复容器内 grep 符号自证。
> 6. 报告：旧 sha→新 sha、digest、health 证据、失败项如实；回滚=IMAGE_TAG 固定回上一 sha- tag 再 up -d。

## Known operational notes (from the 2026-07-11 first deployment)

- **V1 containers are renamed, not removed**: `bic-*-v1` (stopped). V2 reuses the
  original container names; rollback recreates V1 by name from its untouched images.
- **preflight self-idempotency gap**: a HALF-deployed V2 (e.g. keycloak+chem up
  after an aborted `up`) makes preflight flag its own ports as occupied. Workaround:
  `./deploy.sh down && ./deploy.sh up`.
- **MIND_HOST is a bare host** (`192.168.12.104`), port goes in `MIND_PORT` (8002);
  BE builds `http://{host}:{port}` itself (config.py `mcp_address`).

## Site: a1 (192.168.12.239) — cloud-Mind / AWS-S3 口径 (2026-07-13)

a1 (`ssh a1`, hostname `standby`, x86_64, runs the standby V1 stack + other
tenants — layer-craft/artemis/logging are UNTOUCHABLE). Same shared infra +
`infra-net` topology as orin; the switch window stops only the four V1 app
containers (`bic-agent-frontend`, `bic-agent-copilot-bff`, `bic-agent-backend`,
`bic-lab-service`). Differences from orin:

| Knob | orin | a1 |
|---|---|---|
| ssh / `FIELD_HOST` | `orin-tail` / 192.168.12.150 | `a1` / 192.168.12.239 |
| V1 env for init-env | `~/bic/.env` | `V1_ENV_FILE=~/BIC-infra-deploy/.env` — its MQ creds are `RABBITMQ_DEFAULT_USER/PASS`, map to `MQ_USER/MQ_PASSWORD` by hand |
| Mind / ChemEngine | LAN host (`MIND_HOST` bare, `MIND_PORT`) | cloud: `MIND_HOST=52.83.119.132`, `MIND_PORT=8010` |
| S3 | local MinIO (defaults) | real AWS S3 — uncomment the cloud-Mind block in `.env.example`; creds on a1 at `~/.config/bic-v2/s3-bic.env` (IAM user `bic-a1-s3`, scoped to the one shared bucket) |
| LLM | host `:8000` model server | DashScope: `BE_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`, model `qwen3.7-plus-2026-05-26` |
| Portal image | shared (`latest` / `sha-<sha>`) | SAME shared image since BIC-agent-portal#86 — URLs are runtime config (`/env.js` from compose env); the old `field-` / `field-a1-` variants are retired |
| Robot | mock or real | mock only for now; `TLC_DEVELOP_WAIT_SECONDS=30` (restore 180 on a real robot) |

Routine updates: `FIELD_SSH=a1 FIELD_HOST_IP=192.168.12.239 ./update.sh`
(no `PORTAL_VARIANT` since #86 — the portal image is site-agnostic)

Why AWS S3: Mind is cloud-side, so presigned image URLs must be public-internet
reachable — a LAN MinIO presign dies at 52.83.119.132. All four S3 writers (BE,
lab, chem, mock) share ONE bucket; the services have no key-prefix knob, object
keys carry UUIDs (collision risk accepted, ruling 2026-07-13).

## Lab-auth flip (lab #112 + BE #97/#135) — BOTH sites, read before rolling

Current mains enforce auth end-to-end: lab validates Bearer JWTs
(`LAB_AUTH_MODE=enforce`) and the BE calls lab with a service-account token.
Deploying/rolling to these mains REQUIRES:

1. `BIC_AGENT_SERVICE_CLIENT_SECRET` in the field `.env` (init-env generates it).
2. The `bic-agent-service` confidential client in the realm. A FRESH realm
   import (a1) gets it from realm-bic.json automatically. An ALREADY-imported
   realm (orin) is now covered automatically too: `deploy.sh up` (after the
   keycloak health gate) and `update.sh` (guard 2c) both check-then-create it
   idempotently from the field `.env` secret. The manual recipe below remains
   for reference / degraded situations:

   ```bash
   docker exec bic-keycloak /opt/keycloak/bin/kcadm.sh config credentials \
     --server http://localhost:8080 --realm master --user admin --password '<KEYCLOAK_ADMIN_PASSWORD>'
   docker exec bic-keycloak /opt/keycloak/bin/kcadm.sh create clients -r bic \
     -s clientId=bic-agent-service -s enabled=true -s publicClient=false \
     -s serviceAccountsEnabled=true -s standardFlowEnabled=false \
     -s directAccessGrantsEnabled=false -s 'secret=<BIC_AGENT_SERVICE_CLIENT_SECRET>'
   ```

3. Lab now also needs `KEYCLOAK_ISSUER_URL` + portal-origin CORS — the compose
   files default both from `FIELD_HOST`, so a correct `.env` needs no new keys.

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

`update.sh` re-checks this mutex before rolling the mock (expected consumers =
1 iff the mock container is running; anything above aborts the roll) — added
after the 2026-07-14 double-consumer incident, BIC-meta#314.

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
