# S3 任务：c12-ai/BIC-meta#89 — 推荐参数直接 API（BE 端点 + FE 切换）

你是 S3（独立复核 + 实现 + 提交，跨仓）。issue #89 正文是任务书（设计要点 + 六条验收）。先复核 FORM_CONFIRM 的 API-时刻事件追加与每会话锁的现实现（照它的模式做新端点），复核结论评论 issue，再实现。

## 工作区纪律
- BE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-89-recommend-api /Users/wenlongwang/Work/BIC/talos/.wt/be-89 bench-verify`
- FE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-89-recommend-api /Users/wenlongwang/Work/BIC/talos/.wt/portal-89 bench-verify`
- 不碰 bench 主目录、不重启、不 push、不开 PR。BE 单测 `-m 'not real_llm'`。
- 端点覆盖 TLC 起步（当前按钮只在 TLC 表单），但实现按 EntryStepSpec 泛化（CC/RE 顺带可用则一并接，不强制）；在 issue 评论注明覆盖面。
- #66 的消息通道触发路径：FE 移除按钮对它的使用；BE 的聊天兜底（用户口头说"用推荐参数"）保留不动。

## 二元验收
issue #89 六条照抄执行写成测试。两仓全量门禁绿。

## 收尾
复核结论 + 修复摘要（两仓 sha、测试计数、覆盖面）评论 issue #89，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
