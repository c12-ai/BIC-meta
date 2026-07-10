# S3 任务：c12-ai/BIC-meta#120 FE — 洗脱体系选择题化 + 全站输入统一（A-G 全包）

你是 S3（独立复核 + 实现 + 提交）。任务书 = issue #120 的 s2 审计评论（4926527065，含盘点表/方案表/file:line）+ root 裁定评论（A+B+C+D+E+F 全采纳，G 顺带）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal，从 bench-verify（28ede4d+）切工作树 .wt/fe-120 开分支 fix/issue-120-solvent-input-unify（不 push/不 PR/不动台架 :5174）。

## 要点
- 按方案表逐项：A 弃 longSolventLabel 改 SolventPicker（Solvent 枚举白名单多选，按洗脱强度排序 PE<DCM<EA<MeOH 核对契约注释，禁自由文本）；B formatEluent 短式 `PE/EA 2:1` 全站只读复用；C SolventPicker+RatioSteppers 共享控件 CC/TLC/RE 复用；D 删 RE 本地解析四函数改 import；E 术语统一「洗脱体系」（zh/en i18n）；F ParamSummary 柱规格 columnSpecLabel；G 英文全名进 tooltip/aria。
- 并行 child .wt/fe-116（结果面）、.wt/fe-122（样式打磨）在跑——你动表单控件/格式层；ParamSummary 若与 fe-122 撞，以你的格式函数为准、样式让它。
- 表单值最终提交的 payload 形状不得变（契约零改动是裁定前提）——加序列化断言测试守住。
- tests/helpers.ts 不入提交。

## 二元验收
(1) CC/TLC/RE 洗脱体系均为枚举多选+stepper，无自由文本、无英文长串（具名测试）；(2) 只读处全站 `PE/EA 2:1` 短式（含 Summary）；(3) 提交 payload 形状不变（序列化断言）；(4) RE 本地解析删除、共用文法；(5) pnpm lint && pnpm test && pnpm build 整链绿。

## 收尾
修复摘要评论 issue #120，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
