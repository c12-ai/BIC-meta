# S3 任务：meta#244 TLC 形状规则三方打架 — 查清权威、按分叉落地

你是 S3（先调查定权威，再按分叉执行，列车口径）。任务书 = c12-ai/BIC-meta#244（读正文：三处口径、调查任务、分叉）。

冲突：根 PRD rule 9 说『2–4 支、同盒同行、连续列、从第 1 列起』；lab `_validate_tlc_objects` 据称 2026-07-09 按 labrun v5 放宽（允许间隙/任意起步，出处 portal `tlc-params-draft.ts:75` 注释）；portal 镜像放宽版。

## A. 调查（结论评论 #244）

1. **lab 现状一手核对**：BIC-lab-service `command_validator.py` `_validate_tlc_objects` 当前实际校验哪些项；放宽的引入 commit/PR（git log -S）与其声称依据。
2. **物理权威**：mars 机器人协议（mars_doc / tlc-api-reference / labrun v5 协议文档，lab 仓或 BIC-shared-types 里找）对 TLC 管位形状的真实约束——机器人能否间隙点样、能否非第 1 列起步。这是决定性证据。
3. **历史裁定搜索**：07-09 放宽有没有裁定记录（lab 仓 PR 描述、issue、meta issue、.trellis 任务档）。
4. 产出三层口径 + 机器人真相对照表（file:line/commit 级）。

## B. 按分叉落地

- **(a) 放宽有据**（机器人支持 + 有裁定或协议依据）：直接提交根 PRD rule 9 形状条款修订 PR（BIC-meta，引证据，changelog 注明 #244），admin merge 前评论 @root 复核；portal/lab 不动。
- **(b) 放宽无据**（机器人实际要求连续/第 1 列起，或无任何依据）：**不改代码**——lab/portal 收紧属跨仓行为变更，分别立 lab/portal 修复 issue（引 #244 证据）后收档，由 root 排期。
- 模糊地带（证据冲突）：只交调查表 + 建议，dispatch ask 问 root。

## 二元验收

- 对照表 + 分叉判定评论 #244；分叉 (a) 则 PRD PR merged / 分叉 (b) 则两个修复 issue 立案；
- 全程只读代码与文档（除 PRD PR 外无代码改动）。

## 并行知会

- s3-fe237 在 portal 改 tubeSelectionProblem（配对/解释文案，B2 口径）——你**不动 portal 代码**，无冲突；若你的结论影响它（如机器人真要求第 1 列起步），评论 #244 后 dispatch send 知会 root 与 fe237。
- lab 仓无在跑会话。

## 收尾

dispatch done（FACTS/JUDGMENT 分开）。
