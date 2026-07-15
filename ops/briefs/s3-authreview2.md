# S3 任务：auth 五 PR 增量复审（authreview round 2）—— 只读、零发布

你是 S3（增量复审会话）。**GitHub 全程只读：零 comment、零 review、零 label、零 merge。产物只写一个文件：`.dispatch/findings/authreview2-2026-07-13.md`。** 若你发现自己在 gh pr comment/review/merge，立即停手——那是纪律红线。

## 背景

五 PR 在 2026-07-13 首轮联审后各自有新 head（首轮 findings 见 `.dispatch/findings/authreview-2026-07-13.md`，208 行，先通读它作为基线）：

| PR | 首轮 verdict | 首轮 base（findings §时序表） | 当前 head |
|---|---|---|---|
| A1 infra#7 | 可合 as-is | abd37d4 | e74d5de |
| A2 meta#171 | 可合 as-is | — | 17d8057 |
| B BE#97 | 可合 as-is | c132bdc | cf0cc73 |
| C portal#36 | 可合 as-is | 4915908 | dfd2ef8 |
| D lab#112 | 代码可合/开闸受前置 | d57de0f | 32200d8 |

## 任务：增量 = 只审"变了什么"，不重审全量

1. 五仓 `git fetch`，拉各 PR head；对每个 PR 计算**自首轮 review 以来的 delta**（新 commit / force-push 差异）——是纯 rebase 还是有新内容？
2. 若有新内容：逐行核对，判断是否①响应首轮 findings（补测试/改默认/修 minor）②引入新风险③改变首轮 verdict。
3. **机械冲突重算**：五分支对各仓**当前** main tip 的 merge-tree（main 这几天在前进，尤其 lab/portal/BE 都滚了新版）；首轮"零冲突"是否仍成立。
4. 特别复核首轮标记的开闸三坑与断裂清单是否被新 head 触及（如 D 是否补了 issuer 默认、B 是否补了冷启单飞测试、A2 是否补了 e2e-runner/demo curl）。
5. 首轮的两张跟进 issue（meta#296 尾款 / meta#297 field blocker）是否有 PR 已开始消化。

## 产物（findings 文件结构）

- TL;DR 表：每 PR「首轮 verdict → 本轮 delta → verdict 是否变」；
- 每 PR：delta 内容（commit/文件级）+ 是否响应首轮 + 新风险；
- 机械冲突对当前 main 的重算结果；
- 开闸前置/断裂清单的变化；
- 给 Wenlong 的一句话结论（可合顺序是否有变、有无新 blocker）。
- 每条 Facts 可独立核验；判断显式标注。

## 收尾

**不发布任何 GitHub 内容。** dispatch done 用单行短摘要 + 核退出码：`dispatch done '增量复审完成，findings 就绪：<路径>；<verdict 是否变一句话>'`。findings 全文只落文件，主会话自行读。
