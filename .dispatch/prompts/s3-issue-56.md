# S3 任务：c12-ai/BIC-meta#56 — TLC 结果审核面调查 + review + 可读性修复

你是 S3（调查 + review + 实现，用户点名"dispatch一个session调查，review"）。issue #56 正文是任务书主体，先读。

## 工作区纪律
- 调查阶段只读：`/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal`（bench-verify，用户在测，主目录只读）、`/Users/wenlongwang/Work/BIC/talos/BIC-agent-service`（斑点数据的 BE 侧结构）、robot mock（`/Users/wenlongwang/Work/BIC/talos/mars_interface_mock` 若在；以实际路径为准）与 DB 只读（talos-postgres:5433 talos_agent_db，会话 18249ece 的 task_result_analyzed payload 有真实斑点行结构）。
- 实现阶段自建 worktree + 侧分支：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-56-tlc-result-readability /Users/wenlongwang/Work/BIC/talos/.wt/portal-56 bench-verify`。
- 不碰 bench 主目录工作区、不重启、不 push、不开 PR。
- 若调查发现 BE 侧也需改（如识别 payload 缺角色枚举语义），先评论 issue 请示 root 再动 BE。

## 三步
1. **调查**：斑点 id/角色/Rf 数据链（ChemEngine mock → BE task_result_analyzed → FE 渲染组件）+ 板图 URL 链（robot mock → MinIO presigned → FE）。产出"mock 预期 vs 渲染缺陷"边界结论，评论到 issue #56（file:line + DB payload 佐证），并回答"真机数据下这个面长什么样"。
2. **Review**：整个 TLC 结果审核面（判据行、审核态、组分表、板图区）按"化学家可读"标准列问题清单，一并评论。
3. **修复**（issue 修复方向 + 二元验收照抄执行）：斑点显示"斑点 N"（UUID 收进 tooltip/title）、角色 i18n（反应物/产物/辅助斑，与 PR#16 术语对齐，translation-parity 不破）、mock 板图属预期则加"模拟图像"角标（如判定为渲染缺陷则修渲染）。注意与 s3-issue-51-52 并行（不同文件，侧分支互不阻塞）。

## 收尾
复核/调查结论 + 修复摘要（sha、测试计数）评论 issue #56，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。合入窗口由 root 协调。
