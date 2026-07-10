# S3 任务：修复 c12-ai/BIC-meta#42 — RE 入场零 ChemEngine 调用却叙述"Mind 推荐"，推荐值不进表单，FP→RE 回填缺 ratio

你是 S3（独立复核 + 实现 + 提交）。先独立复核 issue #42 根因（读代码+DB 自证），复核结论评论到 issue，再实现。

## 工作区纪律（必须遵守）
- 自建 worktree + 侧分支：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-42-re-recommend /Users/wenlongwang/Work/BIC/talos/.wt/be-42 fix/chat-ux-lang-error-tubeid`。
- **绝不**触碰 bench 主目录（用户手测中）、绝不重启服务、绝不写 DB。BE 单测不需要 live 基础设施（`-m 'not real_llm'`）。
- 提交落侧分支 `fix/issue-42-re-recommend`。不 push、不开 PR。合入窗口由 root 统一协调。
- 注意：s3-issue-39 可能同期在 fix 分支推进 events 层改动；你在侧分支上工作互不阻塞。

## 已知事实（issue #42 全文有细节）
- 会话 e0368686 RE 入场 turn（1678-1682）：task_created→task_params_set→text_done，零 tool_result。
- task_params_set params 全文 `{solvents:[PE,EA], volume_ml:45.0}`——无 temperature_c/air_pressure/solvent_ratio。
- 叙述却称 "Mind recommends 40°C / -0.09 MPa"（捏造）。
- PRD rule 11：FP 确认结果应回填 RE volume + solvents/**ratio**；ratio 缺失。
- CC 已有入场确定性推荐阶梯（commit dfe08ab，specialists/cc.py entry-deterministic recommend）作为镜像范本。

## 修复要求
1. RE 入场确定性阶梯：镜像 CC 模式——调用 ChemEngine RE recommend（mind_client，mock 已有或补 mock 端点）→ 推荐值（temperature_c/air_pressure）+ FP 回填（volume/solvents/ratio，ratio 从 FP 结果溶剂体系解析）一起写入 params draft（task_params_set）。
2. ChemEngine 失败：按 PRD 要求 8 大声失败——错误面向用户可见，narrate 不得出现"推荐"字样、不得编造值。
3. narrate：RE 入场叙述基于真实 draft 生成，纳入世界态防捏造护栏（护栏单一来源在 refactor/narrate-contract 已合入 bench-verify；你基于 fix 分支工作时若缺护栏代码，作最小对齐并在 issue 评论注明——不要复制一份第二实现）。
4. 遵守 spec：改动前读 `.trellis/spec/backend/L3/`（graphs/specialist_tools/narrate-contract/failure）。若改契约，同变更集更新 spec。

## 二元验收（PASS 当且仅当全部成立，写成测试）
- 集成测试断言 RE 入场 turn：(a) 恰一次 ChemEngine RE recommend 调用（mock）且推荐值落入 task_params_set；(b) FP 回填含 solvent_ratio；(c) mock ChemEngine 抛错时表单不带捏造值、错误可见、narrate 无"推荐"口径；(d) narrate 数值与 draft 逐值一致。
- 全量 `pytest tests/unit -m 'not real_llm'` 绿；ruff + pyright 干净。

## 收尾
1. 复核结论 + 修复摘要（commit sha、测试计数、门禁输出）评论到 issue #42，标签改 `stage:已实现待复测`。
2. `dispatch done` 汇报：FACTS 与 Judgment 分开。
