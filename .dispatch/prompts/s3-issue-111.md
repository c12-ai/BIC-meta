# S3 任务：c12-ai/BIC-meta#111 — WorkflowDesignStep footer 漂移修复

你是 S3（独立复核 + 实现 + 提交）。issue #111 正文是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（7e23103）切工作树 .wt/fe-111 开分支 fix/issue-111-workflow-footer（不 push/不 PR/不动台架 :5174）。

## 要点
- 修法平移 git show 9c9c2b6（#104 r2 的 ExperimentObjectiveStep 改法）：滚动器块级流、footer 移出为 shrink-0 兄弟；TaskConfigPane 对应分支若有同款包裹也一并对齐（对照 #104 r2 怎么处理的）。
- 必须运行态真实浏览器验证（自己起 dev server，强制经典滚动条），量测证据写进 issue 评论——#104 一轮的教训。
- 并行 child .wt/fe-110 在动 chatStore（无重叠面）；别碰 ExperimentObjectiveStep。tests/helpers.ts 不入提交。

## 二元验收
issue #111 四条照抄执行。

## 收尾
修复摘要 + 运行态量测证据评论 issue #111，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
