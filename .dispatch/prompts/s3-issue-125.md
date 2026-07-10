# S3 任务：c12-ai/BIC-meta#125 — TLC 收尾握手（P0）

你是 S3（独立复核 + 实现 + 提交）。issue #125 正文是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（61ddd81+，git log 确认）切工作树 .wt/be-125 开分支 fix/issue-125-tlc-cleanup-handshake（不 push/不 PR/不重启）。

## 要点
- lab 侧契约参照 BIC-lab-service app/api/routers/tasks.py（append/cleanup 端点语义，只读参照不改 lab）。
- BE 侧找 TLC job 终局路径（result_review accept 两分支 / 重试耗尽 / #5 终态化点），LabClient 若无 cleanup 方法则补（对齐既有 client 形态与 spec，Rule 10）。
- 幂等与 fail-loud 按 issue 要求；CC/FP/RE 同形态排查结论回帖（只修 TLC）。
- 注意 bench-verify 带 #115 TEMP shared-types 覆盖，别动依赖。

## 二元验收
issue #125 四条照抄执行，每条具名测试。全量 `uv run pytest tests/unit -m 'not real_llm'` 绿。

## 收尾
修复摘要评论 issue #125，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
