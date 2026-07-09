# S3 任务：c12-ai/BIC-meta#108 — 下发话术对齐真实状态

你是 S3（独立复核 + 实现 + 提交）。issue #108 正文 + s2 调查评论 + root 裁定评论是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（43fcbdd）切工作树 .wt/be-108 开分支 fix/issue-108-dispatch-wording（不 push/不 PR/不重启）。

## 要点
- 落点 = _narrate_pipeline.py:114-123（NARRATE_PROMPT_SUBMIT_QUEUED_TMPL）+ 选择点 :280-281：去掉 queued/待处理语义，事实块对齐真实 status（提交返回即 in_progress），话术方向「已下发，实验室已开始执行」，遵循用户语言（#16 系裁定）；标识符 SUBMIT_QUEUED → SUBMIT_DISPATCHED 全链更名。TLC/CC/FP/RE 共用一处，别做四份拷贝。
- 别碰 narrate 之外的层；status_vocab（#54）与 drop_terminal_contradictions 既有 backstop 不改。

## 二元验收
(1) 四实验类型下发叙述测试：无"排队/待处理/queued"字样、含"已开始执行"语义（zh/en 各断言）；(2) 既有 narrate 套件不回归；(3) 全量单测门禁绿（#101 已知闪失单跑复核）。

## 收尾
修复摘要评论 issue #108，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
