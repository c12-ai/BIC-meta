# S3 任务：BIC-meta#178 — Keycloak 登录页 BIC 主题（infra 主题 + compose 挂载 + seed 置 loginTheme）

你是 S3（实现 + PR，列车口径）。任务书 = meta#178（读全 issue）。

仓：**BIC-infra**（本机路径 `/Users/wenlongwang/Work/BIC/infra`，origin c12-ai/BIC-infra）+ **BIC-meta**（up.sh seed 一小段）。infra 从 origin/main 切分支 `feat/issue-178-bic-login-theme`（该仓小，可不建工作树，但不许动 main 工作区未提交内容）。

## 范围

1. **主题**：`themes/bic/login/`——`theme.properties`（parent=keycloak.v2，styles 追加自定义 css）+ `resources/css/bic.css` + logo/背景资源。视觉对齐 portal 设计语言：读 `/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal` 的 tailwind 配置/index.css 取主色、圆角、字体栈；卡片式居中登录框、BIC 标识位、中文文案友好（Keycloak 消息键 zh-CN 已有内建，主题只管样式，别硬编码文案）。
2. **compose**：keycloak service 挂 `./themes/bic:/opt/keycloak/themes/bic:ro`（同事本地/新环境路径，pull+make up 零手工即得）；README 一句注记。
   **生产路径同仓交付**：加一个 `keycloak/Dockerfile`（`FROM quay.io/keycloak/keycloak:<与 compose 同版> ; COPY themes/bic /opt/keycloak/themes/bic`）+ README 生产注记（prod `start` 模式主题有缓存，随发版重启生效）——不接 CI 构建，只留可用的烘焙配方。
3. **realm**：`realm-bic.json` 加 `"loginTheme": "bic"`（first-boot-only 路径）；**meta up.sh 第 5 节 keycloak seed** 追加幂等步骤：admin API 对既有 realm PUT loginTheme=bic（已是 bic 则 skip，输出 ok 卡）。meta 改动单独 commit 直接推 main（ops 口径）。
4. **不动台架容器**：docker cp 注入与 realm 热更由 root 部署（你在 PR 描述里写清 root 部署三步：docker cp themes/bic → kcadm/REST 置 loginTheme → 刷新登录页验证）。本地验证可自起一个一次性 keycloak 容器（端口用 18081+，别撞台架）挂主题跑通截图。

## 二元验收

- 一次性本地 keycloak 实例登录页呈现 BIC 主题（截图进 PR，对照 portal 主色）；OIDC 授权码流程可走通（登录成功回跳）。
- realm-bic.json 与 seed 幂等步骤齐备；`make up DRY=1` 显示新 seed 步骤计划。
- infra PR CI（若有）绿 admin-merge 留痕；meta 改动推 main。**不重启/不重建台架 keycloak**。

## 收尾

PR sha + 截图 + root 部署三步 评论 #178；dispatch done（FACTS/JUDGMENT 分开）。
