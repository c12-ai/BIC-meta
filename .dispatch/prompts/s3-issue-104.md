# S3 任务：c12-ai/BIC-meta#104 — 目标表单 footer 按钮对齐

你是 S3（独立复核 + 实现 + 提交）。issue #104 正文是任务书（含本机截图路径，用 Read 看图）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify 切工作树 .wt/fe-104 开分支 fix/issue-104-footer-align（不 push/不 PR/不重启服务）。

## 要点
- 基线是 bench-verify（含 #89/#90/#92），不是 origin/main。
- 先看图再定位组件；若 footer 是共用组件则一处修复，各步骤自查一遍是否同源（漂移只登记回 issue，不扩改——Rule 3）。
- 台架 portal 跑在 :5174，不要动它；验证用组件测试/门禁。
- 注意仓里 tests/helpers.ts 是台架本地未提交改动，绝不能带进提交。

## 二元验收
issue #104 两条照抄执行。`pnpm lint && pnpm test && pnpm build` 全链绿（短路链修复后从头重跑整链）。

## 收尾
修复摘要（sha、门禁输出）评论 issue #104，标签 stage:待调查 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
