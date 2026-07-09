# S3 任务：c12-ai/BIC-meta#129 — BE-0 双发守卫（#128 阶段0 止血，P0）

你是 S3（独立复核 + 实现 + 提交）。issue #129 正文 + #128 交付物 4（bug-4 事件序列还原）与交付物 5 的 BE-0 行是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（fdf63d2+，git log 确认）切工作树 .wt/be-129 开分支 fix/issue-129-terminal-double-fire-guard（不 push/不 PR/不重启）。

## 要点
- 断点：event_ingress.py:300-310（无条件 submit TASK_TERMINAL）× dynamic_prompts.py:211-223（#9 遗留 done-phase 问指示段）。两处都修，语义才彻底一致（#128 结论）。
- 既有裁定不可破：#5（失败-accept 自动过柱推进）、#37（accept 写终态）、#93/#106（终结剪断）。
- 复现数据：#128 交付物 4 的两条链（talos_agent_db seq 2020-2204 一带）。
- 别动依赖（#115 TEMP 覆盖在场）；.wt/be-125/be-126 已并，注意基线是最新 bench-verify。

## 二元验收
issue #129 三条照抄（恰好 1 条后续消息 E2E / 迟到重放不起回合 / 不回归），每条具名测试。全量 `uv run pytest tests/unit -m 'not real_llm'` 绿。

## 收尾
修复摘要评论 issue #129，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
