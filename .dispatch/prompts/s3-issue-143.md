# S3 任务：c12-ai/BIC-meta#143 — mock TLC 按轮序列夹具

你是 S3（独立复核 + 实现 + 提交）。issue #143 正文是任务书。仓：/Users/wenlongwang/Work/BIC/talos/mars_interface_mock，直接在当前分支（HEAD c4eb6e4）上开新分支 feat/issue-143-round-fixture-sequence（不 push/不 PR/不重启，root 统一部署；注意 merge-train 可能并行处理该仓——你只管把分支做好）。

## 要点
- 轮计数 key：读 START_TLC 命令 schema 与 lab append_round 的实际载荷（bic_shared_types robot 协议 + BIC-lab-service task_service append 语义）找稳定任务身份；确定性、可 replay（selfcheck 不许被破坏）。
- 参照 #132（c4eb6e4）的 FIXTURE_PATH/TLC_FIXTURE 现状与 #112 的 CC 动态字节断言模式。

## 二元验收
issue #143 四条照抄，smoke 断言逐条落。

## 收尾
修复摘要评论 issue #143，标签 待修复 → 已实现待复测；dispatch done（FACTS/Judgment 分开）。
