# S3 任务：#128 阶段1 · ST-1 — shared-types 契约扩展（三层状态 wire 字段）

你是 S3（实现 + PR，继承列车授权：CI 绿 + flow-bot 豁免 + codeowners admin-merge 留痕可合并）。任务书 = BIC-meta#128 交付物 2/5 的 ST-1 行（先通读 #128 五份交付物评论）。仓：BIC-shared-types，从 origin/main（b85ee6c）切分支 feat/issue-128-st1-state-wire。

## 范围（照 #128 交付物5 ST-1 行）
TaskStatusMsgPayload 族：step 携带 round_index；op 级步骤进 step_events（#124-②）；trial 级 execution_status / verdict、job 级 outcome+review 的 wire 字段定义。全部 additive/向后兼容（默认值策略写清）；schema 导出/示例/契约门禁全绿（参照 #95/#97 两次的门禁清单）。

## 边界
只做契约层；lab/BE 消费属 LAB-1/BE-1 后续批。字段语义以 #128 设计表为准，含糊处在 PR 描述里列明假设。

## 收尾
PR 开出并合并（CI 绿），sha 评论到 #128（注明 ST-1 完成、LAB-1/BE-1 可开工）；dispatch done（FACTS/Judgment 分开）。
