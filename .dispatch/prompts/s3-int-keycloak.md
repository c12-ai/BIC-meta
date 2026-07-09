# S3 任务：同事功能集成评审 B — Keycloak 登录（多仓）

你是集成评审员。目标：找到并评审"集成 Keycloak 登录"相关开放 PR（gh pr list -R c12-ai/BIC-agent-service / c12-ai/BIC-agent-portal（必要时 lab），关键词 keycloak/auth/login/sso）。

## 任务
1. Review 代码：正确性、安全形态（token 校验/会话模型 vs 既有 bcrypt 最小 auth）、与 bench-verify 今晚变更的冲突面。
2. 本地集成试跑：工作树合并（.wt/int-kc-*，不动台架不 push）+ 各仓门禁；Keycloak 服务若 PR 带 docker-compose 就本地起一个试跑登录链（自选端口），起不了就静态评审并明说哪些没验证。
3. 报告：可合并性结论、冲突清单、门禁结果、与 Phoenix 批次的合并顺序建议。评论到相应 PR + 汇总评论到 c12-ai/BIC-meta 新 issue「集成评审：Keycloak 登录」。

不合并、不 push、不动台架。收尾 dispatch done（FACTS/Judgment 分开）。
