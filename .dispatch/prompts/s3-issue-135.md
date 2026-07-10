# S3 任务：c12-ai/BIC-meta#135 — G1 孪生编造点修复

你是 S3（独立复核 + 实现 + 提交）。issue #135 正文是任务书（含 #105 的 G1 登记与 #134 复测佐证）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（b3f6cb1+，git log 确认）切工作树 .wt/be-135 开分支 fix/issue-135-fastpath-honest-dosing（不 push/不 PR/不重启）。

## 要点
- 参照 #105 实现（78bcd94，tools.py _objective_reactant_rows_from_goal 与 tests/unit/test_objective_honest_dosing.py）；断点 fast_path_handlers.py:876-885。两处收敛为共享 helper。
- 复现会话 84807d6a（talos_agent_db）。别动依赖（#115 TEMP 覆盖在场）。

## 二元验收
issue #135 三条照抄，具名测试。全量 `uv run pytest tests/unit -m 'not real_llm'` 绿。

## 收尾
修复摘要评论 issue #135，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
