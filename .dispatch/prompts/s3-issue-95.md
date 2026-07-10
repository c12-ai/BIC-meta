# S3 任务：c12-ai/BIC-meta#95 — 化合物名称富化（chem-service + PubChem）

你是 S3（独立复核 + 实现 + 提交，跨仓）。issue #95 正文是任务书（端点设计 + 降级契约 + 四验收）。

## 工作区纪律
- chem-service：仓在 /Users/wenlongwang/Work/BIC/talos/BIC-chem-service（归 yanbowang）——**动它之前先评论 issue #95 请示 root**；获准后侧分支 `feat/compound-names`（该仓 main 基线），本地 :8010 有活体可对照。
- BE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-95-name-enrichment /Users/wenlongwang/Work/BIC/talos/.wt/be-95 bench-verify`。
- 不碰各 bench 主目录、不重启、不 push、不开 PR。
- PubChem 外呼：实现里走 httpx 带超时与并发限制；测试全部 mock 外呼（不打真 PubChem）；真实连通性单独一次手测并在 issue 记录（含代理需求结论）。
- BE 接线落解析富化处（#72 的服务端权威点之后），失败零阻塞。

## 二元验收
issue #95 四条照抄执行写成测试。两仓门禁绿。

## 收尾
复核结论 + 修复摘要（两仓 sha、测试计数、PubChem 连通性实测）评论 issue #95，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
