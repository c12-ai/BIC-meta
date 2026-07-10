# S3 任务：c12-ai/BIC-meta#102 FE 二轮 — 点选卡已答态可重建

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #102 最新"复测反馈"评论（fe 二轮修复要求）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（d301899）切工作树 .wt/fe-102b 开分支 fix/issue-102-answered-rebuild（不 push/不 PR/不动台架 :5174）。

## 要点
- 一轮实现在 src/pages/chat/BaselineClarifyCard.tsx（+ event-dispatcher 接线），git log 查 ec4f6c7 之前的 3c5f1b0。
- 推导规则照评论两条（权威结果优先、对话前进锁定兜底）；已答显示所选项时用服务端 is_baseline 行，别信本地记忆。
- 快照重建路径（session-loader→chatStore）与 live 路径都要得出同一已答态（#110 的双路一致准绳同样适用）。
- 并行 child .wt/fe-114 在改 TaskConfigPane 区（无重叠）；tests/helpers.ts 不入提交。

## 二元验收
(1) 具名测试：卡后有用户消息的事件序列 → live/snapshot 双路均渲染锁定态；(2) 草稿含 is_baseline 行 → 已答且高亮所选项；(3) 未答卡（无后续消息）刷新后仍可点；(4) pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
修复摘要评论 issue #102，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
