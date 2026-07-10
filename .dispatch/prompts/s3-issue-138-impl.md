# S3 任务：#138 实施 — decision 单活跃不变量（BE，工作树）

你是 S3（独立复核 + 实现 + 提交 + PR，列车授权口径）。任务书 = #138 的 s2 设计评论（三缺陷共振：铸造无 supersede / 确认链不解引用 decision→plan / plan 子图侧）+ 用户"设计同意"裁定。仓：BIC-agent-service，从 origin/main（1d9fb7a）切工作树 .wt/be-138 开分支 fix/issue-138-single-active-decision。

## 要点
- 按 s2 设计的实施拆分做"止血+源头"中当下可落的部分：同 kind 新 decision 铸造时旧 pending supersede（事件表达 + FE 卡失活语义登记 FE 增量）；确认链解引用 original_action.plan_id（确认哪张卡就确认哪个 plan——那个"永远确认最老计划"的坑）；plan 子图侧按设计。既有裁定 #5/#37/#102 不可破。
- 与 #128 三层状态正交（s2 已判），但注意 .wt 里可能并行的 be-1 设计——你不动 trial/job 状态族。
- **不部署**：合并 main 后台架同步由 root 在 Playwright 收官后统一做。

## 二元验收
乱序确认/改需求重放 E2E（#138 实录场景 seq 佐证转夹具）：无幽灵叠加、无静默丢指令、确认卡与 plan 一一对应、同 job 无重复 trial/表单（具名断言各一）；全量单测绿；PR CI 绿合并。

## 收尾
sha + 测试计数评论 #138，标签 待裁定 → 已实现待复测；dispatch done。
