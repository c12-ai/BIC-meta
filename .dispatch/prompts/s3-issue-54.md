# S3 任务：修复 c12-ai/BIC-meta#54 — 叙述不再暴露裸状态枚举（状态词汇表）

你是 S3（独立复核 + 实现 + 提交）。issue #54 正文 + 架构报告 `/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/think-message-architecture-2026-07-09.md` 的 R2 节（状态词汇表/display fallback）是任务书。这是 R2 的外科先行片：只做叙述侧词汇表，不动 wire 契约。先复核（找到 narrate 事实块/提交叙述里 status 的注入点），评论 issue，再实现。

## 工作区纪律
- 自建 worktree + 侧分支（基于 bench-verify tip）：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-54-status-vocab /Users/wenlongwang/Work/BIC/talos/.wt/be-54 bench-verify`。
- 绝不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。
- **并行冲突警示**：s3-issue-58 正在 _narrate_pipeline 改出口路由（fix/issue-58-analyze-exit-routing）——若你也要动该文件，先看其分支已有改动（`git -C /Users/wenlongwang/Work/BIC/talos/.wt/be-58 diff bench-verify --stat`），改不同区域并在 issue 评论对齐；无法避让则 dispatch ask 请示 root 排序。

## 修复要求
- 状态词汇表单一来源（zh/en：in_progress→进行中、waiting→排队中、completed→已完成、failed→失败、cancelled/timeout…全枚举覆盖，缺词条 fail loud 而非透传）；注入点：提交/进度/事实块等把 status 送进叙述的地方，送翻译后的词。
- lab_task_id 等 UUID 是否继续出现在叙述正文：按 issue 裁量意见（追踪里有、正文对化学家无用）——移出正文，评论里写明决策。
- value-reconciliation 语义保持：叙述数值/状态与真实状态逐值一致（一致的对象是词汇表映射后的展示词）。

## 二元验收
issue #54 照抄执行：zh 叙述无裸英文状态 token 的断言测试（白名单化学术语除外）；词汇表全枚举覆盖测试；既有 narrate 测试不回归。全量单测绿 + ruff 干净。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #54，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。合入窗口与 #53/#57/#58/#60 同批。
