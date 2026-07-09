# S3 任务：c12-ai/BIC-meta#94 — 基线反应物自动判定（Mind rxn-parse 接入）

你是 S3（独立复核 + 实现 + 提交）。issue #94 正文是任务书（三级判定 + shared-types 约束 + 四验收）。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-94-baseline-inference /Users/wenlongwang/Work/BIC/talos/.wt/be-94 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。
- **shared-types 约束（用户点名）**：先查 bic_shared_types 是否已有 rxn-parse 契约模型（model_service.http.* 命名空间）；有则用；没有则评论 issue 请示 root（跨团队仓治理），拿到许可前用本仓 typed 模型过渡但标注 TODO 与 issue 号。
- 真端点只读验证可打 192.168.12.104:8002（一次性），fixture 按真实响应形状做。
- 并行提示：BE 在飞 #89/#93——objective 解析链与它们域应不相交。

## 二元验收
issue #94 四条照抄执行写成测试。全量单测绿 + ruff 干净。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #94，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
