# S3 任务：c12-ai/BIC-meta#116 FE — 结果面状态标签 fail-first 重接

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #116 的 s2 调查评论（4926228154，含 file:line 全链）+ root 裁定评论（A1+B1+C1+D1+E1 包 + lab_task_id UUID 项）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（3d1124d+，先 git log 确认 HEAD）切工作树 .wt/fe-116 开分支 fix/issue-116-result-status-truth（不 push/不 PR/不动台架 :5174）。

## 要点
- 触点 ResultConfirmationPane.tsx / ResultStageCard.tsx / ResultStageList.tsx；接入既有 selectStatusBadge + terminalStatusFromResultVerdict，删代理布尔推导。
- 文案：中间自动重试轮「未达标 · 已自动重试」；最终失败轮「未通过」；「审核已完成」仅真 accept 轮。zh/en 双语。
- 头部 lab_task_id UUID → 人类可读标题（UUID 进 tooltip），对照 #114 一轮 WorkspaceHeader 的做法。
- 并行 child .wt/fe-114b 在做右侧面板去卡片（可能触 pane 容器样式）、.wt/fe-118 修 CC 面板缩略图——你只动结果面状态/文案逻辑，样式冲突留 root。
- 复现数据：experiment 271919ce / job 9d5e2a25…job-0 / trial d778a2fc 等（DB 佐证在调查评论）。

## 二元验收
(1) 复现数据夹具下：中间轮无"已完成/审核已完成"、显示"未达标·已自动重试"；最终轮"未通过"；头部无 UUID（具名测试）；(2) 真 accept 轮"审核已完成"不回归；(3) pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
修复摘要评论 issue #116，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
