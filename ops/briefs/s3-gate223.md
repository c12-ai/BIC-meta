# S3 任务：meta#223 TLC 未确认下游 CC 已排队 — 确认前锁定下游

你是 S3（先调查定分叉，再修，列车口径）。任务书 = c12-ai/BIC-meta#223（读正文，含用户原话、期望不变量与两个分叉假设）。

现象：TLC 结果解析已出但用户**尚未 accept**，任务列表下游过柱（CC）已显示『排队中』。期望不变量：**上游结果确认（accept）之前，下游步骤锁定，不得进入排队/可执行状态**。

## A. 先定分叉（结论评论 #223，再动手修）

用台架一手证据（bic-postgres:5432 talos_agent_db 只读：jobs/trials 状态行 + 事件表时间线；BE 日志）判定：
1. **BE 真排队**：L3 在 analyzed（非 accepted）时点就推进 CC job / 向 lab 入队 → 门控缺陷，违反 PRD requirement 2（human-controlled confirmation）。修 BE 门控。
2. **FE 标签失真**：BE 实际锁着，portal 状态归约把 pending/blocked 渲成『排队中』→ 显示缺陷。修 portal 归约/文案。
- ⚠️ 语义边界：#5 的 fail-accept 自动过柱是 **accept 之后**的既定行为——别把它当缺陷回滚；#128 三层状态（execution_status / verdict / outcome×review）是判读基准。
- 一并核对：正常 pass 路径 accept 前 CC 的应然状态文案是什么（锁定态要有明确表达，不是空白）。

## B. 修复（按分叉落仓）

- BE 分叉：BIC-agent-service，从 origin/main（≥e26096b）切 `.wt/gate223`，分支 `fix/issue-223-downstream-lock`；
- FE 分叉：BIC-agent-portal，从 origin/main（≥3b2c50e）切 `.wt/gate223`，分支同名。
- 具名测试：analyzed-未-accepted 窗口 CC 不入队/不显示排队（负向断言）；accept 后正常推进（#5 回归保护）；fail-accept 自动过柱不回退（#158/#5 既有套件全绿）。

## 并行知会

- 同仓在跑：s3-fe220（物料 modal，portal）、s3-fe222（tab 路由，portal workspaceStore）。若 FE 分叉要动 workspaceStore 状态归约，先与 fe222 互 ack（dispatch send）再动；BE 分叉无在跑冲突。

## 二元验收

- 全量 pytest（BE 分叉）或 tsc/biome/vitest（FE 分叉）+ CI 绿 → admin squash-merge，内容核验；
- 分叉判定（一手证据链）+ PR sha 评论 #223。**不重启台架**（部署归 root）。

## 收尾

dispatch done（FACTS/JUDGMENT 分开）。
