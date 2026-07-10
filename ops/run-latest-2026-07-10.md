# 如何起最新代码（2026-07-10 合并列车后）

**结论先行。** 2026-07-10 合并列车把 TLC purity 双 PR、Keycloak 登录、Phoenix 点赞点踩、以及一批我方 bench 修复全部合入各仓 main。起最新代码有两个 profile：**最小本地档（无 Mind，同事默认）** 只需 docker 基建 + 本地 MinIO + `MIND_MOCK_MODE=true`；**全真档** 额外需要 Mind 可达的共享 MinIO（台架用 orin 上的 Mind + 192.168.12.150 MinIO）。冷启顺序 **lab→BE→portal→mock**，BE 启动命令**必须 unset 代理变量**。**Keycloak 是本次新增的硬依赖**：BE 只认 Bearer JWT（X-User-Id 回退已删），portal 走 OIDC 登录——本机 8080 被 DMPK 占用，故 keycloak 起在 **18080**，BE/portal 的 issuer 要对齐。所有 `curl` 打本地服务都要 `--noproxy '*'`（本机代理 127.0.0.1:7890 会拦截 localhost）。

各仓 main（本文写作时）：shared-types `b85ee6c` / mars_interface_mock `389a784` / BIC-agent-service `19deb48` / BIC-agent-portal `c224b98` / BIC-lab-service `ef277d8` / BIC-infra `48c2cba`。

---

## 1. 各仓 main 与 shared-types pin

| 仓 | main | 说明 |
|---|---|---|
| BIC-shared-types | `b85ee6c` | #95 pic_urls + #97 pipetting-robot AGV（AgvMoveOp/PipettingAgvMoveOp） |
| mars_interface_mock | `389a784` | 真实 CC/TLC 夹具 + TLC_FIXTURE 开关 + 按轮序列夹具（#112/#132/#143） |
| BIC-agent-service | `19deb48` | purity(#73) + Keycloak(#67) + Phoenix feedback(#44) + bench 修复批 |
| BIC-agent-portal | `c224b98` | 同上前端 + pure/crude 摆放(#21) + Keycloak 登录(#17) + 点赞点踩(#9) |
| BIC-lab-service | `ef277d8` | #61/#68/#115 + op_adapt_v3 properties(#95) + RC-B 重试恢复修复(#105) |
| BIC-infra | `48c2cba` | Keycloak service + chem-service 本地运行时 |

**shared-types pin**：BE pin `3e9d595`（#95 pic_urls，BE 不用 AGV 类型）；lab pin `b85ee6c`（op_adapt_v3 的 planner 要 AGV 类型；含 `[tool.uv] override-dependencies` 强制全图到官方 main，因为 mars_interface_mock 自身仍 pin `bic-shared-types@v1.2.0`——待 mock 收编自身 pin 后可去 override）。两仓 pin 不同但各取所需，无问题。

后续待办（已登记 BIC-meta issue）：
- **#147** chem-service `feat/compound-names` 需属主开 PR 合入 main（`/compound-names` 补名端点只在该分支；台架 chem 从本地 `.wt/chem-95` 起）。
- **#144** portal 缺远端 CI（建议补 GitHub Actions lint+test+build）。
- **#146** portal 管格 add-mode×选择模型视觉走查（CDP 目视）。

---

## 2. Docker 基建

用专用 `talos-postgres` 容器在 **:5433**（本机原生 Homebrew Postgres 占了 :5432，会和 docker `bic-postgres` 脑裂）。其余基建走 docker `bic-*` 默认端口。

| 组件 | 端口 | 凭据 |
|---|---|---|
| Postgres（专用） | `talos-postgres` :5433→5432 | postgres / bic_local_dev；库 `labrun_db`(lab)、`talos_agent_db`(agent) |
| Redis | :6379 | bic_local_dev |
| RabbitMQ | :5672 / :15672 | rabbitmq / bic_local_dev，vhost `/` |
| MinIO | :9000 / :9001 | minioadmin / bic_local_dev |
| Phoenix（可选） | :6006 / :4317 | 无 |
| **Keycloak（新增硬依赖）** | **:18080**（见 §5，8080 被 DMPK 占用） | admin / bic_local_dev；realm `bic` |
| Chem Service | :8010（本地 `.wt/chem-95` 起，见 §4/§6） | 无 |

初次建库：
```bash
PGPASSWORD=bic_local_dev psql -h localhost -p 5433 -U postgres -c "CREATE DATABASE labrun_db;"
PGPASSWORD=bic_local_dev psql -h localhost -p 5433 -U postgres -c "CREATE DATABASE talos_agent_db;"
```

---

## 3. 冷启顺序与健康检查（lab → BE → portal → mock）

每仓先切 main + 同步依赖：
```bash
cd BIC-lab-service    && git checkout main && git pull && uv sync --group mock
cd BIC-agent-service  && git checkout main && git pull && uv sync
cd BIC-agent-portal   && git checkout main && git pull && pnpm install
cd mars_interface_mock&& git checkout main && git pull
```

各仓 `alembic upgrade head`（lab、BE 都要，含本批新迁移）：
```bash
cd BIC-lab-service   && uv run alembic upgrade head    # op_adapt_v3 properties + merge-heads + waiting_busy_retries
cd BIC-agent-service && uv run alembic upgrade head    # phoenix 链 + keycloak + merge d3ccc917bb81
```

启动（推荐 tmux `bic-services`，窗口 lab/agent/portal/mock）：
```bash
# ① lab :8192
cd BIC-lab-service && uv run uvicorn app.main:app --host 0.0.0.0 --port 8192

# ② BE :8800 —— 必须 unset 代理前缀（否则打 localhost/lab/MQ 会被本机 7890 代理拦）
cd BIC-agent-service && \
  unset all_proxy http_proxy https_proxy ALL_PROXY HTTP_PROXY HTTPS_PROXY && \
  uv run uvicorn app.main:app --host 0.0.0.0 --port 8800

# ③ portal :5173
cd BIC-agent-portal && pnpm dev

# ④ mock（连 RabbitMQ）
cd mars_interface_mock && uv run mars-interface-mock
```

健康检查（**注意 `--noproxy '*'`**）：
```bash
curl -s --noproxy '*' http://localhost:8192/health        # lab {"status":"healthy","app":"Nexus"}
curl -s --noproxy '*' http://localhost:8800/health        # BE  {"status":"healthy"}
curl -s --noproxy '*' http://localhost:5173/ -o /dev/null -w '%{http_code}\n'   # portal 200
curl -s --noproxy '*' http://localhost:18080/realms/bic/.well-known/openid-configuration | head -c 80  # keycloak issuer
```

---

## 4. 必需 env

**BIC-agent-service/.env**（占位不写真 key）：
```ini
PG_HOST=localhost
PG_PORT=5433
PG_USER=postgres
PG_PASSWORD=bic_local_dev
PG_DATABASE=talos_agent_db
REDIS_PORT=6379
MQ_HOST=localhost
MQ_PORT=5672
MQ_USER=rabbitmq
MQ_PASSWORD=bic_local_dev
MQ_VHOST=/
API_KEY=sk-...                       # DashScope，真 chat 需要；占位可启动但 chat 降级
MCP_PORT=8011                        # Mind（全真档：经捕获代理→orin 104:8002）
CHEM_SERVICE_HOST=127.0.0.1
CHEM_SERVICE_PORT=8010
# Keycloak（新增，必填）——issuer 端口对齐实际 keycloak 端口（本机 18080）
KEYCLOAK_ISSUER_URL=http://localhost:18080/realms/bic
KEYCLOAK_AUDIENCE=bic-portal
# —— S3 / Mind 见下方两个 profile ——
```

**BIC-agent-portal/.env**（新增 OIDC）：
```ini
VITE_OIDC_AUTHORITY=http://localhost:18080/realms/bic
VITE_OIDC_CLIENT_ID=bic-portal
```

**BIC-lab-service/.env**：`PG_PORT=5433`，`PG_DATABASE=labrun_db`。

### Profile A — 最小本地档（无 Mind，同事默认）
- `MIND_MOCK_MODE=true`（BE main 与 .env.example 默认即 true）：所有 MindClient 调用返回 med005 fixture、打 WARN、不发任何 Mind/ChemEngine 网络请求。**无需 Mind/ChemEngine 可达**。
- `MIND_RECOGNITION_MOCK_MODE`：三态开关，控制「识别类」调用（rxn-parse / TLC recognize）走 mock 还是真 Mind——最小档设 `true`（识别也 mock）。
- chem-service **可选**：`CHEM_SERVICE_HOST` 不配则 ELN 补名（分子量/mole）**惰性跳过、相应字段缺省**（空字段契约，不炸、chemist 不见报错）。
- **唯一新增硬依赖：本地 MinIO**（mock 机器人现在真上传 CC/TLC 照片到 S3）。设 `S3_ENDPOINT_URL=http://localhost:9000` `S3_ACCESS_KEY_ID=minioadmin` `S3_SECRET_ACCESS_KEY=bic_local_dev` `S3_BUCKET_NAME=tlc-images`（bucket 需存在）。此档 mock 识别不真拉图，本地 MinIO 足够。

### Profile B — 全真档（有 Mind）
- `MIND_MOCK_MODE=false` + `MIND_RECOGNITION_MOCK_MODE=false`：走真 ChemEngine（rxn-parse/recommend/recognize 都真调）。任何失败 fail-loud（`MindCallError`→502），**绝不 fabricate**。
- Mind 经 `MCP_PORT=8011`（台架是本地捕获代理→orin `192.168.12.104:8002`）。
- **S3 必须是 Mind 可达的共享 MinIO**：台架用 `S3_ENDPOINT_URL=http://192.168.12.150:9000` `S3_BUCKET_NAME=tlc-images`。**不能换成本机 localhost MinIO**——因为真 Mind 在 orin 上，拉不到你本机 localhost 的照片（这正是全真识别链的约束；反应渲染图也 presign 到 150）。

---

## 5. Keycloak 登录（新增要求）

合并后 **BE 只认 Bearer JWT（keycloak），X-User-Id / `?user_id=` 回退已删**；portal 走 OIDC Authorization Code + PKCE 登录。SSE 用单次 ticket（`POST /sse-tickets` → `?ticket=` 挂 SSE URL）。

**起 keycloak**：BIC-infra 的 compose 有 keycloak service（realm `bic`，DB 走 `config/postgres-databases.txt` 的 `keycloak` 库）。**但本机 8080 被 DMPK 实验管理占用**，且 realm 导入是 first-boot-only。本次台架用独立容器起在 **18080**（H2 内置库、`--import-realm`），并把 BE/portal 的 issuer 对齐 18080：
```bash
docker run -d --name bic-keycloak -p 18080:8080 \
  -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=bic_local_dev \
  -e KC_HOSTNAME=http://localhost:18080 \
  -e BIC_PORTAL_REDIRECT_URI='http://localhost:5173/*' -e BIC_PORTAL_WEB_ORIGIN='http://localhost:5173' \
  -v "$PWD/BIC-infra/keycloak/realm-bic.json:/opt/keycloak/data/import/realm-bic.json:ro" \
  quay.io/keycloak/keycloak:26.3 start-dev --import-realm
```
> `KC_HOSTNAME` 把 token 的 `iss` 钉死到浏览器可见 URL——BE 的 `KEYCLOAK_ISSUER_URL`、portal 的 `VITE_OIDC_AUTHORITY` 必须与它**同一字符串**。若你本机 8080 空闲，可直接用 8080（并把上面三处都改回 8080）。

**登录**：portal 打开 → 跳 keycloak 登录页 → 回 `/auth/callback` → 拿 Bearer。`bic-portal` 客户端是 public PKCE、默认 `directAccessGrants=false`（不能 password 直取 token；脚本化冒烟需临时开、用完回退）。

---

## 6. Chem-service（ELN 补名）

台架 chem 从本地 `.wt/chem-95`（`feat/compound-names` 分支，含 `/compound-names`）起 :8010：
```bash
cd .wt/chem-95 && uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
```
`/compound-names` 端点尚未入 chem-service main（见 issue #147）。BIC-infra 也提供了 `make chem-up`/`make chem-smoke`（ECR 镜像的 chem-service），但那版 main 没有 `/compound-names`，补名会缺省——全真补名目前依赖本地 feat 分支。chem 不可用时 ELN 补名惰性跳过（空字段契约）。

---

## 7. Reset / 冒烟

```bash
TOKEN=<一枚有效 bic-portal Bearer>
curl -s --noproxy '*' -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8800/reset          # 清库+清队列
SID=$(curl -s --noproxy '*' -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' http://localhost:8800/sessions | python3 -c 'import json,sys;print(json.load(sys.stdin)["session_id"])')
# 开 SSE：POST /sse-tickets 拿 ticket → GET /sse/$SID?ticket=...
# 下 objective：POST /sessions/$SID/messages  body {"text":"...反应...","locale":"zh"}
# 确认：POST /sessions/$SID/objective/confirm  body {name,reaction_smiles,reactants[{...is_baseline}],feed_amount_mg,target_purity_pct,target_yield_pct}
```
2026-07-10 冒烟实测（全真 Mind）：objective 一轮跑通——真 Mind rxn-parse 出 reaction_smiles + reactant 命名 + 反应渲染图 presign 到 150 MinIO → `experiment_created` + `objective_baseline_clarify_requested` + `form_requested`(objective) → `turn_completed`，零 error；`/objective/confirm` 喂错载荷时真 Mind goal-confirm 返 400 → BE `upstream_mind_error` 502（never-fabricate 正确）。

---

## 8. 常见坑

- **代理变量**：本机 profile 每个新 shell 都会 set `http_proxy=127.0.0.1:7890`。BE 启动**必须** `unset all_proxy http_proxy https_proxy ALL_PROXY HTTP_PROXY HTTPS_PROXY` 前缀（否则打 localhost/lab/MQ 被拦）；所有 `curl` 打本地服务加 `--noproxy '*'`（`no_proxy` 里的 localhost/127.0.0.1 有时不生效——曾出现整片 000）。**反过来**：`uv lock`/git 拉 github 又**需要**代理（本机直连 github 超时、经 7890 通）——分场景处理。
- **Postgres 脑裂**：用 `talos-postgres:5433`，别用 5432（被原生 pg 影子）。
- **Keycloak 端口/issuer**：8080 可能被占；keycloak 端口、`KC_HOSTNAME`、BE `KEYCLOAK_ISSUER_URL`、portal `VITE_OIDC_AUTHORITY` 四处必须同一字符串。BE 启动时 JWKS warm-up 若 keycloak 未就绪会 WARN（不抛，惰性重取）——先起 keycloak 再起 BE。
- **S3=150 不可换本机**（全真档）：真 Mind 在 orin，拉不到你本机 localhost 的照片。
- **realm 导入 first-boot-only**：改 realm-bic.json 后不会更新已导入的 realm；dev reset = 删 keycloak 库/容器重来。
- **alembic 多 head**：本批各仓补了 merge-heads 迁移（lab `126914ab2869`、BE `d3ccc917bb81`）。跨分支引入迁移后先 `alembic heads` 看是否分叉，分叉就 `alembic merge heads`。
