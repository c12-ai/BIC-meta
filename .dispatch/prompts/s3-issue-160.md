# S3 任务：BIC-meta#160 — headless recommend 不触发 → 拿下 Playwright 单次绿跑

你是 S3（继承 e2e-browser 的收官使命，新鲜预算）。用户验收（verbatim）：「playwright 跑通流程了再和我说 ok」。前任 e2e-browser 的遗产：①issue #160（headless recommend 按钮不触发：手动/JS click 均通，Playwright headless 不通——测试脚手架时序问题）；②portal 台架检出（main 4055ee7）工作区里有其重写过的 bench-local spec（tlc-retry-flow）与 helpers.ts 台架适配（均不可提交）；③收尾报告在 BIC-meta#160/#141 系。台架已全量同步至各仓最新 main、全真档、MQ 单消费者、TLC 链通。

## 任务
1. 修 #160：headless 下 recommend 不触发的根因（waitFor 时序/hydration/festure detection/headed-only 样式遮挡……），修在 spec 脚手架层；若查明是产品可达性缺陷（如按钮依赖 hover/污染 a11y）则修产品并单独 PR。
2. 跑 tlc-retry-flow 全旅程 spec 至**单次全绿**（登录→objective→编排→TLC 物料下发→round1 失败→round2 达标→accept→CC）。识别档位：MIND_MOCK_MODE 可临时 true 求确定性（跑完恢复 false 并核验，前任口径）。
3. 绿跑证据（spec 输出+trace 路径）评论 #160 并关闭；把可提交的 spec 修改（非 bench-local 部分）PR 合入。
## 红线
台架服务重启先 dispatch send 告知 root；BE 重启带 unset 代理前缀；helpers.ts 与 bench-local 适配不入 commit。
## 收尾
dispatch done（FACTS：绿跑输出；Judgment 分开）。不到绿不收工，卡死则 fail-loud 报 root。
