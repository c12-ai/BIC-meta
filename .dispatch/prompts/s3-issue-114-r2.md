# S3 任务：c12-ai/BIC-meta#114 二轮 — 右侧面板去卡片化

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #114 最新"复测裁定"评论（方向反转：不是统一成卡片，是整体去卡片）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（3d1124d，含你一轮 2fce1c4）切工作树 .wt/fe-114b 开分支 fix/issue-114-decard（不 push/不 PR/不动台架 :5174）。

## 要点
- 在一轮成果上做（对齐修复与 UUID 修复保留），把顶层分节的卡片 chrome 全部拆掉：无圆角边框、无卡片底色差，分节靠留白/细分隔线；内容宽度放大；参照左侧对话区的平铺质感。
- 嵌套信息块（上游分析只读区、容器分配等）减少框中框层级——判断准绳：同屏边框矩形数量显著减少、内容可用宽度增加。
- 别碰 #104/#111 的滚动结构（footer 在滚动器外的结构保持）；WorkflowDesignStep 的分节样式若同属卡片 chrome 一并去（现在没有并行 portal child，无边界限制）。
- 运行态截图证据（去卡片前后对比 + 对齐量测）入 issue 评论。

## 二元验收
(1) 右侧面板顶层无卡片样式（无圆角描边容器），运行态截图对照；(2) 内容/footer 边缘同网格线零偏差；(3) 标题无 UUID 不回归；(4) pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
修复摘要 + 截图证据评论 issue #114，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
