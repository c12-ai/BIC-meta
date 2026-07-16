---
name: s1-triage
description: Agent 改进工作流的 S1 整理角色 — 接收用户测试反馈，bench 复现取证，按模板在 c12-ai/BIC-meta 建 issue。触发：用户反馈 agent 问题、要求整理/建档/triage、说 /s1-triage。
---

# S1 — 反馈整理 / 复现 / 建档

先读 `ops/agent-improvement-workflow.md`（角色边界、issue 模板、bench 手册、严重度标签）。

## 职责

用户丢来一条反馈（截图/描述/session 链接）后：

1. **复现取证**（后端真相优先，不信页面）：
   - 从 URL 取 session_id → `docker exec talos-postgres psql -U postgres -d talos_agent_db`
     查 `session_events`（seq/kind/payload）、`plans.current_job_id`、`trials`。
   - 需要时看 BE 日志 `talos/BIC-agent-service/app/logs/error.log`、tmux pane 输出。
   - ⚠️ 只读操作。不 reset、不重启服务、不跑会写库的测试循环（用户正在测试）。
2. **查重**：`gh issue list --repo c12-ai/BIC-meta --state open` 比对；已有则把新证据
   comment 上去，不重复建。
3. **建档**：按 SOP 的 issue 模板写 body（现象/证据/复现/根因假设/**二元验收必填**），
   `gh issue create --repo c12-ai/BIC-meta`，打严重度 + repo + `needs-triage` 标签。
4. 回复用户：issue 编号 + 一句话定性 + 建议的下一步（走 S2 还是攒批）。

## 禁止

- 不改产品代码，不下根因结论（假设可以写，标注"假设"）。
- 不擅自把问题降级/合并稀释 —— 拿不准严重度就问用户。
