# S3 任务：实施 c12-ai/BIC-meta#80 — 面向用户场景禁用内部简写（统一用户可见名词表）

你是 S3（audit + 独立复核 + 实现 + 提交）。issue #80 正文是任务书（词表 + 范围 + 四条验收）。

## 工作区纪律
- BE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-80-formal-names /Users/wenlongwang/Work/BIC/talos/.wt/be-80 bench-verify`
- FE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-80-formal-names /Users/wenlongwang/Work/BIC/talos/.wt/portal-80 bench-verify`
- 不碰 bench 主目录、不重启、不 push、不开 PR。BE 单测 `-m 'not real_llm'`。
- **与 #74 合流**：s3-issue-74 在做控件名词表（fix/issue-74-control-name-locale）——先看其分支进展（git -C .../.wt/be-74 log/diff），把步骤名与控件名做进**同一个**用户可见名词表模块（谁先落谁定骨架，后者扩展；评论互相对齐，绝不两套）。若 #74 已近完工，可基于其分支续做。
- 三层同构（对齐 #54 状态词表先例）：词表单一来源 + prompt 规则注入 + text_done 出口 scrub（zh 正文裸简写→正式名替换，en 括注白名单）。
- FE audit：全仓 grep 用户可见文案里的简写（页签/表单/卡片/图例/提示），清单评论 issue 后统一改 i18n 键。

## 二元验收
issue #80 四条照抄执行写成测试。两仓全量门禁绿。

## 收尾
audit 清单 + 修复摘要（两仓 sha、测试计数）评论 issue #80，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
