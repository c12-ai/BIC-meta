# S3 任务：c12-ai/BIC-meta#116 二轮 — badge 与审核行状态同源

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #116 最新"复测反馈"评论（含截图）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（825238e+，git log 确认 HEAD）切工作树 .wt/fe-116b 开分支 fix/issue-116-badge-sync（不 push/不 PR/不动台架 :5174）。

## 要点
- 一轮实现在 result-stage-status.ts + ResultStageCard.tsx（fd6fa8a）。badge 文案与底部审核行同一推导源：已确认失败轮 badge=「未通过 · 已确认」，未确认=「未通过」；通过轮「已通过 · 审核已完成」语义核对一致；中间重试轮「未达标 · 已自动重试」不变。zh/en。
- 小改动，别扩范围。并行 .wt/fe-122b（tab 样式）、.wt/fe-123b（监控面）无重叠。tests/helpers.ts 不入提交。

## 二元验收
(1) 已确认失败轮 badge 复合态、未确认失败轮单态（具名测试各一）；(2) 一轮测试不回归；(3) pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
修复摘要评论 issue #116，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
