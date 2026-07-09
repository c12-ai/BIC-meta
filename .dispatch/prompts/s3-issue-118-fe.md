# S3 任务：c12-ai/BIC-meta#118 FE — CC 面板 TLC 板照直渲 boxed_pic_url

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #118 的 s2 调查评论（4926218194）+ root 裁定评论。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（先 git log 确认 HEAD）切工作树 .wt/fe-118 开分支 fix/issue-118-cc-tlc-evidence（不 push/不 PR/不动台架 :5174）。

## 要点
- 触点 RecommendationBasis.tsx TlcThumbnail（:135/:152/:167-174）：优先直渲 `tlc_result.plates[0].boxed_pic_url`（Mind 已签 7 天 URL，复用结果页 ResultStageEvidence.tsx:172-180 模式），无 boxed_pic_url 时回落 tlc_file_key presign 路径，两者皆无才占位。
- 并行 child .wt/fe-114b（去卡片）、.wt/fe-116（结果面状态）在跑——你只动 CC 面板缩略图读取，无重叠。
- 复现数据：CC trial d591607f from_user.tlc_result.plates[0].boxed_pic_url 在场（DB 佐证在调查评论）。

## 二元验收
(1) 具名测试：from_user 带 boxed_pic_url → 缩略图渲染该 URL；仅 tlc_file_key → 走 presign 回落；皆无 → 占位；(2) 既有测试不回归；(3) pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
修复摘要评论 issue #118，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
