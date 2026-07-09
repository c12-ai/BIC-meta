# S2 任务：调查 c12-ai/BIC-meta#45 — RE 结果 turn 叙述堆积陈旧段落（3 段前几轮逐字回放 + 1 段完全重复）

你是 S2（只读根因调查，**不改任何代码**，结论评论到 issue）。

## 工作区纪律
- 只读仓库：`/Users/wenlongwang/Work/BIC/talos/BIC-agent-service`（bench 主目录在 bench-verify 分支，用户在测——只读、勿碰工作区、勿重启、勿写 DB；DB 只 SELECT）。
- DB：`docker exec talos-postgres psql -U postgres -d talos_agent_db`（只读查询）。
- 产出：根因分析评论到 issue #45（Facts/Judgment 分开），标签 stage:待调查 → stage:已析根因。`dispatch done` 汇报。

## 已知事实（issue #45 正文）
- 会话 e0368686 seq 1702 的 text_done 含 5 段：段2 逐字回放 turn 1678-82 的叙述（含捏造的 Mind 推荐）、段3 逐字回放 turn 1684-93、段4 提前宣布"entire workflow successfully executed"（TLC 实际 failed）、段5 与段1 完全相同。
- 该 turn（1696-1703）是 RE 结果分析 turn：tool_result→task_result_analyzed→task_analysis_completed→form_requested→text_done。
- 输出后处理（narrate 合同的 strip/dedupe/length-fallback）没拦住跨段逐字重复。

## 要回答的问题（按优先级）
1. 段2/3/5 的来源：narrate 改写器的输入是否含未按 turn 清空的累积草稿（pending narrations 跨 turn 残留）？还是 LLM 回显对话历史且 no-echo 失效？用代码路径（bench-verify 分支的实际代码）+ 该会话 DB 事件证明，不要猜。
2. BE 侧 text_done 的去重后处理为何放过段1==段5 的完全重复（粒度？作用域？根本没跑？）。
3. 段4 的"successfully executed"与 TLC failed 矛盾：世界态防捏造护栏（ff908a9 单一收口）为何未覆盖此路径。
4. 波及面：同机制在 TLC/CC/FP 的结果 turn 是否同样可触发（查同会话或其他会话的 text_done 有没有同款堆积）。

## 边界
- 不改代码、不提修复 commit。修复方向可以建议（一段即可），但注明属于统一步骤流程片3（narrate 组装归一）还是独立外科修。
- 如发现与 #44（收尾空叙述）共根因，在两个 issue 互相引用说明。
