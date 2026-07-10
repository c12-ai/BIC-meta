# S3 任务：c12-ai/BIC-meta#119 — CC 分析边界 presign（#98 平移 + 三处收敛）

你是 S3（独立复核 + 实现 + 提交）。issue #119 正文是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（e7cabbd）切工作树 .wt/be-119 开分支 fix/issue-119-cc-presign-boundary（不 push/不 PR/不重启）。

## 要点
- 断点 tools.py:921；参照实现 tlc.py:252 _presign_recognition_url 与 tools.py:1269 recognize 路径。三处收敛为共享 helper（放哪层你依据 spec 判断，Rule 10 同步文档）。
- 注意 bench-verify 已带 #115 的 TEMP shared-types 覆盖（pyproject [tool.uv] override）——别动依赖配置。
- 并行 child .wt/be-117 在动 narrate；你只动 presign 边界，无重叠。

## 二元验收
issue #119 四条照抄执行，每条具名测试。全量 `uv run pytest tests/unit -m 'not real_llm'` 绿。

## 收尾
修复摘要评论 issue #119，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
