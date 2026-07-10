你是 S3 评审+实现角色（架构动作①：narrate 契约清扫）。开工前读：
1) BIC-agent-service/.trellis/spec/backend/L3/narrate-contract.md（契约全文，你的验收基准）
2) BIC-meta/ops/architecture-memo-2026-07-09.md 第三节
3) ops/agent-improvement-workflow.md（纪律；含外部 PR 对账）
分支纪律：在 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service 从 fix/chat-ux-lang-error-tubeid **新建 refactor/narrate-contract 分支**实现；不 push 不开 PR；commit 按出口分组、Refs BIC-meta#33、footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT。
任务：按契约把全部叙述出口归类 T/S/F 并收编（objective/plan/tlc/cc/fp/re/query 每个 narrate 出口）：出口清单先行（comment 到 #33 存档）；T 类转纯模板；S 类补状态骨架+一致性校验；F 类仅限闲聊问答。每出口补"叙述-状态对账"单测（Rule 7）。⚠️BE bench 正以 fix 分支运行——你在新分支工作不影响运行时。收尾：#33 comment 摘要 + dispatch done。

追加输入（验证轮产物，一并处理）：
- #36：CC auto-proceed 过渡叙述失实（dfe08ab 引入的新出口漏契约）→ 按契约归 T 类纯模板，Refs #36 并收尾换标签。
- #22 残余：规范设备问法回落 collecting_objective 人设（意图路由层，session 50791d85/9e1b19f1）→ 路由触发词修复归本批，Refs #22。
- #24 残余（SSE 渲染层 <think>）不在你范围（portal 渲染路径），只在 #24 comment 标注 BE 侧已尽。
