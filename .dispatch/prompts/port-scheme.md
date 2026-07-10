# 端口治理专车（用户裁定：固定端口方案 + 落档 + 各仓 example 更新）

你是端口治理操作员，继承合并列车的授权（可开 PR/合并，CI 全绿 + flow bot 豁免 + codeowners admin-merge 留痕口径照旧）。用户指令：「端口安排都固定下来，不要用8080这种容易冲突的端口，尽量有一定规律。确认好后落档到infra, meta，然后更新对应repo的example等文件」。

## 方案骨架（root 拟定，你核实可用性后定稿）
规则三条：
1. **在位稳定端口不迁**（迁移成本>规律收益）：BE 8800 / lab 8192 / chem 8010 / Mind 捕获代理 8011 / phoenix 6006 / portal 定一个（5173 vite 默认 vs 台架曾用 5174——你查两处哪个被写进更多脚本/文档后定一个，另一个废止）。
2. **易撞默认端口一律 +10000**：keycloak 8080→18080（已实测）、未来 grafana 3000→13000、通用 8000/5000/8080/3000 列入禁用清单，新服务缺省端口若在禁用清单必须 +10000。
3. **基建口径固定**：postgres 5432(bic)/5433(talos)、rabbitmq 5672、minio 9000、redis 6379——已是事实标准，照录。
定稿前用 lsof 对本机核实每个端口现状，撞了就按规则 2 挪并说明。

## 落档与更新（每处都要做）
1. **infra 仓（权威）**：端口分配表进 README（或 docs/ports.md）+ docker-compose 端口对齐；开 PR 合并。
2. **BIC-meta**：ops/port-allocation-2026-07-10.md 落表 + 更新 ops/run-latest-2026-07-10.md（团队文档）里所有端口引用 + CLAUDE.md 里冷启段落的端口口径；直接 commit（meta 仓可直推）。
3. **各 repo example**：BE .env.example（KEYCLOAK_ISSUER_URL 等）、portal .env.example（VITE_OIDC_AUTHORITY、端口）、lab（如有）、mock（S3_ENDPOINT 默认注释）——各仓小 PR 合并。
4. 与现跑台架一致性：若定稿与台架当前运行态不一致（如 portal 端口二选一），把台架对应服务重启到定稿口（BE 重启带 unset 代理前缀）。

## 收尾
端口表 + 改动 PR 清单评论到 BIC-meta 新 issue「端口分配定档 2026-07-10」；dispatch done（FACTS/Judgment 分开）。

## 并行协调（root 追加）
merge-train 正在写 ops/run-latest-2026-07-10.md（团队文档）——你对该文件的端口修订放在最后一步做：先完成方案定稿/infra/examples，末了检查该文件是否已存在，存在才修订（git pull 先），避免和列车撞写。
