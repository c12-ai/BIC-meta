# S3 任务：c12-ai/BIC-meta#114 — 右侧面板 UI 一致性三项

你是 S3（独立复核 + 实现 + 提交）。issue #114 正文是任务书（先 Read 截图）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（当前 HEAD，含 #104r2/#110-FE）切工作树 .wt/fe-114 开分支 fix/issue-114-pane-consistency（不 push/不 PR/不动台架 :5174）。

## 边界（重要）
- 并行 child .wt/fe-111 正在改 WorkflowDesignStep（footer/滚动结构）——**别碰 WorkflowDesignStep**；若卡片统一涉及它，把该处登记回 issue 由 root 合并后补。
- 底部行对齐是间距/边距层面（对照上方卡片内容边缘），不要动 #104 r2 刚落的滚动结构。
- UUID：有 name 显 name，无 name 只显「实验总览」；UUID 移入 title 属性或删除。数据已有则纯展示改动，别加新请求。
- 统一卡片风格前先数一数现状（哪种样式占多数/更新），在 issue 评论里写明选择依据（Rule 5）。

## 二元验收
issue #114 四条照抄执行；运行态截图/量测证据入 issue 评论。

## 收尾
修复摘要评论 issue #114，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
