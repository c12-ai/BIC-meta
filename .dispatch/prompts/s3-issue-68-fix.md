# S3 任务：修复 c12-ai/BIC-meta#68 — RE end_evaporation 计时器持久化 + 重启恢复

你是 S3（独立复核 + 实现 + 提交）。S2 根因已评论在 issue #68：end_evaporation 派发挂在进程内 asyncio 计时器，lab 在 RE 等待窗（468s）内重启即永久丢失，trial 永卡 dispatched。先复核（读 lab 的 RE 编排代码自证计时器生命周期），复核结论评论到 issue，再实现。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-lab-service worktree add -b fix/issue-68-re-timer-recovery /Users/wenlongwang/Work/BIC/talos/.wt/lab-68 bench-verify`（lab bench 分支含 #61 修复）。
- 不碰 bench 主目录、不重启（root 统一合入重启）、不 push、不开 PR。

## 修复要求
1. **持久化截止时间**：start_evaporation 时把 end_evaporation 的应派发时刻落库（任务行或专表，取既有模式）。
2. **启动恢复**：lab 启动时扫描在途 RE 任务的未派发 end 窗口——已过期立即派发、未到期重新挂计时器。恢复必须幂等（重复启动不重复派发）。
3. 已卡死的存量任务：恢复逻辑应能把"截止已过但未派发"的任务救活（这就是过期即派发分支）。
4. 不改协议/契约面；若表结构变更需 alembic 迁移，照 repo 既有迁移模式。

## 二元验收
(1) 集成测试：等待窗内模拟重启（销毁计时器状态 + 重跑恢复）→ end_evaporation 仍按时派发、任务完成；(2) 过期恢复：截止已过的在途任务在启动恢复时立即派发；(3) 幂等：恢复跑两次不双发；(4) 正常无重启路径零回归。全量 lab pytest 绿 + ruff/pyright 干净。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #68，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。完成后 root 合入重启 lab。
