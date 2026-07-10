# S3 任务：c12-ai/BIC-meta#122 — 右侧面板 UI 细节打磨（截图分析 + frontend-design）

你是 S3（独立复核 + 实现 + 提交）。issue #122 正文是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（28ede4d+，git log 确认 HEAD）切工作树 .wt/fe-122 开分支 fix/issue-122-pane-polish（不 push/不 PR/不动台架 :5174）。

## 要点
- **必须调用 `/frontend-design:frontend-design` 技能**做设计分析与优化（用户点名）。
- 自起 dev server 截图（可连台架 BE :8800 只读取数据；绝不操作台架页面/不发消息）；逐屏截图 → 问题清单（线连续性/圆角档/边框规则/间距/对齐）→ 统一规则 → 实施 → 前后对比截图。
- 基调是 #114 的去卡片平铺（刚落地），别把卡片加回来；#104/#111 滚动结构别动。
- 并行 child .wt/fe-116（结果面状态逻辑）与即将开工的 .wt/fe-120（洗脱体系控件）在改逻辑层——你聚焦样式/布局 token 层，逻辑不碰；文件冲突 root 兜底。
- tests/helpers.ts 不入提交。

## 二元验收
issue #122 四条照抄执行。

## 收尾
问题清单 + 前后对比截图 + 修复摘要评论 issue #122，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
