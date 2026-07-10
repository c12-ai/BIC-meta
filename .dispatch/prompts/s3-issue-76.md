# S3 任务：实现 c12-ai/BIC-meta#76 — 结果页折叠/滚动策略（用户裁定）

你是 S3（独立复核 + 实现 + 提交）。issue #76 正文是任务书（三条裁定 + 四条验收）。先复核结果面板的展开态管理与自动跳转触发点，复核结论评论 issue，再实现。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-76-result-collapse /Users/wenlongwang/Work/BIC/talos/.wt/portal-76 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。
- 注意验收 (3)：用户手动操作优先——展开态需要区分"系统默认"与"用户已干预"。

## 二元验收
issue #76 四条照抄执行写成测试。全量 pnpm vitest run + tsc + 增量 biome 绿。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #76，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
