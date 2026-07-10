# 状态语义规范化 · 全库读取点审计（架构动作 ②）

## 摘要（结论先行）

**审计 154 个状态字段读取点：合规 133 / 违规 3 / 存疑 18。全部 3 个违规都在 portal，全属同一族——"用 `trial.phase`/`progress` 代替 `trial.status` 判终态失败"；BE 生命周期状态机零违规。** 这印证备忘录第一节的判断：编排骨架（BE）健康，问题集中在投影/派生层——此处是 FE 派生层。

三个违规是 **#21 的残留缺口**的精确定位：portal#14 已修好徽章、失败卡（progress=null 时）、MonitorPane、表单重开，但 **tab 路由（`derive-routing.ts` `lifecycleForTrial`）、subtab 派生（`ParameterDesignPanel:303-304`）仍不读 `status=failed`** → 失败 trial 被路由到"配置"面而非失败面，subtab 停在"active"。18 个存疑绝大多数是同一模式的软化版（成功态用 `phase==='done'`/`analysisCompleted` 而非 `status==='completed'`）+ 两处 BE 桥接（SpecialistPhase↔TrialPhase read-through）+ 一个"幽灵 rollup"（`jobs.status` 声明从子 trials 派生，但全库无写入者，恒为 `pending`）。

**建议**：违规按 P1（#21 失败态 UI 恢复：`lifecycleForTrial` + subtab，一批修）/ P2（成功态投影收敛）分批 S3；语义表（第三节）可直接进 spec（L2 persistence + FE 契约各一节）。BE 无需改动。

---

## 一、审计基准与方法（Facts）

**只读铁律遵守**：全程只读 + grep，未改产品代码、未重启、未写库、未跑 reset。

**基准漂移（必读，Fact）**：审计窗口内两仓 HEAD 均被并发 S3 链（#19）推进，BE 甚至在审计末段进入 **未解决 merge 冲突**状态。为可复现，各分区锚定其观察到的不可变 commit，经 `git show/grep <sha>` 读对象库，未触碰进行中的 merge：

| 仓库 | 会话起始 HEAD | 审计末观察 HEAD | 锚定 commit（行号基准） | 备注 |
|---|---|---|---|---|
| BIC-agent-service | `a7b8198` | `10ab0c10` | **`a7b8198`** | `tlc.py` 末段为 `UU`（未解决冲突）；`tools.py` 脏→已提交，RE `query_l4_status` 工作区 :2098 vs `a7b8198` :2105（±7 行） |
| BIC-agent-portal | `025a10b` | `0c008bb` | **`0c008bb`** | 无 merge 冲突；头号违规已在 `0c008bb` 复核 |

分支均为 `fix/chat-ux-lang-error-tubeid`。**行号可能与当前 HEAD 有 ±小幅漂移**（仓库审计期间被推进）；语义结论（哪些读取点存在、其合规性）不受行号漂移影响。

**方法**：6 个只读子会话（互不共享上下文，保证独立性）分区枚举，各按同一 rubric（备忘录第四节语义）逐点分类。主会话对最高信号点（`pick_in_flight_task`、`jobs.status` rollup、`derive-routing.lifecycleForTrial`、`selectStatusBadge`）独立复核 primary source。

| 分区 | 范围 | 合规 | 违规 | 存疑 | 总 |
|---|---|---|---|---|---|
| BE dispatch/reception | reception_node / dispatcher / route_after_admit / plan_subgraph | 12 | 0 | 4 | 16 |
| BE specialists | tlc/cc/re/fp 子图 + tools + guardrail + dynamic_prompts | 51 | 0 | 2 | 53 |
| BE narrate/query | query_agent / narrate 出口 / dynamic_prompts / intent | 12 | 0 | 3 | 15 |
| BE events/repos/session | events.apply / repos / fast_path / reconciler / service | 24 | 0 | 1 | 25 |
| portal stores/selectors | workspaceStore / selectors / derive-routing / event-dispatcher | 10 | **1** | 6 | 17 |
| portal panels/components | workspace/ 各面板 + result/ | 24 | **2** | 2 | 28 |
| **合计** | | **133** | **3** | **18** | **154** |

---

## 二、单一语义（spec-ready 最终稿）

可直接进 spec（L2 `persistence.md` 一节 + FE 契约一节）。权威定义源自备忘录第四节，本审计据此逐点判定并补全边界。

| 字段 | 类型/取值 | 权威范围 | 允许用于 | **禁止**用于 |
|---|---|---|---|---|
| `trial.status` | VARCHAR：`pending`/`in_progress`/`completed`/`failed`（wire 另见 `waiting`/`sent`/`cancelled`/`timeout`/`dispatched`）；终态 = `TERMINAL_TASK_STATUSES`（含 completed/failed/cancelled/timeout） | **权威生命周期；终态判定唯一来源** | 终态判定、在飞判定、retry/dispatch 门控、**失败态 UI（tab/subtab/badge/panel 全部）** | — |
| `trial.phase` = `TrialPhase` | `collecting_params`/`rts`/`conducting`/`done`（per-attempt，持久） | 子图内部阶段机 | 子图内 form-vs-dispatch 路由、跨轮 re-entry 播种 | **生命周期/终态判定**（#5/#21/#26 根因）；**不得漏进用户可见叙述** |
| `SpecialistPhase`（L3 literal） | 同 TrialPhase 四值，**故意不与 TrialPhase 统一**（可能分叉，如 retry-loop） | L3 agent-work 阶段（intra-invoke） | 子图内条件边路由、阶段工具过滤、阶段系统提示选择 | 跨用为持久 TrialPhase 语义、生命周期判定 |
| `progress` / `trial.steps` | Nexus 每步快照 + `task_progress` SSE（**易失**，快照重水合后为 null） | live 执行明细投影 | **仅展示补充**（monitor log、step ticker、进度条、re-render 去重） | 任何路由/生命周期/终态门控；**不得作为终态失败的唯一信号**（须 `trial.status` 兜底） |
| `jobs.status` | `pending`/`running`/`completed`/`failed`（声明为子 trials rollup） | job 级 rollup | job 级展示 | — ⚠️ **当前从不写入，恒为 `pending`（见第六节）；消费前须先落实 rollup 或从 DTO 撤下** |
| `experiments.stage` | `experiment_objective`/`workflow_design`/`parameter_design`（no-backward） | 顶层工作流阶段 | L1 工作流门控（参数设计仅在 objective+plan 确认后）、顶层 stepper/tab 展示 | per-trial/job 执行判定 |
| `plans.status` | `recommended`/`proposed`/`confirmed` | plan 生命周期 | plan 门控、`planConfirmed` 派生、活跃 plan 选择 | per-trial 执行判定 |

**跨层落点**：终态失败的**唯一权威**是 `trial.status ∈ {failed,cancelled,timeout}`；`progress`/`phase` 均为投影，快照重水合会丢 `progress`，故任何失败态 UI 必须以 `trial.status` 为先（这是 #21 的规范表述，已在 `isTerminalFailStatus` docstring 中写明，但未在所有消费点接线）。

---

## 三、逐点审计表

行号锚定第一节的基准 commit（BE `a7b8198` / portal `0c008bb`）。

### 3.1 BE — dispatch / reception（合规 12 · 违规 0 · 存疑 4）

| file:line | 读的字段 | 用作什么判定 | 判定 | 建议 |
|---|---|---|---|---|
| reception_node.py:239 | `trial.status ∈ TERMINAL` | in-flight 门：跳过终态 trial 选下一派发目标 | 合规 | #5 正例，保持 |
| reception_node.py:828 | `trial.status`（经 pick_in_flight_task） | dispatch 主决策：有在飞→复用其 specialist | 合规 | 保持 |
| route_after_admit.py:72 | `trial.status`（pick_in_flight is not None） | 路由门：有在飞→dispatcher；无→stage gate | 合规 | 保持 |
| specialist_dispatcher.py:139 | `trial.status ∈ TERMINAL` | final result_review accept 后 cursor 出界→clean end | 合规 | 保持 |
| route_after_admit.py:88,90,92 | `experiments.stage == *` | L1 工作流门：objective/workflow/parameter→派发头 | 合规 | stage 权威用途 |
| reception_node.py:246 | `plans.params.steps[seq].type` | 步骤 robot/manual 分类 | 合规 | 读 plan 定义（非 trial.steps 易失快照） |
| reception_node.py:317 | `plan_draft.steps` | fast-path 选下一 robot 派发候选 | 合规 | plan 定义驱动 |
| reception_node.py:338 | `ctx.jobs` + `ctx.next_job` 游标 + type | cross-turn 选下一派发（游标=plans.current_job_id） | 合规 | 用 plan 游标非 phase |
| reception_node.py:844 | executor + type（classify_step_dispatch） | disposition→specialist/skip/none 门控 | 合规 | 派发分类唯一权威 |
| reception_node.py:500,892 | job.executor + type（_prior_is_robot_tlc） | CC 派发前拓扑判定→抑制手动上传 | 合规 | 基于 plan 形状 |
| plan_subgraph.py:594 | `plan_draft.steps` | plan-confirm 后首派发选首个 robot | 合规 | 同款派发分类 |
| reception_node.py:437 | `trial.phase ∈ {rts,conducting,done}` | 派生 params_confirmed 兜底（跨轮 form-vs-dispatch 态） | 合规 | phase 权威用途（非终态） |
| reception_node.py:151 | `trial.phase`→`_normalize_phase`→current_phase | params picker：持久 TrialPhase 读作子图 SpecialistPhase 播种 | 存疑 | sanctioned 桥（docstring 明示），仅子图路由；确认跨型 coercion 为设计意图 |
| reception_node.py:190 | 同上（terminal-task picker） | 同上 read-through | 存疑 | 同 :151 |
| reception_node.py:241 | 同上（in-flight 派发） | latest.phase read-through 为播种 | 存疑 | 同 :151 |
| reception_node.py:542（镜像 :631,:742） | 前置 trial `.params`/`.analysis` blob 存在性 | carryforward seed 门：以 blob 存在推断"前置 robot trial 已完成" | 存疑 | 以 blob 存在代替 `status=completed` 推断完成；safe-degrade 到手动、非硬门；建议改读 `trial.status` 或明示为"数据可用性检查"非"完成判定" |

范围负事实：next-step 在飞门读 `status`（非 phase）；`.steps` 读点全部是 `plan.params.steps`/`plan_draft.steps`（plan 定义）；`intent_detection.py`/`user_admittance.py` 范围内无审计字段读取点。

### 3.2 BE — specialists（合规 51 · 违规 0 · 存疑 2）

phase 读取全部为 intra-invoke 门控/工具过滤/提示选择（合规）；**终态检测一律用 `trial.status`**。仅列代表性行与全部存疑。

| file:line | 读的字段 | 用作什么判定 | 判定 | 建议 |
|---|---|---|---|---|
| cc.py:262 · re.py:234 · fp.py:175,222 | `trial.status ∈ TERMINAL`（+not analysis_completed） | 终态检测→路由 auto_analyze/auto_conduct | 合规 | 终态用 status，正确范式 |
| tlc.py:432 | `trial.status == AWAITING_CONFIRMATION`（round-done） | 检测轮次完成→evaluate_tlc_result | 合规 | 用 status 判轮界（非 phase/steps） |
| tlc.py:693 | `trial.status == 'failed'` | 选 LAB_TASK_FAILED 失败态叙述 | 合规 | status=failed 驱动失败态（#21 正例） |
| tlc.py:697 | `current_phase == 'done'` | accepted-failure 叙述分支 | 合规 | 失败原因取自 analysis.criteria（#11 正确形） |
| cc/tlc/re/fp.py（rts/collecting_params/conducting 各门） | `current_phase == *` | emit_form / submit / auto_* 的 intra-invoke 门控 | 合规 | 子图内路由，submit 成败来自 ToolMessage 非 status |
| tools.py:656 | `response.status ∈ {FAILED,CANCELLED}` | 派发响应 is_terminal_failure→写 lab_task_id/派发事件 | 合规 | 读派发调用自身响应（权威源） |
| dynamic_prompts.py:622-623 | `current_phase`（_resolve_phase） | 选 5 个 specialist 的阶段系统提示 | 合规 | intra-invoke；done 分支失败原因取自 analysis |
| guardrail.py:50,75 | `current_phase != rts` / `!= conducting` | submit_l4 / cancel_l4 可调用门控 | 合规 | current_phase 由 trials.phase 水合（同值）；仅 intra-invoke，勿跨用为生命周期 |
| tools.py:1275 | `task_read.status`（CC query_l4_status，live Nexus） | 作 LLM 观测串→提示 LLM 决定 analyze/wait | 存疑 | 展示 vs 门控模糊；真实终态门为确定性 `trial.status` 兜底（cc.py:262），建议文档明确此为软观测 |
| tools.py:2105 | `task_read.status`（RE query_l4_status） | 同上 | 存疑 | 同 :1275，真实门为 re.py:234 |

### 3.3 BE — narrate / query（合规 12 · 违规 0 · 存疑 3）

| file:line | 读的字段 | 用作什么判定 | 判定 | 建议 |
|---|---|---|---|---|
| query_agent.py:1044 | `experiments.stage.value` | 状态问答展示顶层阶段 | 合规 | 权威范围 |
| query_agent.py:1046 | `plans.status` + current_job_id | 状态问答展示 plan 生命周期+游标 | 合规 | 权威范围 |
| query_agent.py:1055 | `jobs.status` | 状态问答展示 job 级态（no trial yet） | 合规 | ⚠️ 但 job.status 恒为 pending（第六节），"no trial yet"时 pending 尚可，一旦有 trial 应回退 trial.status |
| query_agent.py:1061 | `trial.status` | 状态问答展示 trial 生命周期 | 合规 | 终态展示读 status 正确 |
| query_agent.py:1061 | `trial.phase.value` | 与 status 并列写入用户可见状态串 | 存疑 | per-attempt 子图内部机漏进用户叙述（LLM 空/降级时原样回显）；建议移除或标注为内部子阶段 |
| query_agent.py:1103 | `trial.phase.value` | 失败问答里并列回显 phase | 存疑 | 同 :1061 |
| query_agent.py:402,1089,1103,1109 | lab task `status` | 任务列表/active/失败问答展示 lab 侧态 | 合规 | lab 权威展示 |
| query_agent.py:1112 | lab task `steps[].error_message` | 失败问答列失败步骤（展示） | 合规 | steps 仅展示明细 |
| dynamic_prompts.py:224-233 | `trial.analysis`（criteria） | TLC 终态"失败/成功"供 done 叙述 | 合规 | 正范式：终态化学判定来自 analysis 非 phase/status |
| dynamic_prompts.py:783 | `plans.current_job_id` | you-are-here 当前步 fallback | 合规 | plan 游标允许用途 |
| dynamic_prompts.py:792-794 | `job.seq`（相对 current_seq） | 生成"already handled/当前/later"步骤标记喂 LLM | 存疑 | "handled"由 seq 顺序而非前序 job/trial 终态 status 推出；非终态前序步会被叙述成"已处理"；建议以前序 status 终态为准 |

零读取点文件：`intent_classifier.py`、`_narrate_closing.py`、`terminal_once.py`、`plan_dynamic_prompt.py`。

### 3.4 BE — events / repos / session（合规 24 · 违规 0 · 存疑 1）

| file:line | 读的字段 | 用作什么判定 | 判定 | 建议 |
|---|---|---|---|---|
| runtime_emitted.py:378 | `plan.status` | PlanConfirmed 幂等冻结门 | 合规 | plan 生命周期门 |
| runtime_emitted.py:426 · bypass_emitted.py:154 | `experiment.stage` | L1 stage 前进门（no-backward） | 合规 | 工作流阶段门 |
| runtime_emitted.py:616,727 · orch_emitted.py:136 | `trial.phase` | form-confirm 相位规约 / draft 保护门 | 合规 | 子图内，非生命周期 |
| runtime_emitted.py:680 | `trial.status ∉ TERMINAL` | result_review-accept 终态幂等门 | 合规 | **#5 修复点：终态判定唯一读 status** |
| runtime_emitted.py:683 | `trial.analysis`（verdict） | 派生要写入的终态**值**（TLC fail→failed 否则 completed） | 合规 | 派生终态值合规（由 :680 status 门守护，非从 phase 派生；#11 verdict-scoped） |
| trials_repo.py:478,541,573,595,651,663,667 | `trial.status` | apply_terminal_from_lab / round 抑制 / reconciler 选取 / 公告 CAS 终态守护（`WHERE NOT IN terminal`） | 合规 | 规范级终态幂等形（#5/#26） |
| trials_repo.py:73,76 | current/new status | _derive_transition_key：终态回退守护 + 进度公告 key | 合规 | 展示派生，终态回退用 status 守护 |
| trials_repo.py:495 · event_ingress.py:249,274,284 · reconciler.py:215 | durable `trial.status` | 回读 durable 终态构 TASK_TERMINAL turn，防陈旧覆盖 | 合规 | 用回读权威 status |
| event_ingress.py:79,112,124,140,147,231 · fast_path:436,446 · reconciler:198,225,228 | lab wire `payload.status` | ingress/reconcile 路由终态/在飞 | 合规 | 以 lab 权威 status 分派 |
| fast_path_handlers.py:436,446 | `progress.status`/`steps[].status` | try_record_transition_announcement 进度公告 | 合规 | 纯展示（step-strip），非门控 |
| service.py:1090 | `plan.status ∈ {recommended,proposed,confirmed}` | _pick_active_plan 选活跃 plan | 合规 | plan 级选择 |
| jobs_repo.py:38,55 | `jobs.status` | 声明"从子 trials rollup" | **存疑** | **rollup 从未实现**：`update_fields`（唯一可写 `{status}`）全库无调用者，`reconcile` 只写 executor/title→job.status 恒为 server default `pending`（第六节） |

### 3.5 portal — stores / selectors / derive-routing（合规 10 · 违规 1 · 存疑 6）

| file:line | 读的字段 | 用作什么判定 | 判定 | 建议 |
|---|---|---|---|---|
| **derive-routing.ts（lifecycleForTrial）** | **缺读 `trial.status ∈ {failed,cancelled,timeout}`** | **lifecycleForTrial 无 terminal-fail 分支→failed(phase=conducting) 落 `'task'` 配置面** | **违规** | **#21 头号缺口**：`isTerminalFailStatus` 已定义（docstring 称须驱动 badge/progress/monitor）却未接入 tab 路由；与 `onTaskFailed`（"auto-switch to Monitor"）注释漂移。修：`if (isTerminalFailStatus(trial.status)) return 'monitor'`（在 phase switch 前） |
| derive-routing.ts:`phase==='done'`→'result' | `trial.phase === 'done'` | lifecycle tab→'result'（成功终态面） | 存疑 | 成功终态应由 `status==='completed'` 派生；phase 作代理与 status 并行（#26）；awaitingResultReview 已兜 pre-done 窗口 |
| derive-routing.ts:`isMonitorVisibleStatus` | `trial.status`（waiting/in_progress） | lifecycle tab→'monitor' | 合规 | status 用于 monitor 展示 |
| derive-routing.ts:phase switch | `trial.phase`（collecting_params/rts/conducting） | lifecycle tab→'task'（配置面） | 合规 | 子图内 form-vs-dispatch 路由 |
| derive-routing.ts:deriveRouting step2 | `trial.phase !== TERMINAL` | active-trial 选取优先"非终态"候选 | 存疑 | failed(phase=conducting) 被当非终态可抢为 active；终态偏好应含 `status ∈ {completed,failed}` |
| selectors.ts:94 | `trial.status ?? progress.status`（isTerminalFailStatus） | selectStatusBadge→'failed' | 合规 | **#21 修复：status-first，progress 仅 pre-snapshot 兜底** |
| selectors.ts:97 | `analysisCompleted` | selectStatusBadge→'completed'（成功徽章） | 存疑 | 成功终态由 `analysisCompleted` 标志派生非 `status==='completed'`；analysis 落地可能早于 accept 终态→FE 成功态与 BE status 瞬时不一致（#26，仅展示） |
| selectors.ts:106 | `trial.status ?? progress.status` | selectCanShowMonitor 展示门 | 合规 | status→monitor，排除 failed 合理 |
| selectors.ts:114 | `trial.phase === 'done'`（OR analysis/results/pendingForm） | selectCanShowResult 展示门 | 存疑 | result 可见性用 phase 代理；建议改读 status/results 信号 |
| workspaceStore.ts:277-282 | `trial.phase`（主），否则 progress/labTaskId/dispatchedAt 存在性 | trialPhase 重建（喂 deriveRouting） | 存疑 | live-only trial 用 progress 存在性→conducting；注意别让 progress 投影渗入终态语义 |
| workspaceStore.ts:556,564 | `progress.status`/`steps[].status` | sameProgress 去重相等判定 | 合规 | 仅 re-render 去重 |
| workspaceStore.ts:636,672 | `trial.status ?? progress.status` | routableTrials/routingPatch monitor 路由 | 合规 | status-first + progress 兜底 |
| workspaceStore.ts:639 | `phase !== 'done'`（& analysis/analysisCompleted） | awaitingResultReview 派生→result 路由 | 存疑 | phase 作"仍待评审"终态信号与 analysis 并行；phase==='done' 应等价 status 终态却分立 |
| workspaceStore.ts:1036 | `experiments.stage` | hydrate→store.stage | 合规 | 权威范围 |
| workspaceStore.ts:1056 | `trial.status === 'confirmed'`（\|\| lab_task_id） | hydrate 派生 paramsConfirmed | 合规 | status→dispatch 门控（'confirmed' 为开放串值） |
| workspaceStore.ts:1091 | `plans.status === 'confirmed'` | hydrate 派生 planConfirmed | 合规 | plan 确认判定 |

`chatStore.ts`（气泡 phase/status，非 trial 字段）、`event-dispatcher.ts`（按 kind 分发）、`types/*.ts`（纯类型）不计入。

### 3.6 portal — panels / components（合规 24 · 违规 2 · 存疑 2）

| file:line | 读的字段 | 用作什么判定 | 判定 | 建议 |
|---|---|---|---|---|
| ExperimentProgressPanel.tsx:314 | `trial.status`（isTerminalFailStatus） | progress=null（快照重水合）时渲染失败卡 | 合规 | **#21 修复正确：失败 UI 由权威 status 驱动** |
| MonitorPane.tsx:28 | `progress` + `trial.status`（isTerminalFailStatus） | hasActivity 门（内容 vs 空态） | 合规 | 失败经 status 路由到内容而非空态 |
| ParameterDesignPanel.tsx:260,261,274 | `trial.status`（failed/cancelled→terminalFailed） | readOnly 不因失败回退 + footer 重显（retry） | 合规 | **#21/#6 修复正确**；建议纳入 `timeout`（与 isTerminalFailStatus 集合不一致会漏 timeout retry） |
| **ParameterDesignPanel.tsx:304** | **`trial.phase !== 'done'`→'active'（stageTabs 从不读 status）** | **SpecialistSubtab 状态派生** | **违规** | **失败 trial（phase 停 rts/conducting）被标 'active'，subtab 无法显失败（#21/#26）**；应加 `isTerminalFailStatus(trial.status)` 驱动 'failed' tab 态 |
| **ParameterDesignPanel.tsx:303** | **`trial.phase === 'done'`→'completed'** | **SpecialistSubtab 阶段完成，下游 gates 解锁** | **违规** | **用 phase==='done' 判阶段完成（#5 模式）**；应改读 `trial.status === 'completed'` |
| ExperimentProgressPanel.tsx:179 | `progress.status` | 总览卡头部徽章/色调（事实上的 trial 级态显示） | 存疑 | 总览终态应以 `trial.status` 为先（对齐 selectStatusBadge failure-first），progress 仅 live 补充 |
| ExperimentProgressPanel.tsx:305 | `progress`（存在性） | 先渲染 live 卡，早于 :314 终态失败判定 | 存疑 | live 失败但 progress.status 滞后（无终态 push）时总览不显失败（残留 #21）；进卡前先查 `isTerminalFailStatus(trial.status)` |
| ExperimentProgressPanel.tsx:86,96,129,216 | `progress.status`/`steps[].status` | 进度条/步骤光标/图标/完成文案 | 合规 | 纯展示 |
| MonitorPane.tsx:33 · ResultConfirmationPane.tsx:49 | `experiments.stage` | pendingObjective 空态回引导 | 合规 | — |
| task-config-steps.ts:68,81,100,110,120 | `experiments.stage` + planConfirmed + paramsConfirmed | 步锁定/状态标签/canSelectStep（parameter 步仅 parameter_design 可达） | 合规 | L1 核心工作流门，权威字段正确 |
| TaskConfigPane.tsx:39,43,45,113 | `experiments.stage` + planConfirmed + paramsConfirmed | stepper 权威 + 摘要文案 | 合规 | — |
| ParameterDesignPanel.tsx:122 | planConfirmed（plans.status） | stageHasConfirmedRobotJob | 合规 | — |
| WorkspaceHeader.tsx:49 | `selectStatusBadge`（trial.status failure-first） | 头部状态徽章 label/tone（#26） | 合规 | 徽章 failure 优先，与权威 status 一致 |
| ExecutionLogPanel.tsx:106 | step-event `status`（steps/progress 域） | 执行日志每行色调 | 合规 | 纯展示 |
| WorkflowDesignStep.tsx:25,52,57,95 | planConfirmed（plans.status） | confirmed 徽章/hint + 冻结 toggle | 合规 | — |

---

## 四、违规修复清单（按风险分级）

**3 个违规全在 portal，全属"用 `phase`/`progress` 代替 `status` 判终态失败"同一根因（#21/#26 状态投影分裂）。BE 零违规，无需改动。**

### P1 — #21 失败态 UI 恢复缺口（一批 S3，同根因同批修）

| # | 位置 | 缺陷 | 修复方向 |
|---|---|---|---|
| V1 | portal `src/lib/derive-routing.ts` `lifecycleForTrial` | 无 terminal-fail 分支 → 失败 trial 路由到 `'task'` 配置面而非失败面 | 在 phase switch **前**加 `if (isTerminalFailStatus(trial.status)) return 'monitor'`（或专设 'failed' lifecycle）；同步复核 `deriveRouting` step2 非终态偏好纳入 status 终态（存疑 Q-FE-2） |
| V2 | portal `ParameterDesignPanel.tsx:304` | stageTabs 从不读 `trial.status`，失败 trial 标 'active'，subtab 无法显失败 | 加 `isTerminalFailStatus(trial.status)` 驱动 subtab 'failed' 态 |

> V1+V2 是同一失败态在 **tab 层**与 **subtab 层**的两个未接线点，合成一批修最省。修复后须现场验收：TLC 参数确认→选幽灵盒（#19）→lab 400 失败→观察 tab 是否切到失败面、subtab 是否显失败、总览是否显失败（#21 二元验收）。

### P2 — 成功态投影收敛（可攒批，低风险）

| # | 位置 | 缺陷 | 修复方向 |
|---|---|---|---|
| V3 | portal `ParameterDesignPanel.tsx:303` | `phase==='done'`→'completed'，下游 gates 解锁（#5 模式，成功侧） | 改读 `trial.status === 'completed'`；因成功侧还有 analysis/awaitingResultReview 兜底，风险低于失败侧 |

---

## 五、存疑清理清单（18 点，按类分组）

非违规，但语义收敛时应逐一定夺；多数是"成功态用 phase/analysisCompleted 代理而非 status"，与 V1-V3 同族的软化版。

1. **FE 成功终态代理（#26 投影分裂，6 点）**：derive-routing `phase==='done'`→'result'、deriveRouting step2 `phase!==TERMINAL`、selectors.ts:97 `analysisCompleted`→'completed'、selectors.ts:114 `phase==='done'`、workspaceStore.ts:639 `phase!=='done'`、workspaceStore.ts:277 progress 存在性重建。**建议**：统一"成功终态 = `status==='completed'`（可辅以 analysis 信号），phase/progress 仅子图内/展示"，与 V3 一并收敛。
2. **BE SpecialistPhase↔TrialPhase read-through 桥（4 点）**：reception_node:151/190/241 `_normalize_phase`、guardrail.py:50。**建议**：保留（sanctioned，docstring 明示，仅 intra-invoke），但在 spec 明确"这是唯一允许的跨型 coercion 点，且只用于子图播种/门控，不得升格为生命周期"。
3. **BE phase 漏进用户叙述（2 点）**：query_agent:1061/1103 `trial.phase.value` 并列进用户状态串。**建议**：从用户可见串移除或标注为内部子阶段（narrate 契约化 ①的射程内）。
4. **BE "已处理"由 seq 顺序推（1 点）**：dynamic_prompts:792-794。**建议**：`handled` 以前序 `jobs.status`/`trial.status` 终态为准。
5. **BE query_l4_status 软观测（2 点）**：tools.py:1275/2105 live Nexus status 作 LLM 观测串。**建议**：文档明确"软观测，真实终态门为确定性 trial.status 兜底"。
6. **BE carryforward 用 blob 存在性（reception_node:542/631/742 记 1 点）**：以 `.params`/`.analysis` 存在推断前置完成。**建议**：改读 `trial.status` 或注释明示为"数据可用性检查"。
7. **FE 总览用 progress.status（2 点）**：ExperimentProgressPanel:179/305。**建议**：进 live 卡前先查 `isTerminalFailStatus(trial.status)`（与 V1 同族，可并入 P1 收尾）。
8. **jobs.status 幽灵 rollup（1 点）**：见第六节。

---

## 六、专项：`jobs.status` 幽灵 rollup（primary-source 已核验）

**Fact**（`git show a7b8198`）：
- `models.py:279` 注释：`Rollup status (pending/running/completed/failed); derived from the child trial states`。
- `jobs_repo.py:38` `_UPDATABLE_FIELDS = frozenset({"status"})`——status 是唯一可写字段，为 rollup 预留。
- 但 `jobs.update_fields` **全库无任何调用者**（`grep -rn '\.jobs\.update_fields' app` 为空）；`jobs.reconcile` 只写 `executor`/`title`。
- 结论：**`jobs.status` insert 后从不更新，恒为 `server_default="pending"`。**
- DTO：`SnapshotJobItem.status`（sessions.py:719）把该 pending 透传到 portal 快照。
- 消费点：BE `query_agent.py:1055`（"no trial yet"时展示 job 级态）；portal 未见直接据 job.status 做生命周期判定。

**Judgment**：模型注释（"derived from child trial states"）与代码（无派生）矛盾——Rule 5 冲突，须择一：
- (a) **实现 rollup**：在 trial 终态转移时同步 `jobs.set_status`（从子 trials 派生）；或
- (b) **从 DTO/模型撤下 jobs.status**：链推进实际靠 `trial.status` + `plans.current_job_id`，job.status 非必需。
- 现状风险低（消费点少且多有 trial.status 兜底），但属"会说谎的字段"，未来误消费即成 #21 类缺口。**建议 (b) 为默认**（YAGNI：没有真实消费者需要 job 级 rollup），除非产品明确要 job 级进度展示则走 (a)。

---

## 七、与 #5 / #21 / #26 对账

| Issue | 类别 | 本审计对账结论 |
|---|---|---|
| **#5**（P0，已修 `b9800f0`） | 状态投影分裂 | **对齐、健康**。`reception_node:239` 在飞门读 `status`（非 phase）、`runtime_emitted.py:680` result_review-accept 终态幂等门读 `status ∉ TERMINAL`、:683 从 analysis verdict 派生终态值——全合规。#5 的修复（accept 同步写终态 status）正是本审计"终态唯一权威=status"的落地。BE 侧无回归。 |
| **#21**（P1，portal，stage:已实现待复测） | 状态投影分裂 | **部分修复，残留缺口已精确定位**。✅ 已修：selectStatusBadge（selectors:94）、失败卡（ExperimentProgressPanel:314）、MonitorPane（:28）、表单重开（ParameterDesignPanel:260-274）——全 status-first。❌ 残留（本审计新证）：**V1 tab 路由（derive-routing lifecycleForTrial）+ V2 subtab（ParameterDesignPanel:304）不读 status=failed** + 存疑 7（总览 progress.status 滞后）。**#21 的二元验收 (b)"总览/监控明确显示失败"在 tab/subtab 层尚未满足**——不应据 badge 已修就关单。 |
| **#26**（P3，措辞矛盾） | 状态投影分裂 | **同根同族**。头部徽章（WorkspaceHeader:49 已 status failure-first，合规）与步骤/subtab（ParameterDesignPanel:303-304 用 phase）分立，正是"parameters under review vs Waiting"措辞矛盾的结构来源。随 V2/V3 收敛即消解。 |

**数据先行小结**：#5 已彻底（BE 终态语义收敛完成）；#21 的 badge/panel 半已修但 **tab/subtab 路由半未修（V1/V2）**，二元验收未全满足；#26 随 V2/V3 一并解。

---

## 八、落 spec 建议

1. **L2 `persistence.md`**：新增"状态字段权威语义"一节，直接采用第二节最终表；特别写明"终态失败唯一权威 = `trial.status ∈ {failed,cancelled,timeout}`，`progress`/`phase` 为投影，快照重水合丢 `progress`"。
2. **FE 契约（portal `docs/project-prd.md` 或 spec）**：写明"失败态 UI（tab/subtab/badge/panel）必须以 `trial.status` 为先"，并把 `isTerminalFailStatus` 列为唯一失败判定入口。
3. **`jobs.status`**：按第六节择一（默认撤下），同步改 `models.py:279` 注释。
4. **narrate 契约（动作 ①）射程**：存疑 3（phase 漏进叙述）纳入 narrate 契约清扫。

（本文件为本地 markdown，单语中文，与 ops/ 既有文档一致；非飞书文档，双语规则不适用。）
