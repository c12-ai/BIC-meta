# S3 任务：c12-ai/BIC-meta#122 二轮 — tab 体系三层统一 + footer 高度 + 目标步去卡片下沉

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #122 最新"复测反馈"评论（含三张截图路径，先 Read）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（8a0b803，含你一轮 fc2a5e5 + #116/#120 合并）切工作树 .wt/fe-122b 开分支 fix/issue-122-tab-system-r2（不 push/不 PR/不动台架 :5174）。

## 要点
- **必须调用 `/frontend-design:frontend-design` 技能**。先产出导航层级图（L1 任务/监控/结果 → L2 步进器 实验目标/流程编排/参数设计 → L3 实验类型 TLC/过柱/组分收集/旋转蒸发），为每层定视觉语言：层级强弱要成体系（建议方向：L1 最强、L3 最轻，同层内只用一种态样式），写进 issue 评论作为设计决定记录。
- 三个具体修复：①L1/L2 与 L3 统一成一套体系（pill 与下划线不再混用，按你的层级方案定）；②实验目标步内部块（反应图容器/任务名称区）跟随去卡片基调，消框中框；③各步 footer 同一高度（量测断言）。
- 一轮规则（divider token、4px 输入圆角、无 UUID、滚动结构）不回归。
- 并行 child .wt/fe-123（监控面派生逻辑）在跑——你动样式层，它动数据派生，SpecialistSubtabs 可能双方都碰：你只动其 className/样式，逻辑行不动。
- 自起 dev server 连台架 BE 只读截图；运行态前后对比图入 issue。tests/helpers.ts 不入提交。

## 二元验收
(1) 三层 tab 每层单一视觉语言、层级强弱可辨（前后截图 + 设计决定记录）；(2) 目标步内部无描边卡（截图）；(3) 各步 footer 高度量测一致；(4) 一轮规则不回归；(5) pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
设计决定 + 前后截图 + 修复摘要评论 issue #122，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
