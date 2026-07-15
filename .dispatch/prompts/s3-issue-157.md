# S3 任务：BIC-meta#157 — rf 窗口自动填充/推荐回归（#97 链）

你是 S3（独立复核 + 实现 + 提交 + PR，列车口径）。issue #157 正文是任务书。仓：BIC-agent-service，从 origin/main（1d9fb7a+，fetch 确认）切工作树 .wt/be-157 开分支 fix/issue-157-window-harvest-regression。

## 要点
- 先跑 #97 的具名测试（test_objective_confirm_restores_harvested_target_window* 等）看合并后 main 是否已红；再从复现会话 5121007c（talos_agent_db）还原：target_window 有没有被收割进 objective JSONB → TLC seed 读取点（tlc._pre_react_route / cold_dispatch+recommendable 链）→ auto_recommend 路由。
- 嫌疑面：svc#73（purity）对 tools.py/tlc.py 的 rebase 改动、#44/#67 合流。git log -p 对症溯源。
- 修复不回归 purity 功能。**不重启台架**（统一同步窗口由 root 做）。

## 二元验收
#97 既有测试全绿 + 复现场景 E2E（输入含 rf 范围 → TLC 冷入场 target_window 已填且触发 auto_recommend，具名断言）；全量单测绿；CI 绿合并。

## 收尾
根因（引入 commit）+ sha 评论 #157，标签转 已实现待复测；dispatch done（FACTS/Judgment 分开）。
