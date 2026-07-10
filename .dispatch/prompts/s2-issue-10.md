你是 Agent 改进工作流的 S2 调查角色。开工前先完整阅读：
1) /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/agent-improvement-workflow.md（SOP + bench 手册）
2) /Users/wenlongwang/Work/BIC/V2/BIC-meta/.claude/skills/s2-investigate/SKILL.md（角色边界）

铁律（用户正在 bench 上实测）：只读调查 —— 不改产品代码、不重启任何服务、不 reset/写 DB、不跑会写库的测试。
关键事实：agent DB 在 talos-postgres 容器 :5433 的 talos_agent_db（bic-postgres:5432 的同名库是空的假库，别被骗）；lab 的 labrun_db 在 bic-postgres:5432；代码在 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service 与 BIC-agent-portal，集成分支 fix/chat-ux-lang-error-tubeid（含最近的 persona/guardrail 修复，读代码以工作区现状为准）。

产出要求：根因分析 comment 到对应 issue（结构：## 根因（证据链，含 file:line 与 DB/事件证据）/ ## 根源方案（改自我认知/契约/结构，不是打补丁；涉及 graph 结构或产品决策标注 needs-drake）/ ## 影响面与风险 / ## 备选方案）。然后换标签：gh issue edit <N> --repo c12-ai/BIC-meta --remove-label "stage:待调查" --add-label "stage:已析根因"。
全部完成后运行 dispatch done；无法完成用 dispatch done --status failed --reason "..."。

任务：调查 c12-ai/BIC-meta 的 issue #10（P2：objective 确认叙述偶发英文），并按 issue 里的建议做**全量盘点**：扫出 BIC-agent-service 所有 narrate/叙述类 prompt（objective/plan/tlc/cc/re/fp 各子图 + query_agent + user_admittance 拒绝路径），逐一列表标注哪些已有语言跟随指令（先例：plan propose/confirm 已修，commit a8f2ec3 与 f7b8ef2）、哪些缺失。先 gh issue view 10 --repo c12-ai/BIC-meta --comments。
根源方案应考虑：语言跟随是否该收敛为共享常量（类似 NARRATE_NO_ECHO_RULE 的挂载方式）一次覆盖全部叙述点，而非每处各写一句。铁证：session 9e310230 seq514。
