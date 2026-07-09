# S3 任务：修复 c12-ai/BIC-meta#60 — TLC 板照证据链（BE TlcEvidence 契约 + FE 渲染）

你是 S3（独立复核 + 实现 + 提交）。issue #60 正文是任务书主体（源自 #56 调查，先读两个 issue 及 #56 评论的 file:line 佐证），复核结论评论到 issue，再实现。

## 工作区纪律
- 跨仓改动，各自 worktree + 侧分支：
  - BE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-60-plate-photo /Users/wenlongwang/Work/BIC/talos/.wt/be-60 bench-verify`
  - FE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-60-plate-photo /Users/wenlongwang/Work/BIC/talos/.wt/portal-60 bench-verify`
- 绝不碰两个 bench 主目录、不重启、不 push、不开 PR。BE 单测 `-m 'not real_llm'`。
- 契约变更纪律（Rule 10）：TlcEvidence 改动同变更集更新 `.trellis/spec/` 对应契约文档；若需动 BIC-shared-types，先评论 issue 请示 root（跨团队治理）。
- 并行提示：#57/#58 的 S3 在 BE 其他侧分支；form_payloads.py 若有重叠区，评论对齐。

## 二元验收
issue #60 四条照抄执行写成测试（BE：evidence 构造含 URL 的单测；FE：组件测试 URL→<img> 渲染 + 失败降级）。两仓全量门禁绿（worktree 内，infra-gated skip 照报）。

## 收尾
复核结论 + 修复摘要（两仓 sha、测试计数）评论 issue #60，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。合入窗口 root 攒批。
