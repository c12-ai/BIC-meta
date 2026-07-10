你是状态语义审计员（S2 性质，只读）。开工前读：
1) /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/architecture-memo-2026-07-09.md 第四节（单一语义定义）
2) ops/agent-improvement-workflow.md 的 Bench 手册（DB=talos-postgres:5433 等）
铁律：只读，不改产品代码、不重启、不写库。S3 链在两个 repo 工作区跑，以 git HEAD 为准（注明基准 commit）。

任务：全库审计 trial.status / phase / progress / jobs.status / experiments.stage 的**全部读取点**：
- BE：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service（reception_node、specialist_dispatcher、各 specialist 路由、narrate、query_agent、event apply、repos）
- portal：/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal（stores/selectors、derive-routing、各 panel、event-dispatcher）
产出 /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/state-semantics-audit-2026-07-09.md：
- 逐点表格：file:line | 读的字段 | 用作什么判定 | 合规(按备忘录第四节语义)/违规/存疑 | 建议
- 汇总：违规点修复清单（按风险分级）、语义表最终稿（可直接进 spec 的版本）、与已修 #5/#21 的对账。
数据先行：先表格后判断。完成后 dispatch send 给 root 一句摘要（违规点计数），然后 dispatch done。
