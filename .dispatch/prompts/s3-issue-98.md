# S3 任务：c12-ai/BIC-meta#98 — 识别边界裸 MinIO 键必须 presign

你是 S3（调查 + 独立复核 + 实现 + 提交）。issue #98 正文是任务书（抓包原文在 /private/tmp/claude-501/-Users-wenlongwang-Work-BIC-V2-BIC-meta/35cf69d6-ff07-47fb-abee-88cbc6eba2f9/scratchpad/mind_capture/ 的 184128_* 对）。先定位识别边界的 URL 处理（为何 minio/ 裸键透传——presign 分支的匹配条件），结论评论 issue，再实现。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-98-presign-boundary /Users/wenlongwang/Work/BIC/talos/.wt/be-98 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`（S3/minio 外呼全 mock）。
- 并行提示：BE 在飞 #94/#95/#97——识别边界域应不相交。

## 二元验收
issue #98 四条照抄执行写成测试。全量单测绿 + ruff 干净。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #98，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
