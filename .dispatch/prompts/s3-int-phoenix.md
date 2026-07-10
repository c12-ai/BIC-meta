# S3 任务：同事功能集成评审 A — Phoenix + 前端点赞点踩（多仓）

你是集成评审员。目标：找到并评审"集成 Phoenix + 前端点赞点踩"相关的开放 PR（gh pr list -R c12-ai/BIC-agent-service / c12-ai/BIC-agent-portal，关键词 phoenix/feedback/like/点赞；历史参照：service PR#44、portal PR#9 曾被 review 过，要求尽量复用 Phoenix 能力——先看它们现状与后继 PR）。

## 任务
1. Review 代码：正确性、与 bench-verify 今晚大量变更（narrate 管线、事件模型、chatStore 双路、tab 体系）的冲突面、是否复用 Phoenix 能力（既有裁定）。
2. 本地集成试跑：各仓开工作树（.wt/int-phoenix-*），把 PR 分支与当前 bench-verify 合并（只在工作树，不动台架、不 push），跑各自门禁（BE 全量单测 / portal lint+test+build）；若能自起 dev server 验证点赞点踩 UI 与 Phoenix 上报则做动态验证（自选端口，别占 :5174/:8800）。
3. 报告：可合并性结论（能直接合 / 需 rebase 解决哪些冲突 / 有缺陷需作者修）、冲突清单 file:line、门禁结果、建议合并顺序。评论到相应 PR（中文，客观，无待审措辞）+ 汇总评论到 c12-ai/BIC-meta 新 issue「集成评审：Phoenix+点赞点踩」。

不合并、不 push、不动台架。收尾 dispatch done（FACTS/Judgment 分开）。
