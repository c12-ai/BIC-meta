# S3 任务：c12-ai/BIC-meta#123 二轮 FE — 监控上块轮语义 + 状态 chip 语域

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #123 最新"复测反馈"评论（含截图 109 路径）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（825238e，含一期 de60818）切工作树 .wt/fe-123b 开分支 fix/issue-123-monitor-r2（不 push/不 PR/不动台架 :5174）。

## 要点
- 上块（ExperimentProgressPanel 一带）：三条"开始 TLC 分析·步骤 N"改按轮语义（「第 N 轮 · TLC 实验执行」，复用一期 ExecutionLogPanel 的 roundLead/tlcRoundLabel i18n 键），进度文案"N/3 轮"。
- 状态 chip 裸枚举 AWAITING_CONFIRM → status_vocab 模式中文（"等待确认"）；查同 chip 其他枚举值是否同样裸透，一并入词表（对照 BE #54 status_vocab 与 FE 既有翻译层）。
- 并行 child .wt/fe-122b 在动 tab 体系样式——你动监控面内容语义，样式冲突 root 兜底。tests/helpers.ts 不入提交。

## 二元验收
(1) 复现夹具：上块三轮可辨（含"第 N 轮"）、进度"3/3 轮"、chip 显示中文"等待确认"（具名测试）；(2) 各枚举值 chip 全中文（词表测试）；(3) 一期测试不回归；(4) pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
修复摘要评论 issue #123，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
