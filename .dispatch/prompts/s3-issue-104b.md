# S3 任务：c12-ai/BIC-meta#104 二轮 — footer 满宽 + 滚动回归修复

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #104 全部评论（重点最新"复测不通过"帖）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（250fccd，已 revert 一轮修复 bf1d785）切工作树 .wt/fe-104b 开分支 fix/issue-104-footer-align-r2（不 push/不 PR/不动台架 :5174）。

## 要点
- 一轮修复 bf1d785 的 diff 是你的输入（git show bf1d785）：footer 满宽思路可保留，但它使表单失去垂直滚动（用户截图在 issue）。找回归根源（flex 列 min-h-0/overflow 链），一并满足：字段区可滚、footer 固定满宽、按钮不回归。
- 必须在运行态真实浏览器验证（自己起 dev server 或无头，连台架 BE :8800 或 mock 数据均可）——一轮就是因为只做了复刻容器量测而漏掉真实布局链。验证证据（量测数字/截图）写进 issue 评论。
- tests/helpers.ts 台架本地改动绝不能带进提交。

## 二元验收
(1) 运行态：objective 表单内容超视口时可垂直滚动到矩阵底部（量测断言）；(2) footer 分隔线满宽、左右缝 0（含经典滚动条模式）；(3) 两按钮等高居中不回归；(4) pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
修复摘要 + 运行态验证证据评论 issue #104，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
