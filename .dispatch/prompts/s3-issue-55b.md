# S3 任务：c12-ai/BIC-meta#55 二修 — 空气泡回收的逃逸形态（RE 下发窗口）

你是 S3（调查 + 实现 + 提交）。#55 一修（349ee7e，完结时回收）已上台，但用户实测 RE 下发→成功窗口仍出现纯 trace 空气泡（1 事件 0.0s）。最新 FAIL 评论在 issue #55。

## 第一步（调查，结论评论 issue）
在 DB 找到该形态的 turn（最近会话，RE 下发前后、text_done 缺失的 turn），还原其事件序列；对照 chatStore.reclaimEmptyAssistant 的触发/判定条件，定位逃逸原因（候选：tool_result/进度事件被计为内容、turn_completed 未达回收路径、SSE 顺序差、bubble 由非 turn_started 路径铸出）。

## 第二步（修复）
- 补口逃逸形态；保持一修行为（正常 turn 即时思考指示不受损）；live 与 hydrate 重放一致。
- 工作区：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-55b-empty-bubbles /Users/wenlongwang/Work/BIC/talos/.wt/portal-55b bench-verify`。不碰 bench 主目录、不重启、不 push。

## 二元验收
该 turn 形态（真实 DB 序列做夹具）重放 → 0 空气泡；一修既有测试不回归；全量门禁绿。

## 收尾
逃逸根因 + 修复摘要（sha、测试计数）评论 issue #55，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
