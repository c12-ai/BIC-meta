# S3 任务：#128 阶段1 · LAB-1 — lab 轮/op 上 wire

你是 S3（实现 + PR，列车授权口径）。任务书 = #128 交付物 5 的 LAB-1 行 + ST-1 已落契约（shared-types main 45032c9：TaskStatusMsgPayload step/event 带 round_index、op_id/op_name）。仓：BIC-lab-service，从 origin/main（56c0b43）切工作树 .wt/lab-128 开分支 feat/issue-128-lab1-round-op-wire。

## 范围（照交付物 5）
①repin shared-types → 45032c9；②发布 round_index（现算逻辑 task_service.py:743-745 落到 payload）；③op 级步骤进 step_events（现只进内部 event_logs audit——#123 二期 D/F 的正主）。lab 自身状态机不动。TLC 之外的任务类型 round_index 语义（单轮=1）写清。

## 二元验收
CC/TLC E2E 消息载荷断言：TLC 每轮 step 带正确 round_index、op 级事件在 step_events 出现（具名各一）；既有 #115 pic_urls 透传不回归；full pytest 绿；CI 绿合并（admin-merge 留痕）。**不动台架运行态**（部署由 root 在 Playwright 收官后的统一同步窗口做）。

## 收尾
sha 评论 #128（注明 LAB-1 完成、FE 消费面待 BE-1/FE-1）；dispatch done（FACTS/Judgment 分开）。
