# S3 任务：BIC-meta#203（P1）— pre-job 叙述 turn 的 trace 消失（结束即弃 + 刷新无源），三源对账后根修

你是 S3（先调查后修，列车口径）。任务书 = meta#203（读全 issue，含家族史区分与 #194 关联怀疑）。

仓：BIC-agent-service 为主（`.wt/trace203`，分支 `fix/issue-203-prejob-trace`）+ 若 FE 侧有关联改动则 portal 小 PR。
**并行协调（重要）**：s3-pr100split 正在同事 PR#100 分支动 `plan_subgraph.py`（merge main + narrate 迁移）。你的调查只读不冲突；**若修复需要动 plan_subgraph.py / _narrate_prejob.py，先 dispatch send 问 root 排序**（大概率等 pr100split 收档再落你的修复，避免双改）。

## 纪律

1. 三源对账（#165 方法）：复现 objective confirm→plan 的 turn，比对 live SSE 事件序列 / session_events 落库行 / 快照 API——缺哪段、哪条路径丢的，结论评论 issue 再动手。可用台架只读观察（**不重启不接管**，用户正在测试），或本地自起 BE + talos-pg-test-73:5455。
2. 根因修（禁点状）：pre-job 路径缺 flush → 对齐主路径同构；消息关联断 → 修关联。
3. 具名测试：trace-isomorphism 扩展覆盖 pre-job 叙述 turn（live≡persisted≡snapshot）；#165/#194/#156 回归绿。

## 二元验收

- 复现 turn：消息保留追踪块，刷新逐项同构（具名测试 + 说明台架复测步骤留 root/用户）。
- 全量 pytest + ruff/pyright + CI 绿 admin-merge 留痕。**不重启台架**。

## 收尾

对账结论 + PR sha 评论 #203；dispatch done（FACTS/JUDGMENT 分开）。
