# S3 任务：修复 c12-ai/BIC-meta#41 — FP 容器分配选不中烧瓶（改名 Input 吞点击）

你是 S3（独立复核 + 实现 + 提交）。先独立复核 issue #41 的根因（读代码自证，不要只信 issue 文本），复核结论评论到 issue，再实现。

## 工作区纪律（必须遵守）
- 先自建 worktree：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add /Users/wenlongwang/Work/BIC/talos/.wt/portal-41 fix/chat-ux-lang-error-tubeid`，在其中工作。
- **绝不**触碰 bench 主目录 `/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal` 的工作区文件（用户正在手测 bench-verify），绝不重启服务。
- 提交落 portal 的 `fix/chat-ux-lang-error-tubeid` 分支。不 push、不开 PR。
- 若该分支 tip 已被其他 S3 推进，commit 前先确认 worktree 处于最新 tip。

## 根因（S1 已析，待你复核）
`src/components/workspace/forms/FpParamsForm.tsx`
- :413-421 外层 `<button>` 的 onClick 是唯一 `setActiveContainerId` 入口；
- :427-436 烧瓶分支在按钮内部套 `<Input>`（铺满 chip 文本区），其 `onClick` `stopPropagation()`（:434）吞掉点击 → 烧瓶永远选不中；
- 废液瓶分支（:422-424 纯 span）不受影响 → 只有废液瓶能选，与用户截图一致。
- 结构性根源：`<input>` 嵌在 `<button>` 里（interactive-inside-interactive）。修复要拆结构，不要再叠 workaround。

## 修复要求
- chip 的选中点击移到非嵌套结构上（如 li/div 处理选中，Input 独立）；Input 获得焦点/点击时同步选中该烧瓶（点进改名框 = 选中，直觉一致）。
- 保留：改名功能、MAX_FLASK_NAME_LEN 约束、readOnly 禁用、空烧瓶可删（× 按钮）、aria 语义（aria-pressed / aria-label）。
- 波及检查：键盘可达性（Tab 到 chip 可用 Enter/Space 选中）尽量保持或改善，不作硬性验收。

## 二元验收（PASS 当且仅当全部成立）
1. 新增组件测试：点击烧瓶名区域 → activeContainerId 切到该烧瓶（aria-pressed=true 或等价断言）；改名输入仍可编辑；废液瓶选中行为不变。
2. 全量 `pnpm vitest run` + `tsc` + `biome check` 绿。

## 收尾
1. 复核结论 + 修复摘要（commit sha、测试计数）评论到 issue #41，标签改 `stage:已实现待复测`。
2. `dispatch done` 汇报：FACTS 与 Judgment 分开。不需要请示合入——合入窗口由 root 统一协调。
