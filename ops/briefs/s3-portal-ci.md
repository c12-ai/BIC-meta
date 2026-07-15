# S3 任务：BIC-meta#144 — BIC-agent-portal 仓级 CI 落地

你是 S3（实现 + PR，列车口径）。任务书 = BIC-meta#144（读全 issue 与评论）。

仓：BIC-agent-portal，从 origin/main 切工作树 `.wt/portal-ci`，分支 `ci/issue-144-portal-ci`。

## 范围

- GitHub Actions workflow（push main + PR）：pnpm install（frozen-lockfile, 带 pnpm cache）→ typecheck → lint → vitest 全量 → build。四 gate 分 job 或分 step 皆可，取跑得快且失败定位清晰的结构。
- Playwright E2E **不进** 本次 CI（需要活台架，#160 已裁定 quiescence 工程化待后续；workflow 里留注释注明）。
- node/pnpm 版本对齐仓内 volta/packageManager/engines 现有声明；没有就按本地实测版本固定（node 22 / pnpm 11.9）。
- 参考 BIC-agent-service 的 CI 命名口径（ci / lint 等），保持 check 名稳定可被分支保护引用。

## 二元验收

- PR 自身四 gate 全绿（这就是 CI 的自证）；故意引入一处 lint 破坏的验证 commit 证明会红、再修复（留痕在 PR 历史或描述截图）。
- 合并后 main 上触发一次全绿 run。admin-merge 留痕。
- **不重启台架**。

## 收尾

PR sha + main run 链接评论 BIC-meta#144；dispatch done（FACTS/JUDGMENT 分开）。
