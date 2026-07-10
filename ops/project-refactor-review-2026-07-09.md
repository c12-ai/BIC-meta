# 项目整体重构评审（第二轮，基于 #38-#45 及全量台账）

日期：2026-07-09 · 作者：S1 orchestrator · 依据：Wenlong "从项目整体高度，通过最近几个issue，看看应该重构的地方，dispatch session 去做，用 fable"

## 结论（先说）

BE specialist 层的重复已由「统一步骤流程」（ops/unified-step-flow-memo-2026-07-09.md，片1在飞）收口。台账剩余的结构性信号聚成 **三个重构行动**，全部是同一病型的三个器官转移：**同一语义有 N 条手写路径，各自漂移**。

| 行动 | Repo | 证据密度 | 状态 |
|---|---|---|---|
| A. FE store 单一写路径（乐观写=合成事件走同一 reducer） | portal | 6 issues | 本轮 dispatch（fable） |
| B. Lab 校验单一流水线（create/dry-run/readiness 共用一个核） | lab-service | 3 issues | 本轮 dispatch（fable） |
| C. 事件 apply 层不变量测试挽具（先测不改产码） | agent-service | 3 issues | 本轮 dispatch（fable，tests-only） |
| （下一波）跨服务契约测试（shared-types 漂移） | 全部 | 2 issues | 记录待命 |

## A. FE store 单一写路径（portal）

**病灶**：同一语义动作有两条写路径——乐观本地写（点击时的手工局部 patch）+ SSE 回声写（事件 reducer），加上 snapshot 重取第三条，互相拆台。
**证据**：#40（乐观 clearForm 丢参数 + 回声因 pendingForm 已清而失效 → 终态化永不发生）、#37（accept 只写 phase 不写 status）、#26（badge/subtab 两处派生打架）、#21（rehydrate 丢 progress 投影）、#24（渲染层重复/`<think>`）、#34（failed 掉进 task tab）。六个 issue 同族：**投影漂移**。
**目标形态**：乐观路径不再手写局部 patch，而是**合成与 SSE 等价的规范事件**送进同一 apply/reducer；所有 handler 按 event_id 幂等；live/回声/replay/snapshot 四条路径收敛到一个状态机。deriveRouting 已经是"单一路由真相"，把同一原则推广到 mutation 全域。
**验收（二元）**：等价性质测试——任意乐观 mutation 后的 store 状态 === 应用对应 SSE 事件后的状态（参数化覆盖 form confirm/decision/result accept）；#40 的会话事件序列 replay 测试在无外科补丁的结构下通过；全量 vitest+tsc+biome 绿。

## B. Lab 校验单一流水线（lab-service）

**病灶**：create-gate 与 dry-run `/preparations/validate` 是两条手写校验路径（#32 根因：dry-run 只调 validate_task_materials，TLC 摆位校验零覆盖）；错误分型也曾分叉（#19："不存在"报成"非2ml"）。#32 的修复（f2c80fe）把 TLC 补进了 dry-run，但**按执行器逐个补 = 继续镜像**——与统一步骤流程同病。
**目标形态**：一个校验核（per-executor 校验器注册表），create / dry-run / readiness 三个调用方共用；同一任务状态在任何入口得到**逐字相同的verdict 与错误分型**。
**验收（二元）**：参数化性质测试——对同一 task 状态，create-gate 与 dry-run 的校验结果（通过/失败+错误类型）完全一致，覆盖 TLC/CC/FP/RE 四执行器 × 缺料/幽灵/错型三类故障；既有 lab 测试全绿（含 #32 的新测试）。

## C. 事件 apply 层不变量挽具（agent-service，tests-only）

**病灶**：语义相同的事件从不同路径落盘出不同状态——#39（agent-form 确认路不盖 confirmed=True，direct-REST 路盖）、#5/#37（result accept 的终态化各路径不一致）、#16b（tool_call_id 配对契约漂移）。
**本轮范围**：**只加测试不改产码**（避免与在飞的片1/#39/#42 冲突）：不变量测试挽具——(1) 任何确认路径 ⇒ objective.confirmed=True（#39 若早有此测必被拦）；(2) 任何 result accept ⇒ trial.status 终态且与 verdict 一致；(3) 事件 apply 幂等；(4) tool_call 配对完整。发现的现行违例**只报 issue 评论，不修**。
**验收（二元）**：挽具落地且全绿或每条红都有对应 issue 评论；产码 diff 为零。

## 时序与纪律

- A/B/C 各自独立侧分支 + worktree，不碰 bench 主目录，不重启，不 push。
- A 与在飞 s3-issue-40/41/43（外科修）并行：外科修先进 bench 救急，A 是结构解，合流时由 root 语义合并（先例：fix 分支 vs refactor/narrate-contract）。
- 模型：本轮三个重构 session 按用户指定用 **fable**（此前 S2/S3 统一 Opus 1M 的 SOP 对这三个例外）。
- 跨服务契约测试（#16b/#19 族）留待 A/B/C 落地后的下一波。
