# S3 任务：#128 BE-1 · PR-1 切片 — L2 verdict 顶层投影（无迁移）

你是 S3（实现 + PR，列车授权口径）。任务书 = #128 的 BE-1 设计笔记（comment-4932228473）⑤ 切片中的 PR-1 + root 裁定（新列基线；本切片无迁移）。仓：BIC-agent-service，从 origin/main（1d9fb7a）切工作树 .wt/be1-pr1 开分支 feat/issue-128-be1-pr1-verdict-projection。

## 范围（严格 PR-1，不越界到 PR-2/3）
task_result_analyzed 事件载荷加顶层 `verdict`（从 analysis.criteria 确定性铸造，#11 权威源不动）；DTO/快照投影同步；spec（Rule 10）。不加列、不动 trial.status/jobs、不动 FE。设计笔记 ② 列的 6 个受影响 apply 中只触达本切片相关者，逐一在 PR 描述对账。

## 二元验收
具名测试：criteria 全 pass→verdict=pass、任一 fail→fail、无 criteria→null（三例）；既有 #11/#116 读侧不回归；全量单测绿；CI 绿合并（admin-merge 留痕）。

## 收尾
sha 评论 #128（注明 PR-1 落地、PR-2/3 等 ST-1）；dispatch done（FACTS/Judgment 分开）。
