# S3 任务：c12-ai/BIC-meta#103 — 草稿期化合物名自动填写

你是 S3（独立复核 + 实现 + 提交）。issue #103 正文是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（e5c5a12+）切工作树 .wt/be-103 开分支 fix/issue-103-draft-name-enrichment（不 push/不 PR/不重启服务）。

## 要点
- 基线是 bench-verify（含 #94/#95/#97/#98 合并），不是 origin/main。
- 参照 issue 任务 1：先读 #95 的确认点补名实现（SessionService）与 #94/#97 的 update_objective_params 草稿持久化通道，选挂点；单挂点能同时覆盖草稿+确认就收敛为单挂点。
- 只动补名路径；基线/clarify 路由是 #102 的地盘，别碰。
- 台架 chem-service 在 127.0.0.1:8010 活着，可做一次真连通对照（测试仍用 fake）。

## 二元验收
issue #103 四条照抄执行，每条一个具名测试。全量 `uv run pytest tests/unit -m 'not real_llm'` 绿（#101 已知闪失单跑复核即可）。

## 收尾
修复摘要（sha、测试计数）评论 issue #103，标签 stage:待调查 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
