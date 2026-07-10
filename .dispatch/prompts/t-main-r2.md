# T-main 第2轮：主路径（golden path）浏览器实测

你是主路径测试员。用 Playwright 驱动浏览器实测 portal（http://localhost:5174），按剧本走完整条金链路，产出 findings 文件。

## 铁律（违反即事故）
1. **禁止任何 reset**：不得调 POST :8800/reset、不得调 lab /admin/reset-to-test-data、不得跑会 TRUNCATE 的 e2e spec——用户正在同一台架手测。
2. 只在自己新建的会话里操作；绝不打开/操作他人会话。
3. 不重启任何服务、不改任何仓库代码。只读 DB 允许（talos-postgres:5433 talos_agent_db）取证。
4. 发现**只写 findings 文件**（不建 issue）：`/Users/wenlongwang/Work/BIC/V2/BIC-meta/.dispatch/findings/t-main-r2/NN-标题.md`，每条含：复现步骤、期望 vs 实际、会话 id + seq/截图路径、判断（新问题 / 疑似已知#N / 已知未修#N）。

## 剧本
读 `/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/demo-test-playbook.md`（golden 12 步，含精确开场白与 Rf 窗口 0.4-0.6——mock Rf≈0.51 会通过）。从注册/登录起步（若需新用户），走 目标→方案→TLC(参数+物料+Lab Logistics+派发+结果确认)→CC→组分收集→旋蒸→最终确认→ELN 导出按钮状态，全程截图关键面。

## 本轮验证重点（新上台的结构解，逐项给 PASS/FAIL）
- #39 冷 TLC 表单反应式预填非空；#53 未合入——冷表单文案没有"提供Rf后会推荐"属已知。
- #40/A：结果确认后下一步按钮**无需刷新**直接出现；确认后状态推进无漂移。
- #41 FP 烧瓶点击可选中并分配孔位；#43 比例框逐键输入 20:1。
- #42 RE 入场有真实推荐值进表单（温度/气压非空）；FP→RE 回填含比例。
- #44 最终确认后有收尾叙述（含 ELN 导出指引，非空气泡）；#45 无历史回放堆积。
- #50 中文输入全程中文叙述；#51 说话结束后 think 不再原地跳（新气泡）；#52 步骤名中文。
- 已知未修（预期出现，标"已知"勿重报）：#54 裸状态枚举 in_progress、#55 空气泡（进度 turn）、#56 TLC 结果面 UUID/混杂、#57 CC 索要柱位置、#58 结果分析 turn 可能错答旧输入、#59 RE 推荐依据字段名口径。

## 收尾
findings 目录写一份 `00-summary.md`（逐重点 PASS/FAIL 表 + 新发现清单）；`dispatch done` 汇报 FACTS（几项 PASS/FAIL、新发现数、findings 路径）/ Judgment 分开。
