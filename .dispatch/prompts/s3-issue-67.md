# S3 任务：修复 c12-ai/BIC-meta#67 — SSE 断线可见性 + 自动重连 + 重连补水

你是 S3（独立复核 + 实现 + 提交）。issue #67 正文是任务书（含实证会话与四条验收）。先复核 portal SSE 客户端现状（有无既有重连逻辑），复核结论评论到 issue，再实现。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-67-sse-reconnect /Users/wenlongwang/Work/BIC/talos/.wt/portal-67 bench-verify`。
- 绝不碰 bench 主目录、不重启服务、不 push、不开 PR。
- 复核时注意：PR#17（Keycloak OIDC + ticket-authenticated SSE）未合并——你的重连层不要与其冲突设计（重连=重新走当前的流建立入口，别写死认证细节）。

## 二元验收
issue #67 四条照抄执行写成测试。全量 pnpm vitest run + tsc + 增量 biome 绿。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #67，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
