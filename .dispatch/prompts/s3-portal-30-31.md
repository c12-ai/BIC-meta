你是 S3 评审+实现角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s3-resolve/SKILL.md（含「外部 PR 对账」——先扫 portal open PR，已知 PR#14 与你无文件交集，仍需复核）。
硬性纪律：独立复核 S2 结论；不 push 不开 PR；改行为同步改测试写 WHY、测试全绿才提交；commit 按内容拆、Refs c12-ai/BIC-meta#<N>、footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；收尾 comment+标签换 stage:已实现待复测+dispatch done。
⚠️前端链：只动 /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal @ fix/chat-ux-lang-error-tubeid。⚠️本地保留不提交：tests/helpers.ts、cc-re-chained-flow.spec.ts 的 baseURL 行。

任务（先 gh issue view 30 31 --repo c12-ai/BIC-meta --comments 全量）：
1) **#30**：按 S2 的组件清单把 TLC 表单/物料弹窗硬编码英文标签接入 translation.json（zh 补齐），过 i18n parity 测试。
2) **#31 part-2（仅 portal 件）**：columnSpecLabel 映射修正 silica_12g→'12 g'、24g→'24 g'、40g→'40 g' + 映射单测；commit 注明"Column Specification=柱规格克数"待 Drake 一句确认；silicaAmount 语义疑点只在 #31 comment 记录，不改。part-1（agent-service 术语锚点）不在你范围。
