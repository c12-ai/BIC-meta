# S3 任务：c12-ai/BIC-meta#97 — 收割用户已给的目标 Rf 窗口并自动推荐

你是 S3（独立复核 + 实现 + 提交）。issue #97 正文是任务书（设计要点 + 四验收）。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-97-window-harvest /Users/wenlongwang/Work/BIC/talos/.wt/be-97 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。
- **强协同 #94**（在飞，同在 objective 抽取链）：先看 .wt/be-94 分支进展；抽取增强点共用一处（评论互相对齐，必要时基于其分支续做并注明）；绝不两套抽取。
- 播种落点对齐 #39 的 seed 路径（build_tlc_objective_seed / plan-confirm PARENT-Command / dispatcher persist），窗口值随 rxn 同通道持久化（防 #39 同款 in-memory-only 坑）。

## 二元验收
issue #97 四条照抄执行写成测试。全量单测绿 + ruff 干净。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #97，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
