# 重构任务 C：事件 apply 层不变量测试挽具（tests-only，不改产码）

你是测试挽具 session（独立设计 + 实现 + 提交）。整体依据：`/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/project-refactor-review-2026-07-09.md` §C（先读）。

## 硬边界（最重要的规则）
- **只加测试文件，产码 diff 必须为零**。发现现行代码违反不变量：**报 issue / 评论，不修**——BE 正有多个在飞分支（#39 seed 修、#42 统一入场流水线），产码改动会制造合并地狱。
- 自建 worktree + 分支：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b refactor/apply-invariants /Users/wenlongwang/Work/BIC/talos/.wt/be-invariants fix/chat-ux-lang-error-tubeid`（注意：fix 分支 tip 已含 #39 的 ad9884b——你的不变量 1 应该已被它满足，正好做正例）。
- 不碰 bench 主目录、不重启、不写共享 DB、不 push、不开 PR。单测用 `-m 'not real_llm'`。

## 病灶（为什么需要挽具）
同一语义事件从不同路径落盘出不同状态，且没有任何测试层能拦：
- #39：agent-form 确认路不盖 objective.confirmed=True，direct-REST 路盖（已修 ad9884b，靠人肉差分发现——挽具本该秒拦）。
- #5/#37：result accept 的终态化各路径不一致。
- #16b：tool_call_id 配对契约漂移。

## 要建的不变量（起点集，可扩充但每条要有台账依据）
1. **确认收敛**：任何路径产生的 ExperimentObjectiveConfirmedEvent apply 后 ⇒ objective.confirmed=True（正例：ad9884b；mutation 检查：注释掉 stamp 该测试必红——不要真提交 mutation，验证后还原）。
2. **accept 终态化**：任何 result_review accept 路径 apply 后 ⇒ trial.status ∈ 终态集且与 analysis verdict 一致、phase='done'。
3. **apply 幂等**：同一事件 apply 两次 === 一次（对全部 runtime_emitted / bypass_emitted 事件类型参数化，能构造的都覆盖，不能构造的在测试里显式 skip 并注明原因——fail loud）。
4. **tool_call 配对**：任一 turn 的事件流中 tool_call 与 tool_result 按 tool_call_id 一一配对（用现有 fixture/golden 会话数据驱动）。
5. **事件流可重放**：对既有 golden 会话事件序列，全量 replay 与增量 apply 终态一致（有现成 harness 就复用，没有就建最小版）。

## 二元验收（PASS 当且仅当全部成立）
1. 挽具落地为独立测试模块（如 tests/unit/invariants/），全绿；或每条红都有对应 issue/评论链接（红=发现现行违例=挽具的胜利，照实报）。
2. `git diff --stat` 产码为零（只有 tests/ 新增）。
3. 全量 `pytest tests/unit -m 'not real_llm'` 绿（你的新测试计入）；ruff 干净。

## 收尾
1. 挽具清单（每条不变量 ↔ 它本可拦下的历史 issue）+ commit sha + 发现的违例列表，评论到 c12-ai/BIC-meta#39（它是动机案例）。
2. `dispatch done` 汇报：FACTS 与 Judgment 分开。
