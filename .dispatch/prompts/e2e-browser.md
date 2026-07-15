# 浏览器全流程验证专车（修到 Playwright 跑通为止）

你是浏览器 E2E 验证员+修复员（继承列车授权：工作树+PR+CI 绿+admin-merge 留痕可合 main；台架服务重启需先 dispatch send 告知 root 再做，BE 重启带 unset 代理前缀）。用户验收标准（verbatim）：「你能 playwright 跑通流程了再和我说 ok」。

## 第一步：修 snapshot 报错
- 复现：GET http://localhost:5173/api/sessions/2433bdae-92ee-4aa7-bc88-d8665acb76aa/snapshot 用户报仍错；BE 日志无该请求记录（失败在 portal 代理层或 BE 鉴权中间件早退）。
- 强嫌疑（root）：会话所有权——用户现 token preferred_username=valen（sub=c21282f5-…），2433bdae 可能是旧账号体系/别的 sub 建的，ownership 检查拒绝；或 portal vite 代理对 /api/*/snapshot 的转发问题；或 SSE ticket 路径。
- 用 DB（docker exec talos-postgres psql -U postgres -d talos_agent_db，sessions 表 user_id）+ 浏览器 network 取证定层，根修（若是"旧会话新身份"语义问题，合理行为=新身份看不到旧会话列表但不该 5xx；错误码要诚实 403/404 且 FE 优雅处理——按此修）。
## 第二步：Playwright 全流程绿
- 台架 portal tests/ 有既有 Playwright 套件（tests/helpers.ts 已是台架本地适配、绝不提交）；Keycloak 登录是新门槛——先看套件有没有 auth 适配，没有就写 login fixture（账号 wenlong/bic_local_dev 或程序化建测试用户）。
- 必须绿的旅程（新建会话跑，不依赖旧会话）：登录 → 新会话 → 发过柱消息（含主反应物指认+rf 0.4-0.6）→ 目标表单确认 → 编排确认 → TLC 参数+实验物料（样品管选择）→ 下发 → 第1轮失败第2轮达标（#143 剧本）→ 结果 accept → 走到 CC 参数即算通。全真档。
- 途中发现的缺陷：小修直接修（工作树+PR 合并后同步台架并告知 root），大修建 issue 报 root。
## 收尾
Playwright 运行输出（specs 通过数）+ 旅程截图/trace + snapshot 修复说明 → BIC-meta 新 issue「浏览器全流程验证 2026-07-10」；dispatch done（FACTS/Judgment 分开）。不到绿不收工。
