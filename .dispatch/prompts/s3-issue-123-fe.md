# S3 任务：c12-ai/BIC-meta#123 一期 FE — 监控面执行态解耦 + 日志轮间区分

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #123 的 s2 调查评论（4926830246，含双链 file:line）+ root 裁定评论（一期 A+E）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（dc24fd4，git log 确认 HEAD）切工作树 .wt/fe-123 开分支 fix/issue-123-monitor-truth（不 push/不 PR/不动台架 :5174）。

## 要点
- 触点：experiment-progress-derive.ts:16-23 / monitor-steps-derive.ts:40-46 / SpecialistSubtabs.tsx:42-48——监控面横幅/子 tab 的执行态改读执行真值（task_progress/skill 结果这条链现有数据里就有：lab 三 skill code200 + awaiting_confirm），评估失败不再染红执行横幅；执行真值失败（机器人 code=500 类）仍红。
- 日志条目：轮间区分（"第 N 轮 · TLC 实验执行 · 完成" + 各轮时间戳已有），确保 3 轮肉眼可辨为 3 次实验；轮内 skill 细粒度是二期（#124 族），不做。
- 结果面刚落 #116 fail-first（result-stage-status.ts）——监控面语义与它相互独立、不要互相串源；zh/en 双语。
- 并行 children：.wt/fe-120（表单控件）、.wt/fe-122（样式打磨）——你只动监控面派生/文案，冲突 root 兜底。tests/helpers.ts 不入提交。

## 二元验收
(1) 复现数据（experiment 271919ce / lab task c06c7e85）夹具：执行横幅非"失败"（显示执行完成/等待确认语义），评估未达标只出现在结果面；机器人真失败夹具横幅仍红（具名测试各一）；(2) 日志 3 轮可辨（文案含轮次）；(3) 既有测试不回归；(4) pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
修复摘要评论 issue #123，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
