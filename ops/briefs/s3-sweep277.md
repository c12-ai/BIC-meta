# S3 任务：c12-ai/BIC-meta open issues 全量清理整理（三态口径）

你是 S3（issue 台账清理，列车口径）。用户指示（2026-07-11 晚）：『过一遍 issues，清理整理一下』。

范围：c12-ai/BIC-meta 全部 open issues（当前 ~60+）。逐个按三态处置：

1. **可关**：修复已合 main 且有部署/验证留痕（用内容核验：squash 正文 issue 号 + 具名测试在 main；deployment 佐证在今日台账评论）→ 评论关闭依据后 close。注意：**验收权在提出人的（stage:已实现待复测 且提出人=Wenlong）不代关**，改评论『待 Wenlong 复测』并标注今日部署 sha；例外：Wenlong 今日已在对话/操作中实质确认的（如 #266 实弹 PASS 他知情、#242 他明示接受关闭路径）可关。
2. **仍开有效**：更新状态评论（当前依赖什么：外部方/Drake 任务/backlog 优先级），补/正标签（stage:*、external、backlog）。
3. **过时/被取代**：写明被哪个决定/重设计取代（如 item-card 重设计 supersede 的面），评论后 close。

特别核对今日大批量档：#192-#277 区间基本都有当日动态；老区间（<#192）对照当前 main 与 PRD 现实逐个判。产出：清理汇总表（关闭 N / 待复测 M / 外部 K / backlog J，各含 issue 号）评论到一个新的台账 issue（标题『issue 清理 2026-07-11 晚』）并 dispatch done 引用。

纪律：只动 c12-ai/BIC-meta 的 issue（评论/标签/关闭）；**不动代码不动 PR**；拿不准的留 open 并列入汇总表『待 root 裁定』节。done 用单行短摘要+核退出码。
