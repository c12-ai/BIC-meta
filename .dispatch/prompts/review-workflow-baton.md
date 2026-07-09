# 评审任务：WorkflowBaton 架构提案 review（同事提案，产出评审报告）

你是架构评审 session（**只读代码，唯一产出一份评审报告**）。评审对象：同事的提案《用 WorkflowBaton 收敛业务状态，防止表单流与对话流失步》，快照在 `/Users/wenlongwang/Work/BIC/V2/BIC-meta/.dispatch/findings/workflow-baton-proposal.md`（对应 BIC-agent-service issue #70，Feishu 原文 wiki Knz0w51riisyXVkjTr9cNP66nEc）。

## 评审基线（先全部读完再下笔）
1. 提案快照全文。
2. 我方本轮已落地/已设计的同域工作（全在 `/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/`）：
   - unified-step-flow-memo-2026-07-09.md（片1-3 已实现并合入集成 PR：EntryStepSpec、统一 advance/收尾、单一 narrate 流水线+确定性终态过滤）
   - think-message-architecture-2026-07-09.md（R1-R4 路线，R1 已落、R2 先行片已落）
   - state-semantics-audit-2026-07-09.md、architecture-memo-2026-07-09.md、project-refactor-review-2026-07-09.md（A=FE 单一写路径已实现、B=lab 校验单一核已实现、C=apply 不变量挽具已实现）
3. 代码现状：BE `/Users/wenlongwang/Work/BIC/talos/BIC-agent-service`（bench-verify，即集成 PR#69 内容）、portal 同名 bench-verify（PR#18）。主目录只读（用户在测）。
4. 台账：c12-ai/BIC-meta issues #1-#60（提案引用的是 BIC-agent-service 仓的另一套 issue 编号，注意区分）。

## 必答（结论先行，Facts/Judgment 分开）
1. **问题诊断评审**：提案的病理描述与我方审计是否一致？其 git/issue 证据基于 main@07-09——**不含 PR#69**；逐条标注提案"已观察症状"里哪些已被我方修复/结构性收口（给 commit/测试证据），哪些仍开放。
2. **方案实质评审**：Baton/Engine 的每个构件 vs 我方已落地物的映射表——SpecialistDefinition vs EntryStepSpec/StepSpec、narration guard vs 终态一致性过滤+世界态事实块、transition 收敛 vs FormConfirmedEvent apply/不变量挽具、authorization matrix vs guardrail 门、outbox/saga vs 现 dispatch 路径、ActiveFormSnapshot/version vs #46+#40 事件同构、baton vs R3 segment/turn_kind。哪些是**真增量**（我判断：CAS 版本化+行动授权矩阵、outbox 幂等派发、shadow mode 方法论、form patch 版本策略——待你验证），哪些是重复发明。
3. **顶回去的点**：与已落地决策冲突处（例如"引入第二套 truth"风险 vs 我方 event-sourcing 单一权威 + deriveRouting/StepSpec 派生原则；phase/stage/status 三元 vs 我方 status 权威裁定）；工期估算合理性（其 4-6 周 vs 我方 strangler 片已用数天落地三片的实证速率）。
4. **合流建议**：不要"两套架构竞争"——给出 baton 提案与 unified-step-flow + R2/R3 路线的合并路径（哪些 baton 构件作为 R2/R3 的实现载体、哪些 phase 直接砍掉因已完成、shadow mode 从哪片开始），以及给 Drake 的决策问题清单。
5. **验收标准评审**：提案的验收标准哪些已被现有测试覆盖（不变量挽具/一致性矩阵/结构 grep 测试），哪些需要新建。

## 产出
`/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/review-workflow-baton-2026-07-09.md`（唯一可写文件）。数据先行：每个论断带 file:line / commit / 测试名。不改代码、不开 issue、不评论 GitHub（评审意见由 root/用户决定如何回给提案人）。

完成后 dispatch done：FACTS（文档路径、五问各一句话结论）/ Judgment 分开。
