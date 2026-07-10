# S3 任务：c12-ai/BIC-meta#113 — FP 空上游行为 gate + 孔位词表

你是 S3（独立复核 + 实现 + 提交）。issue #113 正文是任务书（含截图路径）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（dd50f08）切工作树 .wt/be-113 开分支 fix/issue-113-fp-empty-upstream-gate（不 push/不 PR/不重启）。

## 要点
- 复现会话 8069b19d-ab48-4cfb-9fe8-c08761770fe0（FP 回合在 seq1773 之后；DB docker exec talos-postgres psql -U postgres -d talos_agent_db，列 kind/emitted_at/payload）。#112 的调查评论（4925549575）给了 FP 预填 gate 的 file:line（reception_node.py:639-641/986-988）——从那里入手。
- 确定性 gate 优先（Rule：能用代码判定就不靠提示词）；提示词负向指令是兜底不是主防线。
- 并行 child .wt/be-110 在动事件下发层（哨兵抑制），你别碰 SSE/事件流层；触点仅 FP 子图。
- 词表检查限 FP 话术范围（Rule 3），别全仓扫。

## 二元验收
issue #113 四条照抄执行，每条具名测试。全量 `uv run pytest tests/unit -m 'not real_llm'` 绿（#101 已知闪失单跑复核）。

## 收尾
修复摘要评论 issue #113，标签 stage:待调查 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
