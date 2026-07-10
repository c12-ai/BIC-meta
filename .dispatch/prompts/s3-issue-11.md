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

任务：实现 c12-ai/BIC-meta issue #11（= #9 一期止血 + #7 根因修复，已合并）。先读 gh issue view 11 / 7 / 9 --repo c12-ai/BIC-meta --comments（#7 有完整根因证据链，#9 有决策 comment）。
范围：verdict 投影进 done 阶段（system prompt / workflow context / narrate 特判）+ 失败 accept 后诚实陈述失败并在聊天里询问化学家下一步（重跑/照常推进/终止，自然语言）。
范围外（勿动）：cursor 推进语义（等 #5）；结构化三选项 UI（二期）；#10 的语言常量（后续 S3 做，避免冲突 —— 你若改到叙述 prompt，保持与现有语言指令风格一致即可）。
收尾 comment 同时回填 #11 和 #7（#7 的根因被此实现覆盖）。
