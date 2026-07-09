# S3 任务：修复 c12-ai/BIC-meta#40 — result_review accept 后 live store 永不终态化，下一步表单无确认按钮

你是 S3（独立复核 + 实现 + 提交）。先独立复核 S1 的根因分析（issue #40 正文），复核结论（同意/推翻+证据）评论到 issue，再实现。

## 工作区纪律（必须遵守）
- 工作目录：`/Users/wenlongwang/Work/BIC/talos/.wt/state-portal`（分支 `refactor/state-semantics`）。
- **绝不**触碰 bench 主目录 `/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal`（用户正在手测），绝不重启任何服务，绝不写 DB。
- 提交落 `refactor/state-semantics` 分支。不 push、不开 PR。

## S1 已析根因（待你独立复核，见 issue #40 全文）
两处叠加，导致 result_review accept 的终态化写入（workspaceStore.ts:864-894）在 live 会话里从不执行：
1. `src/lib/use-submit-form.ts:93`（confirm）与 `:153`（decide）乐观调用 `clearForm()` 不带 confirmKind → `onFormCleared(undefined)` 跳过 result_review 分支。
2. SSE 回声 `event-dispatcher.ts:181` 带了 confirm_kind，但 pendingForm 已被 1 清空 → `pendingResultReviewTrialId()`（workspaceStore.ts:631）返回 undefined → 再次跳过。
后果链：被评审 trial 无 phase → `trialPhase()` 回退 'conducting'（labTaskId 非空）→ `deriveRouting` 非终态优先+最低 seq → 旧 trial 永久霸占 activeTrialId → 下一步 stage `isShownLive=false` → ParameterDesignPanel footer（:279-283）隐藏。
实证会话 e0368686：DB trials TLC failed/done、CC completed/done、FP pending/collecting_params（按 DB 跑 deriveRouting 本应选 FP），但界面 FP"排队中"无按钮、TLC 显示"完成"（progress.status 掩盖 failed）。

## 修复要求（方向，独立复核后可改进）
- 让 accept 终态化不依赖"清表单时 pendingForm 还在"：confirm()/decide() 在点击时捕获 confirmKind + 被评审 trialId 并显式传入（改 `onFormCleared` 签名或新增专用 mutator）；SSE 回声路径保持幂等（重复终态化无害），可用 evt 载荷兜底。
- 不要用"再发一次 snapshot 重取"掩盖问题——那是碰运气痊愈路径，修的是结构性时序洞。
- 注意 decide() 路径（result 面板的接受/拒绝按钮）与 confirm() 路径都要覆盖；reject 不应终态化。

## 二元验收（预先承诺，PASS 当且仅当全部成立）
新增确定性 vitest 重放事件序列「result_review accept（乐观 clearForm）→ SSE form_confirmed('result_review') 回声 → 下一步 task_created + form_requested」，断言：
(a) 被评审 trial `phase==='done'` 且 status 为判定终态（failed 判定不被 progress 'completed' 掩盖）；
(b) `activeTrialId` === 下一步 trial；
(c) 下一步 stage 的 footer 门控四条件全真（executeAllowed 除外，用 selector 层断言 isLiveTrial + !paramsConfirmed）。
再加一条 reject 路径不终态化的反向断言。全量 `pnpm vitest run` + `tsc` + `biome check` 绿。

## 收尾
1. 复核结论 + 修复摘要（含 commit sha、测试计数）评论到 issue #40，标签改 `stage:已实现待复测`。
2. 完成后 `dispatch ask` 请示 root 是否合入 bench-verify + 重启（用户在测，重启必须 root 协调）。
3. `dispatch done` 汇报：FACTS（commit、测试数、门禁输出）与 Judgment 分开。
