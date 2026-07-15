# S3 任务：PR-train B/C/E 组 + D 组杂项 — 分组联审/更新/按纪律合并

你是 PR review+update 会话，按组处理。**合并纪律（用户裁定）：作者无 reviewRequests 的 PR 一律不合并**（审+更+评论）；有 reviewRequests 且审净+CI 绿才可 admin merge。

## B 组：service#94（guardrail 准入+状态感知授权，reviewReq=2 → 唯一合并候选）

- 深审：与今晚 BE 主线（#128 三层、#194 narrate、#181/#182）的相容性；guardrail 语义与 PRD requirement 2（human-controlled confirmation）的关系；基点漂移与冲突实测；测试质量。
- 冲突则 merge main 更新（禁 force）；审净+CI 绿 → **admin merge**；有 BLOCKER → 评论不合。

## C 组：portal#29 + lab#111（c12-syq，TLC 耗材维护双仓）

- 联审：portal#29（TLC consumable maintenance controls/隐藏机器人维护区）与 lab#111（显影液按盒组解耦维护）是否互相依赖、与 PRD rule 1/7（Consumable Maintenance 语义、shelf read-only for specific items）一致性。
- **排序风险**：portal#29 可能与 s3-fe46 正在更新的 #46（MaterialPreparationPanel 一带）撞面——先 diff 文件面；有交集则只 review 不更新分支，结论里注明"待 #46 落地后 rebase"。
- 无 reviewReq → 不合并；审+评论（+无交集时可更新分支）。

## D 组杂项（只评论，不动分支）

- lab#117（bot auto-fix for #116）：#116 已 squash 合入（624e4e5）——核实后评论"目标 PR 已合，此 auto-fix 已过时，建议作者关闭"（不代关）。
- lab#115（auto-fix for #114）+ lab#114（draft，labrun v7）：draft 只审——重点给 #114 一个方向性 review（与 #177 collect_config 前缀语义、mock 246f6d4 的契约测试相容性），不合不更。
- portal#47：已有 review 结论（可合但建议 #46 落地后重跑 sweep）——补一条评论同步该建议即可。

## E 组：lab#64/#66/#69（Shion EXAMPLE 系列，pin v1.1.x 远古 shared-types）

- 评论现状：现行 pin 45032c9（v1.3.1+），EXAMPLE 分支已严重过期；问作者意图（参考文档 vs 待合），建议转 docs 或关闭。不合不更。

## 收尾

分组处置台账（每 PR：verdict/动作/合并与否+依据）评论到一个新 meta issue（标题：PR train 2026-07-11）；dispatch done（FACTS/JUDGMENT 分开）。
