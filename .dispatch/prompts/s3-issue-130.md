# S3 任务：c12-ai/BIC-meta#130 — FE-0 live 形状对齐（#128 阶段0 止血）

你是 S3（独立复核 + 实现 + 提交）。issue #130 正文 + #128 交付物 2（差距 2 的形状失配 file:line）是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（d4e3fbd+，git log 确认）切工作树 .wt/fe-130 开分支 fix/issue-130-live-evidence-shape（不 push/不 PR/不动台架 :5174）。

## 要点
- 断点：workspaceStore.onTaskResultAnalyzed(:1561-1584) 存 e.analysis ≠ monitor-exec-status 谓词需要的 e.evidence 形状(:1207)。改存 e.evidence，live 与 snapshot 同形；快照路径不动。
- 小改动止血，别扩范围（该谓词在 BE-1/FE-1 落地后整体删除）。tests/helpers.ts 不入提交。

## 二元验收
issue #130 两条照抄（live 不刷新横幅不红夹具测试 / 刷新行为不变），具名测试。pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
修复摘要评论 issue #130，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
