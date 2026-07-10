# 评审任务：BIC-agent-service#62 护栏验收基线提案——可行性 + 与现状冲突审查

你是评审 session（只读代码，结论回帖到 BIC-agent-service issue #62）。对象：`gh issue view 62 -R c12-ai/BIC-agent-service`（含正文全部矩阵行）。用户要求回答：**是否可行、与我们现状是否冲突**。

## 评审基线（先读）
- 现状代码：BE bench-verify（准入层 user_admittance、reception 路由、GuardrailMiddleware 相位门、TERMINAL_ONCE、#69 reject-rework、#73 幂等门+CTA 规则、统一入场流水线）。
- 我方已有验收资产：tests/unit/invariants/ 挽具（apply 幂等/确认收敛/终态化/tool 配对/replay）、t-challenge r2 的七类挑战实测结论（.dispatch/findings/t-challenge-r2/，其中准入/离题拒绝 PASS、拒绝流 PASS）、narrate 合同不变量。
- 相关裁定：#69（reject≠accept、返工语义）、#63-meta（plan reject 引导）、失败-accept 自动前进（既定不重议）。

## 必答（回帖结构，Facts/Judgment 分开）
1. **可行性**：矩阵覆盖的 11 种状态在现架构里是否都可确定性识别（reception/dispatch_source/phase 的映射表——给 file:line）；评估用"状态×输入类型"矩阵做成参数化测试套件的成本（可否挂进 invariants 挽具或独立 scenario suite）。
2. **与现状冲突/重叠**：逐行对照提案矩阵的 Expected decision 与已落地语义——特别是 pending confirmation 下短确认（"confirm/yes"）当前实际走哪条路（表单在侧、聊天短语确认是否等效 FORM_CONFIRM——这是已知张力点）、failed/retry 状态的输入语义（#69 后）、completed 后输入。列出提案期望与现实现冲突的行 + 我们已有裁定覆盖的行（附 issue/commit 引用）。
3. **落地建议**：基线以什么形态落（评估矩阵 YAML/参数化测试/live 剧本）；建议的最小第一片；与 t-challenge 发现（04/05 系列）的合并点。
4. 结论：可行/需修订（逐点）；不与现状冲突的前提条件。

## 纪律
只读；不改代码不开单；回帖署名 Wenlong 侧评审。dispatch done：FACTS=四问各一句话 / Judgment 分开。
