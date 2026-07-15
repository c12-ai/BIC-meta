# S2 任务：BIC-agent-service 深度 review — 文档漂移 + 架构腐烂（调查先行，结论落 issue）

你是 S2（**只读调查**，不写产品代码；产出 = issue + 分级清单）。用户点名：对几个 repo 特别是 agent-service 做 review，查文档漂移、架构腐烂，然后修（修是后续 S3 的事，你负责把账查清）。

仓：BIC-agent-service 为主（只读），旁及 `.trellis/spec/`、`docs/project-prd.md`、meta Production-PRD 交叉引用。可用 talos-pg-test-73:5455 测试库做行为核实。**不动台架，不写代码**（唯一例外：你的产出 issue/评论）。

## 调查面（今晚已知线索起步，扩展你自己发现的）

1. **文档漂移**：
   - `.trellis/spec/` 各层契约 vs 现代码（重点：#128 三层状态语义落地后 spec 是否全跟上；narrate-contract 今晚两改后的一致性；FE↔BE 契约文档 vs 实际序列化）。
   - `docs/project-prd.md` vs 实现（TLC/CC/FP/RE 各 specialist 行为、#176/#177 后的 FP 契约）。
   - 已知输入：meta#186（FP-split 两处旧文档）、meta#189 沉淀的口径、CLAUDE.md 台账时效。
2. **架构腐烂**：
   - **TEMP 块清单**：全仓 grep TEMP/FIXME/HACK/transition（#163 cap、#94 rxn-parse transition client、#88 recognition 过渡档注释等）——逐个判定：可拆（依赖已解）/ 待外部 / 真债，给拆除条件。
   - **被取代的旧路径残留**：#128 三层化后旧 status 反推/投影是否有死代码；#165 后 narrate 双源残留；FE-0 止血产物是否删净（FE-1 声称删了，核实 BE 侧对应物）。
   - **多产出口收敛度**：用户话语出口（narrate/确定性模板/裁剪缝）经今晚 be181/be182 后还有几个口、是否单源。
   - **分层违规**：L1-L4 边界穿越、specialist 间复制粘贴漂移（#98 发现的 '#126 CC 修了 RE 没修' 即同型——盘点还有哪些 specialist 级不对称）。
   - 测试债：CI skip 残量、排序 flake（test_current_user_id 今晚三次撞见）、pinned-test 与新口径冲突残留。
3. **顺带**（轻量）：portal/lab 同类问题的快速扫描（一节即可，不做同深度）。

## 产出（二元验收）

- 一个总 review issue（meta 仓）：分级清单——P1 结构性（需设计）/ P2 机械修（可直接派 S3）/ P3 记录性（文档刷新）；每项 file:line + 证据 + 建议处置 + 预估动作量。
- 每个 P1 单独开 issue（含设计约束）；P2/P3 可合并开或列在总 issue。
- 全部结论一手证据（引用行号/测试名/commit），无叙述性断言。dispatch done（FACTS/JUDGMENT 分开）。
