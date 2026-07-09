# T-challenge 第2轮：异常路径（adversarial）浏览器实测

你是异常路径测试员。用 Playwright 驱动浏览器实测 portal（http://localhost:5174），专攻失败/拒绝/边界/干扰路径，产出 findings 文件。

## 铁律（违反即事故）
1. **禁止任何 reset**：不得调 POST :8800/reset、不得调 lab /admin/reset-to-test-data、不得跑会 TRUNCATE 的 e2e spec——用户正在同一台架手测。
2. 只在自己新建的会话里操作；绝不打开/操作他人会话。
3. 不重启任何服务、不改任何仓库代码。只读 DB 允许（talos-postgres:5433 talos_agent_db）取证。
4. 发现**只写 findings 文件**（不建 issue）：`/Users/wenlongwang/Work/BIC/V2/BIC-meta/.dispatch/findings/t-challenge-r2/NN-标题.md`，含复现步骤、期望 vs 实际、会话 id+seq、判断（新 / 疑似已知#N / 已知未修#N）。已知台账见 `gh issue list -R c12-ai/BIC-meta --state all -L 60`。

## 挑战清单（按序执行，每项给 PASS/FAIL/BLOCKED）
1. **拒绝流**：目标表单点拒绝→修改重来；方案拒绝；参数拒绝；结果复核拒绝（观察 reject 不终态化、可返工）。
2. **TLC 失败链**：目标窗口设 0.3-0.5（mock Rf≈0.51 必败）→ 3 次重试 → 失败 accept → 观察诚实叙述 + 后续走向（#5/#11 语义）；随后失败实验的最终收尾是否照实说失败（#44 验收点）。
3. **非法输入**：质量输负数/"abc"/超大值；比例框输 "0:1"/"abc"；Rf 窗口反向 (0.6,0.4)；观察校验与错误文案。
4. **物料缺失派发**：跳过/清空物料选择直接确认参数尝试派发→应被校验挡住并引导回物料面板（#32 干跑一致性：检查就绪与真派发同判）。
5. **中途插话**：执行中问"现在什么状态/库存还有多少样品管"（query 路径）；发无关话题（admittance 拒绝口径）；中文会话里夹英文输入（三态语言表现）。
6. **界面韧性**：执行中刷新页面（SSE 重连、状态还原、无重复气泡）；表单填一半切页签再回来（脏值守卫）；快速连点确认按钮（幂等，#48 双重应用族的 FE 面）。
7. **多会话并发**：自己开两个会话交替推进，观察串扰。

## 收尾
findings 目录写 `00-summary.md`（逐项 PASS/FAIL 表 + 新发现清单）；`dispatch done` FACTS/Judgment 分开。
