# S3 任务：全链 Playwright 走查（今晚全部合并产物上台后的回归验收）

你是台架 E2E 走查会话。台架当前：BE `81a78b7` · portal `424efae` · lab `3c03a84` · mock `df0e393`（全 = main），postgres 单实例 bic-postgres:5432，全真档（MIND 两键 false）。

## 授权（root 预授）

- **限定接管 BE 与 mock 生命周期**（本任务期间）：BE 重启 = 按端口找 pane（tmux bic-services，窗口名 agent；先 kill -KILL 端口占有者；unset 代理前缀 + `uv run uvicorn app.main:app --host 0.0.0.0 --port 8800`；**禁 make dev**）；mock 重启 = 窗口名 mock，带 S3 env（S3_ENDPOINT=192.168.12.150:9000 S3_ACCESS_KEY=minioadmin S3_SECRET_KEY=bic_local_dev S3_BUCKET=tlc-images）。每次接管动作前后 dispatch send 简报 root。
- **档位**：跑 spec 用 #88 过渡档（MIND_MOCK_MODE=false + MIND_RECOGNITION_MOCK_MODE=true，脚本化 Rf 确定性）；**收尾必须两键复原 false + 重启全真 + 贴 .env grep 与 health 核验**。
- **夹具适配（关键）**：mock 默认达标照已换 tlc_plate_real01.png（Rf≈0.787），而 bench-local retry spec 断言窗口 [0.4,0.6]——跑 retry 链时 mock 以 `TLC_FIXTURE_SEQUENCE=tlc_plate_fixture.png,tlc_plate_med02.jpg` 启动（收尾去掉该 env 恢复默认）。或改 spec 窗口到含 0.787——二选一，收尾说明。
- lab reset API 可用（CLAUDE.md 的 /admin/reset-to-test-data + BE /reset）——跑前重置，**先确认用户不在测试**（深夜默认可跑；若发现 5173 有活跃会话操作痕迹，dispatch send 问 root）。

## 走查范围（bench-local specs 在台架 portal 工作区未提交文件里：tests/tlc-retry-flow.spec.ts、tlc-e2e-final-chain.spec.ts、helpers.ts——直接用/按需适配，仍不提交）

1. tlc-retry-flow：TLC 首轮出窗→追加轮→达标→审核（今晚 #180 修复后 confirm→monitor 跳转断言可加）。
2. tlc-e2e-final-chain（或手动 CDP 补全）：全链 objective→plan→TLC→过柱→组分收集（**验今晚 #176 全孔可分配：分配一个 Mind 未引用的孔**）→旋转蒸发（验 #98：思考无索要话术）→最终总结（验 #182：TLC 重试达标不标失败、无粘连、无裸 RE）→ELN 下载（验 #183：加载态 + username/反应图/FW 字段）。
3. 观测型断言随做随记：#179 短表单无抖动、#172 分析中段、#167 op 行绿勾中文。

## 交付

- 每条链 PASS/FAIL + 失败的 primary-source 取证（截图/trace/事件序列），新发现问题逐个开 meta issue（格式照今晚惯例：现象/根因线索/验收）。
- 汇总评论到一个新开的走查 issue（标题：全链走查 2026-07-11 凌晨）。dispatch done（FACTS/JUDGMENT 分开）。
