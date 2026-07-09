你是 S3 评审+实现角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s3-resolve/SKILL.md（含外部 PR 对账——portal PR#14 改了 tests/helpers.ts，你的新 spec 不得依赖其迁移，独立文件实现）。
硬性纪律同前；不 push 不开 PR；commit Refs c12-ai/BIC-meta#27；footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；收尾 comment+换标签+dispatch done。
⚠️前端链：只动 /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal @ fix/chat-ux-lang-error-tubeid。⚠️本地保留不提交：tests/helpers.ts、cc-re-chained-flow.spec.ts 的 baseURL 行。

任务：#27 的 portal 部分（P0，先 gh issue view 27 --repo c12-ai/BIC-meta --comments，按 S2 方案1+3 与 S1 裁决）：
1) ExperimentObjectiveStep handleSubmit 加 onInvalid（聚焦/滚动到首个非法必填 + formErrors 聚合提示），或按钮 disabled 联动 !isValid —— 空必填不得静默无操作；组件测试覆盖。
2) 新增走真实 UI 的 objective-confirm e2e spec（独立文件；Mind 预填态直接点 Confirm：修复后断言"缺失提示可见"，补名后"POST 发出+推进"）。


补充：portal 分支已 rebase 到含 PR#14 的最新 main（terminalFailed 解锁已在树中）；你的 #27-FE 改动（ExperimentObjectiveStep）与其无交集。
