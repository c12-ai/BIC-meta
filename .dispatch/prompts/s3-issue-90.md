# S3 任务：c12-ai/BIC-meta#90 — TLC 物料面板状态化呈现 + 超选报错

你是 S3（调查 + 独立复核 + 实现 + 提交）。issue #90 正文是任务书（两裁定 + 定层待查 + 三验收）。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-90-material-panel-ux /Users/wenlongwang/Work/BIC/talos/.wt/portal-90 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。lab 侧只读定层（需改 lab 则另开单请示，本单不动 lab）。
- 并行提示：portal 在飞 #89（推荐 API），域不相交。
- 文案走 i18n（zh/en），错误码映射优先；无码时 FE 以 code-or-fallback 模式处理并在 issue 注明 lab 缺口。

## 二元验收
issue #90 三条照抄执行写成测试。全量门禁绿。

## 收尾
定层结论 + 修复摘要（sha、测试计数）评论 issue #90，标签改 stage:已实现待复测；lab 缺 code 则另开单互引；dispatch done（FACTS/Judgment 分开）。
