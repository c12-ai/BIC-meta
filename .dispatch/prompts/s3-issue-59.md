# S3 任务：修复 c12-ai/BIC-meta#59 — RE"推荐依据"改为化学家可读的来源说明

你是 S3（独立复核 + 实现 + 提交）。issue #59 正文是任务书主体，先读，复核（定位 RE 表单 basis 说明组件与 FP 回填载荷结构），复核结论评论到 issue，再实现。

## 工作区纪律
- 自建 worktree + 侧分支（基于 bench-verify 当前 tip，含 51-52 合并）：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-59-re-basis-copy /Users/wenlongwang/Work/BIC/talos/.wt/portal-59 bench-verify`。
- 绝不碰 bench 主目录、不重启、不 push、不开 PR。
- 并行提示：s3-issue-56 在修 TLC 结果面可读性（fix/issue-56-...）——同"可读性"族不同文件；若其 review 清单覆盖了本点，评论互引、由你实施本 issue 范围。

## 二元验收
issue #59 照抄执行写成组件测试；translation-parity 不破；全量 pnpm vitest run + tsc + 增量 biome 绿。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #59，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。合入窗口 root 攒批。
