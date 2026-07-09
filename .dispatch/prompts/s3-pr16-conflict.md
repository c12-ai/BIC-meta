# S3 任务：解决 BIC-agent-portal PR#16 的冲突，review 并更新 PR

你是外部 PR 协助 session（先例：s3-pr66-conflict 对 BE PR#66 的处理）。用户已明确授权：**解决冲突、push 到同事的 PR 分支、更新 PR（评论）**。

## 对象
- 仓库：`/Users/wenlongwang/Work/BIC/talos/BIC-agent-portal`（注意：主目录 checkout 在 bench-verify 分支、用户正在手测——**绝不触碰主目录工作区、绝不重启服务**）
- PR：#16 "Complete Chinese localization coverage"，分支 `origin/feat/display-name-i18n-ui`（yanbowang）
- 先 `gh pr view 16 --json mergeable,mergeStateStatus,baseRefName` 确认冲突现状与 base。

## 工作流程
1. 自建 worktree：`git worktree add /Users/wenlongwang/Work/BIC/talos/.wt/portal-pr16 -b pr16-conflict-resolve origin/feat/display-name-i18n-ui`（基于 PR 分支）。
2. `git merge origin/main`（用 merge 不用 rebase——不重写同事历史），逐冲突做**语义并集**：保双方意图，逐处记录决策理由。
3. 门禁（worktree 内）：`pnpm install`（CI=true 若要求 TTY）→ `pnpm vitest run` 全绿 → `tsc -b --noEmit` 0 error → biome 对改动文件干净（全仓有 ~45 个既有基线错误，不要求清零，要求增量为 0）。
4. Review（用户点名要求）：读 PR 的实质内容（i18n 覆盖 + `agent-client.ts` 的 locale 发送线），按正常 code review 标准给意见——尤其检查：
   - `currentLocale()` 的归一化（i18n 语言可能是 `zh-CN` 形态，BE 只收 `^(en|zh)$`，不匹配会被 422 或忽略——验证映射正确）；
   - locale 是否覆盖了三个 BE 端点（message / form confirm / decision）；
   - 翻译文件与 en 的 key 齐全性（repo 里有 translation-parity guard 测试，跑它）。
5. push：`git push origin pr16-conflict-resolve:feat/display-name-i18n-ui`（先确认 fast-forward 性质；若期间同事又推了新提交，fetch 重做，不 force-push）。
6. PR 评论：逐冲突决策清单 + review 意见 + 门禁输出摘要，署名注明 Wenlong 侧协助。

## 背景（review 时须知）
- BE 侧 #66 已合并 main；bench-verify 上另有 S1 热修 commit `0014961`（BIC-meta#50 三态：显式 zh/en 钉死语言，**未发送 locale → 跟随用户输入语言**）。PR#16 的 FE 发送线是三态的第一档，两者兼容——review 时确认 PR 不与该语义冲突（如 PR 若把缺省硬编码为 'en' 发送，会把兜底档饿死——那样应建议改为发送真实 UI locale）。
- BIC-meta#30 在等这个 PR 合并，你的评论里可以 ref。

## 纪律
- 不 merge PR（合并权在同事/Drake）；只解冲突 + push + 评论。
- 全程不碰 bench 主目录、不重启、不写 DB。
- `dispatch done` 汇报：FACTS（冲突数与决策、门禁输出、push 结果 sha、PR 评论链接）与 Judgment 分开。
