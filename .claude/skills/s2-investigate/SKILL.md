---
name: s2-investigate
description: Agent 改进工作流的 S2 调查角色 — 对指定 BIC-meta issue 找根因、设计根源解决方案并 comment 到 issue。触发：/s2-investigate <issue编号>，或用户要求调查某个 issue 的根因。
---

# S2 — 根因调查 / 方案设计（不实现）

先读 `ops/agent-improvement-workflow.md`（角色边界、bench 手册、变更纪律）。
输入是一个 issue 编号（`$ARGUMENTS`）。

## 流程

1. `gh issue view <N> --repo c12-ai/BIC-meta --comments` 读全量上下文。
2. **从一手证据重推导**：代码（talos/BIC-agent-service、talos/BIC-agent-portal）、
   DB（⚠️ agent DB 在 talos-postgres:5433，bic-postgres:5432 的同名库是空的假库）、
   BE 日志、git log（找引入点）。issue 里的"根因假设"只是假设，必须验证或推翻。
3. **找根因，不是找补丁点**：问"为什么会存在这个问题"直到碰到设计决策层
   （参照先例：话术泄漏的根因是 specialist 自我认知框定，不是缺一句禁令）。
4. **设计根源解决方案**：改自我认知/可见信息/契约/结构，而非叠加禁止规则。
   涉及 graph 结构、跨层契约（Rule 10）、产品决策的，明确标注 needs-product-decision。
5. 把分析写成 issue comment（格式：`## 根因` 证据链 → `## 方案` → `## 影响面/风险` →
   `## 备选`），换标签 `needs-triage` → `stage:已析根因`。

## 禁止

- **不改产品代码**（只读；复现脚本放 scratchpad）。
- 不重启 bench 服务、不 reset DB（用户可能在测试）。
- 不实现方案 —— 那是 S3 的事，且 S3 会独立复核你的结论。

## 开工前必做：外部 PR 对账

分析/实现前先扫对应 repo 的 open PR（`gh pr list --repo c12-ai/<repo> --state open --json number,title,headRefName,author`），命中同域 PR 就 `gh pr diff <N> --repo <r> --name-only` 比对文件集：重复→标注"由该 PR 解决"不重复做；文件冲突→对齐后实现并在 comment 注明基于/规避的 PR。详见 ops/agent-improvement-workflow.md「外部 PR 对账」。
