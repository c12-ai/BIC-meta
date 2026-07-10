# E2E 挑战路径测试轮（S-tester）

你是台架 E2E 测试员。先读 /Users/wenlongwang/Work/BIC/talos/.claude/agents/bic-e2e-runner.md（台架 playbook）。台架：portal :5174、BE :8800、lab :8192、Mind 全真（经 :8011 捕获代理）。用户睡觉中，**允许 reset**（轮开始一次：BE /reset + lab /admin/reset-to-test-data）。方法学参照上一轮（#134 报告）：SSE 长连页 executeScript 等不到 document_idle，以 API 契约 + wire 事件 + Mind 捕获为主证据。

## 任务：挑战/异常路径（主路径轮 #134 已覆盖 happy+失败链，勿重复）
1. 异常输入：乱码/超长文本/非化学请求/空消息/纯 emoji → agent 应礼貌拒答或澄清，不崩轮。
2. 中途改需求：目标确认后要求改反应式/改窗口 → 状态一致性（草稿/表单/矩阵同步，无幽灵旧值）。
3. 拒绝路径：plan 拒绝（#63 已知话术弱，验证不崩即可）、表单反复改后再确认、点选卡不点改打字回答。
4. 重复/乱序操作：重复点确认、对已 accept 的结果再 accept、旧表单重提交（should 409/幂等）。
5. 失败注入：TLC 下发时物料不齐（清库存造缺）→ 预检拦截与引导（PRD 要求 9）；Mind 暂不可达（可短暂 kill :8011 捕获代理再拉起，注意恢复）→ fail-loud 中文、无静默。
6. 会话级：同实验双窗口并发操作、刷新后状态重建一致（#110/#102 已修，回归确认）。

每个偏离预期：证据（wire/DB/捕获）→ c12-ai/BIC-meta 建 issue（P0-链路断/P1-功能/P2-话术/P3-UIUX + repo:* + stage:待调查）。已知未修勿重复：#127/#124/#128/#132/#136/#103(二轮中)/#126(待复测)。BE 可能被 root 重启，按 playbook 恢复。

## 收尾
汇总报告 → 新建 issue「E2E 挑战路径轮 1 报告」；dispatch done（FACTS/Judgment 分开）。
