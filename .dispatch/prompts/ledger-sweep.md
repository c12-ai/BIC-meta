# 台账清扫（issue 关闭批处理）

你是台账管理员。用户指令：把已处理好的 issue 关闭。仓：c12-ai/BIC-meta（gh issue list --state open -L 200 全量过一遍）。各代码仓 main 已含列车步骤①全部合并（BE d55e472 / portal 1919d9a / lab 61b3d5f / mock 389a784 / shared-types c86f9b4）。

## 关闭规则（二元，逐条核对）
可关闭 = 满足其一：
1. 标签 stage:已验证（#142 独立验收过）；
2. 标签 stage:已实现待复测 且其修复 commit 可达对应仓 main（用 issue 评论里记录的 sha `git merge-base --is-ancestor <sha> origin/main` 核实，本地仓在 /Users/wenlongwang/Work/BIC/talos/ 下先 fetch）；
3. issue 正文/评论明确记录"已关闭/已解决/superseded"但状态还开着的。
关闭评论模板：修复 sha + 所在合并 PR + 验证级别（「#142 独立验证」或「已合入 main，复测挂了请 reopen」），一句话，不长篇。

## 必须保持 open（勿动）
- stage:待调查 / 待裁定 / 待修复 的一切；
- 外部依赖类：#127（等 Algo）、#124（二期蓝图，待 #128 实施吸收后由实施者关）、#144（portal CI）；
- 设计/裁定类：#128 #131 #138（实施完成才关）；报告类汇总 issue（#134 #141 #142 #133 #135 #137 及列车报告）保持 open 供用户查阅，除非正文已注明可关；
- 拿不准的一律留 open 并在报告里列出（宁漏勿错）。

## 收尾
清扫报告评论到新建 issue「台账清扫 2026-07-10」：关闭清单（号+一句依据）、保留清单（拿不准项+原因）、台账余量统计（open 数 by stage 标签）。dispatch done（FACTS/Judgment 分开）。
