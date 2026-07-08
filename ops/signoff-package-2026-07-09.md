# 拍板材料包（2026-07-09）

## 摘要
32 小时内：33 个 issue 建档 → 24 关闭（自动化证据）→ 黄金链路 e2e 首次全绿（1 passed/10.6m）。
两个架构动作（narrate 契约化、状态语义收敛）已在独立 refactor 分支落地。三个 fix 分支已 rebase
latest main、门禁全绿、未 push。**待拍板：手测确认 → push + rolling PR。**

## 分支全景（全部本地未 push）
| 分支 | 位置 | 领先 main | 门禁 |
|---|---|---|---|
| BE fix/chat-ux-lang-error-tubeid | 主目录（bench 运行中） | 27 commits | 1298 单测 / ruff / pyright ✓ |
| portal fix/chat-ux-lang-error-tubeid | 主目录 | 6 commits | tsc / 149 单测 ✓ |
| lab fix/chat-ux-lang-error-tubeid | 主目录 | 1 commit | 243 单测 ✓ |
| BE refactor/narrate-contract | .wt/narrate（stacked on fix） | +6 | 1028 单测 0 fail ✓ |
| portal refactor/state-semantics | .wt/state-portal（stacked） | +4 | 门禁 ✓ |
| BE refactor/state-semantics | .wt/state-be（stacked，spec/注释为主） | +2 | ✓ |

## 验证证据（关单依据）
- e2e cc-re-chained：1 passed（10.6m），首次全链绿
- T-verify-main：7/7 PASS（含失败轮动态实证）
- T-verify-challenge：8 PASS / 2 FAIL（FAIL 残余已由 refactor 分支修复：#22 路由、#24 渲染层）
- 关单 24 个，逐 issue 证据 comment 在案

## Open issues（9）
#10/#30（等同事 PR#66/#16 合入）· #22/#24/#36/#37（refactor 分支已修待复测）·
#25/#26 已修（state 分支 d04efa6 覆盖 #26；#25 待 mock fixture 决策）· #32/#35（needs-drake）· #33（架构主线，动作③模型A/B 推迟中）

## Push + rolling PR 方案（待拍板执行）
1. push 三个 fix 分支 → 各开 rolling PR（描述含 issue 清单 + 验证证据链接；Refs 不 Fixes）。
2. push 三个 refactor 分支 → 各开 stacked PR（base = fix 分支 PR）。
3. **Drake 复核清单**（PR 描述单独标注）：D47 submit 边界反转（647d8c2）· trial 终态化（b9800f0/5b48666）·
   once-gate（8fa3be7）· form-first 契约（a2c9dc7）· #14 baseline 推断（2d03fb1）· #19 硬闸（ec78072）·
   narrate 契约（narrate-contract.md + 清扫批）· 状态权威表（d2397da）· taskName 归属 · #32/#35 决策。
4. 合并顺序建议：同事 PR（#66/#16/#88）先 → 我们 fix PR rebase 合入 → refactor PR。

## 手测入口（bench 已刷新就绪）
portal http://localhost:5174（fix 分支代码，BE 57ae857 运行中，lab 干净，robot idle）。
建议动线：黄金开场白全链（观察叙述质量/预填/失败恢复）→ 能力自述 → 设备/任务查询。
