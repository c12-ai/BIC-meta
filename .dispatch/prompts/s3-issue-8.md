你是 Agent 改进工作流的 S3 评审+实现角色。开工前完整阅读：
1) /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/agent-improvement-workflow.md（SOP + bench 手册 + 变更纪律）
2) /Users/wenlongwang/Work/BIC/V2/BIC-meta/.claude/skills/s3-resolve/SKILL.md（角色边界）

硬性纪律：
- 独立复核 S2 结论（从代码/DB 一手重推导），发现分析有误就 comment 异议并 dispatch ask --wait 上报，不硬实现。
- 实现在集成分支上：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service @ fix/chat-ux-lang-error-tubeid（portal 同名分支）。工作区里 portal 的 tests/helpers.ts 与 cc-re-chained-flow.spec.ts 的 baseURL 改动保持本地，绝不提交。
- 当前只有你一个 S3 在跑（串行链），但不得改 issue 范围外的文件。
- 需要重启 BE 验证时：先 dispatch ask --wait 询问（用户可能正在 bench 测试），得到允许才重启；重启后告知需刷新页面。
- 测试纪律：改行为必须同步更新断言旧行为的测试并写明 WHY；相关单测全绿后才提交。
- 提交：按内容拆 commit，message 引用 Refs c12-ai/BIC-meta#<N>，footer 带 Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT。不 push、不开 PR。
- 收尾：把「实现摘要 + commit 哈希 + 测试数字 + 二元验收执行证据（或待复测说明）」comment 到 issue，标签换 stage:已实现待复测（gh issue edit <N> --repo c12-ai/BIC-meta --remove-label "stage:已析根因" --add-label "stage:已实现待复测"），然后 dispatch done。
关键事实：agent DB 在 talos-postgres:5433 的 talos_agent_db（bic-postgres:5432 同名库是假的）；qwen3.7-plus 有非确定性，prompt 类修复的验收按概率取证。

任务：实现 c12-ai/BIC-meta issue #8 的 **Part 1**（S2 comment 中的「根源方案 Part 1」：reception_node 给 TLC 种 objective.reaction_smiles 进 params_draft + TLC collecting_params prompt 告知已预填勿索要 + 从 exit-B 可索要字段删 rxn）。先读 gh issue view 8 --repo c12-ai/BIC-meta --comments。
明确范围外：Part 2（form-first 交互契约）已标 needs-drake，**不得实现**；验收里"首 turn 即 form_requested"属于 Part 2，本次验收只覆盖 Part 1 的两条：from_user.rxn 预填非空 + 聊天不索要 rxn。
注意：前一个 S3（issue #11）刚在同分支提交过 dynamic_prompts.py 相关改动 —— 开工先 git log/pull 工作区现状，基于最新代码实现。

任务更新（用户裁决后追加）：#8 的 Part 2 已解锁（用户裁决 form-first，见 issue 最新 comment）—— 与 Part 1 一并实现：进入步骤即自动预填上下文可得项并发出表单（确定性冷派发 emit 路径），必填缺失项由叙述引导（右侧输入或直接回复）；交互契约变更按 Rule 10 同步 .trellis/spec 相关文件；commit 注明待 Drake 复核。二元验收恢复 issue 原文全量（含"首 turn 即 form_requested"）。


⚠️并行隔离：你是 BE 链，只动 BIC-agent-service，勿碰 portal/lab-service（另一条链在改）。
