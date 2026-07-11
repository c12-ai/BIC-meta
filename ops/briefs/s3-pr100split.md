# S3 任务：协助迁移 service#100 —— narrate 修复迁入 #194 单源，直接提交到 PR 分支

你是 S3（协作修缮，**直接 commit 到同事的 PR 分支** `fix/plan-propose-narrate-fixed-workflow`，用户已授权）。对象 = c12-ai/BIC-agent-service PR#100。前情 = s3-prreview 的 review 评论（PR 上）+ root 结论：params-draft 半边干净、narrate 半边落在 #194 之前的旧路径（rebase 后必挂结构锁）。

## 红线（同事分支协作纪律）

- **禁 force-push**：不 rebase 重写历史——用 `git merge origin/main` 进分支解冲突（唯一冲突 plan_subgraph.py），迁移改动作为新 commit 叠加。开工前 `git fetch` 确认分支无新提交；若作者在推进，dispatch ask 停等。
- commit message 写明动机并引 PR review 与 #194（对事条理清楚，让作者一眼看懂动了什么为什么）。
- **不合并 PR**（合并留作者/用户）。

## 迁移内容

1. merge origin/main（≥48c7579）入分支，解 plan_subgraph.py 冲突：保留 #194 的 `emit_prejob_narration` 装配，弃分支上的旧 `deterministic_form_closing` 路径。
2. 把 #100 的 narrate 修复本体（换掉旧"单步 CC"示例的 prompt 内容修正）迁到 #194 单源落点：`PLAN_NARRATE_SPEC` / `_narrate_prejob.py` 的对应喂养片——内容保留、落点搬家。
3. 验证：#194 结构锁测试绿（emit_prejob_narration 在场 / deterministic_form_closing 不在场）、#100 自带测试绿、params-draft 半边测试不动也绿；全量本地 pytest 绿（用 talos-pg-test-73:5455）。
4. push 到 PR 分支（普通 push，无 force）；等 CI 绿后在 PR 评论：迁移说明 + 结构锁/全量结果 + "可合"结论 @作者。

## 二元验收

- PR mergeable=MERGEABLE、CI 全绿、结构锁具名测试在 PR 分支上真实执行且绿。
- **不重启台架、不合并**。

## 收尾

PR 评论链接 + 迁移 commit sha 评论回 root（dispatch done，FACTS/JUDGMENT 分开）。
