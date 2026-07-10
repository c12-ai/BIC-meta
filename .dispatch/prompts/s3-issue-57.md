# S3 任务：修复 c12-ai/BIC-meta#57 — CC 推荐门槛只需粗产物质量；样品柱位置挪到派发阶段

你是 S3（独立复核 + 实现 + 提交）。issue #57 正文是任务书主体（含用户裁定原话、疑似落点、二元验收四条），先读，复核结论评论到 issue，再实现。

## 工作区纪律
- 自建 worktree，**基于 fix/issue-53-tlc-copy 分支**（#53 刚在同域改了指引措辞，你的文案改动接着它做，合并历史一条线）：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-57-cc-recommend-gate /Users/wenlongwang/Work/BIC/talos/.wt/be-57 fix/issue-53-tlc-copy`。
- 绝不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。

## 关键边界（只挪门，不放水）
- recommendable 门：CC 推荐前置改为粗产物质量唯一（`_from_user_recommendable` / 片1 CC EntryStepSpec）。
- submit/派发侧对 sample_cartridge_location 的硬校验**一行不动**（guardrail params_validated、lab 校验、物料面板流程照旧）——写反向测试锁住：无 location 时 submit 仍被拒。
- 入场收集话术：只要质量；柱位置改为"派发前在实验物料（Lab Logistics）面板配置"的提示语（与 #53 已落的指引措辞对齐，zh/en）。

## 二元验收
issue #57 的四条照抄执行，写成测试。全量 pytest -m 'not real_llm' 绿（在 worktree 内以非 infra-gated 的子集为准，报告注明 skip 数）+ ruff 干净。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #57，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。合入窗口 root 攒批。
