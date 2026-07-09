你是 Agent 改进工作流的 S2 调查角色。开工前先完整阅读：
1) /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/agent-improvement-workflow.md（SOP + bench 手册）
2) /Users/wenlongwang/Work/BIC/V2/BIC-meta/.claude/skills/s2-investigate/SKILL.md（角色边界）

铁律（用户正在 bench 上实测）：只读调查 —— 不改产品代码、不重启任何服务、不 reset/写 DB、不跑会写库的测试。
关键事实：agent DB 在 talos-postgres 容器 :5433 的 talos_agent_db（bic-postgres:5432 的同名库是空的假库，别被骗）；lab 的 labrun_db 在 bic-postgres:5432；代码在 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service 与 BIC-agent-portal，集成分支 fix/chat-ux-lang-error-tubeid（含最近的 persona/guardrail 修复，读代码以工作区现状为准）。

产出要求：根因分析 comment 到对应 issue（结构：## 根因（证据链，含 file:line 与 DB/事件证据）/ ## 根源方案（改自我认知/契约/结构，不是打补丁；涉及 graph 结构或产品决策标注 needs-drake）/ ## 影响面与风险 / ## 备选方案）。然后换标签：gh issue edit <N> --repo c12-ai/BIC-meta --remove-label "stage:待调查" --add-label "stage:已析根因"。
全部完成后运行 dispatch done；无法完成用 dispatch done --status failed --reason "..."。

任务：调查 c12-ai/BIC-meta 的 issue #8（P1：进入 TLC 不预填可推导参数 rxn，反而聊天索要）。先 gh issue view 8 --repo c12-ai/BIC-meta --comments。
调查重点：TLC collecting_params 首 turn 的参数来源 —— objective 的 rxn 如何（不）流入 params_draft；对比 FP 的确定性预填先例（reception_node 的 prefill_containers）与 TLC→CC 的 carry-forward 先例（06-21-cc-carryforward）；评估「代码确定性预填 objective.rxn 进 TLC draft」vs「靠模型首 turn 调 update_tlc_params」的根源方案取舍。铁证：session 9e310230 seq527（聊天索要 Rf 范围，无 form）vs session 9a2c507a seq437-443（正确形状）。
