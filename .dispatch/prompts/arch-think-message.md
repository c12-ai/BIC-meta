# 调查任务：think / message 架构审计 — 报告 + 重构建议（不写代码）

你是架构调查 session（**只读两个代码仓库 + 只读 DB，唯一产出是一份报告文档**）。

## 用户裁定（原话要义，即目标不变量）

> "think 是 agent 自己思考过程，message 是和用户沟通话语，整体是顺的：不应该出现说完话了、这句话的 think 还在跳动；不应该有空 think；所有 think 都应该为动作、或者说为说话服务。"

即三条不变量：
- **I1 语域分离**：think＝内部推理（可折叠、面向调试/透明度），message＝面向化学家的话语。两者不得互相渗漏（think 内容不出现在 message，message 不藏在 think 里）。
- **I2 时序贴合**：一条 message 的 think 在该 message 结束时同时结束；message 落地后继续的工作属于**下一个**语段（气泡）。
- **I3 无孤儿 think**：每段 think 必须服务于一个动作（工具调用/派发）或一句话语；不存在只有 think 没有产出的空气泡。

## 台账证据（这些 issue 是同一架构病的症状，全在 c12-ai/BIC-meta）

#51（叙述句结束、同 turn 的 think 继续跳→假卡死）、#55（无 text_done 的自动重试 turn 渲染空卡，DB 实证 turn e5aee129）、#54（叙述回显裸状态枚举 in_progress）、#24（渲染层 <think> 泄漏/重复）、#45（narrate 历史回放堆积——输入语域污染）、#12/#15/#16c/#17/#18（narrate 语域根因族，memory: chat 单一产出口 narrate 是改写器、react 散文进 thinking）。先读这些 issue 与 `ops/unified-step-flow-memo-2026-07-09.md`（片3 已实现 narrate 流水线归一）。

## 工作区（全部只读）
- 新 repo：`/Users/wenlongwang/Work/BIC/talos/BIC-agent-service`（bench-verify，含片1-3）与 `/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal`（bench-verify，含重构A）。主目录用户在测，**只读**。
- 旧 repo 快照：`/Users/wenlongwang/Work/BIC/talos/.wt/ref-backend`（detached @ origin/main）。已有研读 `ops/reference-study-agent-backend-2026-07-09.md`（注意其结论：presenter.py 是死代码、老版行为层零置信——对比时先读它，别重复劳动）。
- DB 只读：`docker exec talos-postgres psql -U postgres -d talos_agent_db`（会话 18249ece 等有实证 turn）。
- 产出：`/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/think-message-architecture-2026-07-09.md`（唯一可写文件）。

## 报告必答（结论先行，Facts/Judgment 分开）

1. **现状盘点**：当前"think"与"message"各由哪些事件/通道构成（reasoning 流、tool_call/tool_result、text_done、task_* 事件；SSE 与持久化两侧），FE 如何聚合成气泡（chatStore turn→气泡逻辑）；对照 I1-I3 列出每条不变量今天在哪些代码点被破坏（file:line + DB turn 实证）。
2. **旧 repo 对比**：老版的对话产出模型（它如何组织面向用户输出 vs 内部过程；有无同类病；有什么切面值得借）——基于代码事实，引用研读文档已有结论勿重复。
3. **根因定性**：这些症状是（a）事件分类学缺失（没有一等的 think/message 语义，FE 靠 turn 猜）、（b）turn 粒度与语段粒度错配、（c）narrate 单出口改写器的输入/输出污染，三者各占多少——给出主次。
4. **重构方案**（建议，不实现）：目标事件分类学（如 message_segment 边界事件/气泡 id、think 归属标注）、BE/FE 各自改动面、与已落地结构（narrate 流水线片3、FE 事件同构重构A、#51/#55 在飞外科修）的关系（吸收谁、依赖谁）、迁移排序与兼容策略（历史会话重放）。每条建议标注解决哪些 issue。
5. **代价与风险**：改动量级估计、SSE 契约变更影响面（Rule 10 spec 清单）、可先行的低风险切片。

## 纪律
- 不改任何代码/不开 issue（发现新事实评论到相关 issue 可以）。
- 完成后 `dispatch done`：FACTS（文档路径、每问一句话结论）与 Judgment 分开。
