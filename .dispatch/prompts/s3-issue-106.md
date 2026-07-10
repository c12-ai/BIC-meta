# S3 任务：c12-ai/BIC-meta#106 — objective 循环剪断 + 报错透出治理（P0）

你是 S3（独立复核 + 实现 + 提交）。issue #106 正文 + s2 调查评论 + root 裁定评论是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（43fcbdd）切工作树 .wt/be-106 开分支 fix/issue-106-objective-loop-cut（不 push/不 PR/不重启）。

## 裁定三件套（照 issue 裁定评论执行）
1. parse_reaction 整表替换保留既有 baseline 指认（根因修复）。
2. objective 子图 catch GraphRecursionError → draft 完整时转 emit_form 无损救回（复用 _post_route backstop objective.py:199-212 模式）；draft 不完整时仍失败但走 3 的可读话术。
3. TurnFailedEvent 加 display 字段（key/params/fallback），_classify:703/_failure_message:721 非 LabClientError 不再裸 str(exc)；Rule 10 同步 .trellis/spec 契约文档；FE 消费增量登记回 issue（不改 portal 仓）。不抬 recursion_limit。

## 边界
- #102（.wt/be-102，clarify/基线预选）与 #105（.wt/be-105，row-builder 止血）并行中：你在 tools.py 只动 parse_reaction 的 baseline 保留逻辑，别碰 clarify 话术与 row-builder 的 amount/eq；后落地方 rebase 由 root 兜底。
- 复现会话：243864a0 turn 844f82c3（DB talos-postgres:5433 talos_agent_db）。

## 二元验收
(1) clarify 应答重放 E2E：同阶梯不再打穿 25（事件数断言 + baseline 保留断言）；(2) 人造超限场景：draft 完整→表单照发（无 TurnFailed）；draft 不完整→TurnFailed.display 中文 fallback，无英文框架文案；(3) #93 既有剪断测试不回归；(4) 全量单测门禁绿（#101 已知闪失单跑复核）。

## 收尾
修复摘要评论 issue #106，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
