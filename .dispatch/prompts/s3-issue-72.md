# S3 任务：修复 c12-ai/BIC-meta#72 — 真 ChemEngine 下化合物矩阵富化全空（契约漂移调查+修复）

你是 S3（调查 + 独立复核 + 实现 + 提交）。issue #72 正文是任务书（含 DB 实证与三方对照要求）。真 ChemEngine 已在台架接通（52.83.119.132:8003，BE 无代理直连），BE 日志有真实响应可取证（app/logs/app.log）。

## 工作区纪律
- BE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-72-parse-enrichment /Users/wenlongwang/Work/BIC/talos/.wt/be-72 bench-verify`；FE 若需改（矩阵行结构图 SMILES 客户端渲染兜底）：portal 同名侧分支。
- 不碰 bench 主目录、不重启、不 push、不开 PR。BE 单测 `-m 'not real_llm'`（真响应形状可以做成夹具）。
- 可以只读调用真 ChemEngine 取证响应形状（curl POST /api/protocol/... 只读解析类接口），不得高频压测。
- 并行提示：s3-issue-71 在 portal 另一侧分支（监控日志），文件不相交。

## 二元验收
issue #72 四条照抄执行写成测试（真响应形状夹具 + mock 回归锁）。全量门禁绿。

## 收尾
调查结论（漂移点 file:line + 真响应样本节选）+ 修复摘要（sha、测试计数）评论 issue #72，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
