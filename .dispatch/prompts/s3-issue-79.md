# S3 任务：c12-ai/BIC-meta#79 — 化合物矩阵行级结构图

你是 S3（方案查证 + 独立复核 + 实现 + 提交）。issue #79 正文是任务书（三方案取舍）。先查证：chem-service 加 depiction 端点的改动量（RDKit MolDraw2DSVG，仓在 /Users/wenlongwang/Work/BIC/talos/BIC-chem-service，注意该仓归 yanbowang——若选 a 先评论 issue 请示 root）vs 前端渲染库的包体/一致性，选型结论评论 issue 再实现。

## 工作区纪律
- portal：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-79-structure-images /Users/wenlongwang/Work/BIC/talos/.wt/portal-79 bench-verify`；若选 a，chem-service 侧分支同名（该仓 main 即基线）。
- 不碰各 bench 主目录、不重启、不 push、不开 PR。
- 并行提示：portal 在飞 #76/#77/#78——矩阵在目标表单域，应不相交。

## 二元验收
issue #79 照抄执行写成测试。全量门禁绿。

## 收尾
选型结论 + 修复摘要（sha、测试计数）评论 issue #79，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
