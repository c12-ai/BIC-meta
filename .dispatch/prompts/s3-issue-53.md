# S3 任务：修复 c12-ai/BIC-meta#53 — TLC 引导文案两处精确化（用户裁定文案）

你是 S3（独立复核 + 实现 + 提交）。issue #53 正文含用户裁定原话与已知落点，先读 issue，复核落点（读代码自证，slice-3 后模板在 narrate 流水线/_narrate_closing.py），复核结论评论到 issue，再实现。

## 工作区纪律
- 自建 worktree + 侧分支（基于 bench-verify 当前 tip）：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-53-tlc-copy /Users/wenlongwang/Work/BIC/talos/.wt/be-53 bench-verify`。
- 绝不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。

## 修改要求
1. 冷表单收尾（zh/en）补动机："提供期望 Rf 窗口后，系统将自动推荐其余参数（如溶剂体系）"语义。
2. params 收尾指引（T 模板族 + NARRATE_NEXT_STEP_RULES["params"] 规则措辞，zh/en）：物料选择指向实验物料/Lab Logistics 面板（或"在实验窗口配置好物料后下发"）；TLC=样品管、CC=样品柱各自正确（PRD rule 10）。
3. 不破坏：#38 验收（objective/plan 阶段不提管柱）、#39 状态驱动模板（rxn 空时不宣称已预填）、no-echo endswith 测试、locale 三态。

## 二元验收
issue #53 的三条验收照抄执行，写成/更新测试。全量 pytest -m 'not real_llm' 绿 + ruff 干净。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #53，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。合入窗口由 root 协调（BE 重启与其他待合项攒批）。
