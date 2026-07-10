# S3 任务：实施 c12-ai/BIC-meta#75 — 样品柱配置统一收归物料面板（用户裁定）

你是 S3（独立复核 + 实现 + 提交）。issue #75 的 S2 查证结论 + 最新裁定评论是任务书。

## 裁定要点
1. CC 表单的样品柱字段**整体移除**（不留只读展示）；物料面板为唯一配置/展示面。BE 载荷兼容不变（sample_cartridge_location 继续由面板写入）。
2. 随同实施：**CC 派发前活体库存门**（对齐 TLC #19 先例——_submit_l4 cc 臂在 POST 前对选定样品柱做活体复检，失败走同款 submit_l4 FAILED 契约+返回物料面板指引，lab 读错误 fail-open）。
3. 迁移 S2 点名的 4 个依赖下拉的 e2e 用例（改走面板路径；bench-local 适配文件仍不入库）。

## 工作区纪律
- FE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-portal worktree add -b fix/issue-75-single-surface /Users/wenlongwang/Work/BIC/talos/.wt/portal-75 bench-verify`
- BE：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add -b fix/issue-75-cc-live-gate /Users/wenlongwang/Work/BIC/talos/.wt/be-75 bench-verify`
- 不碰 bench 主目录、不重启、不 push、不开 PR。BE 单测 `-m 'not real_llm'`。spec 同变更集更新（Rule 10：specialist_tools.md 的 CC 派发段）。
- 并行提示：BE 在飞 #73/#74；FE 在飞 #76/#77/#78/#79——CC 表单域与它们应不相交，撞则评论对齐。

## 二元验收
(1) CC 表单无样品柱字段；物料面板选择→确认→派发全链通（表单 presence gate 相应调整不误伤）；(2) CC 派发前活体门：注入"占用/幽灵柱"状态的集成测试→submit 拒绝并给面板指引；lab 读错误 fail-open；(3) 4 个 e2e 迁移后绿（本地跑标注 skip 数照报）；(4) 两仓全量门禁绿。

## 收尾
复核结论 + 修复摘要（两仓 sha、测试计数）评论 issue #75，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
