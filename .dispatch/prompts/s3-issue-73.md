# S3 任务：修复 c12-ai/BIC-meta#73 — 终报后幽灵叙述 turn + 反向 CTA

你是 S3（调查 + 独立复核 + 实现 + 提交）。issue #73 正文是任务书（含 DB 时间线 seq 845-861 与两问）。先查 turn 88e450aa 的触发源（L2 队列消费/orchestrator 对迟到事件的 turn 铸造路径）与产话 prompt 族，结论评论 issue，再实现。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-73-phantom-turn /Users/wenlongwang/Work/BIC/talos/.wt/be-73 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。DB 只读取证。
- 并行提示：s3-issue-72 在 be-72（mind client 映射），文件应不相交；narrate 规则若相邻，评论对齐。

## 二元验收
issue #73 四条照抄执行写成测试。全量单测绿 + ruff 干净。

## 收尾
调查结论（触发源 file:line + prompt 族）+ 修复摘要（sha、测试计数）评论 issue #73，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
