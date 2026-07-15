# S3 任务：meta#195 census 的 P2 机械清理批（含 P2-1 安全项与 P2-9 flake 根修）

你是 S3（实现 + PR，列车口径）。任务书 = meta#195（母 census，P2×13 逐条 file:line）+ 相关评论。仓：BIC-agent-service，从 origin/main 切工作树 `.wt/p2sweep`，分支 `chore/issue-195-p2-sweep`。
并行知会：s3-be194 在叙述归一设计面、s3-docsync 在文档面——你只做 #195 列为 P2 的机械项，撞面的跳过并注明。

## 优先序

1. **P2-1（安全，最先）**：`_DebugLLMIO` 在 live 路径写世界可读 `/tmp/llm-io.log`（llm_client.py:198/224）——LLM 输入输出含实验数据落全局可读文件。修法：默认关闭（env 门控 opt-in）+ 文件权限 0600 + 路径进用户目录/明确配置；确认 live 生产路径零写出。
2. **P2-9（flake 根修）**：test_current_user_id 顺序污染根因 = alembic/env.py:16 fileConfig 重配日志污染 caplog（census 实跑复现）——按根因修（fileConfig 加 disable_existing_loggers=False 或测试隔离），今晚撞了三次的噪音源就此消灭；修后全量跑 3 遍证明稳定。
3. 其余 P2 逐条过：可安全机械修的修（每条独立 commit 引 #195 条目号）；发现实为设计问题的跳过并在 #195 评论注明归 #194 或另立。

## 二元验收

- P2-1：live 路径无调试写出（具名测试/代码断言）+ opt-in 门控生效；P2-9：全量 pytest ×3 稳定绿（含原 flake 用例）。
- 逐条对账表（P2-1..13：fixed/skipped+why）评论 #195；全量 pytest + ruff/pyright + CI 绿 admin-merge 留痕。**不重启台架**（e2ewalk2 正持有接管，绝不碰运行态）。

## 收尾

PR sha + 对账表评论 #195；dispatch done（FACTS/JUDGMENT 分开）。
