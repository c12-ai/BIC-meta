# S3 任务：c12-ai/BIC-meta#115 lab 侧 — CC 任务照片透传

你是 S3（独立复核 + 实现 + 提交）。issue #115 正文是任务书（lab 侧那半）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-lab-service，从 bench-verify 切工作树 .wt/lab-115 开分支 fix/issue-115-cc-image-passthrough（不 push/不 PR/不重启）。

## 要点
- 断点 task_service.py:648-656（TLC-only captured-images 透传）。先读 TLC 怎么带图（载荷字段、来源、时机），CC 终步（start_column_chromatography 的终条 SkillResult.images）用同一形态透传。
- **若需改 bic_shared_types schema → 停下 dispatch ask root**，不得擅自改。
- mock 侧上报形态见 mars_interface_mock feat/issue-112-cc-photos@3eb7874（images: [{work_station, camera, url: "minio/...", create_time}]）。

## 二元验收
issue #115 lab 侧两条：CC E2E 消息载荷断言（两 minio/ 键在场）+ TLC 不回归；仓门禁绿（lint/test 按仓惯例整链）。

## 收尾
修复摘要评论 issue #115（注明 lab 侧完成），dispatch done（FACTS/Judgment 分开）。
