# S3 任务：c12-ai/BIC-meta#103 二轮 — 确认后补名被冲掉

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #103 最新复测评论（确认后 name=null，会话 84807d6a）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（b3f6cb1+）切工作树 .wt/be-103b 开分支 fix/issue-103-confirm-name-preserve（不 push/不 PR/不重启）。

## 要点
- 先从 DB（talos_agent_db，会话 84807d6a）还原确认回合事件：草稿名在场 → 确认后哪一步写回 null（#72 reconcile / #95 确认兜底 / #105 止血 / G1 fast_path 的交互面，注意 .wt/be-135 并行在修 G1——你查名字链路，别碰量纲逻辑）。
- 根因修复 + 不回归：#103 草稿补名、#95 确认兜底、#72 反应物权威恢复的既有测试全绿。

## 二元验收
(1) E2E：草稿补名 → 确认 → 持久化 objective 反应物 name 保留（具名断言，两条确认路径都覆盖）；(2) 既有 #72/#95/#103 测试不回归；(3) 全量单测绿。

## 收尾
修复摘要评论 issue #103，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
