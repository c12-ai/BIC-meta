# S3 任务：修复 c12-ai/BIC-meta#51（叙述后思考应开新气泡）+ #52（中文界面 plan 步骤名中文化）

你是 S3（独立复核 + 实现 + 提交）。两个 portal UIUX issue，一个 session 处理，**每个 issue 独立 commit**。先分别独立复核根因/现状（读代码自证），复核结论各自评论到 issue，再实现。

## 工作区纪律
- 自建 worktree + 侧分支（基于 bench-verify 当前 tip）：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-51-52-uiux /Users/wenlongwang/Work/BIC/talos/.wt/portal-51-52 bench-verify`。
- **绝不**触碰 bench 主目录工作区（用户手测中）、绝不重启服务、不 push、不开 PR。合入窗口由 root 协调。
- 注意 bench-verify 上已有重构 A（事件同构：optimistic-events.ts + 事件按 event_id 幂等）与 PR#16（i18n 全量中文化 + localized-display-name.ts）——你的改动必须与两者兼容。

## Issue #51：text_done 后同 turn 的后续事件应开新气泡
- 现状：一个 turn 的叙述句落地后，同 turn 继续的推理/工具事件仍流入当前气泡的折叠"追踪"，计时继续走——用户看起来像卡住（会话 18249ece 实证）。
- 用户裁定：text_done 是分段边界；其后的事件开新的分析气泡，让"进行中"的追踪始终挂在最新气泡上（有活动指示）。
- 验收（issue #51 正文的二元验收照抄执行）：turn 内 [trace…, text_done, trace…] → 两个气泡；历史 hydrate 重放产生相同分段（无漂移）；单 text_done turn 行为不变；全量门禁绿。
- 落点提示：chatStore 的 turn→气泡聚合逻辑；与 #24 渲染层去重、#16b tool_call 配对渲染兼容。

## Issue #52：中文界面 plan 步骤名中文化
- 现状：步骤卡周边全中文，但步骤名本体是 BE title 英文（TLC / Column chromatography / Fraction Pool / Rotary evaporation）。
- 方向：FE 确定性映射（executor kind → i18n 键，en/zh 双语），BE title 作 fallback；与 PR#16 的 localized-display-name.ts / 既有 skill-labels.ts 术语对齐，**勿造第二套术语表**——中文叫法与 Parameter Design 页签等处一致（柱层析/组分收集/旋蒸；TLC 的中文叫法以 repo 现有术语为准）。
- 验收（issue #52 正文照抄执行）：四类步骤名中文界面显示中文、英文界面不变、切换即时生效；executor→标签映射双语齐全的组件测试；translation-parity guard 不破；全量门禁绿。

## 收尾
1. 每个 issue：复核结论 + 修复摘要（commit sha、测试计数）评论，标签改 `stage:已实现待复测`。
2. `dispatch done` 汇报：FACTS 与 Judgment 分开。
