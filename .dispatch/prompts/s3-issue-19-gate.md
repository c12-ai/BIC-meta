你是 S3 评审+实现角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s3-resolve/SKILL.md（含「外部 PR 对账」）。
硬性纪律：独立复核 S2 结论；不 push 不开 PR；改行为同步改测试写 WHY、单测全绿才提交；commit 按内容拆、Refs c12-ai/BIC-meta#19、footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；收尾 comment+dispatch done。
⚠️并行隔离：你是 BE 链，只动 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service @ fix/chat-ux-lang-error-tubeid。⚠️agent/lab DB 都在 talos-postgres:5433。⚠️BE no-reload 运行中，勿重启。

任务：实现 c12-ai/BIC-meta #19 的「(a) 纵深防御」（用户已批准三块全做；portal 主修与 lab 错误分型已由前端链落地——portal f39d30e / lab 969e571）。先 gh issue view 19 --repo c12-ai/BIC-meta --comments 全量。
范围：dispatch 前对选中样品管调 lab POST /preparations/validate（端点已含 _validate_tlc_objects，与 create-gate 共判定），命中缺失/失效 → 按 PRD req 9 把 raw 400 转成"所选样品管已不存在，请回物料准备重选"的引导（走已有的失败叙述通道，不新增事件 kind）。闭合 refetch 与 submit 之间的 TOCTOU 竞态窗。
Rule 10：dispatch 契约变更同步 .trellis/spec 相关文件；commit 注明待 Drake 复核。
注意：BE 链前序（#20 等）已改 tools.py/_submit_l4 附近——基于工作区最新状态实现，与 #2 的 submit-rejection 叙述通道、#20 的收尾指引衔接自洽。
