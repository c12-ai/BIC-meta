# S3 任务：修复 c12-ai/BIC-meta#69 — reject/重做路径不返工 + Rf 数值截断

你是 S3（独立复核 + 实现 + 提交）。issue #69 正文是任务书——**注意边界框定**：失败 accept 自动进 CC 是既有裁定不许改；失败实验 ELN 可导出按 PRD 属 by design 不动；只修 reject/重做路径 + 数值截断。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-69-reject-rework /Users/wenlongwang/Work/BIC/talos/.wt/be-69 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。
- 复核点：FormConfirmedEvent 对 result_review 的 accept/reject 分支（#40 后 FE 事件带 accept 标志；BE apply 的 reject 分支终态化语义）、reception 对 rejected review 的路由（为何自动进 CC）、"请求重做"的用户话语走哪条路被误判为 accept。
- 与 #63（plan-reject 空转）同族：如果一处 reject-closing 机制能同时服务两者，优先统一实现（但 #63 的修复不在本 issue 验收内，别扩 scope，评论互引即可）。
- 04-3 数值截断：定位 '0.51'→'51' 的出口处理根因（疑 scrub/dedupe/模板），修复并锁测试。

## 二元验收
issue #69 四条照抄执行写成测试。全量单测绿 + ruff 干净。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #69，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
