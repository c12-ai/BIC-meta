# S3 任务：c12-ai/BIC-meta#126 — CC 推荐不追问已 carry-forward 的 TLC 数据

你是 S3（独立复核 + 实现 + 提交）。issue #126 正文是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（61ddd81+，git log 确认）切工作树 .wt/be-126 开分支 fix/issue-126-cc-no-reask-carryforward（不 push/不 PR/不重启）。

## 要点
- 参照 #113 的实现模式（fp.py 确定性 gate + dynamic_prompts 负向指令，87d33d9）与 #118 调查的 carry-forward 坐标（reception_node.py:511-596）。
- 复现会话：最新 rxn 实验（DB docker exec talos-postgres psql -U postgres -d talos_agent_db，找最近 experiment 的 CC job 回合）。
- 并行 .wt/be-125（TLC cleanup 握手）动 job 终局路径，你动 CC 推荐 gate/提示词——若同文件注意行区隔，冲突 root 兜底。别动依赖（#115 TEMP 覆盖在场）。

## 二元验收
issue #126 三条照抄执行，每条具名测试。全量 `uv run pytest tests/unit -m 'not real_llm'` 绿。

## 收尾
修复摘要评论 issue #126，标签 stage:待调查 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
