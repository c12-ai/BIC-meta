# S2 任务：c12-ai/BIC-meta#128 — TLC 三层状态语义架构梳理（只读，深度设计，不改码）

你是 S2（架构调查+设计，只读）。issue #128 正文是任务书（用户 verbatim 指令，先 Read 五张截图）。这是设计任务不是补丁任务——历史上 #116/#123 两轮 FE 读侧补丁都被复测击穿，用户明确要求从建模层理清。

## 仓与数据
- BIC-lab-service（task/run/skill/op 建模：app/data/schemas/task.py、task_service.py、event.py）+ labrun_db 实录（今晚 3 轮 TLC：task b2996e95 已 completed、最新失败链 task 见 tasks 表）。
- BIC-agent-service bench-verify（trial/job/analysis 状态族：runtime_emitted.py、#5/#11/#37 终态化史、tlc.py 重试环、#125 cleanup）。DB talos_agent_db（最新 experiment 的完整事件序列，bug 4 的 accept 回合）。
- BIC-agent-portal bench-verify（现状读侧：monitor-exec-status.ts、result-stage-status.ts、experiment-progress-derive.ts；TLC 表单 第N次 tab 先例）。
- 既有裁定不可推翻：#5（失败-accept 自动过柱）、#11（verdict 在 analysis.criteria）、#37（accept 写终态）、#123 裁定（执行/评估分离方向）、#124（二期 B+D/F 蓝图——你的设计应吸收或明确取代它）。

## 交付
按 issue 五项交付物逐项落评论（设计表用 markdown 表格；实施拆分带依赖序与粗工作量）。标签 stage:待调查 → stage:待裁定。不改任何代码。收尾 dispatch done（FACTS/Judgment 分开）。
