你是 S3 评审+实现角色（架构动作②：状态语义收敛批）。开工前读：
1) BIC-meta/ops/state-semantics-audit-2026-07-09.md（18 存疑点清单 + 语义表终稿）
2) BIC-meta/ops/architecture-memo-2026-07-09.md 第四节
3) ops/agent-improvement-workflow.md（纪律）
分支纪律：portal 在 /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal 从 fix/chat-ux-lang-error-tubeid 新建 refactor/state-semantics；BE 侧若有需改点同样新建同名分支。不 push 不开 PR；Refs BIC-meta#33。
任务：1) 语义表进 spec（BE .trellis/spec 相应节 + portal 契约文档）；2) 18 个存疑点逐点收敛（成功态判定统一到 status==='completed'，桥接点写明语义注释）；3) 每收敛点带测试。#35（jobs.status 幽灵）不做——needs-drake。收尾：#33 comment + dispatch done。

追加输入（验证轮产物）：
- #37：失败终态 live 视图滞后（accept 即刻 DONE、刷新才 FAILED）→ live 事件流/store 终态新鲜度收敛属本批（FormConfirmedEvent 终态化的 live 对应更新），Refs #37 并收尾换标签。
- #24 残余（SSE 渲染层 <think> + 重复渲染，session a332526f）→ portal 渲染增量路径的确定性 sanitize 属本批 portal 侧，Refs #24。
