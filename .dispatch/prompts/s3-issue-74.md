# S3 任务：修复 c12-ai/BIC-meta#74 — 叙述控件名随界面语言（控件名词汇表）

你是 S3（调查 + 独立复核 + 实现 + 提交）。issue #74 正文是任务书。先调查：哪些 prompt/规则/模板携带英文控件名（重点 NARRATE_NEXT_STEP_RULES params 规则与 #53 修订 6e3adfa 后的措辞），调查结论评论 issue，再实现。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-74-control-name-locale /Users/wenlongwang/Work/BIC/talos/.wt/be-74 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。
- 并行提示：s3-issue-72（be-72）、s3-issue-73（be-73）在飞；#73 也在 narrate 规则域——若同文件相邻 hunk，评论互相对齐；控件名词汇表做成独立模块最稳。
- 与 #54 状态词汇表同构：控件名词汇表单一来源（zh/en），按 ctx.locale 三态注入（None=跟随输入语言时给双语名或按输入语言选）。

## 二元验收
issue #74 四条照抄执行写成测试。全量单测绿 + ruff 干净。

## 收尾
调查结论 + 修复摘要（sha、测试计数）评论 issue #74，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
