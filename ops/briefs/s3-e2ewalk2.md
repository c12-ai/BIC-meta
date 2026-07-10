# S3 任务：#188 解锁后的真链补验（走查第二轮）

你是台架 E2E 补验会话。前情 = meta#190（第一轮走查台账：chain1 PASS，CC 被 #188 阻断）。#188 已修并上台（portal 533828b 含 #188+#189），specs 已收编入仓（tests/*.spec.ts 环境参数化，README 有运行前置；注意这是它们规范化后**首次实跑**，遇 harness 问题按 spec 侧修不动产品，修完可直接提 PR）。

台架：BE `81a78b7` · portal `533828b` · lab `3c03a84` · mock `246f6d4`，全真档。

## 授权（root 预授，同第一轮口径）

- 限定接管 BE 生命周期：翻 `MIND_RECOGNITION_MOCK_MODE=true`（#88 过渡档，主键保持 false）+ pane 规范重启（窗口名 agent，kill -KILL 端口占有者，unset 代理前缀 + uvicorn 直启，禁 make dev）；接管前后简报；**收尾两键 false + 全真重启 + 贴核验**。
- lab/BE reset API 跑前重置；portal 若需重启先 rm -rf node_modules/.vite。
- mock 不动（S3 env 已 150）。

## 补验清单（第一轮被 CC 阻断的全部）

1. **cc-re-chained / fp-chain specs**：CC 段现在应过 #188 的占用槽选择——这是 #188 的活链终验；FP 段顺验 #176 全孔分配（分配一个 Mind 未引用孔进 payload）。
2. **#98**：FP→RE 链思考文本无索要话术、RE 表单预填 FP 派生值。
3. **#182**：最终总结——重试达标 TLC 显示达标、LLM 叙述含真实终态、无粘连、无裸 RE。
4. **#183**：ELN 下载点击即加载态、报告含 username/反应图/FW（chem 可达）。
5. 观测型：#180 下发→监控跳转、#179 短表单无抖动、#172 分析中段、#167 op 行绿勾中文。

## 交付

- 逐项 PASS/FAIL + 一手取证；FAIL 开 issue（今晚惯例格式）；PASS 项在对应 issue 评论活验证据并可判定关闭的列出来（关闭动作留 root/用户）。
- 汇总追评 #190；收尾复原核验；dispatch done（FACTS/JUDGMENT 分开）。
