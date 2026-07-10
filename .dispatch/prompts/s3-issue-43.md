# S3 任务：修复 c12-ai/BIC-meta#43 — RE 溶剂比例输入框无法输入（受控 input 规范化覆盖吃掉冒号）

你是 S3（独立复核 + 实现 + 提交）。先独立复核 issue #43 根因（读代码自证），复核结论评论到 issue，再实现。

## 工作区纪律（必须遵守）
- 自建 worktree + 侧分支：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-43-re-ratio-input /Users/wenlongwang/Work/BIC/talos/.wt/portal-43 fix/chat-ux-lang-error-tubeid`。
- **绝不**触碰 bench 主目录 `/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal` 工作区（用户手测中），绝不重启服务。
- 提交落侧分支。不 push、不开 PR。合入窗口由 root 统一协调。
- s3-issue-41 同期在 portal fix 分支的另一 worktree 修 FpParamsForm——文件不相交，侧分支互不阻塞。

## 根因（S1 已析，待你复核）
`src/components/workspace/forms/ReParamsForm.tsx`
- :248 输入框 value = `ratioLabel(draft.solvent_ratio, ...)`（数组 join ' : ' 的派生串）；
- :250 onChange 每击键 `parseRatio()`（parseInt + 按 `[:/,+\s]+` 切分，丢非数字中间态）→ 立即用规范串覆盖输入框；
- 效果：逐键输入 "20:1" 在打 ":" 时被吃、继续打 "1" 变 "201"。两段比例无法正常键入。空起点（BE 未播种 ratio，见 #42）必踩。
- presence gate :144 把 ratio 设为确认硬门 → 功能级阻塞。

## 修复要求
- 受控输入保留原始文本 state（本地 string state），parse 延迟到 blur/commit，或允许中间态存在而不回写规范串；外部 draft 更新（如 BE 播种）仍能同步进来。
- 溶剂体系输入框（:171 updateSolventSystem，同款模式）检查是否同病，如是一并修（同文件同根因，不算扩scope）；CC/TLC 表单若有同款模式只在 issue 评论列出，不修。
- 保留现有校验语义（ratio ≥1 整数、长度与溶剂数一致）。

## 二元验收（PASS 当且仅当全部成立）
1. 组件测试：模拟逐键输入 "2","0",":","1" → draft.solvent_ratio === [20,1] 且显示 "20 : 1"（或等价原始文本保留断言）；空起点可键入两段比例；错误态（"abc"、"0:1"）仍报 ratioPositiveInt。
2. 全量 `pnpm vitest run` + `tsc` + `biome check` 绿。

## 收尾
1. 复核结论 + 修复摘要（commit sha、测试计数）评论到 issue #43，标签改 `stage:已实现待复测`。
2. `dispatch done` 汇报：FACTS 与 Judgment 分开。
