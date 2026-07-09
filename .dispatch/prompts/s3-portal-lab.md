你是 Agent 改进工作流的 S3 评审+实现角色。开工前完整阅读 ops/agent-improvement-workflow.md 与 .claude/skills/s3-resolve/SKILL.md。
硬性纪律：独立复核 S2 结论（一手重推导，有误 comment 异议+dispatch ask --wait，不硬实现）；改行为同步改测试写 WHY、相关单测全绿才提交；commit 按内容拆、Refs c12-ai/BIC-meta#<N>、footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；不 push 不开 PR；收尾 comment（实现摘要+commit+测试数字+待复测说明）+ 标签换 stage:已实现待复测 + dispatch done。
⚠️关键：agent DB 与 lab DB 都在 talos-postgres 容器 :5433（talos_agent_db / labrun_db）；bic-postgres:5432 同名库是假的。⚠️BE 当前以 no-reload uvicorn 跑，改 BE 源码不会热重载不中断用户；仍不得擅自重启（链尾统一验证）。
⚠️⚠️并行隔离：此刻有两条 S3 链在跑。
你这条是前端/实验室链，只动 BIC-agent-portal 与 BIC-lab-service。绝对不要碰 BIC-agent-service（另一条链在改它）。

任务：串行实现两个 issue 的**非 BE 部分**，都不碰 agent-service：
1. **#16 (b) FE 配对键单一来源**（repo:portal）：以 tool_call_id 为唯一 tool_call↔tool_result 配对键（events.ts:ToolResultEvent 补 tool_call_id，finalizeToolResult 删 ?? event_id 回退），修 thinking 工具卡孤儿-待处理悬挂。见 #16 S2 方案 (b)。Rule 10：wire 契约字段变更同步 spec/类型。仅做 (b)，#16 的 (a)(c) 属 BE 链。
2. **#19**（repo:portal + repo:lab-service，用户批准三块全做）：
   - (b) lab 错误分型（BIC-lab-service）：command_validator.py:598 与 preparation_service.py:555 的合并判断拆成"box_row is None → does not exist in lab inventory" 与 "!=2ml → is not a 2ml tube box"。
   - (a) 主修（portal）：TLC 选择面 confirm 前强制 refetch sample-tube-boxes + 剔除已失效的选中管（见 #19 S2 方案 F/主修）。
   - (a) 纵深（**注意：此项属 agent-service dispatch 前硬闸，不在你范围** —— 只在 #19 comment 里标注"纵深硬闸留给 BE 链"，由 root 另行安排；你只做 portal+lab 两块）。
先 gh issue view 16 19 --repo c12-ai/BIC-meta --comments。分别回填 #16(仅标注(b)完成)/#19，换标签。
