# S3 任务：c12-ai/BIC-meta#102 FE 增量 — 主反应物点选卡

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #102 最新修复摘要评论的「FE 增量登记」项 + BE 侧契约文档。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（bf1d785，含 #104）切工作树 .wt/fe-102 开分支 fix/issue-102-baseline-clarify-card（不 push/不 PR/不重启）。

## 契约来源（先读）
- BE 分支工作树 /Users/wenlongwang/Work/BIC/talos/.wt/be-102 内 .trellis/spec/backend/ contracts.md §3d + L4/events.md（事件 objective_baseline_clarify_requested：question / candidates[{smiles,name?}] / preselected_smiles|null）。
- 点选回流走**既有 clarify 回复链**（无新入站契约）：确认/更正 = 把所选反应物按 §3d 约定的回复形态发送。

## 要点
- 聊天流内渲染交互卡：每候选一个按钮（name 为标签、smiles 兜底显示），preselected 高亮为默认；确认后卡片进入已答状态（不可重复点）。zh/en 文案跟随界面语言。
- 未知事件兼容不许回归：其他事件渲染路径零改动。
- 复用既有卡片/按钮组件与 optimistic-events 单写路径（读 deriveRouting/事件应用现状再动手）。
- 仓里 tests/helpers.ts 是台架本地未提交改动，绝不能带进提交。

## 二元验收
(1) 组件/集成测试：带预选事件→卡渲染+默认高亮+点选发送内容断言；无预选事件→无高亮；已答态锁定；(2) 既有测试不回归；(3) pnpm lint && pnpm test && pnpm build 整链绿（短路后从头重跑）。

## 收尾
FE sha + 测试计数评论 issue #102（注明 FE 增量完成，等 root 双端部署复测）；dispatch done（FACTS/Judgment 分开）。
