你是 Agent 改进工作流的 S3 评审+实现角色。开工前完整阅读 ops/agent-improvement-workflow.md 与 .claude/skills/s3-resolve/SKILL.md。
硬性纪律：独立复核 S2 结论（一手重推导，有误 comment 异议+dispatch ask --wait，不硬实现）；改行为同步改测试写 WHY、相关单测全绿才提交；commit 按内容拆、Refs c12-ai/BIC-meta#<N>、footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；不 push 不开 PR；收尾 comment（实现摘要+commit+测试数字+待复测说明）+ 标签换 stage:已实现待复测 + dispatch done。
⚠️关键：agent DB 与 lab DB 都在 talos-postgres 容器 :5433（talos_agent_db / labrun_db）；bic-postgres:5432 同名库是假的。⚠️BE 当前以 no-reload uvicorn 跑，改 BE 源码不会热重载不中断用户；仍不得擅自重启（链尾统一验证）。
⚠️⚠️并行隔离：此刻有两条 S3 链在跑。
你这条是 BE 链，只动 BIC-agent-service。绝对不要碰 BIC-agent-portal 与 BIC-lab-service（另一条链在改它们）。BE 内部你与后续 BE 任务串行，收到本任务即轮到你。

任务：实现 c12-ai/BIC-meta **元 issue #20**（叙述层统一重构），覆盖 #12/#15/#16的(a)(c)/#17/#18。先 gh issue view 20 12 15 16 17 18 --repo c12-ai/BIC-meta --comments 全量（#16 的 S2 方案有 (a)once-gate/(c)语域契约的具体候选与 file:line；#20 有拍板的 5 条契约）。
范围（BE 内）：
1. 终结工具 once-gate（结构性，参照 _SUBMIT_LOCKS/Guardrail 先例；覆盖 request_plan_confirmation + request_params_confirmation）。
2. request_clarification 问题原文确定性一等通道 emit_clarification（#12(a)，5 个 specialist 统一，勿只改 objective）。
3. 叙述宣称不变量：narrate 收尾由真实终结状态驱动，禁止宣称当 turn 无 tool_result 的动作。
4. 语域归位（#17）：面向用户请求进 text_done 不进 reasoning。
5. 叙述收尾指向待办（#15/#18）：form_requested 后收尾必含下一步指引；修 objective→plan 自动链的收尾错序。
6. prose-only abandon 结构兜底（collecting_params）。
按症状分组 commit，分别回填各 issue（#12/#15/#16/#17/#18 + #20）。graph/契约结构改动在 commit 注明待 Drake 复核，Rule 10 同步 .trellis/spec。
注意：#16 的 (b) FE 配对键属 portal，**不在你范围**（另一条链做）。
