# S3 任务：c12-ai/BIC-meta#91 — 识别 fixture 按会话分子重键（修 #88 分档交叉污染）

你是 S3（独立复核 + 实现 + 提交）。issue #91 正文是任务书（抓包实证 + #25 先例 + 四验收）。抓包原文在 /private/tmp/claude-501/-Users-wenlongwang-Work-BIC-V2-BIC-meta/35cf69d6-ff07-47fb-abee-88cbc6eba2f9/scratchpad/mind_capture/（.req/.resp 对）。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-91-fixture-rekey /Users/wenlongwang/Work/BIC/talos/.wt/be-91 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。单测 `-m 'not real_llm'`。
- 落点：mind_client mock 分支的识别 fixture 构造（recognize_tlc_plate / analyze_result(CC)），从请求上下文取 rxn 拆分子重键；对齐 #25 的 rxn-keyed 派发模式，别造第二套机制。

## 二元验收
issue #91 四条照抄执行写成测试（抓包形状夹具）。全量单测绿 + ruff 干净。

## 收尾
修复摘要（sha、测试计数）评论 issue #91，标签改 stage:已实现待复测；dispatch done。root 合入后恢复分档模式。
