# S3 任务：c12-ai/BIC-meta#84 — 澄清期表单清空闪烁

你是 S3（调查 + 独立复核 + 实现 + 提交）。issue #84 正文是任务书。先从 DB 还原会话 daf8dfdd 目标阶段的事件序列，定位表单清空窗口的成因（FE pendingForm/draft 时序 vs BE 事件顺序），结论评论 issue，再实现（倾向 FE 过渡策略：旧值保持到新数据就绪原子替换）。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-84-form-flicker /Users/wenlongwang/Work/BIC/talos/.wt/portal-84 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。DB 只读。
- 并行提示：portal 在飞 #75-fix/#80/#82——表单状态域与 #75-fix 可能相邻，评论对齐。

## 二元验收
issue #84 照抄执行写成测试（真实序列夹具）。全量门禁绿。

## 收尾
调查结论 + 修复摘要（sha、测试计数）评论 issue #84，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
