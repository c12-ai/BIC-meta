# S2 任务：跨仓架构评审 — 结构性问题识别（只读，fable）

你是架构评审员（只读）。范围：BIC-agent-service（重点）、BIC-agent-portal、BIC-lab-service、mars_interface_mock、shared-types（各 bench-verify HEAD）。输入之二：c12-ai/BIC-meta 全部 issues（gh issue list -R c12-ai/BIC-meta --state all -L 130）——今晚 #94-#128 尤其密集。

## 任务
1. 通读 issue 台账，按根因聚类：哪些家族是同一结构缺陷的反复症状（例：状态语义重载 #116/#123/#128；"问用户要机器数据" #113/#126；边界 presign 三处 #98/#107/#119；生命周期握手 #125；live/snapshot 双路 #110；输入格式 #120）。
2. 结合代码通读（service 分层 L1-L4、事件模型、narrate 管线、specialist 子图模式），识别应该**架构级解决**的题目：给每题一份一页方案（问题本质/现状代价/结构方案/迁移路径/风险），对照 .trellis/spec 与 ops/ 下既有架构文档（unified-step-flow、WorkflowBaton 等）避免重复提案。
3. 排序：按"消除未来 issue 数量的杠杆"排优先级，标工作量。
4. 落地物：汇总报告建为 c12-ai/BIC-meta 新 issue「架构评审 2026-07-10：结构性问题清单」（stage:待裁定），每个提案一节；不改任何代码。

## 收尾
dispatch done（FACTS: issue 号 + 提案数；Judgment: top3 推荐）。
