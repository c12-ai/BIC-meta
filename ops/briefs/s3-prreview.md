# S3 任务：同事三 PR 按序 review（portal#46 → portal#47 → service#100）——只审不合

你是 PR review 会话（**只发 review 评论与结论，不合并、不推分支**）。这些是同事（Drake/codex 会话）的 PR，措辞对事不对人、结论给一手证据。

## 关键背景（今晚刚落的、必查撞面）

- portal main 今晚大改 lab-logistics 区：#188（rule-8：占用槽=选中、空槽=仅维护模式、维护开关恢复，MaterialPreparationPanel）、#173/#174（蛇形架 serpentineRackLayout 单源 + 化学家色板）、#176（全孔可分配 + collect_config 前缀语义）、#179/#175（FormChromeCollapse）。
- service main 今晚落：#194（pre-job 叙述单源 _narrate_prejob.py + 结构 grep 锁）、#181（executor_display_name 单源）、#182（finale 受约束 LLM）、#107（P2 批）。
- PRD rule 8 是产品红线；narrate 单产出口是结构不变式（有 grep=0 结构锁测试）。

## 审查项（按序，每个 PR 独立 review 评论）

**portal#46**（lab-logistics persist + tube numbering，携 ~10 commits 旧栈 + merge main）：
1. merge 解决核查（重点）：#188 的占用槽选择/维护开关、#173 蛇形布局、#174 色板、#176 可点性——在 PR 结果树里逐一确认未被回退（对 origin/main 跑 diff，任何今晚具名测试被改/删都是红旗）。
2. 新功能本体：刷新持久化的选择恢复与 rule-8 语义相容性（恢复的是"选择"非"库存"）；tube numbering positional 修复与 #173 蛇形编号的一致性。
3. 638 tests pass 的构成：今晚新增的具名测试（issue-188/174/176/179 族）是否都在且绿。

**portal#47**（纯格式化）：确认零逻辑 diff（git diff -w 近空 / AST 级无变化）；与 #46 的顺序依赖（谁先合谁 rebase）。

**service#100**（lab-logistics draft 持久化 + PlanAgent narrate fix）：
1. narrate fix 与 #194 单源架构的关系：是否绕开 _narrate_prejob 又开新装配路径（违反结构锁）？grep 锁测试是否仍绿？
2. 新 route/event 的契约面：rule 10——.trellis/spec 是否同步；事件是否走 #165 的持久化口径（emitted_at 等）。
3. 分支基点与 main 的漂移量；本地 17 个集成失败=缺 Keycloak 的说法用 CI 结果核实。

## 交付

- 每 PR 一条 review（gh pr review --comment，分 BLOCKER/建议/nit 三级）；总结论评论给 root：每个 PR 合并建议（可合 / 需改 / 需与今晚工作 rebase 重解）+ 建议合并顺序。
- **不合并**。dispatch done（FACTS/JUDGMENT 分开）。
