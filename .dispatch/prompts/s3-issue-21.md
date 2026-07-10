你是 S3 评审+实现角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s3-resolve/SKILL.md（含「外部 PR 对账」）。
硬性纪律：独立复核 S2 结论；不 push 不开 PR；改行为同步改测试写 WHY、单测全绿才提交；commit 按内容拆、Refs c12-ai/BIC-meta#21、footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；收尾 comment+标签换 stage:已实现待复测+dispatch done。
⚠️并行隔离：你是前端链，只动 /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal @ fix/chat-ux-lang-error-tubeid；勿碰 agent-service/lab-service。⚠️本地保留不提交：tests/helpers.ts、tests/cc-re-chained-flow.spec.ts 的 baseURL 行。⚠️agent DB=talos-postgres:5433。

任务：实现 c12-ai/BIC-meta issue #21 子缺陷(b)（S2 主线方案：终态 trial.status 成为三个面的权威失败源）。先 gh issue view 21 --repo c12-ai/BIC-meta --comments 全量。
三处：selectors.ts selectStatusBadge 失败优先于 dispatched；ExperimentProgressPanel 容器终态判定（AwaitingProgressBody 不得对终态渲染「已下发」）；MonitorPane hasActivity 补终态。
外部 PR 对账：gh pr diff 14 --repo c12-ai/BIC-agent-portal --name-only 确认无文件交集（已知 PR#14 改 workspaceStore.ts，你只改 selectors.ts —— 若发现实际交叉，comment 注明并对齐）。子缺陷(a) 已由 portal#14 解决，勿动 ParameterDesignPanel 的锁逻辑。
注意：链B 前序任务（#16b/#19）可能已改 events.ts/chatStore/lab-service-client —— 基于工作区最新状态实现。
