# Agent 系统改进工作流（S1/S2/S3）

## 摘要

对 BIC agent 系统（话术 / 主链路 / UI-UX / 数据）做系统性改进的三段式工作流：
**S1 整理建档 → S2 根因调查 → S3 独立评审+实现**。统一台账 = `c12-ai/BIC-meta` 的
GitHub Issues。核心原则：**作者 ≠ 验证者**（分析、实现、验收由不同 session/人完成）、
**每个 issue 建档时写死二元验收**、**close 权在提出人（bench 复测通过才关）**、
数据先行（结论必须附 session_id / seq / 截图 / DB 证据）。

## 三个角色

**组织形式（单一对话入口）**：用户只和 **S1/编排会话** 对话。S2/S3 由 S1 会话通过
`session-dispatch`（或裸 tmux）派生为独立子会话执行，产出写回 issue comment，
S1 负责监督进度、转述结论、汇总待用户决策项。子会话之间不共享上下文 ——
独立性由此保证（作者 ≠ 验证者是结构性的，不是口头的）。

| 角色 | 职责 | 禁止 | 启动方式 |
|---|---|---|---|
| **S1 整理/编排** | 接收用户反馈 → bench 复现（DB/事件/截图取证）→ 查重 → 按模板建 issue + 打标签；按用户指令派生并监督 S2/S3 子会话 | 不改代码、不下根因结论（只写"根因假设"） | 用户对话所在的常驻会话（skill `s1-triage`） |
| **S2 调查** | 读 issue → 代码/DB 找根因 → 设计**根源**解决方案（不是打补丁）→ 以 comment 形式写进 issue | 不改产品代码（只读 + 可写复现脚本）；不自己实现 | 由 S1 派生：子会话执行 `/s2-investigate <issue#>` |
| **S3 评审+实现** | 独立复核 S2 的根因（从一手证据重推导，不信 comment 的结论本身）→ 设计实现 → 实现 + 测试 + 按 issue 分组 commit → comment 实现证据 | 不得自己宣布 issue 关闭；验收权在提出人 | 由 S1 派生：子会话执行 `/s3-resolve <issue#>` |

**验收闭环**：S3 comment 附二元验收的执行证据 → 提出人（用户）bench 复测 → 通过才 close。

## 严重度路由

| 标签 | 含义 | 流程 |
|---|---|---|
| `P0-链路断` | 主链路不通/数据损坏 | 完整 S1→S2→S3，优先 |
| `P1-功能` | 功能行为错误（含诚实性问题，如失败被说成完成） | 完整 S1→S2→S3 |
| `P2-话术` | agent 表达/语言问题 | 可**攒批**：一个 S2 分析一批，一个 S3 实现一批 |
| `P3-UIUX` | 界面/交互不合理 | 同上攒批 |

辅助标签：`repo:agent-service` / `repo:portal` / `needs-drake`（产品决策）。

标签走**两根轴**（定档 2026-07-16，详见 `docs/agents/triage-labels.md`）：
- **分诊轴**（入口，`mattpocock` engineering skills 读它）：`needs-triage` → `needs-info` /
  `ready-for-agent` / `ready-for-human` / `wontfix`。
- **生命周期轴**（分诊之后，S1/S2/S3 自己的态）：`stage:已析根因` → `stage:已实现待复测` →
  `stage:已验证`。

一条 issue 的常规流转：`needs-triage`（S1 建档）→ `stage:已析根因`（S2 出根因）→
`ready-for-human`（待产品裁定）或 `ready-for-agent`（待 S3 派工）→ `stage:已实现待复测`（S3 实现）
→ `stage:已验证`（独立验收）。旧的 `stage:待调查` / `stage:待裁定` / `stage:待修复` 已退役，
分别由 `needs-triage` / `ready-for-human` / `ready-for-agent` 取代。

## Issue 模板（S1 建档用）

```
### 现象
<一句话 + 截图/原话引用>

### 证据（可独立核验）
session_id: xxx；关键 seq/事件；DB 查询结果；报错原文

### 复现步骤
1. ...

### 根因假设（S1 可留空，S2 填写正式分析到 comment）

### 二元验收（PASS/FAIL，建档时必填）
<可独立执行判定的标准>
```

## 分支模型

- **集成分支**（bench 常驻运行）：BE = `talos/BIC-agent-service` 的
  `fix/chat-ux-lang-error-tubeid`；portal = 同名分支。所有修复落在集成分支上。
- **每个 issue = 一组 commit**，message 引用 `BIC-meta#<N>`；同文件混多个修复时按
  hunk 拆分（先例见分支上 a8f2ec3…ed22658 七连 commit）。
- **PR 策略**：集成分支各挂一个 rolling PR（随 issue 累积、在描述里逐个勾）；
  仅高风险改动（如 D47 边界反转类）单独摘 PR 给产品负责人隔离审。
- 本地保留不提交：portal `tests/helpers.ts`（DB 指向本机）与
  `tests/cc-re-chained-flow.spec.ts` 的 baseURL 行（用户指定 never push/PR）。

## Bench 手册（每个 session 开工前必读）

- **服务**：tmux `bic-services` 四 pane（lab :8192 / be :8800 / portal **:5174** /
  robot mock）。pane 按 title 找（lab/be/robot/portal），索引会漂。
- **Portal 在 :5174**（:5173 被无关项目占用，不要动它）。
- **⚠️ Agent DB 在 `talos-postgres` 容器 :5433**（`talos_agent_db`）。infra 的
  `bic-postgres` :5432 里有一个**同名空库，是假的** —— 查 session_events/plans/trials
  必须 `docker exec talos-postgres psql -U postgres -d talos_agent_db`。
  lab 的 `labrun_db` 才在 bic-postgres :5432。
- **⚠️ 重启 BE 会掐断页面 SSE**：用户正在测试时不得擅自重启；改动攒批，
  重启前先打招呼，重启后用户需刷新页面。杀 :8800 要 `kill -KILL`（TERM 不释放端口）。
- **⚠️ 事故教训（2026-07-08）**：绝不在用户使用 bench 时跑会 reset/TRUNCATE
  agent DB 的测试循环 —— 曾把用户的活跃 session 删掉造成 500。跑 e2e 前确认 bench 空闲。
- **代理**：本机 curl localhost 前 `unset http_proxy https_proxy … ALL_PROXY`
  或 `curl --noproxy '*'`。
- **Mock 特性**：lab 是 mock，TLC 识别 Rf ≈ 0.51 固定；目标窗 (0.4,0.6) 会过、
  (0.3,0.5) 会失败 —— "TLC 失败"多半是窗口/mock 错配，不是化学问题。
- **LLM**：qwen3.7-plus @ DashScope（BE .env 的 BASE_URL/API_KEY/DEFAULT_MODEL）。
  改 .env 后必须重启 BE（旧值驻留内存曾致 401）。
- **诊断入口**：后端真相优先 —— `session_events`（kind/payload/seq）、
  `plans.current_job_id`、`trials`；BE 错误日志
  `talos/BIC-agent-service/app/logs/error.log`；e2e 剧本
  `BIC-meta/.claude/agents/bic-e2e-runner.md`。
- **已知底账**：`talos/BIC-agent-service/docs/chat-ux-findings-2026-07-08.md`
  （已修/未修清单，第一批 issue 的来源）。

## 变更纪律

- agent 行为改动（prompt/中间件/图）合并前过产品负责人 review；graph 结构性改动先出
  方案再动手。
- 测试必须编码意图（改行为必须同步改断言旧行为的测试，写明 WHY）。
- 报告一律数据先行：PASS/FAIL 在前，解释在后；跳过 = 失败。

## 补充（2026-07-08 事故追加）

- **⚠️ BE dev 模式带 auto-reload**（`main.py: reload=settings.debug`）：S3 编辑 BE 源码会触发运行中服务热重载；若用户页面挂着 SSE，优雅关闭会 wedge（`Waiting for connections to close`，需 kill -KILL）。**S3 实现期间 BE 必须以 no-reload 方式跑**（`uv run uvicorn app.main:app --host 0.0.0.0 --port 8800 --log-level info`），改动在链尾统一验证窗口重启生效；链结束后恢复 `make dev`。

## 外部 PR 对账（2026-07-08 追加，强制）

同事（尤其产品负责人）会在**同一批 issue 上独立并行提 PR**。为避免双改冲突/重复劳动：

- **S2 与 S3 开工前，必须先扫对应 repo 的 open PR**：
  ```bash
  gh pr list --repo c12-ai/BIC-agent-service --state open --json number,title,headRefName,author
  gh pr list --repo c12-ai/BIC-agent-portal  --state open --json number,title,headRefName,author
  gh pr list --repo c12-ai/BIC-lab-service   --state open --json number,title,headRefName,author
  ```
  命中疑似同域 PR → `gh pr diff <N> --repo <r> --name-only` 比对将改文件集。
- **判定与处置**：
  - **重复**（同一 bug 的两份实现）：撤我们的改动（revert），issue 标注"由 <repo>#<PR> 解决"、指向该 PR，**不重复实现**。
  - **文件冲突但不同 bug**：以对方将合入 main 的版本为基准 rebase 心态实现，comment 注明"基于/规避 <repo>#<PR>"。
  - **同子系统、语义相关**（如 lab TLC planner 大改）：动手前读对方 diff 的相关语义，对齐后再改。
- **本地 bench 适配文件的覆盖风险**：外部 PR 若改了 `tests/helpers.ts` 等我们"本地保留不提交"的文件，其合入 main 后会覆盖本机 bench 适配（如 DB 5433 指向、dev/dev 登录）→ 合入后需手动重打本地适配，先例见 portal#14。
- **编号巧合**：各子 repo 的 issue 编号与 `BIC-meta` 台账编号是**两套独立命名空间**，语义不同（如 portal#12 ≠ BIC-meta#12）。引用时一律带 `owner/repo#N` 全名。

## S1 边界（产品负责人重申 2026-07-09，第二次）

S1（主会话）只做：症状登记（截图/一句话现象+会话id）→ 建 issue（needs-triage）→ 立即 dispatch S2/S3（Opus）→ 核验完工、部署、合入。
**根因调查一律下沉给 dispatch session，结论评论到 issue**——S1 不在主会话里跑 DB 取证/代码翻查（超过定位会话 id 级别的都算调查）。此前 S1 多次先挖根因再建档，属违规先例，勿再循。
