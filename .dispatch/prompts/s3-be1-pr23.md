# S3 任务：#128 BE-1 · PR-2 + PR-3 切片（jobs 两轴迁移 + execution_status 新列）

你是 S3（实现 + PR，列车口径）。任务书 = #128 BE-1 设计笔记（comment-4932438779 前后的完整设计）+ root 裁定（新列 execution_status 基线）+ PR-1 已落（BE main cf6209b，verdict 投影）。仓：BIC-agent-service，从 origin/main（cf6209b）切工作树 .wt/be1-pr23 开分支 feat/issue-128-be1-pr2-jobs-axes（PR-2 先行，PR-3 在其上或分支续切，按设计笔记 ⑤ 两个独立 PR 交付）。

## 范围
- PR-2：jobs.outcome + jobs.review 两列 + 迁移回填（设计笔记 ① 的 CASE，down_revision 接现 head）+ #37 accept 时刻写两轴 + #5 游标等价保持（笔记 ③ proof obligation 逐条对账）+ step_outcome 事件（ST-1 枚举 45032c9——先 repin shared-types 45032c9，这也是 BE 侧 repin 的正主）。
- PR-3：trials.execution_status 新列 + 迁移回填（含 superseded 清 21 行僵尸的 CASE）+ 设计笔记列出的 ~12 个 trial.status reader 迁移清单逐一处理（每个 reader 在 PR 描述对账表打勾）+ emit_terminal_progress 只带 L1。
- stage 值域（PR-4）不做（门控 #80 另批）。

## 二元验收
每 PR：迁移在真库 upgrade/downgrade 往返 + 回填断言（历史行夹具）；#37/#5 等价具名测试；全量单测绿；CI 绿合并（admin-merge 留痕）。**不重启台架**。

## 收尾
两 PR sha + reader 对账表评论 #128；dispatch done（FACTS/Judgment 分开）。
