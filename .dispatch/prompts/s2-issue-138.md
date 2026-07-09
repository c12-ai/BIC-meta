# S2 任务：c12-ai/BIC-meta#138 — decision 单活跃不变量设计调查（只读，fable）

你是 S2（架构调查+设计，只读）。issue #138 正文（挑战轮 1 实录：幽灵叠加/指令静默丢失/objective-plan 反应式不一致/同 job 重复 trial+表单）是任务书。仓 BIC-agent-service bench-verify（ca19223+）；DB talos_agent_db（挑战轮会话，issue 里有 id 与 seq 佐证）。

## 任务
1. 还原 decision 生命周期现状：铸造/pending/resolve/CAS 全链 file:line；乱序确认与改需求场景下每个坏态如何产生。
2. 设计"单活跃 decision"不变量：同 kind 新 decision 铸造时旧 pending 的 supersede 语义（谁 supersede 谁、事件如何表达、FE 卡片如何失活）、改需求后下游派生物（plan/params/trial）的一致性策略。对照 #128 三层状态设计与 #131-P1 提案，明确关系（吸收/正交/依赖）。
3. 实施拆分（止血 vs 源头，各 issue 粒度、依赖、工作量），供用户裁定。
落 issue 评论（Facts/设计/Interpretation），标签转 stage:待裁定。不改码。收尾 dispatch done。
