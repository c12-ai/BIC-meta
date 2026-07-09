# S3 任务：修复 c12-ai/BIC-meta#55 — 无叙述 turn 不再渲染空"Talos 分析"卡

你是 S3（独立复核 + 实现 + 提交）。issue #55 正文 + 架构报告 `/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/think-message-architecture-2026-07-09.md` 的 R1 节是任务书（报告已论证：FE 每 turn_started 无条件开泡是直接根因，本修复是 R1 分段规则的外科落地）。先复核，评论 issue，再实现。

## 工作区纪律
- 自建 worktree + 侧分支（基于 bench-verify 当前 tip，含 #51 分段 189936a——你的改动与它同域，必须兼容其测试）：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-55-empty-bubbles /Users/wenlongwang/Work/BIC/talos/.wt/portal-55 bench-verify`。
- 绝不碰 bench 主目录、不重启、不 push、不开 PR。
- 并行提示：s3-issue-59（RE 依据文案）、s3-issue-60（板照 FE 渲染）在其他 portal 侧分支；不同文件，若撞 chatStore 评论对齐。

## 修复要求（R1 语义）
- 无 text_done 的 turn 不渲染独立空气泡：延迟开泡（首个可见内容到达才 spawn）或完结时空泡回收，方案二选一以"历史 hydrate 重放与 live 一致"为准绳（报告点名 live/replay 气泡结构漂移是既有病，别加重）。
- 该 turn 的 trace 事件归属：并入下一个有内容气泡的追踪，或按报告 R1 建议挂进度事件到工作区监控面——取最小改动方案，在 issue 评论里写明取舍。
- #51 的分段行为（189936a）与其测试不回归。

## 二元验收
issue #55 照抄执行：turn e5aee129 形态（DB 实证序列）重放 → 无空气泡；有文本 turn 行为不变；live 与 hydrate 重放分段一致。全量 vitest + tsc + 增量 biome 绿。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #55，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
