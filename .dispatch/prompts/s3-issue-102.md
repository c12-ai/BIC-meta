# S3 任务：c12-ai/BIC-meta#102 — 主反应物 LLM 预判 + 按钮确认（裁定已下）

你是 S3（独立复核 + 实现 + 提交）。issue #102 正文 + 调查评论（4924728920）+ 用户裁定评论是任务书。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（e5c5a12+）切工作树 .wt/be-102 开分支 fix/issue-102-baseline-prefill（不 push/不 PR/不重启）。

## 裁定要点（照 issue 裁定评论执行）
1. 幻觉字段审查：rxn_parse_contract.py 与 #94 代码/注释/文档对照真实响应字段表（issue 正文捕获件），引用不存在字段处改掉或去掉；若确认无此类引用，回帖澄清。
2. 多底物无指认时：LLM 推断最可能主反应物，clarify 卡预选默认项 + 按钮确认/更正；LLM 不确定→无预选按钮 clarify。优先复用现有表单/选项事件契约；若需要 FE 配合，把 FE 增量登记回 issue（不改 portal 仓）。
3. #94 复测标准措辞按新形态修订（评论 #94 对应位置）。

## 边界
- 只动基线判定/clarify 路径。#103（草稿补名，实现中）、#105（编造投料量，调查中）同区域——别碰补名和数量填充逻辑；冲突面留给 root 合并。
- 契约若有跨层变化，按 Rule 10 同步 .trellis/spec。

## 二元验收
(1) 多底物+未指认 E2E：clarify 事件 payload 含候选列表与 LLM 预选项（或显式无预选），每种一个具名测试；(2) 指认/单底物路径不回归（#94 既有测试绿）；(3) 幻觉字段审查结论落 issue（有改动则测试守住真实字段表）；(4) 全量单测门禁绿（#101 已知闪失单跑复核）。

## 收尾
修复摘要评论 issue #102，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
