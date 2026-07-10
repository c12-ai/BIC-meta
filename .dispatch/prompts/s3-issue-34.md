你是 S3 评审+实现角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s3-resolve/SKILL.md（含外部 PR 对账）。
硬性纪律同前；不 push 不开 PR；commit Refs c12-ai/BIC-meta#34；footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；收尾 comment+换标签+dispatch done。
⚠️前端链：只动 /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal @ fix/chat-ux-lang-error-tubeid（已 rebase 含 PR#14 的 main）。⚠️本地保留不提交：tests/helpers.ts、cc-re-chained-flow.spec.ts baseURL 行。
任务：实现 #34（先 gh issue view 34 --repo c12-ai/BIC-meta + 读 BIC-meta/ops/state-semantics-audit-2026-07-09.md 第三节 portal 分区的精确 file:line）：lifecycleForTrial 与 ParameterDesignPanel subtab 改读权威 trial.status 判终态（与 #21/#14 已修面一致）；补 derive-routing 终态用例（Rule 7 写 WHY）。范围外：18 个存疑点（属后续 refactor/state-semantics 批）。
