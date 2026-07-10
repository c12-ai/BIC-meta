你是 Agent 改进工作流的 S2 调查角色。开工前先完整阅读：
1) /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/agent-improvement-workflow.md（SOP + bench 手册）
2) /Users/wenlongwang/Work/BIC/V2/BIC-meta/.claude/skills/s2-investigate/SKILL.md（角色边界）

铁律（用户正在 bench 上实测）：只读调查 —— 不改产品代码、不重启任何服务、不 reset/写 DB、不跑会写库的测试。
关键事实：agent DB 在 talos-postgres 容器 :5433 的 talos_agent_db（bic-postgres:5432 的同名库是空的假库，别被骗）；lab 的 labrun_db 在 bic-postgres:5432；代码在 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service 与 BIC-agent-portal，集成分支 fix/chat-ux-lang-error-tubeid（含最近的 persona/guardrail 修复，读代码以工作区现状为准）。

产出要求：根因分析 comment 到对应 issue（结构：## 根因（证据链，含 file:line 与 DB/事件证据）/ ## 根源方案（改自我认知/契约/结构，不是打补丁；涉及 graph 结构或产品决策标注 needs-drake）/ ## 影响面与风险 / ## 备选方案）。然后换标签：gh issue edit <N> --repo c12-ai/BIC-meta --remove-label "stage:待调查" --add-label "stage:已析根因"。
全部完成后运行 dispatch done；无法完成用 dispatch done --status failed --reason "..."。

任务：为 c12-ai/BIC-meta 的 issue #9（步骤失败被接受后的推进策略未定义，needs-drake）产出**决策备忘录**（不是代码修复方案）。先 gh issue view 9 --repo c12-ai/BIC-meta --comments。
备忘录内容：现状证据（失败接受后停滞，无引导）；三个候选策略的完整对比 —— (a) 带失败上下文照常推进 (b) 阻塞要求重跑/改参 (c) 给用户显式选项（重跑/跳过推进/终止）：各自的化学合理性、PRD 修改点（Production-PRD 哪一节）、agent-service spec/实现影响面、UI 影响；给 Drake 的推荐项 + 理由。可参考 Production-PRD.md（/Users/wenlongwang/Work/BIC/V2/BIC-meta/）与 bench playbook 中 cross-step failure 的 open question。comment 到 issue #9 后换标签。
