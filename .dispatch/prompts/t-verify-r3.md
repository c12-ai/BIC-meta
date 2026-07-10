# T-verify 第3轮：补验 r2 被 #61 挡住的全部项（reset 绕过已执行）

你是补验测试员。lab 刚已 reset（silica_plate_001 已复位），#61 缺陷用户裁定暂不修、轮间 reset 绕过。用 Playwright 驱动 http://localhost:5174 补验以下项。

## 铁律
1. **reset 政策（比 r2 放宽一档）**：本轮开始时台架已就绪，无需 reset；若你把金链路跑完导致 _001 再次废弃、且还需要第二条链，可以且只可以调 lab reset（`curl --noproxy '*' -s -X POST http://127.0.0.1:8192/admin/reset-to-test-data -H 'Content-Type: application/json' --data-raw '{"robot_id":"talos.001"}'`）——**每次 reset 前先确认 robot idle 且 5 分钟内无非自己会话的活动**（DB 只读查 session_events 最新 emitted_at）。绝不调 :8800/reset（会清所有人会话）。
2. 只用自建会话；不重启服务；不改代码。发现只写 findings：`.dispatch/findings/t-verify-r3/NN-标题.md`（新 / 疑似已知#N / 已知未修#N）。
3. 已知未修（预期出现勿重报）：#53/#54/#55/#56/#57/#58/#59/#60/#62 均完工未合入 bench；#61 本身（若 TLC 派发再死于 silica_plate 即它，reset 后重试）。

## 补验清单（金链路走到底，逐项 PASS/FAIL）
1. **#40A**：TLC/CC 结果确认后下一步表单+确认按钮无需刷新直接出现；连点确认无重复效应。
2. **#41**：FP 烧瓶 chip 点击可选中、可分配孔位、可改名（≤5字）。
3. **#43**：RE 比例框逐键输入 "4:2" 成功。
4. **#42**：RE 入场表单温度/气压带真实推荐值（非空、非默认巧合——对照叙述数值一致）。
5. **#44**：最终结果确认后收尾叙述非空、含各步真实终态与 ELN 导出指引。
6. **#45**：全程无历史段落逐字回放、无重复段。
7. **挑战项（r2 顺延）**：a) TLC 失败链——新会话 Rf 窗口 0.3-0.5（mock Rf~0.51 必败），3 次重试后失败 accept：叙述诚实说失败、给下一步询问；失败实验走到最终确认时收尾不得出现成功美化。b) 结果复核 reject：reject 后不终态化、可返工。
8. **ELN 导出**：全部确认后下载按钮可用（点击下载 zh 版验证 200；未全确认时按钮禁用）。

## 收尾
`00-summary.md`：逐项 PASS/FAIL 表（注明证据会话 id/seq/截图）+ 新发现清单 + reset 使用记录。`dispatch done`：FACTS/Judgment 分开。
