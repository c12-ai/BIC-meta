# S3 任务：BIC-meta#163 TEMP workaround — cc/result 透传前把 product spot 截到 ≤3（可随时整体拆除）

你是 S3（实现 + PR，列车口径）。背景 = BIC-meta#163（读全 issue：Mind cc/result 对 ≥4 个 product 角色 spot 确定性 400，二分矩阵已锁死规律；契约本意是原样透传，Mind 侧修复已 ask）。用户裁定：加**最小、可随时去掉**的 BE 侧止血。

仓：BIC-agent-service，从 origin/main（≥2daa934）切工作树 `.wt/mindcap`，分支 `fix/issue-163-cc-product-spot-cap`。
注意：s3-be90 正在同仓 `.wt/be90` 动 `fast_path_handlers.py`，你别碰那个文件（改动面应只在 mind_client 或其紧邻）。

## 设计（KISS，按此做，勿扩）

- 单点拦截：`app/infrastructure/mind_client.py` 的 `analyze_result` CC 分支（真实 HTTP 前）。
- 规则：若 `tlc_result.plates[*].spots` 中 role=product 的数量 > 3，保留**按 |rf − confirmed_product_rf| 最近的 3 个** product（锚点必然保留），非 product 点全保留；确定性排序（距离相同按 spot_id）。
- 配置门控：`mind_cc_product_spot_cap: int | None = 3`（config.py，env `MIND_CC_PRODUCT_SPOT_CAP`；None/空 = 关闭 = 恢复契约原样透传）。
- 触发裁剪时 `logger.warning`，内容含被裁 spot 数量与 meta#163 引用。
- 整段代码用显式 `# TEMP(BIC-meta#163): remove this block when Mind accepts full pass-through` 注释包住——"随时去掉"的验收口径：删掉该块 + config 字段 + 测试文件即可回到纯契约行为，无其他耦合点。

## 二元验收

- 具名测试：7-spot（4 product）请求 → 发出的 payload 恰 3 product（锚点在内）+ 全部非 product；cap=None → 原样透传；≤3 product → 不动。
- 全量本地 pytest 绿；ruff/pyright 干净；CI 绿（现在 CI 是真 CI 了，#88 后 DB 套件全跑）admin-merge 留痕。
- **不重启台架**（部署归 root）。

## 收尾

PR sha 评论 meta#163（注明 TEMP 性质与拆除口径）；dispatch done（FACTS/JUDGMENT 分开）。
