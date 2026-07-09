# S 任务：s3-issue-117

你是 s3（S2 只读调查 / S3 复核+实现+提交，按名字）。issue #117 正文是任务书。仓 BIC-agent-service，从 bench-verify（e1f8f3b）切 .wt/be-117 开分支 fix/issue-117-retry-narration（不 push/不 PR/不重启）。narrate 语域既有结论参照 _narrate_pipeline.py 与 #108 刚落的 SUBMIT_DISPATCHED 模板。并行 child .wt/be-115 动 event_ingress，别碰 ingress；你只动 narrate/事实块。完工按 issue 四条验收各具名测试，全量单测绿，评论 issue 转 已实现待复测。收尾 dispatch done（FACTS/Judgment 分开）。
