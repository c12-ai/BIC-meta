# S3 任务：同事功能集成评审 C — TLC 更新双 PR（service#73 + portal#21）

你是集成评审员。目标 PR：
- https://github.com/c12-ai/BIC-agent-service/pull/73（已有 review 4665430347，先读历史 review 意见与作者回应）
- https://github.com/c12-ai/BIC-agent-portal/pull/21（已有 review 4665425307，同上）

## 任务
1. Review 代码与历史 review 的处置情况；**重点冲突面**：今晚 bench-verify 对 TLC 动了大量地方（#107 mixcase 规范形、#117 重试叙述、#119 presign 三处收敛、#121 fail-loud、#125 cleanup 握手、#123/#116 FE 状态读侧、#128 架构梳理进行中）——逐一对照 PR 改动是否冲突/重复/被取代。
2. 本地集成试跑：工作树合并（.wt/int-tlc-*，基当前 bench-verify，不动台架不 push），跑各自门禁（BE 全量单测 / portal lint+test+build）。
3. 报告：可合并性结论、冲突清单 file:line、门禁结果、与 #128 架构方向的关系（若 PR 与三层状态设计相left，建议等 #128 裁定）。评论到两个 PR + 汇总评论到 c12-ai/BIC-meta 新 issue「集成评审：TLC 双 PR」。

不合并、不 push、不动台架。收尾 dispatch done（FACTS/Judgment 分开）。
