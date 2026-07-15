# S3 任务：BIC-meta 一键起环境 Makefile + 自愈脚本

你是 S3（实现 + 提交，meta 仓可直推）。用户指令：在 meta 写 make 脚本（或配套 skill）让同事一键起环境，并自动 fix 常见错误（端口占用等）。

## 交付物（BIC-meta 仓）
`Makefile`（薄入口）+ `scripts/bic-env/`（bash，可单测的函数拆分）+ `.claude/skills/env-up/SKILL.md`（skill 包装：怎么用/怎么读 doctor 输出）。目标：
- **make doctor**：全面体检——docker daemon、五容器（bic-postgres/talos-postgres/rabbitmq/minio/redis）、keycloak、chem；逐端口 lsof 对照权威表（ops/port-allocation-2026-07-10.md）；**5433 隧道遮蔽检测**（listener 是 ssh 而非 docker → 红牌+给出 kill 命令；再连库验证 talos_agent_db 真存在——今晚真坑）；代理变量毒化检测（all_proxy 等指向 127.0.0.1:7890 → 提示 BE 启动会带 unset）；node/pnpm/uv 在位。
- **make up**：幂等一键起。顺序与自愈：①infra compose up（缺容器自动起）→ **wait-for-postgres 循环就绪**（冷启竞态教训，不许 sleep 裸猜）；②keycloak 就绪后种子自愈：realm bic 在位、dev 用户 wenlong/valen（密码 bic_local_dev）不存在则建、bic-portal redirectUris 含 localhost+127.0.0.1:5173；③依赖自愈：portal pnpm install（lockfile 变更或 node_modules 缺包时）、BE/lab uv sync；④tmux 会话 bic-services 按约定布局起 lab→BE→portal→mock（BE 命令带 unset 代理前缀），每个起完做**真健康检查**（portal 查 /src/main.tsx 返回 JS，不只 HTTP 200；BE/lab /health；DB 连通到正确库）。
- **make status**：一屏各服务:端口:状态:git sha。
- **make down / make restart-<svc>**：干净收/单服务重启（带同款自愈检查）。
- **端口占用自愈策略**：占用者是我们自己的旧进程（命令行匹配）→ kill 后重启；外来进程（如 DMPK/隧道）→ 不杀，红牌输出占用者与处置命令（端口治理原则：不动别人的东西）。
- **profile**：默认最小档（MIND_MOCK_MODE=true + 本地 MinIO）；`BIC_PROFILE=full-real` 切全真档（读 .env 现值不覆盖）。仓库根用 BIC_ROOT 环境变量（默认按 meta 相对路径推断），同事检出路径不同也能用。

## 依据
ops/run-latest-2026-07-10.md + ops/port-allocation-2026-07-10.md 是权威（读完再写）；CLAUDE.md 冷启段落同步引用新 make 入口（保留原手工步骤作 fallback 说明）。

## 二元验收
(1) 在当前已运行的台架上 `make doctor` 输出全绿（不破坏运行态——doctor 只读）；(2) `make status` 正确列出六服务；(3) 脚本 shellcheck 干净；(4) 不执行 make down/up 全流程实测（台架在被用户和 e2e-browser 使用，**不许动运行态**）——up 的幂等逻辑用 dry-run 模式（make up DRY=1 打印将执行动作）验证，真实全流程留用户下次冷启验收，文档里写明。

## 收尾
commit+push 到 meta；摘要 + doctor/status 实测输出评论到 BIC-meta 新 issue「一键环境 make 2026-07-10」；dispatch done（FACTS/Judgment 分开）。
