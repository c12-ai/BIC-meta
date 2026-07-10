# S3 任务：c12-ai/BIC-meta#78 — FP 孔位分色 + 试管架完整性查证与修复

你是 S3（查证 + 独立复核 + 实现 + 提交）。issue #78 正文是任务书（分色裁定 + 架子来源两问 + rule 11 契约核对）。先查证（FpParamsForm 网格数据源、CC 结果 rack map 结构、派发数组构造长度 vs PRD rule 11 整架契约），结论评论 issue，再实现。

## 工作区纪律
- FE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-78-fp-rack /Users/wenlongwang/Work/BIC/talos/.wt/portal-78 bench-verify`；若查证出 BE 派发数组也要修（整架长度），BE 同名侧分支并先评论 issue 说明。
- 不碰 bench 主目录、不重启、不 push、不开 PR。DB 只读。
- 并行提示：portal 在飞 #76（结果面板）/#77（ELN 按钮）——FpParamsForm 域应不相交；#41 曾改 ContainerChip，基线已含。

## 二元验收
issue #78 三条照抄执行写成测试。全量门禁绿。

## 收尾
查证结论 + 修复摘要（sha、测试计数）评论 issue #78，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
