# S3 任务：修复 c12-ai/BIC-meta#62 — 参数设计子页签走 executor 术语表 + RE 词条统一

你是 S3（独立复核 + 实现 + 提交）。issue #62 正文是任务书（#52 的遗留面：子页签 SpecialistSubtabs 未走 StepStrip 已用的 workspace.stage.* 术语表；RE 两处中文词条不一致）。先复核，评论 issue，再实现。

## 工作区纪律
- 自建 worktree + 侧分支：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-62-subtab-glossary /Users/wenlongwang/Work/BIC/talos/.wt/portal-62 bench-verify`。
- 绝不碰 bench 主目录、不重启、不 push、不开 PR。
- 并行提示：#55/#56/#59/#60 的 portal 侧分支在飞——SpecialistSubtabs.tsx 应无重叠，撞了评论对齐。

## 二元验收
issue #62 照抄执行：子页签与步骤卡同用 workspace.stage.*、zh 两处一致、en 不变、RE 词条二选一去重（以既有术语表为准）、translation-parity 绿、组件测试断言。全量 vitest + tsc + 增量 biome 绿。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #62，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
