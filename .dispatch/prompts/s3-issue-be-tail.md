你是 S3 评审+实现角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s3-resolve/SKILL.md（含外部 PR 对账，注意 agent-service PR#66）。
硬性纪律：独立复核 S2 结论；不 push 不开 PR；改行为同步改测试写 WHY、单测全绿才提交；commit 按内容拆、Refs 各 issue、footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；收尾各 issue comment+换标签+dispatch done。
⚠️BE 链：只动 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service @ fix/chat-ux-lang-error-tubeid。⚠️DB=talos-postgres:5433。⚠️no-reload 勿重启。graph/契约结构改动 commit 注明待 Drake 复核。

**BE narrate 硬化统一批**（P0 优先，先 gh issue view 28 27 29 24 31 --repo c12-ai/BIC-meta --comments 全量，特别是 #28 的 S2 残余缺口三条方案与 #27 的 S1 裁决 comment）：
1) **#28（P0，三条全做）**：narrate 注入确定性进度投影（per-job/trial 真实状态 ground-truth）+ no-fab 扩到世界状态断言（禁宣称无 completed trial 的步骤完成）+ 过渡 turn 走确定性文案；CC 入场即确定性 recommend（扩 _auto_recommend_node 到 entry）；narrate 输出后处理（<think> 剥离[=#24]、单响应重复段折叠、finish_reason==length 退化回退确定性文案、cc/tlc 补 recursion_limit=25）。
2) **#27 BE 半（P0）**：confirm_goal 的 _objective_reactant_rows_from_goal 停止丢弃 parse 已带的 name（透传 name=）；taskName 默认归属不改（留 Drake，见 issue 裁决 comment）。
3) **#29**：narrate 权威值投影（与 1 的进度投影同机制，TLC params 实际值）。
4) **#24**：已并入 1 的 think 剥离，单独回填该 issue。
5) **#31 part-1**：CC 提示词锚定"载样物料=样品柱"正词。
按 issue 分组 commit；#28 的结构改动逐条在 commit body 注明 needs-drake。
