# S3 任务：BIC-meta#159 — 步骤生命周期面板自动跳转 + 间隙 loading

你是 S3（实现 + PR，列车口径）。issue #159 正文是任务书。仓：BIC-agent-portal，从 origin/main（4055ee7+，fetch 确认）切工作树 .wt/fe-159 开分支 feat/issue-159-step-nav。
- 事件源读 workspaceStore/事件派生现状（#123 的 monitor-exec-status、#116 的 result-stage-status 是你的语义基石）；跳转编排建议独立小模块（如 step-nav-orchestrator），一次事件一次跳、用户操作优先。
- e2e-browser 在台架跑 Playwright——你在工作树，别动台架 :5173；tests/helpers.ts 不入提交。
按 issue 四条验收执行；PR 本地门禁全链绿后合并（无远端 CI 仓口径：门禁数字贴 PR），评论 issue 转 已实现待复测；dispatch done（FACTS/Judgment 分开）。
