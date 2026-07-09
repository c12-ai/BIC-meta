# S3 任务：实现 c12-ai/BIC-meta#70 — 首页清理六项（用户逐项裁定）

你是 S3（独立复核 + 实现 + 提交）。issue #70 正文是任务书（六项裁定 + 六条验收），先复核落点（首页/布局/composer/侧栏组件、devtools 挂载点、主题基建有无），复核结论评论到 issue，再实现。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-70-homepage /Users/wenlongwang/Work/BIC/talos/.wt/portal-70 bench-verify`。
- 绝不碰 bench 主目录（用户在测）、不重启、不 push、不开 PR。
- 六项分组提交（调试组件+菜单 disable 一个 commit；主题切换一个；文案+输入说明一个；快速开始一个——或按实际耦合合理分组，每 commit 门禁绿）。
- 主题项（3）如工程量超预期（无任何主题基建且暗色需全面调色），先落"图标+切换+主表面调色"，边角问题列清单评论到 issue 交 root 决定是否追加 polish issue——不许烂尾也不许无限膨胀。
- 快速开始模板（6）的中文参考文本在 issue 里；en 版自拟等价模板；点击=填入输入框。

## 二元验收
issue #70 六条照抄执行写成测试（2/3/6 有组件测试）。全量 pnpm vitest run + tsc + 增量 biome + translation-parity 绿。

## 收尾
复核结论 + 修复摘要（sha 列表、测试计数）评论 issue #70，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
