# S3 任务：c12-ai/BIC-meta#92 — 聊天追踪步骤点终态收敛

你是 S3（调查 + 独立复核 + 实现 + 提交）。issue #92 正文是任务书。落点：聊天气泡追踪面板的步骤渲染（与 #71 修的监控 ExecutionLogPanel 是不同组件——先定位，复用其折叠语义）。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-92-trace-dots /Users/wenlongwang/Work/BIC/talos/.wt/portal-92 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。
- 并行提示：portal 在飞 #89/#90，域应不相交。

## 二元验收
issue #92 四条照抄执行写成测试。全量门禁绿。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #92，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
