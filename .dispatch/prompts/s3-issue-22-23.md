你是 S3 评审+实现角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s3-resolve/SKILL.md（含「外部 PR 对账」——开工先扫三 repo open PR，特别注意 agent-service PR#66 是否已合入/是否碰 query_agent.py/user_admittance.py）。
硬性纪律：独立复核 S2 结论；不 push 不开 PR；改行为同步改测试写 WHY、单测全绿才提交；commit 按内容拆、Refs c12-ai/BIC-meta#<N>、footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；收尾 comment+标签换 stage:已实现待复测+dispatch done。
⚠️BE 链，只动 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service @ fix/chat-ux-lang-error-tubeid。⚠️agent/lab DB=talos-postgres:5433。⚠️BE no-reload 运行中勿重启。

任务：实现两个 issue（先 gh issue view 22 23 --repo c12-ai/BIC-meta --comments 全量）：
1) **#22**（S2 三条方案全做）：query_agent 增 devices 维度分支 + 修分派优先级（任务/汇总/整体 →_lab_overview 合流出口，覆盖设备/任务/机器人/库存四维）+ compose prompt 区分「空集」vs「未查询」。S2 已给精确 file:line。补四类查询路由的单测。
2) **#23**（S2 方案 1+2 最小闭环）：_QUERY_COMPOSE_SYSTEM_PROMPT 换 Talos 一体人设（对齐 _TALOS_IDENTITY，能力如实介绍）+ user_admittance 的 off_topic user_facing_message 不得捏造能力否认（能力元问题不属 off_topic）。方案 3（能力介绍意图路由，graph 结构）不做——needs-drake，comment 里注明留待决策。
注意：#20 已在同分支落 6 个 commit（narrate 层），工作区以最新为准；#8 的 S3 可能刚跑完同文件——git log 先看。

基底更新（2026-07-09 rebase 后）：分支已 rebase 到含 #68 的 main（narrate grounding / dispatch redirect / recognition_mode / reset dev seed 都在基底），全量 1258 单测绿。你的 query_agent/user_admittance 改动与 #68 无文件冲突，但实现前先读 #68 对 query/admittance 有无相邻语义（git log origin/main -1 -p -- app/runtime/graphs/nodes/query_agent.py app/runtime/graphs/nodes/user_admittance.py）。
