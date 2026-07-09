# S3 任务：c12-ai/BIC-meta#139 — 缺料下发失败引导回物料准备（PRD req9）

你是 S3（独立复核 + 实现 + 提交）。issue #139 正文是任务书（根因裸 RuntimeError tools.py:715 → turn.failed.generic/unknown）。仓 BIC-agent-service，从 bench-verify（ca19223+）切 .wt/be-139 开分支 fix/issue-139-material-guidance（不 push/不 PR/不重启）。

## 要点
- 缺 sample_tubes（及同类物料校验失败）→ 类型化异常/display key（走 #106 display 通道），话术中文引导"请到确认按钮左侧的「实验物料」完成样品管选择后重试"（PRD req 9 路由语义；参照 #77 wording 裁定：是"确认按钮左侧"不是"左侧面板"）。
- 排查 tools.py:715 同函数族其他裸 RuntimeError，同类一并类型化（限 dispatch 物料校验域，Rule 3）。
## 二元验收
(1) 缺管下发 E2E：turn.failed display key=物料引导、中文 fallback 含「实验物料」（具名断言）；(2) 物料齐全路径不回归；(3) 全量单测绿。
## 收尾
评论 issue #139，标签 待调查 → 已实现待复测；dispatch done。
