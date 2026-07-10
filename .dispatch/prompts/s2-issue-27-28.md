你是 S2 调查角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s2-investigate/SKILL.md（含「外部 PR 对账」——先扫三 repo open PR，注意 agent-service PR#66/portal PR#14 是否碰你要查的文件）。
铁律：只读；不重启（T 系列可能复跑）；⚠️agent/lab DB 都在 talos-postgres:5433。⚠️一条 S3 链在 BE 工作区跑（#14），文件疑似编辑中以 git HEAD 为准并注明基准 commit。原始 findings：BIC-meta/.dispatch/findings/t-main/。

任务（两个 P0 深查，分别 comment + 换标签 stage:已析根因，dispatch done）：
1) **#27** objective 确认死锁：追 (a) portal ObjectiveForm 确认按钮对必填缺失的静默拦截点（为何 0 POST 无提示）；(b) Mind mock/parse_reaction 为何名称字段留空（与 #25 stub 同域）；(c) e2e 为何用 API 绕过 UI 确认（掩盖机制）——给"UI 路径必须有 e2e 覆盖"的补测方案。
2) **#28** TLC accept 后幻觉下游全完成+重复12次：⚠️注意工作区已有未生效修复（#16c 宣称不变量 660583f、once-gate 8fa3be7、#20 收尾指引 adfca83）——你的任务是判定：这些已落地修复能否覆盖本症状？逐条对照（重复12次→once-gate/anti-stall 管不管这种 narrate 重复？"未跑说成完成"→宣称不变量管终结工具动作，管不管步骤完成度宣称？）。给出"已覆盖/部分覆盖/未覆盖"结论与残余缺口的补充方案（如 workflow-context 的 verdict/进度投影强化）。这直接决定统一验证窗口的复测预期。
