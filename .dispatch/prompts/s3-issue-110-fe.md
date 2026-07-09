# S3 任务：c12-ai/BIC-meta#110 FE 侧 — live/snapshot 事件语义对齐兜底

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #110 正文 + s2 调查评论（4925363118）+ root 裁定评论（做第 2 项 FE 兜底；第 1 项 BE 根因修由并行 child 在做，别依赖它先落地）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（7e23103，含 #104 r2）切工作树 .wt/fe-110 开分支 fix/issue-110-snapshot-spawn-align（不 push/不 PR/不动台架 :5174）。

## 要点
- 调查定位：live 路 text_delta 走 spawn（sse-client.ts:136 → chatStore.ts:354-363/191-212），snapshot 路只有 text_done 走原地 patch（session-loader.ts:149-151 → chatStore.ts:473-499/165-180）。兜底 = text_done 携带正文且落在 form_requested 冻结气泡之后时，对齐 spawn 语义（另起气泡），使两路对同一事件序列渲染出同一终态；孤儿 trace 剪除逻辑（#55 既定期望，chatStore.test.ts:215-248）保持。
- 判定准绳：同一 DB 事件序列（复现 turn session 40c52ae5/fff34dab，seq1600-1606）经 live 模拟与 snapshot 重建，气泡结构与 trace 显隐一致。
- 别碰 BaselineClarifyCard（#102 刚合入）与 ExperimentObjectiveStep（#104 r2 刚合入）。tests/helpers.ts 不入提交。

## 二元验收
(1) 同序列双路终态一致的具名测试（复现 turn 的事件夹具）；(2) 既有 chatStore/#55 测试不回归；(3) pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
修复摘要评论 issue #110（注明 FE 兜底完成；与 BE 侧汇合后 root 转标签），dispatch done（FACTS/Judgment 分开）。
