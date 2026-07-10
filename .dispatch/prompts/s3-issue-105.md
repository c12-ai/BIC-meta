# S3 任务：c12-ai/BIC-meta#105 — 非基准行不透传 Mind 回显 amount/eq（止血）

你是 S3（独立复核 + 实现 + 提交）。issue #105 正文 + s2 调查评论（4924941148）+ root 裁定评论是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（43fcbdd，已含 #103 补名合并）切工作树 .wt/be-105 开分支 fix/issue-105-no-fabricated-feed（不 push/不 PR/不重启）。

## 要点
- 落点 = _objective_reactant_rows_from_goal（tools.py:1906-1916 一带，#103 刚在同区挂了补名——基于 43cfbdd 后的现状重读再动手）。非基准行 amount/eq 显式留空；基准行不变。
- 下游消费空态检查：ObjectiveReactantRow 允许 null（form_payloads.py:399-400），但 ExperimentMaterial 必填（experiment.py:60-61）——确认空态在草稿→确认→下发链路不炸（下发前应有量纲收集步；若有缺口如实登记回 issue，不扩改）。
- FE 矩阵渲染空值显示核对一遍（只读 portal 仓），异常登记不改。

## 二元验收
(1) goal-confirm 回显 15/1 场景 E2E：非基准行入库 amount/eq 为空（DB/事件断言）；(2) 基准行 15/1 保留；(3) 用户显式提供非基准量时正常透传；(4) 全量单测门禁绿（#101 已知闪失单跑复核）。

## 收尾
修复摘要评论 issue #105，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
