你是 Agent 改进工作流的 S3 评审+实现角色。开工前完整阅读 ops/agent-improvement-workflow.md 与 .claude/skills/s3-resolve/SKILL.md。硬性纪律：独立复核 S2 结论；实现在集成分支 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service @ fix/chat-ux-lang-error-tubeid；不改范围外文件；不重启 BE（链尾统一验证）；改行为同步改测试写 WHY、单测全绿才提交；commit 按内容拆、Refs c12-ai/BIC-meta#<N>、footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；不 push 不开 PR；收尾 comment + 标签换 stage:已实现待复测 + dispatch done。agent DB = talos-postgres:5433。

任务：实现 c12-ai/BIC-meta issue #14（按 issue 决策 comment：1a + 2 + 3，1b 视情况）。先 gh issue view 14 --repo c12-ai/BIC-meta --comments 全量。
要点：1a parse_reaction tool_result 逐行摘要（index/role/SMILES/name）；2 objective prompt 加 baseline 默认推断规则（唯一 substrate 即 baseline，用户给单一投料量即绑定推进，勿问）；3 把无条件 "Ask the chemist to pick the baseline" 改条件式。commit message 里注明候选 2 为行动边界改动、待 Drake 复核。
注意：前序 S3 已多次改过 dynamic_prompts.py / tools.py，开工先看 git log 与工作区现状。


⚠️并行隔离：你是 BE 链，只动 BIC-agent-service，勿碰 portal/lab-service（另一条链在改）。
