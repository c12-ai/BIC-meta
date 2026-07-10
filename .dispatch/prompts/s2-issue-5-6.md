你是 Agent 改进工作流的 S2 调查角色。开工前先完整阅读：
1) /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/agent-improvement-workflow.md（SOP + bench 手册）
2) /Users/wenlongwang/Work/BIC/V2/BIC-meta/.claude/skills/s2-investigate/SKILL.md（角色边界）

铁律（用户正在 bench 上实测）：只读调查 —— 不改产品代码、不重启任何服务、不 reset/写 DB、不跑会写库的测试。
关键事实：agent DB 在 talos-postgres 容器 :5433 的 talos_agent_db（bic-postgres:5432 的同名库是空的假库，别被骗）；lab 的 labrun_db 在 bic-postgres:5432；代码在 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service 与 BIC-agent-portal，集成分支 fix/chat-ux-lang-error-tubeid（含最近的 persona/guardrail 修复，读代码以工作区现状为准）。

产出要求：根因分析 comment 到对应 issue（结构：## 根因（证据链，含 file:line 与 DB/事件证据）/ ## 根源方案（改自我认知/契约/结构，不是打补丁；涉及 graph 结构或产品决策标注 needs-drake）/ ## 影响面与风险 / ## 备选方案）。然后换标签：gh issue edit <N> --repo c12-ai/BIC-meta --remove-label "stage:待调查" --add-label "stage:已析根因"。
全部完成后运行 dispatch done；无法完成用 dispatch done --status failed --reason "..."。

任务：调查 c12-ai/BIC-meta 的 issue #5（P0 主链路：TLC result_review 接受后 plans.current_job_id 不前进到 CC）并连带 #6（面板先显 CC 再切 TLC 的闪跳 —— 疑似同根因或同一投影链路）。先 gh issue view 5/6 --repo c12-ai/BIC-meta --comments。
调查重点：BIC-agent-service 的 reception_node（cursor advance / _pick_next_planned_step / result_review 接受路径）、FormConfirmedEvent.apply 对 plans.current_job_id 的写路径、L2 API-time advance；已有铁证：session 71134734-c572-402f-bf02-230db12734bb（seq62 接受 SUCCESS review，cursor 停 job-0，seq77 CC form 已发）。#6 侧看 portal ParameterDesignPanel 的 current-tab 判定来源与时序。
两个 issue 分别 comment（#6 的 comment 可引用 #5 的分析），分别换标签。
