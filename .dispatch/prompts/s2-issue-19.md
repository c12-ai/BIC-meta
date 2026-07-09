你是 Agent 改进工作流的 S2 调查角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s2-investigate/SKILL.md。
铁律：只读 —— 不改产品代码、不重启、不写 DB。⚠️关键：agent DB 与 lab DB 都在 talos-postgres 容器 :5433（talos_agent_db / labrun_db）；bic-postgres:5432 的同名库是另一份/空，勿被骗。一个 S3 正在同一 BE 工作区，文件疑似编辑中时以 git HEAD 为准。
代码：/Users/wenlongwang/Work/BIC/talos/{BIC-agent-portal,BIC-lab-service,BIC-agent-service} @ fix/chat-ux-lang-error-tubeid。

任务：调查 c12-ai/BIC-meta issue #19（样品管选择器可选到不存在的幽灵盒子 tube_box_2ml_l2_004，提交才失败 + 错误措辞误导）。先 gh issue view 19 --repo c12-ai/BIC-meta --comments。
必查：
1) `l2_004` 与其派生 tube_id `tlcws_tube_2ml_tube_box_2ml_l2_004_A1` 的产生源 —— 是 lab-service `/preparations/...` 样品管盒 grid API 真返回了它，还是 portal（lab-service-client.ts / TubeSelectorGrid / material-preparation-adapter）或某 adapter 按命名模板拼造 id？把数据流从 API 响应追到 confirm 载荷 seq 600。
2) lab 侧 tlc_inventory 只有 l1_001/l2_001..003 —— 为何 UI 里出现 l2_004？是种子数据缺 004 而 UI 硬造格位，还是 grid 渲染空格位也带可选 id。
3) 错误措辞：command_validator.py:598 / preparation_service.py:555 把"get 命不中/非2ml"都报成"非2ml规格" —— 建议区分。
根源方案两条子缺陷分别给：(a) 选择器只展示真实库存（源头拦截，portal 或 lab API）；(b) lab 错误分型。分别指明 repo。comment 到 #19，换标签 stage:已析根因，dispatch done。
