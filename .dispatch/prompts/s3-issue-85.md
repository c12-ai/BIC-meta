# S3 任务：c12-ai/BIC-meta#85 — CC/UV 图 URL 适配层透传（ELN Figure 2）

你是 S3（独立复核 + 实现 + 提交）。issue #85 正文与 agent-service#63 的复查回帖（4923003235）是任务书。断点已定位：specialists/tools.py:896-946 丢弃 + CcEvidence 无字段。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-85-cc-uv-images /Users/wenlongwang/Work/BIC/talos/.wt/be-85 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。契约改动 spec 同步（Rule 10；涉 shared-types 先评论请示）。
- 并行提示：BE 在飞 #74/#75-fix/#80——tools.py 若相邻 hunk 评论对齐。

## 二元验收
issue #85 四条照抄执行写成测试。全量单测绿 + ruff 干净。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #85 并同步一条到 agent-service#63；标签改 stage:已实现待复测；dispatch done。
