# S3 任务：c12-ai/BIC-meta#81 — RE 物料弹窗三处清理 + RE 物料规则缺失顺查

你是 S3（独立复核 + 实现 + 提交）。issue #81 正文是任务书（三处 UI 裁定 + 一项顺查）。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-81-re-modal /Users/wenlongwang/Work/BIC/talos/.wt/portal-81 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。顺查部分只读（lab 配置源/接口响应，DB 只读）。
- 并行提示：portal 在飞 #75-fix/#79/#80——物料弹窗域与 #75-fix（物料面板）可能相邻！先看 .wt/portal-75 已有改动，错开或评论对齐。
- 文案走 i18n 键（zh/en），与 #80 的正式名称词表方向一致（若其已落用户可见名词表，接入）。

## 二元验收
issue #81 四条照抄执行写成测试。全量门禁绿。

## 收尾
复核结论 + 顺查定性 + 修复摘要（sha、测试计数）评论 issue #81，标签改 stage:已实现待复测；若 lab 配置缺 RE 行则另开 repo:lab-service issue 并互引；dispatch done（FACTS/Judgment 分开）。
