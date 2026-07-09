硬性纪律：读 ops/agent-improvement-workflow.md（含外部 PR 对账）；改行为同步改测试写 WHY、门禁全绿才提交；commit footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；收尾 issue comment+换标签 stage:已实现待复测+dispatch done。
⚠️bench（各 repo 主目录 bench-verify 分支）正被用户手测：绝不碰主目录、绝不重启服务、绝不 reset/写 DB（agent/lab DB 都在 talos-postgres:5433）。你的全部工作在指定 worktree。
任务：实现 c12-ai/BIC-meta #35（用户拍板：补真实 rollup）——给 jobs.status 建立真实写入路径：从子 trials 状态派生 job 级 rollup（何时写：trial 状态变更的 apply 路径；语义对齐 ops/state-semantics-audit-2026-07-09.md 的权威表）。
worktree：git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add /Users/wenlongwang/Work/BIC/talos/.wt/be-35 -b fix/issue-35-jobs-rollup fix/chat-ux-lang-error-tubeid。
先 gh issue view 35 --repo c12-ai/BIC-meta --comments + 读审计报告"幽灵 rollup"节。rollup 规则（pending/in_progress/completed/failed 的派生）在 spec 写明（Rule 10）；含幂等与回放安全（事件溯源 apply 必须可重放）；单测覆盖各状态迁移。Refs c12-ai/BIC-meta#35。不 push。
