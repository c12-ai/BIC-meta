# S3 任务：c12-ai/BIC-meta#88 — Mind 识别单项 mock 分档开关

你是 S3（独立复核 + 实现 + 提交）。issue #88 正文是任务书。落点：app/infrastructure/mind_client.py 的 mock 分派 + config.py 开关。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-88-recognition-mock-split /Users/wenlongwang/Work/BIC/talos/.wt/be-88 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。
- 识别类端点清单以 mind_client 实际方法为准（带图/视觉类全归识别档），在 issue 评论列出归档清单。

## 二元验收
issue #88 四条照抄执行写成测试。全量单测绿 + ruff 干净。

## 收尾
修复摘要（sha、测试计数、端点归档清单）评论 issue #88，标签改 stage:已实现待复测；dispatch done。root 会立即合入重启并把 MIND_MOCK_MODE 恢复 false + 新开关置 true。
