# S3 任务：c12-ai/BIC-meta#110 BE 侧 — 内部终结哨兵 tool_result 不下发 FE 流

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #110 正文 + s2 调查评论（4925363118）+ root 裁定评论（做第 1 项 BE 根因修，第 2 项 FE 兜底不归你）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（dd50f08）切工作树 .wt/be-110 开分支 fix/issue-110-sentinel-not-streamed（不 push/不 PR/不重启）。

## 要点
- 范围 = 终结确认哨兵族（request_plan_confirmation / request_objective_confirmation / request_params_confirmation 等 emit-form 前置哨兵，对照 plan_tools.py:39-66 与各 specialist 同族）：其 tool_result 事件不进 FE 可见流（SSE/snapshot 两路都不带），内部路由与落库语义不变——**live 与 snapshot 必须喂出同构事件集**，这是本修复的判定准绳。
- 真实工具（Mind/lab/chem）trace 不受影响；#93/#106 的终结剪断与 refusal 路径不回归。
- 复现 turn：session 40c52ae5 / turn fff34dab（DB seq1600-1606）。
- 若发现哨兵 tool_result 的持久化被下游依赖（snapshot 重建/对账），如实登记权衡并选最小面：可下发但 FE 标记不可见字段，或不下发；说明理由。

## 二元验收
(1) E2E：plan/objective 确认回合的 SSE 流与 snapshot 重建事件集同构（都无哨兵 tool_result 或都带同样标记），具名断言；(2) 真实工具调用 trace 两路仍在；(3) #93/#106/#102 既有测试不回归；(4) 全量单测门禁绿（#101 已知闪失单跑复核）。

## 收尾
修复摘要评论 issue #110（注明 FE 兜底另批），标签保持 stage:待修复 直到 FE 侧完成——评论里写清 BE 部分完成；dispatch done（FACTS/Judgment 分开）。
