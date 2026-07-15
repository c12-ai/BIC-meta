# S3 任务：文档漂移集中刷新 — meta#195 P3×9 + #186 FP-split 两处 + #128 state.md 缺口

你是 S3（文档修 + PR，列车口径）。任务书 = meta#195（P3 清单）+ #186（anm-handbook§4、lab-logistics-validation.md:21 的 FP-split 旧记载）+ #128 评论（state.md §6.5 未跟三层化，Rule10 缺口）+ #101 评论（归因错位更正）。

仓：BIC-agent-service（`.wt/docsync`，分支 `docs/issue-195-drift-sweep`）为主；若 P3 项落在 portal/lab 的 spec 文档则各仓小 PR。
并行知会：s3-p2sweep 在代码面、s3-be194 在叙述设计面——你只动文档/注释/spec，零行为改动（ruff/pyright/测试必须零变化即为自证）。

## 范围

1. `.trellis/spec/tech_design/backend/state.md` §6.5 按 #128 三层语义重写（P3-1，反向误导项最优先）。
2. #186 两处 FP-split 旧文档对齐 rule 11 现况（flasks 归 FP 任务参数等）。
3. #195 其余 P3 逐条刷新；#94 rxn-parse transition 的 7 个站点加追踪注记（TEMP 标注 + 指向 shared-types 收编条件——promotion 本身不做）。
4. 每处修改引 #195/#186 条目号，逐条对账表。

## 二元验收

- 全部改动为文档/注释（diff 无行为行）；全量测试绿证零行为变化；CI 绿 admin-merge 留痕。对账表评论 #195/#186。**不动台架**。

## 收尾

PR sha + 对账表；dispatch done（FACTS/JUDGMENT 分开）。
