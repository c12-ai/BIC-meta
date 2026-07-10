# S3 任务：c12-ai/BIC-meta#96 — 澄清应答首次误路由修复

你是 S3（调查 + 独立复核 + 实现 + 提交）。issue #96 正文是任务书（含实验 id 0d1e33f7 与两 turn 对照要求）。先 DB 还原两个 turn 的完整路由证据链（admittance verdict / reception dispatch_source / 落到哪个子图），结论评论 issue，再实现。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-96-clarify-routing /Users/wenlongwang/Work/BIC/talos/.wt/be-96 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。DB 只读。
- 参考：agent-service#62 评审回帖（短确认路由张力点）与 route_after_admit/reception 的 stage 门；#94 在飞（基线自动判定会减少这类澄清，但澄清存在时的路由正确性独立成立——两者互补不互替）。
- 并行提示：BE 在飞 #89/#93/#94/#95——路由域与 #94 可能相邻（同在 objective 链），先看其分支改动，评论对齐。

## 二元验收
issue #96 四条照抄执行写成测试。全量单测绿 + ruff 干净。

## 收尾
路由证据链 + 修复摘要（sha、测试计数）评论 issue #96，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
