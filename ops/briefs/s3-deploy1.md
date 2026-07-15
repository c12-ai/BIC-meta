# S3 任务：现场部署 P1（构建就绪）— portal Docker 化 + 三仓镜像构建 + 现场部署资产

你是 S3（现场部署实施一期）。任务书 = BIC-meta PR#231 分支 `ops/field-deploy-proposal` 上的 `ops/field-deploy-v2-proposal.md`（**先读全文**，含 Wenlong 五条 inline 决议——V1 先退役、端口 pre-flight、Mind 现场端点、PAT、不删镜像）。用户裁定：方案 PR 不合并、直接开干（2026-07-11）。

**铁律：本期绝不触碰 orin-tail 现场机**（不 ssh 写操作；P2 退役+部署窗口由 root 另约）。P1 全部在 GitHub/本地完成。

## A. portal Docker 化（BIC-agent-portal PR）

1. 多段 Dockerfile：node20-alpine 构建段（corepack pnpm，`pnpm build`）→ nginx:alpine 服务段（SPA fallback `try_files … /index.html`、静态资产缓存头、gzip；监听 80，宿主映射交给 compose）。加 `.dockerignore`（node_modules/.wt/dist 等）。
2. `docker-build.yml` workflow：镜像 `ghcr.io/c12-ai/bic-agent-portal`，对齐 BE 仓同名 workflow 的结构（workflow_dispatch 手动触发、GITHUB_TOKEN 登录、tags main-<sha> + latest）。**VITE_* 是构建期烘焙**：workflow_dispatch inputs 暴露 `vite_oidc_authority`/`vite_api_base`（及仓内实际用到的其它 VITE_ 变量——先 grep `import.meta.env` 盘点全量），作为 build-args 传入；现场构建产出 tag `field-<sha>`。默认值给台架口径，现场值见方案文档（authority=`http://192.168.12.150:18080/realms/bic`，API=`http://192.168.12.150:8800`）。
3. 本地 docker build 冒烟：镜像能起、`/` 返回 index、SPA 路由 fallback 生效（curl 任意深路径 200）。
4. PR → CI 绿 → admin squash-merge。并行知会：s3-fe226b 在同仓改 locales（不相交，动前 dispatch send ack）。

## B. 现场部署资产（BIC-meta PR，落 `ops/field/`）

1. `deploy.sh`：子命令 login/pull/up/down/status/logs + **up 前端口 pre-flight**（Wenlong 决议：8192/8800/15173/8010/18080 逐口检查无监听者，占用即中止并打印占用进程；共享口 5432/6379/9000/5672 只做存活确认）。V1 风格（~/bic/bic-deploy.sh）可参考但精简。
2. 每服务目录 compose：`keycloak/`（postgres 库 keycloak_db + realm 种子挂载，复用 `scripts/bic-env` 的 realm 资产——先读它怎么种）、`chem-service/`、`lab-service/`（:8192）、`agent-service/`（:8800，`BASE_URL=http://host.docker.internal:8000/v1` per 决议、Mind 现场端点 env 留 `.env` 占位）、`portal/`（:15173→80）。全部挂外部 `infra-net`，容器名寻址 `bic-postgres` 等；镜像引用 `ghcr.io/c12-ai/<repo>:${IMAGE_TAG}`。
3. `.env.example` 每服务一份（**只有 key 和注释，绝无真实秘密**）；`README.md` 现场 runbook：P2 窗口步骤（停 V1 四容器 stop 不 rm → pre-flight → 顺序 up 带 health-gate → 验收清单含 Mind 真链与 ELN 下载 → 回滚 = V2 down + V1 up）。
4. PR → admin squash-merge（meta 无 CI，自查 shellcheck 级干净）。

## C. 镜像构建触发

- 对 BIC-agent-service / BIC-lab-service / BIC-chem-service / BIC-agent-portal（A 合并后）各 `gh workflow run docker-build.yml`（main），等构建完成，`gh api` 核验 ghcr.io 包存在与 tag。
- 若某仓 workflow 有坏死（跑失败），修到绿（workflow 修改也走 PR）。

## 二元验收（P1 出口 = 方案表格）

- 四个 ghcr.io/c12-ai 包各有 main-<sha> 镜像（列包名+tag+digest 落报告）；portal 另有 field-<sha>（用现场 build-args 触发一次）；
- portal 镜像本地冒烟通过；
- `ops/field/` 资产合入 meta main，deploy.sh pre-flight 有单测式自查（bash -n + 对本机空口/占用口各跑一次逻辑分支）；
- 遗留给 root 的清单写清：Wenlong 建 PAT（read:packages）落 orin、约 P2 窗口、robot 团队打招呼。

## 收尾

PR shas + 镜像清单 + 遗留清单评论到 meta PR#231（方案 PR 当作实施台账）；dispatch done（FACTS/JUDGMENT 分开）。
