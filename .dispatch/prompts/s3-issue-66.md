# S3 任务：实现 c12-ai/BIC-meta#66 — TLC 表单"推荐参数"按钮（完整版）+ 话术同步

你是 S3（独立复核 + 实现 + 提交，跨仓）。issue #66 正文是任务书（用户裁定完整版：表单按钮触发推荐 + 话术如实）。先复核（重点：表单 draft 的 form_draft rider 通道现状、TLC recommend 阶梯的触发条件、片1 _entry_pipeline 是否顺势可接 TLC），复核结论评论到 issue，再实现。

## 工作区纪律
- FE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-66-recommend-button /Users/wenlongwang/Work/BIC/talos/.wt/portal-66 bench-verify`
- BE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-66-recommend-button /Users/wenlongwang/Work/BIC/talos/.wt/be-66 bench-verify`
- 不碰 bench 主目录、不重启、不 push、不开 PR。BE 单测 `-m 'not real_llm'`。
- 契约变更走 Rule 10（若新增触发语义，spec 同变更集更新）。
- 并行提示：s3-issue-67 在 portal 另一侧分支（SSE 层）；文件应不相交。
- 注意刚落的话术修正（bench-verify@6e3adfa：物料面板指引改为"确认按钮左侧的「实验物料」"）——你的冷表单话术更新基于它。

## 要点（issue #66 实现要点照抄）
按钮（前置未齐禁用+缺项提示；可重跑）→ 保存 draft + 触发 turn（等价快捷消息但携带表单 draft）→ BE 确定性推荐（倾向接 _entry_pipeline 的 recommendable→auto_recommend，不强制本次收编整个 TLC）→ 推荐值回填表单；冷表单叙述改为按钮指引（zh/en）。

## 二元验收
issue #66 四条照抄执行写成测试（FE 组件 + BE 集成）。两仓全量门禁绿。

## 收尾
复核结论 + 修复摘要（两仓 sha、测试计数）评论 issue #66，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
