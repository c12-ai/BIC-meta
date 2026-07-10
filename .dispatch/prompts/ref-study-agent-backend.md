# 研读任务：老 BIC-agent-backend 的统一 specialist 流程 → 统一步骤流程的可借鉴清单

你是参考研读 session（**只读**，产出一份研读文档，不改任何仓库代码）。

## 背景与定位（用户原话裁定）
- 老 repo `BIC-agent-backend` "验证过主体流程能走通，但流程不如我们这个版本，仅作为参考"。
- 我们正把新版 BIC-agent-service 的 4 份手写 specialist 子图重构为统一步骤流程（必读：`/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/unified-step-flow-memo-2026-07-09.md`，含 StepSpec 槽位表与三片迁移路径）。
- 老 repo 已有同构形态：`app/agents/specialists/base.py`（36KB，BaseSpecialistAgent 统一生命周期）+ 每步小文件只覆写钩子（tlc_agent 3.6KB / cc_agent 6.5KB / re_agent 5.3KB / presenter 2.4KB）。它是"统一流程、每步只注入步骤信息"的**已验证活标本**。

## 工作区
- 老 repo 快照（origin/main 最新，detached worktree，只读）：`/Users/wenlongwang/Work/BIC/talos/.wt/ref-backend`
- 新 repo（对照，只读）：`/Users/wenlongwang/Work/BIC/talos/BIC-agent-service`（bench 主目录，**只读勿碰**）
- 产出文件：`/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/reference-study-agent-backend-2026-07-09.md`（写这一个文件，其余全部只读）

## 要回答的问题（文档结构照此组织，结论先行）
1. **钩子清单**：BaseSpecialistAgent 把哪些点做成了每步覆写的钩子（全列，带 file:line 与一句话语义）？它的统一生命周期骨架长什么样（入场/seed/推荐/表单/确认/派发/结果/叙述在 base 里如何编排）？presenter.py 扮演什么角色（是不是老版的 narrate 出口）？
2. **与我们 StepSpec 槽位表的映射**：备忘录里的槽位（seed 来源/recommend/params 模型/结果分析/重试策略/narrate 事实块）逐行对照老钩子——哪些老钩子证明了槽位可行、哪些槽位老版没有（我们的新增复杂度：trials 事件溯源、result_review、FP、Mars、ChemEngine 失败大声、narrate 合同）、哪些老钩子我们漏想了。
3. **不要抄的部分**（用户判断"流程不如我们这个版本"）：识别老版的结构性短板并点名（比如 coordinator/意图检测的组织、事件/状态模型、HITL 门控…以实际代码为准，不要猜），每条给"为什么新版的做法更好"的一句话依据。
4. **对三片的具体建议**：片 1（入场流水线，s3-issue-42 在做）/ 片 2（accept/advance + 收尾叙述 #44）/ 片 3（narrate 组装归一 #45）各自能从老代码借什么具体形态（类/函数级引用），迁移时的兼容注意点。
5. **一页结论**：统一流程在老 repo 被验证到什么程度（哪些链路真跑通过——看它的测试/benchmarks/docs 证据，不要只信 README），我们照搬的置信度评级。

## 纪律
- 文档遵守 data-first：Facts（file:line、行数、测试证据）与 Judgment 分开。
- 全程只读两个代码仓库；只写 ops/ 下那一份文档。
- 完成后 `dispatch done`：一段 FACTS（文档路径、回答了几问、关键结论一句话）+ Judgment。
