# S3 任务：c12-ai/BIC-meta#82 — 监控页跟随当前 trial + 步骤切换

你是 S3（调查 + 独立复核 + 实现 + 提交）。issue #82 正文是任务书。先查监控面 trial 绑定为何停在 TLC（MonitorPane 的 trial 选择、deriveRouting monitor 分支），结论评论 issue，再实现（取最小交互方案并注明取舍）。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-82-monitor-follow /Users/wenlongwang/Work/BIC/talos/.wt/portal-82 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。
- 并行提示：portal 在飞 #55b/#75-fix/#80/#81——MonitorPane 域应不相交，撞则评论对齐。#71 刚改过执行日志渲染（已在基线），别回退其行为。

## 二元验收
issue #82 四条照抄执行写成测试。全量门禁绿。

## 收尾
调查结论 + 修复摘要（sha、测试计数）评论 issue #82，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
