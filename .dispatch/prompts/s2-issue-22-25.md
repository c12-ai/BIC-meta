你是 S2 调查角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s2-investigate/SKILL.md（含「外部 PR 对账」——先扫 gh pr list 三个 repo）。
铁律：只读。⚠️agent/lab DB 都在 talos-postgres:5433；bic-postgres:5432 同名库是假的。⚠️一条 S3 链在 BE 工作区跑（#8），文件疑似编辑中以 git HEAD 为准并注明基准 commit。代码 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service @ fix/chat-ux-lang-error-tubeid。

任务（P1 两个深查，P2/P3 两个轻查；四个 issue 分别 comment + 换标签 stage:已析根因，然后 dispatch done）：
1) **#22** 实验室查询不查实时数据：追 query_agent 的数据源（注入快照 vs lab-service 实时 API）、为何 devices/tasks 维度缺失、"空集≠不可得"的诚实性修复点。原始 findings 在 BIC-meta/.dispatch/findings/t-challenge/001,002。
2) **#23** 能力自我否认：追 user_admittance 判定逻辑 + query_agent 人设（query_agent.py:32 附近"实验室状态查询助手"）为何未纳入 _TALOS_IDENTITY（f7b8ef2 只改了 5 个子图 header）；方案 = persona 统一收尾 + admittance 对能力元问题的正确路由（介绍能力≠超范围请求）。finding 006。
3) **#24** <think> 标签泄漏：找 text_done 的输出路径（narrate → TextDoneEvent），设计确定性剥离推理标记的挂点（含单测）。finding 005。轻查即可。
4) **#25** mock stub 化合物：确认 Mind mock（med005_fixture）对非 MED005 分子的返回行为；给两个修复方向（demo 分子补真实 fixture / stub 显式降级呈现）的取舍建议，标注哪个属 bench 配置哪个属产品。finding 004。轻查即可。
