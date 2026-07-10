# S3 任务：c12-ai/BIC-meta#122 三轮 — 左右两栏底部基线对齐（验收口径重定）

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #122 最新"复测反馈"评论（用户第三次报不对齐——历轮口径都错在只量单栏，务必先 Read 截图 113 理解用户在比什么）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（0b5f6cb+，git log 确认）切工作树 .wt/fe-122c 开分支 fix/issue-122-cross-pane-baseline（不 push/不 PR/不动台架 :5174）。

## 要点
- 量测对象是**整页**：左聊天栏输入区（含其顶部分隔线）与右工作区 footer（含其顶部分隔线）。目标：两条分隔线同一 y、两底部条总高一致（或给出有依据的设计决定并对齐主导线）。
- 用 /frontend-design:frontend-design 技能定设计决定；自起 dev server 连台架 BE，整页截图前后对比 + getBoundingClientRect 量测数字入 issue。
- 改动可能落在左栏（chat composer 容器）或右栏（PaneFooter）或两者——以最小改动达成基线一致；历轮成果（三步等高 72px、去卡片、tab 体系）不回归。
- tests/helpers.ts 不入提交。

## 二元验收
(1) 整页量测：左输入条分隔线 y == 右 footer 分隔线 y，两底部区 offsetHeight 相等（数字入 issue）；(2) 三步间 footer 仍等高；(3) pnpm lint && pnpm test && pnpm build 整链绿；(4) 全页前后截图对比入 issue。

## 收尾
设计决定 + 量测数字 + 截图评论 issue #122，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
