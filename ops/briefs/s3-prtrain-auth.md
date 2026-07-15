# S3 任务：PR-train A 组 — lab 身份验证三部曲跨仓联审（service#97 + portal#36 + lab#112）

你是 PR review+update 会话。三 PR 同属 Shion 的 lab auth hardening 系列（B/C/D，lab#112 自标 merge LAST），**作为整体联审**。

## 合并纪律（用户 2026-07-11 裁定，严格执行）

- **三个 PR 的 reviewRequests 均为 0 → 一律不合并**。产出 = review 评论（分级 BLOCKER/建议/nit）+ 冲突时帮助更新分支 + 联审总结论。
- 更新同事分支：禁 force-push（merge origin/main + 叠加 commit）；开工 fetch 确认无新推进；commit message 说明动机。

## 联审要点

1. **系列完整性**：找 PR-A（shared-types 或已合部分？读三 PR 描述互引），确认合并顺序依赖（B→C→D？D 标 merge LAST 的原因）；缺失环节标注。
2. **与现 main 的鸿沟**：这些分支的基点 vs 今晚的大量合并（BE 48c7579+、portal b4ceea3+、lab 624e4e5）；mergeable=UNKNOWN 的实际冲突面跑 merge-tree 实测。
3. **与已上线 Keycloak 栈的一致性**：台架现状 = BE 只收 Bearer JWT（issuer :18080）、portal react-oidc-context、up.sh seed。三 PR 的 service-account/Bearer 透传/lab JWT 校验与现状是补全还是重复/冲突（例如 BE→lab 调用现在是什么鉴权？一手核）。CORS allowlist 与 portal 端口口径（5173）对齐。
4. 安全面：token 获取/缓存/刷新路径、secret 落盘、日志泄漏（参照 #195 P2-1 教训）。
5. 冲突则更新分支到可合状态（CI 绿 + MERGEABLE），但**停在合并前**。

## 收尾

三 PR 各发 review 评论；联审总结论（合并顺序建议 + 是否 ready + 缺什么）评论到 lab#112（系列尾） + dispatch done 给 root（FACTS/JUDGMENT 分开）。
