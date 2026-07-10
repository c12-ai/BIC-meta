# [快照] 架构改进提案：用 WorkflowBaton 收敛业务状态（Feishu wiki Knz0w51riisyXVkjTr9cNP66nEc，取于 2026-07-09）


对应 GitHub Issue：[c12-ai/BIC-agent-service#70](https%3A%2F%2Fgithub.com%2Fc12-ai%2FBIC-agent-service%2Fissues%2F70)

## **摘要**

当前 `BIC-agent-service` 的架构已经反复暴露出一类核心问题：**对话流、表单流、持久化业务快照和 LangGraph 子图路由之间经常出现状态漂移**。

最典型的故障是 **越权推进**：业务状态还停留在“等待用户确认表单”，但助手对话或图路由已经表现得像下一阶段已经开始。例如：

- TLC 参数表单还没有确认，助手却说 TLC 实验已经开始；
- 右侧工作台还停在 TLC 参数表单，助手却开始叙述 CC handoff；
- plan narration 说下一个 specialist 是 CC，但实际 event 创建的是 TLC trial；
- LLM narration 在 `collecting_params` 阶段编造 task id、产率、纯度或下游 specialist 工作。
这说明当前系统缺少一个统一的、确定性的业务状态权威。本文建议引入 **WorkflowBaton / Capability Token** 和中心化 **WorkflowEngine**：所有业务状态推进必须经过 baton 校验；LangGraph 和 LLM agent 保留扩展能力，但不再拥有业务状态推进权。

**---**

## **1. 当前架构的主要问题与项目拖累**

### **1.1 核心问题**

当前项目的业务状态事实分散在多个位置：

- 持久化实体：`experiment`、`plan`、`jobs`、`trials`、`pending_decisions`
- L2 API-time event apply 路径
- L3 `reception_node` 对 `GraphState` 的投影
- objective / plan / TLC / CC / FP / RE 各自的 subgraph local state
- `Command(graph=Command.PARENT, update={...})` 里的 handoff payload
- dynamic prompt 和 narration prompt
- conversation history / rehydrated messages
- 前端 active form state 和 form draft rider
这导致一次用户动作往往需要穿过一条很长的隐式协议：

```plaintext
FORM_CONFIRM / USER_MESSAGE
  -> API-time event apply
  -> fresh SessionContext load
  -> reception_node projection
  -> route_entry / route_after_admit
  -> child subgraph local state
  -> optional PARENT Command update
  -> specialist_dispatcher
  -> emitted events
  -> session snapshot / replay
  -> narration
```


这条链路里任何一个字段 stale、prompt 假设过期、PARENT update 漏字段、late confirm、active form 不匹配，都会造成用户可见的状态分裂。

### **1.2 已经观察到的具体症状**

- 新 objective 已确认后，旧 objective decision 仍然 pending；
- plan narration 说 handoff 到 CC，但事件流实际创建的是 TLC trial；
- 助手叙述下游工作时，右侧 active form 仍属于上一个步骤；
- 对话中的参数抽取会以意外方式覆盖表单字段或单位语义；
- LLM narration 编造 lab task id、yield、purity 或未来 specialist 行为；
- `auto_analyze` 需要额外 guard 才不会对 failed execution 触发；
- admittance 不理解上下文时，会拒绝合法的短参数回复；
- 系统不断增加 fail-loud、prompt rule、route carve-out 来修补同一类状态错乱。
### **1.3 Git 历史证据**

基于 `main` 分支在 2026-07-09 的本地审计：

- 全仓提交数：**84**
- 涉及 `runtime/session/events/L3 spec/tests` 核心链路的提交：**50 / 84**
- 涉及 `app/runtime/graphs` 的提交：**36 / 84**
- `app/runtime/graphs` 当前规模：约 **14.9k LOC**
- `app/runtime/graphs` 历史 churn：约 **23.9k changed lines**
- runtime/session/events/L3-spec 核心路径当前规模：约 **30.2k LOC**
- runtime/session/events/L3-spec 历史 churn：约 **45.4k changed lines**

几个关键 PR 的影响范围：

- #28 `Overhaul task model to experiments/plans/jobs/trials hierarchy`
  - 396 个文件变更
  - 约 15.3k insertions / 40.6k deletions
- #31 `Add experiment-objective + TLC specialists...`
  - 198 个文件变更
  - 约 18.4k insertions / 6.8k deletions
- #33 `test: add agent service invariant test suite`
- #41 `Live-testing fixes (admittance #37 / narrate dedupe / form-first) + context-management P0-P4`
- #68 `Fix manual-test batch: narrate grounding, failed-terminal analyze skip, dispatch guardrail...`
这不只是正常功能增长。反复被修补的是同一组架构面：routing、state projection、form confirmation、narration、specialist handoff、event ordering、snapshot consistency。

### **1.4 工期拖累估算**

仅凭 git 无法精确还原原计划与实际计划差，但可观察成本已经很明显：

- 至少 **2-3 个工程师周** 投入到状态流、上下文、narration、guardrail 的稳定化与返工；
- 从 #28（2026-06-12）到 #68（2026-07-08），约 **4 周** 时间内核心 workflow 持续 churn；
- 2026-07-06 到 2026-07-08 期间集中出现 live-testing fixes、context management、narration repair、guardrail additions。
如果继续沿用当前方式，未来影响大概率是：

- 每新增一个 specialist 或 form kind，都需要同时修改 routing、events、state、prompts、tests 和 FE snapshot 假设；
- 状态 bug 会继续以跨层不一致形式出现，而不是局部模块 bug；
- 测试数量增长会快于架构清晰度增长；
- prompt rule 会继续承担本应由 deterministic workflow 承担的业务正确性；
- 长链路手工测试会持续昂贵，因为很多问题只在多轮交互中暴露。
**---**

## **2. 现有 issue 中哪些本质上是架构设计问题**

当前可见 GitHub issues 审计：**20 个**。

### **2.1 保守统计**

至少 **11 / 20** 个 issue 直接属于架构 / 状态机 / 流程设计问题。

Open：

- #65 `Param collection desync across TLC→CC handoff, conversational quantity parsing, and active form state`
- #47 `Workflow state desync after objective/plan confirm leaves TLC trial stuck before dispatch`
Closed：

- #61 `Guardrail: agent must never dispatch...`
- #59 `CC/RE auto_analyze fires on failed execution...`
- #58 `CC narrate node fabricates lab task ID, results, and FP plan at collecting_params stage`
- #57 `TLC narrate second-pass hallucinates tool name...`
- #51 `FP result card shows blank volume totals live — SSE fan-out drops evidence camelCase aliases`
- #49 `Plan confirmation ack can name wrong specialist for TLC/FP handoff`
- #43 `TLC params-confirm dispatch fails the turn... request-shape / shared-types drift`
- #39 `Streaming narration degenerates into an unbounded token-level repetition loop`
- #37 `Admittance is context-blind... parameter answers rejected as off-topic`
### **2.2 扩展统计**

如果把架构相邻问题也算入，合理估计是 **14 / 20**：

- #62 guardrail acceptance baseline
- #56 QueryAgent scope verification against full feature contract
- #50 Separate FP from RE
重点不是所有 bug 都由架构导致，而是主导失败模式高度一致：**业务 workflow state、active form state 和 LLM conversation state 没有被一个权威 transition model 统一治理**。

**---**

## **3. 新架构设计：WorkflowBaton + deterministic WorkflowEngine**

### **3.1 核心原则**

为每个 active experiment/session workflow 引入一个权威 baton：

```plaintext
No baton, no action.
Wrong baton, no action.
Stale baton version, no action.
Narration cannot claim a state beyond the baton.
LLM cannot mutate the baton directly.
```


这里的 baton 不是 LangGraph 节点之间自由传递的分布式 token ring，而是由 deterministic WorkflowEngine 拥有的 **业务能力令牌 / 接力棒**。

### **3.2 WorkflowBaton 示例结构**

```plaintext
WorkflowBaton {
  baton_id
  session_id
  experiment_id
  plan_id
  job_id
  trial_id

  owner              objective | plan | tlc | cc | fp | re | none
  stage              objective | workflow_design | parameter_design | conducting | review | done
  phase              collecting_params | wait_confirm | rts | dispatching | conducting | result_review | done

  active_form_kind   objective | plan | params | result_review | null
  active_decision_id
  active_form_version
  active_form_owner  experiment_id | plan_id | trial_id

  cursor_seq
  allowed_actions[]
  forbidden_actions[]

  version            optimistic-lock / CAS version
}
```


### **3.3 中心化 Transition API**

所有会影响 workflow 的输入都经过一个 deterministic reducer：

```plaintext
WorkflowEngine.transition(snapshot, baton, input) -> TransitionResult
```


输入包括：

```plaintext
USER_MESSAGE
FORM_DRAFT_PATCH
FORM_CONFIRM
FORM_REJECT
DECISION_EXPIRED
TASK_TERMINAL
RESULT_REVIEW_CONFIRM
LAB_ACCEPTED
LAB_FAILED
```


输出不再是自由的 graph jump，而是 typed actions：

```plaintext
TransitionResult {
  new_baton
  events_to_persist[]
  outbox_commands[]
  agent_jobs[]
  active_form_snapshot
  user_visible_status
}
```


### **3.4 AgentRuntime 的职责**

LangGraph / LLM agents 变成执行助手，而不是状态拥有者。

它们可以产出：

```plaintext
ObjectiveDraftProposal
PlanDraftProposal
ParamsDraftPatchProposal
ClarificationProposal
NarrationProposal
ToolResultProposal
```


它们不能直接做：

```plaintext
advance workflow phase
confirm a form
create a trial
dispatch lab task
advance cursor
claim a future specialist has started
mark a result complete
```


### **3.5 FormRuntime 的职责**

active form state 必须成为 canonical runtime input，而不是 prompt-only block 或偶发 rider。

```plaintext
ActiveFormSnapshot {
  kind
  decision_id
  owner_id
  version
  values
  schema
  editable_sections
  unit_policy
  conflict_policy
}
```


表单 / 对话冲突处理必须 deterministic：

- chat instruction 可以生成 patch proposal；
- WorkflowEngine 根据 active form schema 和 unit policy 校验 patch；
- 单位转换必须显式、canonical；
- shape / unit 变化可以要求确认；
- stale form patch 通过 `decision_id + version` 拒绝。
### **3.6 Action Authorization 示例**

当 TLC 参数尚未确认：

```plaintext
baton.owner = tlc
baton.phase = wait_confirm
baton.active_form_kind = params
allowed_actions = [form_patch, form_confirm, explain_waiting]
forbidden_actions = [dispatch_lab_task, narrate_task_started, analyze_result, advance_to_cc]
```


如果 agent 尝试 dispatch：

```plaintext
required phase: rts
actual phase: wait_confirm
=> deny; no lab call
```


如果 narration 说 “TLC experiment has started”，但 `lab_task_id == null`：

```plaintext
narration_guard sees baton.phase < dispatching
=> replace with safe text:
   “TLC 参数表单还未确认，实验尚未开始。请先确认表单。”
```


### **3.7 Event / Outbox 模型**

lab dispatch 应该是 saga/outbox action，而不是隐式 graph side effect：

```plaintext
FORM_CONFIRM(params)
  -> WorkflowEngine validates baton and form
  -> persist params_confirmed + baton phase rts
  -> create DispatchLabTask outbox command with idempotency key
  -> worker executes lab submit
  -> LAB_ACCEPTED or LAB_FAILED transitions baton
```


这会让恢复路径变明确：

- lab validation error 可以回到 editable params state；
- missing materials 可以重新打开表单并附带可操作错误；
- retry 通过 idempotency key 保证幂等；
- dispatch 失败不会让用户卡在 `rts`。
### **3.8 扩展性保证**

这个设计至少保留当前同等扩展能力，同时降低新增 specialist 的 blast radius。

新 specialist 通过定义注册：

```plaintext
SpecialistDefinition {
  kind
  form_schema
  phases
  allowed_actions_by_phase
  tools
  draft_builder
  validation_policy
  dispatch_adapter optional
  result_review_adapter optional
}
```


新增 specialist 应主要需要：

- 注册 specialist definition；
- 添加 form schema 和 validation policy；
- 添加 agent/tool implementation；
- 添加 transition table 中该 specialist 的 phase 边。
不应再需要大量 ad hoc 修改：

- parent graph PARENT Command update payload；
- broad dispatcher special cases；
- prompt-only state assumptions；
- active-form guessing；
- unrelated specialist narration rules。
**---**

## **4. 实施计划、风险、预计工期与改进后影响**

### **Phase 0：架构 spec 与 transition table**

预计：**2-3 天**

交付：

- 写出 canonical workflow-state table；
- 定义 baton schema；
- 定义 action authorization matrix；
- 将当前 experiment / plan / job / trial 状态映射为 baton state；
- 明确旧 session 和 event replay 的兼容规则。
### **Phase 1：Shadow WorkflowBaton**

预计：**3-5 天**

交付：

- 从现有 DB snapshot 推导 baton，但不改变行为；
- 记录 expected state 与当前 L2/L3 routing decision 的差异；
- 增加 baton violation metrics；
- 为 #47 / #65 类型流程增加 shadow mode 测试。
这一阶段风险较低，能快速暴露当前行为与期望状态机之间的偏差。

### **Phase 2：危险 transition 收敛到 WorkflowEngine**

预计：**5-7 天**

优先迁移：

- `FORM_CONFIRM(params)`
- `FORM_CONFIRM(plan)`
- `FORM_CONFIRM(objective)`
- `TASK_TERMINAL`
- trial creation
- cursor advance
- lab dispatch intent
验收：

- stale confirm 不能推进状态；
- wrong active decision 不能创建 trial；
- params 未确认时不能 dispatch；
- result-review confirm 只有在 baton 允许时才能进入 next job。
### **Phase 3：Canonical active form snapshot 与 form/chat patch policy**

预计：**5-7 天**

交付：

- 从 baton + persisted decision state 暴露 active form；
- form draft / version 成为一等 runtime input；
- chat-extracted params 变成 patch proposal，而不是直接写状态；
- sample quantity / lab logistics 等字段拥有 deterministic unit policy；
- stale form patch 通过 `decision_id + version` 拒绝。
验收：

- UI active form、L3 active specialist、narration facts 一致；
- chat 不会静默改变 form unit semantics；
- form-only changes 不会从 agent context 消失。
### **Phase 4：Narration / action capability guard**

预计：**3-5 天**

交付：

- 将 baton facts 注入所有 narration call；
- 对 future-state claims 做 post-generation narration guard；
- narration 越权时输出 deterministic fallback text；
- baton 未推进时禁止跨 specialist 叙述。
验收：

- `collecting_params` 阶段 narration 不能声称 dispatch / completion；
- TLC form state 下不能 narration CC execution；
- 不再编造 lab task id、yield、purity 或未来结果。
### **Phase 5：AgentRuntime 简化与 Specialist Registry**

预计：**5-8 天**

交付：

- subgraph 改为返回 proposal，而不是 parent-state update；
- 减少 / 移除业务字段的 PARENT Command propagation；
- 引入 `SpecialistDefinition` registry；
- 先迁移 TLC / CC 路径，再迁移 FP / RE。
### **Phase 6：清理、迁移与监控**

预计：**3-5 天**

交付：

- 移除过时 route carve-outs；
- 将关键 invariant tests 转换为 baton transition tests；
- 增加旧 session replay / backfill 策略；
- 增加 baton violation dashboard / logs。
### **总体工期估算**

保守估计：

- 单工程师保持现有行为兼容：**4-6 个自然周**
- 双工程师并行拆分 WorkflowEngine/FormRuntime 与 AgentRuntime migration：**2-3 个自然周**

建议 rollout：

1. shadow mode only；
2. 只强制 params-confirm / dispatch authorization；
3. 强制 active form snapshot；
4. 强制 narration guard；
5. specialist 逐个迁移。
### **风险与注意事项**

- 不要让 baton 变成第二套 truth。初期要么从 persisted state 推导，要么明确用 CAS 持久化并成为 source of truth。
- 必须保持 event replay 兼容。旧 events 需要能 hydrate 出合法 baton。
- 不要把 baton 放进 LangGraph local state。baton 属于 workflow orchestration，不属于 LLM graph。
- LLM output 一律视为 proposal。任何业务 transition 必须 typed + validated。
- 避免 big-bang rewrite。shadow mode 是必要步骤。
- 保留当前扩展性：specialist-specific tools/forms 仍模块化，只是 transition authority 移到 WorkflowEngine。
- 对真正 impossible state 保持 fail-loud；对可恢复用户错误，应转为 editable form state。
### **改进后的预期影响**

- 防止 unauthorized agent progression，例如“表单未确认但实验已开始”；
- 降低 form/chat/snapshot desync；
- late confirm、duplicate MQ、stale event 行为变 deterministic；
- 降低 prompt rule 对业务正确性的承担；
- 降低新增 specialist 的 blast radius；
- 将许多长链路 integration bug 转化为小型 transition-table 测试；
- 改善 lab dispatch failure 后的用户恢复路径；
- narration 被 baton facts 约束，减少 future-state / sibling-specialist hallucination。
**---**

## **建议验收标准**

- 存在覆盖 objective -> plan -> TLC -> CC -> FP -> RE 的 baton transition table。
- 所有 form confirmations 校验 `active_decision_id`、`active_form_kind`、owner id 和 baton version。
- baton phase 不允许时，任何 lab dispatch 都无法发生。
- narration 不能声称超出 baton state 的未来阶段或 sibling specialist actions。
- UI active form、session snapshot、current specialist 和 assistant text 都从同一组 baton facts 派生。
- regression tests 覆盖 #47 和 #65 的状态错乱流程。
- 新增 specialist 不需要修改无关 specialist prompts 或 parent-state propagation payload。
