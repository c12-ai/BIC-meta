# S3 任务：c12-ai/BIC-meta#86 — plan 确认工具重复调用未被 once-gate 如实拦截

你是 S3（调查 + 独立复核 + 实现 + 提交）。issue #86 正文是任务书。先 DB 还原该 turn（会话 daf8dfdd 或最近含双 request_plan_confirmation 形态的 turn）事件序列与第二次调用的真实工具名/结果，比对 TerminalOnceMiddleware 行为，结论评论 issue，再实现。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-86-plan-once-gate /Users/wenlongwang/Work/BIC/talos/.wt/be-86 bench-verify`；若 FE 呈现问题另开 portal 侧分支。
- 不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。DB 只读。

## 二元验收
issue #86 三条照抄执行写成测试。全量门禁绿。

## 收尾
调查结论 + 修复摘要评论 issue #86，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
