# S3 任务：实现 c12-ai/BIC-meta#77 — ELN 下载按钮只在最终实验结果面显示

你是 S3（独立复核 + 实现 + 提交）。issue #77 正文是任务书。先复核下载按钮当前挂载点与门控来源，复核结论评论 issue，再实现。

## 工作区纪律
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-77-eln-visibility /Users/wenlongwang/Work/BIC/talos/.wt/portal-77 bench-verify`。
- 不碰 bench 主目录、不重启、不 push、不开 PR。纯 FE 可见性改动，BE 409 门一行不动。
- 并行提示：s3-issue-76 在改同一结果面板的展开/滚动（fix/issue-76-result-collapse）——大概率同文件！先看其分支已有改动（git -C .../.wt/portal-76 diff bench-verify --stat），错开 hunk 并评论对齐；无法错开则 dispatch ask 请示 root 排序。

## 二元验收
issue #77 四条照抄执行写成测试。全量门禁绿。

## 收尾
复核结论 + 修复摘要（sha、测试计数）评论 issue #77，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
