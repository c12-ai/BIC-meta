# BIC 端口分配定档（2026-07-10）

**结论先行。** 端口方案已定档并落地：三条规则——①在位稳定端口不迁、②易撞默认端口一律 `+10000`、③基建照录事实标准——外加一份禁用清单（`3000/5000/7000/8000/8080`）。**唯一实质迁移是把 Keycloak 从 8080 定到 18080、Chem 从 infra 曾用的 8810 收敛到 8010**；其余服务本就在定稿口，**零迁移**。定稿表经 root 确认，且与台架当前 lsof 现状逐口一致，六个受管服务 health 全绿。infra 为权威源（`BIC-infra` README 有同表），本文是团队侧镜像 + lsof 证据 + PR 台账 + 待切换清单。

权威机器可读表在 `BIC-infra/README.md` §Port allocation；本文与其一致，冲突时以 infra 为准。

---

## Facts（可验证）

### 定稿分配表

| 域 | 服务 | 主机端口 | 说明 |
|---|---|---|---|
| 前端 | BIC-agent-portal (Vite) | `5173` | vite 默认；`5174` 废止 |
| 后端 | BIC-agent-service (BE) | `8800` | 在位不迁 |
| 后端 | BIC-lab-service (Nexus) | `8192` | 在位不迁 |
| 后端 | BIC-chem-service | `8010` | ECR 镜像与源码检出同口，二选一起 |
| AI | Mind 捕获代理 (`MCP_PORT`) | `8011` | 台架本地代理 → 上游 ChemEngine |
| 认证 | Keycloak | `18080` | `8080 + 10000`（规则 2） |
| 可观测 | Phoenix UI / OTLP gRPC | `6006` / `4317` | 在位不迁 |
| 可观测 | Grafana（未来） | `13000` | `3000 + 10000`（规则 2） |
| 数据 | Postgres（单实例 `bic-postgres`） | `5432` | 事实标准；全部库归 infra `postgres-databases.txt` 管（#153） |
| 数据 | ~~Postgres（talos 专用）~~ | ~~`5433`~~ | **退役**（#153，2026-07-10）：数据已对账迁入 5432；任何 5433 监听视为错误状态 |
| 数据 | Redis | `6379` | 事实标准 |
| 消息 | RabbitMQ AMQP / 管理台 | `5672` / `15672` | 事实标准 |
| 对象存储 | MinIO S3 API / 控制台 | `9000` / `9001` | 事实标准 |

### 规则

1. **在位稳定端口不迁** —— 迁移成本 > 规律收益，已落定的服务口保持不动。
2. **易撞默认端口一律 `+10000`** —— 上游默认落在禁用清单的服务，改绑 `默认 + 10000`（Keycloak `8080→18080`；未来 Grafana `3000→13000`）。
3. **基建照录事实标准** —— Postgres/Redis/RabbitMQ/MinIO 保持约定俗成端口。

### 禁用清单（BIC 服务永不绑定于此）

`3000` · `5000` · `7000` · `8000` · `8080` —— 高撞车默认口。新服务上游默认若落此，按规则 2 `+10000`。

本机 lsof 实测占用（2026-07-10）：

- `3000` = node
- `5000` / `7000` = macOS ControlCenter / AirPlay Receiver
- `8000` = docker
- `8080` = docker（DMPK 实验管理占用）

### 逐口 health 核验（2026-07-10，`curl --noproxy '*'`）

| 服务 | 端口 | 结果 |
|---|---|---|
| lab | `8192` | `200` `{"status":"healthy","app":"Nexus"}` |
| BE | `8800` | `200` `{"status":"healthy"}` |
| portal | `5173` | `200` + 真加载（`/src/main.tsx`→JS 6809B，`react-oidc-context` 已 Vite deps-optimize，注入 env `VITE_OIDC_AUTHORITY=http://localhost:18080/realms/bic`） |
| keycloak | `18080` | `200` `issuer=http://localhost:18080/realms/bic` |
| chem | `8010` | `200` `{"status":"healthy","app":"BIC Chem Service"}`（`/health` + `/health/readiness`） |
| Mind 代理 | `8011` | `200` |
| phoenix | `6006` | `200` |
| minio | `9000` | `200` |
| rabbitmq mgmt | `15672` | `200` |
| redis / postgres | `6379` / `5432` | TCP-open（`5433` 退役：必须**无**监听） |

### portal 5173 vs 5174 定夺

定为 **5173**，废止 5174。判据：当前树 5173 出现于 75 文件、5174 仅存于归档 task/日志共 10 文件；`vite.config.ts port:5173`、keycloak realm redirect_uri `5173/*`、全部 live playwright spec 均 5173。

### PR 台账（改动落地）

| 仓 | PR | 合并 sha | 内容 |
|---|---|---|---|
| BIC-infra | [#4](https://github.com/c12-ai/BIC-infra/pull/4) | `0c52b5d` | keycloak `8080→18080`（`${KEYCLOAK_PORT:-18080}`）、chem `8810→8010`、README 权威端口表 + 规则 + 禁用清单 |
| BIC-agent-service | [#76](https://github.com/c12-ai/BIC-agent-service/pull/76) | `8850f81` | `.env.example` + `docker-compose.yml` 的 `KEYCLOAK_ISSUER_URL→18080`；容器 app 口 `8000→8800`；deploy 文档 keycloak URL `8080→18080` |
| BIC-agent-portal | [#24](https://github.com/c12-ai/BIC-agent-portal/pull/24) | `5198b5f` | `.env.example` + `src/lib/env.ts` fallback + `oidc.test.ts` 的 `VITE_OIDC_AUTHORITY→18080` |

三个 PR 均按端口治理专车继承的合并列车授权 admin-merge（实质 CI 全绿或无 CI，唯一剩余阻塞为 codeowners REVIEW，作者无法自审自批；flow-bot review-fix 豁免；每 PR 留痕）。

**不需改动的仓**（已符合定稿）：BIC-lab-service（`.env.example` 无 keycloak/chem，PG 5432 为 bic 标准）；mars_interface_mock（`S3_ENDPOINT` 默认 `localhost:9000` 已合规）。

---

## 待切换清单（留给 root + 用户约时执行）

台架当前六个受管服务已在定稿口（**本次零迁移**）。以下是**其他消费方**在同步最新 main 后需要对齐的点：

1. **本地 `.env` 仍指 8080 的开发者**：`make up`（infra 新默认）现起 keycloak 于 18080；本地 BE `.env` 的 `KEYCLOAK_ISSUER_URL` 与 portal `.env` 的 `VITE_OIDC_AUTHORITY` 需改 18080（issuer 三处必须同一字符串：infra `KEYCLOAK_HOSTNAME` / BE issuer / portal authority）。
2. **infra 容器化 chem**：`make chem-up` 现默认绑 8010（原 8810）；若有脚本硬编 8810 需改。
3. **切 main 后依赖同步（root 补充的真坑，已写进 run-latest 冷启流程）**：
   - portal 切 main 后**必须 `pnpm install`**（BE/lab `uv sync` 同理）—— Keycloak 批新增 `react-oidc-context`，不装则页面白屏 import error。
   - portal 健康判据不能只看 `:5173` HTTP 200（dev server 起 ≠ 页面能编译）；需加真加载检查（`curl /src/main.tsx` 得 JS，或浏览器开一下）。
4. **BE 容器化 app 口 `8000→8800`**：仅 `docker-compose.yml`（scaffold 派生、台架用宿主 uvicorn :8800，此 compose 处于休眠）。台架运行态不受影响。

---

## Interpretation（判断，可能有误）

- **零迁移是"在位不迁"规则的直接收益**：定稿前先用 lsof 核对本机现状，发现台架早已跑在规律化后的口上（keycloak 18080、portal 5173、chem 8010），于是定稿=现状，无需重启任何服务、不打断用户测试。
- **最大残余风险是 issuer 三处漂移**：keycloak 换口后，`KEYCLOAK_HOSTNAME` / BE `KEYCLOAK_ISSUER_URL` / portal `VITE_OIDC_AUTHORITY` 必须同一字符串，否则 JWT `iss` 校验失败。三处提交默认已统一到 18080，但已有本地 `.env` 需手动对齐（见待切换清单）。
- **chem 8810→8010 是消解漂移而非新增约束**：8010 本就是 BE `CHEM_SERVICE_PORT` 所拨、源码 chem 所绑的口；infra 曾用的 8810 是孤立漂移，收敛后"一服务一口"。
