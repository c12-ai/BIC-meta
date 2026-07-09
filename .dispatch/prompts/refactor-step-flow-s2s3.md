# 重构任务：统一步骤流程 片2（accept/advance 归一）+ 片3（narrate 组装归一）

你是重构 session（独立设计 + 实现 + 提交）。总纲：`/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/unified-step-flow-memo-2026-07-09.md`（必读，含证据台账与槽位表）。参考研读：`/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/reference-study-agent-backend-2026-07-09.md`（老 repo 钩子清单与"不要抄"清单；注意其结论：老版行为层零置信，只借切面选择，HITL/状态模型/结果链路不搬）。

## 工作区纪律
- 自建 worktree + 分支（基于 bench-verify 当前 tip，含片1/#66/narrate/state 全部合并）：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b refactor/unified-step-flow /Users/wenlongwang/Work/BIC/talos/.wt/be-stepflow bench-verify`。
- **绝不**触碰 bench 主目录工作区（用户正在测试）、绝不重启服务、不写共享 DB、不 push、不开 PR。单测 `-m 'not real_llm'`。
- 大改动分片提交：片2一个（或多个）commit、片3一个（或多个）commit，每个 commit 全量门禁绿（pytest+ruff+pyright 改动集）。
- 改契约必须同变更集更新 `.trellis/spec/backend/L3/`（Rule 10）。

## 片2：accept/advance 归一（吸收 #44、对齐 #5/#11 语义）
现状：result_review accept 后的走向散在各处——有 next_job 走过渡 T-closing（f65c36a），无 next_job（workflow 收尾）**没有任何叙述路径**（#44：turn 19ms 静默结束，空气泡）；done-verdict 投影曾 TLC-scoped（#11）。
要求：
1. 一个统一的 advance 决策点：accept → 终态化（已有）→ 按 next_job 有无走「过渡 closing」或「收尾 closing」，两者都是确定性 T 类模板 + 状态填充。
2. 收尾 closing（#44 验收）：各步骤真实终态陈述（失败照实说，禁"successfully"美化失败实验）+ ELN 报告导出指引（PRD 要求 10）。集成测试断言最终 accept turn 产出非空 text_done 且含导出指引；失败终态实验的收尾无成功字样。
3. verdict→终态语义走单一来源（与 #5 的 FormConfirmedEvent 终态化、不变量挽具 test_invariant_result_accept_terminal 对齐——挽具已在树上，你的改动必须保持它绿）。

## 片3：narrate 组装归一（吸收 #45，杀掉 4 份拷贝）
现状与根因（#45 S2 已析，issue 评论有全量证据）：
- `_build_narrate_prompt` ×4 份近逐字拷贝（tlc/cc/re/fp），PR#66 类冲突的重复税来源；
- narrate 改写器输入是全量 50 条历史（rightsize 关闭时），末工具为 analyze 落 TEXT_REPLY prompt（"用历史回答"）→ 整段逐字回放历史叙述（两会话实证：e0368686 seq1702、f12e6e3a seq1851，过渡 turn 高频引爆）；
- 全局 text_done 出口只剥 `<think>` 不去重；collapse_degenerate_repeats 未挂出口 + 长度门 + 仅邻接（段1==段5 三重逃逸）；re.py 缺 cc.py 的 degenerate 分支（mirror drift）；
- 世界态护栏是软 prompt，挡不住 "entire workflow successfully executed"（TLC 实际 failed）。
要求：
1. narrate 提示组装收敛为单一实现（延展片1的 `_entry_pipeline.py` 或新 `_narrate_pipeline.py`），各步骤只注入步骤事实块/模板键；4 份 `_build_narrate_prompt` 与 `_NARRATE_PROMPT_BY_TOOL` 拷贝删除（grep=0 的结构测试）。
2. narrate 输入收窄：改写器只看本 turn 的状态事实块 + 必要的直近上下文，不再喂全量历史（#45 Q1 根断）。
3. 确定性出口过滤挂全局 text_done chokepoint：跨段（非邻接）逐字去重 + 终态一致性过滤（叙述宣称的步骤终态与 ctx 真实终态矛盾时删句或替换为事实句——确定性代码，不是 prompt）。#45 的二元验收写成测试：单 turn text_done 无前序 turn 逐字段落、无段级重复、无与真实终态矛盾的成功宣称。
4. TLC 重试阶梯本轮**不强制**收编（备忘录标注它是设计合格验收）：若 narrate 归一自然覆盖 TLC 就收；有结构阻力则在 issue 评论记录阻力点，留下一轮。

## 二元验收（PASS 当且仅当全部成立）
1. #44 集成测试（收尾叙述+导出指引+失败照实）绿；
2. #45 三断言测试绿（无历史回放段/无重复段/无终态矛盾宣称）；
3. 结构测试：narrate 组装单一实现，specialists 目录无 `_build_narrate_prompt` 拷贝；
4. 全量 `pytest tests/unit -m 'not real_llm'` 绿（含不变量挽具 6 xfail 状态不变）+ ruff + pyright 改动集 0 error；
5. 行为保真：既有 narrate/closing 测试（T-closing、no-echo endswith、cold-form 状态驱动模板）不回归——允许按新结构搬迁测试位置，语义断言保留。

## 收尾
1. 设计摘要 + commit sha 列表 + 测试计数评论到 #44 与 #45，两 issue 标签改 `stage:已实现待复测`；
2. `dispatch done`：FACTS 与 Judgment 分开。合入窗口由 root 协调（用户在测，不请求立即合入）。
