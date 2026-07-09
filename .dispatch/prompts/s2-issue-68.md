# S2 任务：调查 c12-ai/BIC-meta#68 — RE 末步"结束蒸发"卡死（干净台架复现 + 根因）

你是 S2（调查 + 复现，**不改产码**，结论评论到 issue）。issue #68 正文与 t-verify-r3 findings/01（`/Users/wenlongwang/Work/BIC/V2/BIC-meta/.dispatch/findings/t-verify-r3/`）是任务书。

## 台架纪律
- 共享台架有用户手测：复现前确认 robot idle 且 5 分钟无他人会话活动（DB 只读查 session_events）；满足才可 reset lab（命令见 findings）并复现；不满足就先做纯取证（读 DB/日志/代码），复现窗口等 root 协调。
- 绝不调 :8800/reset；不重启服务；不改代码。

## 要回答
1. 干净复现：新会话走到 RE、执行结束蒸发，卡死是否稳定复现（会话 id + seq 证据）。
2. 卡点定位：robot mock 是否发出 RE 终报（查 mock 日志/MQ）→ lab 是否转发 → BE 是否消费（task_terminal 路由对 RE 的处理）→ RE 结果合成路径。逐环给"到达/未到达"证据。
3. 定级：mock 台架缺口（mock 不发 RE 终报）还是产品缺陷（BE/lab 消费缺失）；给修复建议与落仓。
4. 评论到 issue #68（Facts/Judgment 分开），标签改 stage:已析根因。dispatch done。
