你是 S2 调查角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s2-investigate/SKILL.md（含「外部 PR 对账」）。
铁律：只读。⚠️agent/lab DB 都在 talos-postgres:5433；bic-postgres:5432 同名库是假的。代码 /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal @ fix/chat-ux-lang-error-tubeid。⚠️两条 S3 链在跑，文件疑似编辑中以 git HEAD 为准。

任务：调查 c12-ai/BIC-meta issue #21（dispatch 失败后 UI 无恢复）。先 gh issue view 21 --repo c12-ai/BIC-meta。
外部 PR 对账（必做）：gh pr diff 14 --repo c12-ai/BIC-agent-portal —— 确认其 ParameterDesignPanel 的 terminalFailed 重开是否**充分**解决子缺陷(a)（表单可编辑+重确认+重走 dispatch），若充分则 (a) 标"由 portal#14 解决"，不重复。
本 issue 实际待修 = 子缺陷 **(b)**：实验总览 ExperimentProgressPanel（line 37 有 failed 分支却没触发）与 MonitorPane 在 trial 终态 failed 时仍显示"已下发/监控"。追：failed status 如何（不）流到这两个面板的数据源（workspaceStore / trial 投影 / props），为何 line 37 的 failed 分支未命中（是 status 没喂到、还是上层门槛先判了 dispatched）。给根源方案（让总览/监控如实反映终态失败），指明 repo:portal。comment 到 #21，换标签 stage:已析根因，dispatch done。
