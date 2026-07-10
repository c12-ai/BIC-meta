你是验证窗口的 T-verify-main（黄金链路复跑，验证已修复项）。先读 ops/demo-test-playbook.md（剧本+铁律+轮末reset）与 ops/verification-window-runbook.md。
bench 已重启加载全部修复。你的任务不是找新问题，是**逐项验证**下列 issue 的二元验收（gh issue view <N> --repo c12-ai/BIC-meta 看各自验收标准与实现 comment）：
- #27：objective 表单必填缺失时点确认→可见提示；补名后 POST+推进（UI 路径！）
- #8：plan 确认后 TLC 首 turn 即 form_requested 且 rxn 预填非空、聊天不索要 rxn
- #5：TLC accept（成功路径）后 CC 被派发/表单激活，e2e 同款断言
- #28：TLC accept 后无"下游已完成"幻觉、无同句重复、自动进入 CC 参数收集
- #7/#11：失败场景（窗口 0.3-0.5 跑一轮）accept 后诚实叙述失败+询问下一步
- #19：（若可复现幽灵管）dispatch 前被硬闸拦截并引导，而非 lab 400
- #21/#34：dispatch 失败后刷新，总览/监控/tab 全部如实显示失败
产出：逐项 PASS/FAIL 表（附 session_id/seq/截图证据）写入 .dispatch/findings/t-verify-main/RESULTS.md；PASS/FAIL 各自列清。轮末照常 lab reset。完成 dispatch send 摘要给 root + dispatch done。铁律：不 reset agent DB；DB=talos-postgres:5433。
