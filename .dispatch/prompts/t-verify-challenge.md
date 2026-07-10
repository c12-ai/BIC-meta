你是验证窗口的 T-verify-challenge（挑战场景复跑，验证已修复项）。先读 ops/demo-test-playbook.md 与 ops/verification-window-runbook.md。禁止 dispatch 机器人任务（验证项都在参数确认之前或查询类）。
逐项验证（gh issue view <N> 看验收）：
- #22：问设备状态→列真实 3 台+状态；问任务汇总→空集答"0 个"（如实）
- #23：问"你能做什么/能否规划下发"→如实介绍完整能力，无"仅限查询"，无 admittance_rejected
- #12：制造需澄清场景→问题原文第一人称直达聊天（含选项）
- #14：黄金开场白含"主反应物投料量"→无决策震荡（thinking 无反复横跳）、不再问 baseline
- #17/#24：thinking 无对用户说话正文；聊天无 <think> 泄漏
- #13/#15/#18：叙述第二人称、发表单后收尾指向待办
- #16：工具卡无悬挂"待处理"（配对修复验证）
产出：逐项 PASS/FAIL 表（session_id/seq/截图）写 .dispatch/findings/t-verify-challenge/RESULTS.md。完成 dispatch send 摘要 + dispatch done。铁律照旧；DB=talos-postgres:5433。
