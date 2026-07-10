你是 S2 调查角色。开工前读 ops/agent-improvement-workflow.md 与 .claude/skills/s2-investigate/SKILL.md（含外部 PR 对账）。
铁律：只读；⚠️DB 都在 talos-postgres:5433；S3 在 BE 工作区跑，以 git HEAD 为准。原始 findings：BIC-meta/.dispatch/findings/t-main/。

任务（批查，三个 issue 分别 comment + 换标签，dispatch done）：
1) **#29** 叙述编造"默认[0.3,0.5]"：验证根因假设（narrate 上下文缺 params_draft 实际值→模型顺 prompt 示例编造）；方案对齐 #16c 宣称不变量机制（真实值投影）。
2) **#30** 表单标签硬编码英文：定位未走 i18n 的组件清单（TLC 表单/物料弹窗），给 translation.json 补齐方案；对账 portal PR#14 与 agent-service PR#66 不重叠。
3) **#31** CC 术语/标签：样品柱 vs sample tube 的叙述来源（prompt 术语表缺失?）+ columnSpecLabel(silica_12g)→"4 g" 的映射 bug 定位（portal label map）。
