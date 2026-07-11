# V2 现场部署方案：orin-tail (192.168.12.150)

## 摘要（结论先行）

沿用 V1 已验证的部署骨架——**远端镜像仓 + 每服务 compose + 外部 `infra-net` 网络 + 部署脚本**——共享基础设施（postgres/redis/minio/rabbitmq/phoenix/日志栈/宿主 LLM :8000）**零改动**。V2 应用层与 V1 应用层做一次**计划内切换窗口**：V1 四个应用容器停但不删（镜像留在本机，回滚 = 一条 compose up）。构建走各仓已有的 GitHub Actions `docker-build.yml` → GHCR（现场实测可达），portal 需新建 Dockerfile（Vite 静态构建 + nginx）。V2 端口全部落在实测空闲位：BE `:8800`、portal `:15173`、chem `:8010`、Keycloak `:18080`；lab `:8192` 在切换窗口由 V1 交接给 V2。预计三阶段落地：①构建产物就绪（CI+Dockerfile）→ ②现场旁路部署与联调（不占 8192）→ ③切换窗口 + 回滚演练。

---

## Facts（现场勘察 2026-07-11，全程只读 SSH，未改动任何现场状态）

### 机器

- `orin-tail` = `c12-workstation-fx523t-x`（tailscale），LAN `192.168.12.150`，用户 `wangwenlong`。
- **x86_64**，Ubuntu 24.04 LTS，112 核，125G 内存，根盘 937G（余 355G）。机名带 orin 但**不是 ARM**——无跨架构构建问题。
- Docker 29.2.1 + Compose v5.1.0。

### V1 部署模式（`~/bic`，运行 8 周）

- `bic-deploy.sh`（25KB 编排器：`ecr_login / cmd_up / cmd_down / cmd_redeploy / cmd_pull / cmd_status / cmd_logs`）+ 每服务目录（`talos_service/{backend,bff,frontend}`、`nexus_service`、`robot_service`）各带 `docker-compose.cloud.yml` + `.env`。
- 镜像：CI 构建 → **AWS ECR 中国区**（`432084094746.dkr.ecr.cn-northwest-1.amazonaws.com.cn`），tag 约定 `production-latest` / `main-<sha>`。
- 所有容器挂**外部网络 `infra-net`**，以容器名寻址（`PG_HOST=bic-postgres`）。
- V1 应用容器（Up 8 weeks）：`bic-agent-frontend` :8080、`bic-agent-copilot-bff` :3001、`bic-agent-backend` :8124、`bic-lab-service` :8192、`mars-log-consumer`、`artemis-eval` :61241。
- V1 BE 的 LLM：`BASE_URL=http://host.docker.internal:8000/v1`——**宿主 :8000 跑着本地 LLM 服务**（在听）。

### 共享基础设施（动不得的部分）

- `bic-postgres` :5432（postgres:16）、`bic-redis` :6379、`bic-minio` :9000/:9001、`bic-rabbitmq` :5672/:15672、`bic-phoenix` :4317/:6006、`logging-grafana` :3000 / `loki` :3100 / promtail。全部 Up 8 weeks (healthy)。
- 数据隔离现状（V1 README）：postgres 分库（`labassistant_db`/`labrun_db`）、redis 分 DB index（0/1/2）、minio 分桶。
- 台架 mock 的 `S3_ENDPOINT=192.168.12.150:9000` 已经指向这台 minio——它本来就在为我们服务，佐证"共享、勿动"。
- robot 团队资产在同机：`~/bic/robot_service`（mars_engine/mars_interface），经共享 rabbitmq 通信。

### 新近变动（避让项）

- **`bic-sa-*` standalone 栈**（Up 19–22h，`~/bic` mtime 7月10）：`bic-lab-service:standalone` :18192 + 独立五件套（:15432/:16379/:15673+:25672/:19000+:19001）。lab 团队最近在现场部署的独立验证栈——**V2 端口选择已避开这些口**。

### 端口占用实测

在听（节选）：22, 3000, 3001, 3100, 4317, 5432, 5672, 6006, 6379, **8000**, 8080, 8124, 8192, 9000, 9001, 15432, 15672, 15673, 16379, 18192, 19000, 19001, 25672, 61241。
**V2 需要的 :8800 / :18080 / :8010 / :15173 全部空闲**；:8192 被 V1 lab 占用（切换窗口交接）。

### V2 侧资产盘点（本地仓）

| 仓 | Dockerfile | 镜像 CI | 备注 |
|---|---|---|---|
| BIC-agent-service | ✅ multi-stage python:3.12-alpine | ✅ `docker-build.yml` → **ghcr.io**（workflow_dispatch 手动触发，push 触发被注释） | |
| BIC-lab-service | ✅ | ✅ 同上 | 另有 standalone/cloud 双 compose |
| BIC-chem-service | ✅ | ✅ 同上 | 台架 :8010 已在跑 |
| BIC-agent-portal | ❌ **缺** | ❌ 仅 ci.yml | V2 去 BFF 后为纯 Vite SPA，需新建 |

- Keycloak（V2 新硬依赖）：台架种子/巡检脚本在 meta `scripts/bic-env/`（up/doctor 已含 realm 检查），可复用到现场。
- 镜像仓连通性实测（自 orin-tail）：`ghcr.io` HTTP 405 / 0.42s（端点可达）；ECR 中国区 401 / 0.48s（存活，待认证）。

---

## 方案（我的建议，供 review）

### 1. 构建管线：GHCR 为主，ECR 为备

- 启用三仓已有 `docker-build.yml`（当前 workflow_dispatch 手动触发即可，暂不开 push 自动触发），tag 沿用 V1 约定：`main-<sha>` + `production-latest`。
- **portal 新建 Dockerfile**（node 构建段 → nginx:alpine 服务段）+ 同款 `docker-build.yml`。`VITE_OIDC_AUTHORITY`/`VITE_API_BASE` 等是**构建期**烘焙 → 用 build-arg 出**现场专用 tag**（如 `field-<sha>`，authority=`http://192.168.12.150:18080/realms/bic`）。
- 现场拉取：GHCR packages 若保持 private，orin-tail 需一枚 read:packages 的 PAT（`docker login ghcr.io`）；若 GHCR 在现场网络出现不稳（本次实测 OK），回退方案是继续用 V1 的 ECR 中国区通道（推送侧加一步 re-tag+push）。

### 2. 目录与脚本：`~/bic-v2`，不碰 `~/bic`

- 新建 `~/bic-v2/`：`deploy.sh`（精简版编排器，登录/up/down/pull/status/logs）+ `keycloak/`、`agent-service/`、`lab-service/`、`chem-service/`、`portal/` 各带 `docker-compose.yml` + `.env`。
- 这套文件**版本化在 BIC-meta `ops/field/`**（或 BIC-infra），现场只是 checkout/scp 的落点——告别 V1 "脚本只活在服务器上"的状态。
- V1 的 `~/bic` 原样保留（回滚依赖）。

### 3. 端口与网络（对齐权威口径 `ops/port-allocation-2026-07-10.md`）

| 服务 | 端口 | 依据 |
|---|---|---|
| lab-service (Nexus) | **:8192**（切换窗口从 V1 交接） | 已在位不迁 |
| agent-service BE | **:8800** | canon，实测空闲 |
| portal (nginx) | **:15173** | 5173+10000 惯例，实测空闲；避开禁用口 8080 |
| chem-service | **:8010** | canon，实测空闲 |
| Keycloak | **:18080** | canon，实测空闲 |

- 全部挂既有 `infra-net`，以容器名寻址共享基础设施（`bic-postgres`/`bic-minio`/`bic-rabbitmq`/`bic-redis`）。
- 共享口（5432/6379/9000/5672/…）与 `bic-sa-*` 栈的口零触碰。

### 4. 数据与初始化（只增不改）

- postgres：在共享 `bic-postgres` 内**新建** V2 库（`talos_agent_db`、lab V2 库、`keycloak_db`），与 V1 的 `labassistant_db`/`labrun_db` 并存；库清单按 BIC-infra `postgres-databases.txt` 口径登记。
- redis：V2 用未占用的 DB index（V1 用 0/1/2 → V2 从 3 起），登记成文。
- minio：按需加桶（`tlc-images` 已存在且台架在用）。
- Keycloak：新容器（连 `keycloak_db`）+ realm 种子（复用 `scripts/bic-env` 资产）；issuer 三处一致：`http://192.168.12.150:18080/realms/bic`（BE `KEYCLOAK_ISSUER_URL` = portal 构建期 authority = 浏览器可达地址）。

### 5. 切换与回滚（关键约束：rabbitmq 消费互斥）

- V1 lab 与 V2 lab 消费**同一 robot.exchange**，不能并行双跑 → lab 是**天然切换制**，没有灰度双活。
- **切换窗口**（预约时段，与 robot 团队打招呼）：
  1. `docker stop` V1 四容器（frontend/bff/backend/lab）——**stop 不 rm**，镜像与容器保留；
  2. `~/bic-v2` 顺序 up：keycloak → chem → lab(:8192) → BE(:8800) → portal(:15173)，每步 health-gate（照搬台架 `make up` 的分步健康检查纪律）；
  3. 验收清单（预写二元项）：五端口 health 200、Keycloak issuer 匹配、portal 真实登录+一次 TLC 派发往返、ELN 下载。
- **回滚** = `docker stop` V2 五容器 + V1 目录 `bic-deploy.sh up`（镜像都在本机，分钟级）；V2 新建的库/桶留着不碍事。
- `mars-log-consumer`、`artemis-eval`、日志栈、robot_service 均不动。

### 6. 分阶段实施

| 阶段 | 内容 | 出口条件（二元） |
|---|---|---|
| P1 构建就绪 | portal Dockerfile+workflow；三仓 dispatch 构建；GHCR 拉取通路（PAT） | orin-tail 能 `docker pull` 全部五镜像 |
| P2 旁路部署 | `~/bic-v2` 落位；keycloak/chem/BE/portal 起在空闲口；lab **暂不起**（8192 未交接），BE 先指台架 lab 或仅做静态联调 | 四服务 health 200 + portal 可登录 |
| P3 切换窗口 | 停 V1 应用层 → V2 lab 接 8192 → 全链验收 → 回滚演练一次 | 预写清单全绿；回滚演练实测通过 |

### 7. 开放问题（需拍板/外部）

1. **LLM 供给**：V2 BE 在现场用云 API（需现场外网/代理）还是宿主 :8000 本地模型（V1 方式）？影响 `.env` 与网络出口。
2. **Mind ChemEngine 现场端点**（#127 内网部署未落）：requirement 8 的 fail-loud 意味着没有 Mind 时参数推荐/结果分析会可见地报错——P3 验收范围要不要含 Mind 链路，取决于 Mind 侧进度。
3. **portal 对外端口**：:15173 是我的建议（+10000 惯例）；若现场用户习惯 :8080，需要先退役 V1 frontend 且推翻 canon 禁用口——不建议。
4. **GHCR org 权限**：c12-ai packages 的可见性/PAT 发放（谁的账号、最小权限 read:packages）。
5. **V1 退役节奏**：切换稳定多久后 rm V1 容器/清 ECR 旧镜像（建议 ≥2 周观察期）。
6. **bic-sa-\* 栈归属**：与 lab 团队确认其用途与生命周期，避免 P3 窗口误伤。

## 附：本次勘察未做的事

- 未读任何 `.env` 秘密值（只取了 key 名）；未在现场执行任何写操作（无 docker 命令变更、无文件创建）。
