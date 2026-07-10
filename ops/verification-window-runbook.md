# 统一验证窗口 Runbook（自动化验证，2026-07-09 用户授权跳过人工阶段）

前置：双链清空（be-tail、#34 落地）；bench 空闲。
1. 重启 BE（kill -KILL :8800 → uvicorn no-reload 起新代码）+ 重启 portal dev（rebase 后代码）；健康检查四服务。
2. lab reset（协议 curl）+ 轮询 robots/idle。
3. e2e：cc-re-chained-flow（PORTAL_BASE_URL=:5174，--workers=1）+ tlc-retry-flow。
4. T-main 复跑黄金链路 round（重点：#27 UI确认、#28 accept 后推进、#8 form-first、#5 链路推进）。
5. T-challenge 复跑关键场景（#22 设备/任务查询、#23 能力自述、#12 clarification 直达、#17/#24 语域）。
6. 汇总：逐 issue PASS/FAIL 表 → PASS 的关单（comment 附证据）；FAIL 的降回 stage:已析根因 并记残余。
7. 恢复 bench 日常态（BE 保持 no-reload 直至 refactor 批结束）。
