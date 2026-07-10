# S3 任务：修复 c12-ai/BIC-meta#58 — analyze 出口误路由 TEXT_REPLY，结果分析 turn 错答旧输入

你是 S3（独立复核 + 实现 + 提交）。issue #58 正文是任务书主体（含 DB 实证 turn 2d0592d6、#45-Q1 谱系、二元验收四条），先读并复核（读 _narrate_pipeline 出口路由代码自证），复核结论评论到 issue，再实现。

## 工作区纪律
- 自建 worktree + 侧分支（基于 bench-verify 当前 tip，含片1-3）：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-58-analyze-exit-routing /Users/wenlongwang/Work/BIC/talos/.wt/be-58 bench-verify`。
- 绝不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。
- 并行提示：s3-issue-57 在 fix/issue-57-cc-recommend-gate（基于 #53 分支）改 CC 入场门与收集话术——与你的出口路由不同域；若发现同文件同区域改动，issue 评论对齐。

## 核心修改
_narrate_pipeline 出口路由：`form_requested(result_review)` / analysis-completed 出口绑定**结果审核收尾**（分析事实块驱动），TEXT_REPLY 仅保留给"本 turn 有新用户消息且无表单/派发出口"的场景。统一流水线上应是一处改、四步骤（tlc/cc/fp/re）全收益——分别加断言。

## 二元验收
issue #58 四条照抄执行写成测试；全量 pytest -m 'not real_llm' 绿 + ruff 干净（worktree 内 infra-gated skip 数照报）。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #58，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。合入窗口 root 攒批（与 #53/#57 同一次 BE 重启）。
