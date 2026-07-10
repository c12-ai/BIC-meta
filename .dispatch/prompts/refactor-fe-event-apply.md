# 重构任务 A：FE store 单一写路径（乐观写 = 合成事件走同一 reducer）

你是重构 session（独立设计 + 实现 + 提交）。整体依据：`/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/project-refactor-review-2026-07-09.md` §A（先读）。这是结构性重构，不是修 bug——但它必须让 #40 族 bug 在结构上不可能复发。

## 工作区纪律（必须遵守）
- 自建 worktree + 分支：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b refactor/fe-event-apply /Users/wenlongwang/Work/BIC/talos/.wt/portal-event-apply fix/chat-ux-lang-error-tubeid`。
- **绝不**触碰 bench 主目录 `/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal` 工作区（用户手测中），绝不重启服务、不 push、不开 PR。
- 并行提示：s3-issue-40（外科修，refactor/state-semantics 分支 commit a284c78）、s3-issue-41/43（侧分支）与你并行。外科修先救急、你做结构解——**读一读 a284c78 理解外科修形态**（`git -C /Users/wenlongwang/Work/BIC/talos/.wt/state-portal show a284c78`），你的结构必须覆盖同一场景；合流时 root 做语义合并。

## 病灶（六 issue 同族，全在 c12-ai/BIC-meta 可查）
#40：乐观 `clearForm()` 丢 confirmKind + SSE 回声因 pendingForm 已清而失效 → result_review 终态化在 live 会话永不发生 → activeTrial 卡死、下一步无确认按钮。
#37/#26/#21/#24/#34：accept 只写 phase 不写 status / badge 与 subtab 两处派生打架 / rehydrate 丢投影 / 渲染层重复 / failed 掉错 tab。
共同根因：同一语义动作有三条写路径（乐观手工 patch、SSE 事件 reducer、snapshot rehydrate），各自漂移。

## 目标形态
1. 乐观路径不再手写局部 patch：点击成功后**合成与 SSE 等价的规范事件**（form_confirmed 等，含 confirm_kind、trial/task id、event_id=API 返回的权威 id），送进与 SSE 完全相同的 apply/reducer。
2. 所有事件 handler 按 event_id 幂等：回声重放、乐观+回声双至、snapshot 后补发都收敛到同一状态。
3. deriveRouting 已是"单一路由真相"；把该原则推广到 mutation 全域，收敛 workspaceStore 中绕过 reducer 的直写点（先盘点再收敛，盘点结果写进 commit message 或 issue 评论）。
4. 范围控制：本轮收敛 form confirm / decision / result accept 这条主链（六 issue 的病灶带）；其余直写点列清单不强改（YAGNI）。

## 二元验收（PASS 当且仅当全部成立）
1. 等价性质测试：对 form_confirm（params/result_review/objective/plan）与 decision 两类动作，「乐观合成事件后的 store 状态」逐字段 === 「直接应用对应 SSE 事件后的状态」（参数化）。
2. #40 会话事件序列 replay 测试（accept 乐观清除 → SSE 回声 → 下一步 task_created/form_requested）：被评审 trial 终态化、activeTrialId 前进、footer 门控为真——**在没有外科补丁代码的前提下由结构保证**。
3. 幂等测试：同 event_id 的事件应用两次 === 应用一次。
4. 全量 `pnpm vitest run` + `tsc` + `biome check` 绿；既有测试不回归（行为保真）。

## 收尾
1. 设计摘要 + 直写点盘点 + commit sha + 测试计数，评论到 c12-ai/BIC-meta#40（注明"结构解，另有外科修 a284c78"）。
2. `dispatch done` 汇报：FACTS 与 Judgment 分开。合入窗口由 root 统一协调。
