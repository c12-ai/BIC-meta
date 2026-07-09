你是 Agent 改进工作流的 S2 调查角色。开工前完整阅读 ops/agent-improvement-workflow.md 与 .claude/skills/s2-investigate/SKILL.md。
铁律：只读调查 —— 不改产品代码、不重启服务、不 reset/写 DB（用户正在 bench 测试）。
并发提示：一个 S3 正在同一 BE 工作区实现别的 issue —— 文件疑似编辑中时以 git 已提交状态为准（git show HEAD:<path>）并注明基准 commit。
关键事实：agent DB = talos-postgres:5433 的 talos_agent_db；代码 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service 与 BIC-agent-portal @ fix/chat-ux-lang-error-tubeid。
产出：根因分析 comment 到 issue（## 根因(证据链 file:line+DB) / ## 根源方案 / ## 影响面与风险 / ## 备选），换标签 stage:待调查→stage:已析根因，dispatch done。

任务（两个 issue 分别 comment + 换标签）：
1) issue #15：objective→plan 自动链叙述错序（桥接叙述在前、表单后无收尾叙述；propose 叙述疑似被路由进 reasoning 而非 text_done）。追 plan_subgraph 的 narrate 拓扑与 auto-run 链（7d2b1ba）的叙述时序；对照 9e310230（有收尾）vs d909cdd8（无收尾）两个 session 找分岔条件。
2) issue #16：终结工具调用纪律失效三症状 —— (a) request_plan_confirmation 一 turn 双发（两个 tool_call_id 都有结果；prompt 禁令挡不住 → 评估结构性 once-gate，参照 _SUBMIT_LOCKS/guardrail 先例）；(b) FE thinking 工具卡在 tool_result 已持久化时仍挂「待处理」（查 portal ThinkingSection/chatStore 的 tool_call↔tool_result 配对：流式 tool_call 事件与 tool_result 的 id 对齐）；(c) TLC turn 叙述宣称「已请求澄清」但无任何 request_clarification tool_result（seq 585/587）—— 行动宣称与实际工具执行脱钩的契约缺失（与 #12 的送达契约、narrate 契约相邻，注意引用其 S2 结论避免方案冲突）。
铁证入口：session d909cdd8 seq 555-588；对照 9a2c507a seq 423/424。
先 gh issue view 15 / 16 --repo c12-ai/BIC-meta --comments。
