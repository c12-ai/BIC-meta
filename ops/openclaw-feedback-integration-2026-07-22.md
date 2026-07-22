# BIC 项目吐槽小虾 · 浅耦合反馈链路

日期：2026-07-22

## 结论

BIC Portal 新增了一个可选悬浮反馈球。用户提交后，本机旁路服务收集当前页面截图和
`BIC-agent-service` 已有日志（脱敏后），调用 OpenClaw 生成飞书诊断文档，并向指定反馈
负责人发送“已受理”和“已完成”通知。该能力不修改 BIC 后端业务代码，也不把 OpenClaw
嵌入 Portal 进程。

## 仓库与分支

| 范围 | 位置 | 内容 |
|---|---|---|
| OpenClaw sidecar | [`c12-ai/BIC-openclaw-feedback`](https://github.com/c12-ai/BIC-openclaw-feedback) `main` | 反馈 API、截图/日志报告包、飞书文档生成、OpenClaw 工作区配置 |
| Portal 接入 | [`c12-ai/BIC-agent-portal`](https://github.com/c12-ai/BIC-agent-portal/tree/feat/openclaw-feedback-bubble) `feat/openclaw-feedback-bubble` | 悬浮球 UI、浏览器截图、运行时 `FEEDBACK_API_URL` |
| BIC Meta 说明 | 当前分支 `docs/openclaw-feedback-integration` | 架构边界、配置和安全约定 |
| Agent service | 无代码分支 | sidecar 只读现有日志，不改后端代码 |

## 调用边界

```text
BIC Portal feedback bubble
  -> POST http://127.0.0.1:18790/api/feedback
  -> local BIC OpenClaw sidecar
     -> screenshot + redacted recent backend logs
     -> OpenClaw report job
     -> Feishu document + owner notifications
```

`127.0.0.1` 是刻意选择：当前实现面向安装了 sidecar 的 BIC 工作站，不新增组织公网入口。
sidecar 不可用时仅反馈功能失败，不影响 Portal 其他页面。

## 飞书访问与隔离

- 飞书内部应用对组织成员开放私聊；群聊目前关闭。
- OpenClaw 使用 `session.dmScope=per-channel-peer`，按“渠道 + 用户 open_id”隔离会话。
- 非反馈负责人禁止使用本机文件、命令、跨会话和全局记忆工具。
- 悬浮球报告索引、受理通知和完成通知只属于环境变量 `FEISHU_FEEDBACK_OWNER` 指定的负责人。
- 不同成员可以持续保留各自私聊上下文，但不能读取或继承其他成员的对话和个人记忆。

## BIC 项目诊断 skill

sidecar 仓库内置并且只启用 `bic-project-diagnostics`。该 skill 由本仓库 revision
`cd92db19ad0a` 下的根 PRD/README、wiki 与 agent 指南、架构/重构/状态语义备忘录、验证
runbook，以及历史 briefs/tasks/prompts 中的回归证据提炼而成；BIC 业务仓库里的其他 skill
和代理约束不会被加载。

它要求报告按以下链路查找首个证据分歧：

```text
Portal 展示
  -> 前端 store / SSE
  -> Agent durable state
  -> Lab / Nexus 权威状态
  -> ChemEngine / Mars / 结果
```

核心方法包括：

- 本次运行证据优先于当前配置和文档；历史任务书、旧端口和过去事故只可作为假设。
- `trial.status`、`trial.phase`、易失的 `progress/steps`、`experiments.stage` 和
  `plans.status` 必须按不同语义层对账，不能互相代替。
- 诊断必须分开记录事实、推断和未知，并提供可复现步骤与二元 PASS/FAIL 验收。
- 截图只证明捕获时的展示；单个日志没有命中不证明请求未发生；端口存活不等于业务就绪。

为保持组织成员的最小权限，普通飞书私聊不会获得本机文件读取能力。悬浮球后台任务由
sidecar 直接注入受信 skill 正文、反馈清单和脱敏日志，截图则通过图像工具读取；因此完整
诊断上下文不依赖放宽会话权限。项目规则发生变化时，应在 sidecar 仓库同步更新该 skill，
并记录新的 BIC-meta 来源 revision。

## 数据与密钥

- 真实截图、后端日志、报告目录、飞书文档索引、每日记忆和本地运行日志均被 Git 忽略。
- 飞书 App Secret 使用本机文件型 SecretRef；模型 API Key 从后端 `.env.local` 动态读取，
  都不会写入仓库。
- sidecar 只引用当前反馈相关日志，并在生成报告前执行常见凭据脱敏。

## Portal 配置

Vite 本地开发使用：

```dotenv
VITE_FEEDBACK_API_URL=http://127.0.0.1:18790
```

容器运行时环境使用：

```bash
FEEDBACK_API_URL=http://127.0.0.1:18790
```

详细安装和环境变量见 sidecar 仓库的 `README.md` 与 `.env.example`。
