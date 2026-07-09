# 统一步骤流程重构备忘录（unified step flow）

日期：2026-07-09 · 作者：S1 orchestrator · 依据：Wenlong 裁定"每一步的处理流程应该是一样的，不要镜像，重构成统一流程，每个步骤只填入各自流程的步骤信息"

## 结论（先说）

可行，且 bug 台账证明过期未做。四个 specialist 子图（tlc/cc/fp/re）是**同一条步骤生命周期的四份手写拷贝**：cc/re/fp 近逐字，tlc 是带重试阶梯的超集变体。本轮 45 个 issue 中至少 9 个是"拷贝分叉"类缺陷——一份拷贝修了、其他拷贝没跟上。重构目标：**一个通用 StepFlow 子图 + 每步一份声明式 StepSpec**，步骤从代码变成数据。迁移按 strangler 三片走，片 1（入场流水线）已由 s3-issue-42 按此方向开工。

## 证据：重复度量化（2026-07-09 实测）

- 行数：tlc.py 1349 / cc.py 900 / re.py 687 / fp.py 713（+共享 tools.py 2387）＝ 6036 行。
- cc/re/fp 三份近逐字同名函数（tlc 另有变体）：`_last_message_of_type`、`_last_tool_content`、`_submit_failed`、`_is_params_confirm_dispatch`、`_pre_react_route`、`_post_react_route`、`_emit_form_node`、`_emit_task_dispatched_node`、`_emit_task_failed_node`、`_extract_match`、`_NARRATE_PROMPT_BY_TOOL`、`_NARRATE_PROMPT_SUBMIT_FAILED`、`_build_narrate_prompt`。
- 重复税实锤：PR#66 的 4 处冲突**全部**是同一行改动在四份 `_build_narrate_prompt` 拷贝上的重复解决。

## 证据：拷贝分叉 bug 台账

| Issue | 分叉形态 |
|---|---|
| #42 | CC 有入场确定性推荐阶梯（dfe08ab），RE 没有 → RE 叙述捏造"Mind 推荐" |
| #42 附带 | FP→RE 回填缺 ratio（PRD rule 11 三项只落了两项） |
| #39 | seed 只覆盖 confirmed=true 一条确认路（demo/direct-REST），agent-form 路静默失败 |
| #38 | 结束语模板未按 form kind 分化，objective 阶段提"管/柱" |
| #44 | 有 next_job 有 T-closing 过渡叙述；next_job=None（收尾）无叙述路径 → 空气泡 |
| #11 | done-verdict 投影 TLC-scoped（kind=="tlc"），其他步骤不生效 |
| #5 | result_review accept 终态化，各步骤各自处理 |
| #24/#45 | 输出后处理（strip/dedupe）在不同路径覆盖不齐；#45 S2 证实 re.py 缺 cc.py 的 degenerate-repeats 分支（mirror drift 又一例），且全局 text_done chokepoint 只去 `<think>` 不去重（collapse_degenerate_repeats 未挂 chokepoint + 仅 length 门 + 仅邻接） |
| #45 (Q1) | narrate 历史回显：rightsize 关闭时改写器看全量 50 条历史，末工具为 analyze 时落 TEXT_REPLY prompt（"用历史回答"）→ 整段逐字回放前几轮叙述；片 3 需把 narrate 输入收窄为本 turn 状态事实块 |
| #45 (Q3) | 世界态防捏造护栏（ff908a9）是软 prompt 非确定性过滤：DB 真相 TLC=failed 在块里，LLM 仍宣称 "entire workflow successfully executed"（seq 1675 FP 结果已同款美化）→ 片 3 需要确定性的终态一致性过滤，不能只靠 prompt |
| 早期 D | "You are the X specialist agent" ×5 份身份提示各自维护 |

## 统一生命周期（四步实际相同的骨架）

```
entry(上游 seed + recommend + params 写入) → emit form → confirm → validate
  → dispatch → progress → result analyze → result review → accept
  → advance(有下一步：T-closing 过渡；无下一步：收尾叙述 + ELN 导出指引[#44])
```

## 每步真正的变异点 → StepSpec 槽位（不是 fork）

| 槽位 | TLC | CC | FP | RE |
|---|---|---|---|---|
| seed 来源 | confirmed objective | TLC evidence | CC result（verbatim，rule 11） | FP result（volume+solvents+**ratio**） |
| recommend | ChemEngine TLC 溶剂体系 | ChemEngine CC 柱选择 | **None**（确定性预填） | ChemEngine RE 参数 |
| params 模型/表单 | TLCParam | CCParam | FP containers | REParam |
| 结果分析 | ChemEngine 视觉 + Rf 窗口判定 | ChemEngine CC 分析 | 确定性合成（15ml/管） | **Mars**（Robot 团队，非 ChemEngine） |
| 重试策略 | 3 次 Rf 阶梯 | — | — | — |
| narrate 步骤事实块 | 各步一段状态事实，模板/骨架共用 | 同 | 同 | 同 |

原则：变异点必须以槽位显式存在于 StepSpec；任何"这个步骤特殊所以另写一条路"都是设计失败（TLC 重试是唯一确认的结构性变体，见风险）。

## 迁移路径（strangler，三片）

1. **片 1：入场流水线**（seed+recommend+set+narrate）——**已开工**：s3-issue-42 按用户裁定转向，CC（重构现有 dfe08ab 为配置化消费者，行为保持）+ RE（第二消费者，获得 #42 全部行为）先接入；TLC/FP 后续收编。
2. **片 2：accept/advance 统一**——收编 #44（收尾叙述）、#5/#11（verdict/终态语义）、过渡 T-closing；一个 advance 节点按 next_job 有无走过渡或收尾。
3. **片 3：narrate 返回与提示组装统一**——`_build_narrate_prompt` ×4 → 1（PR#66 类冲突永久消失），随后 emit/dispatch/progress 节点收敛，最后收编 TLC 重试阶梯。

时序纪律：片 1 现在做（独立侧分支）；片 2/3 等本波 S3（#40-45）落地 + bench-verify 合入窗口后，开 `refactor/unified-step-flow` 分支——避免与在飞修复在同一批文件上打架。

## 风险与对策

- **TLC 重试阶梯**是最大变体：最后迁移，作为统一流程表达力的验收（能收编它 = StepSpec 设计合格；收编不了 = 槽位设计要返工，不许 fork）。
- **行为保真**：每片迁移必须带新旧同输出对照（现有全量单测 + golden transcript 对照），CC 既有测试零回归是片 1 的硬验收。
- **正交性**：与已完成的 narrate 合同、状态语义两个重构正交；三者经同一 bench-verify 集成方式合流。
- **RE 实时分析归 Mars**（PRD 要求 8 例外）在 StepSpec 里是 result-analyzer 槽位的另一实现，不是特殊路径。
