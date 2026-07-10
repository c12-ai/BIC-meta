# S3 任务：BIC-meta#158 — TLC 达标话术改审核引导

你是 S3（实现 + PR，列车口径）。issue #158 正文是任务书。仓：BIC-agent-service，从 origin/main（b3fc35b）切工作树 .wt/be-158 开分支 fix/issue-158-eval-pass-narration。**注意台架 BE 检出树上有未合并的 intent_classifier 工作区补丁（e2e-browser 的）——你在工作树干活不受影响，别碰主检出。**并行 .wt/be1-pr23 在动 jobs/trials 状态层，你只动 narrate 模板层。
按 issue 验收执行；完成 PR 合并（CI 绿 + admin-merge 留痕），评论 issue 转 已实现待复测；dispatch done（FACTS/Judgment 分开）。
