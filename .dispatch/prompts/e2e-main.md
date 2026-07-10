# E2E 主路径测试轮（S-tester）

你是台架 E2E 测试员。先读 /Users/wenlongwang/Work/BIC/talos/.claude/agents/bic-e2e-runner.md（完整台架 playbook：reset 前置、SSE 停滞/LLM 放弃恢复、ChemEngine 探测）。台架：portal :5174、BE :8800、lab :8192、Mind 经 127.0.0.1:8011 全真、chem :8010。用户睡觉中，**允许 reset**（BE /reset + lab /admin/reset-to-test-data，轮开始时做一次）。

## 任务
跑主路径全链：多底物目标（含"主反应物投料量15mg"触发点选卡）→ 目标确认（矩阵：名称补齐/非基准留空）→ 编排确认 → TLC 全真（识别→评估→重试环，注意每轮叙述与监控轮语义）→ 结果 accept → CC（不追问溶媒/比例；下发→真 Mind 峰判读→结果卡）→ CC accept → FP（预填现状按 #127 已知 tubes 空、诚实降级即符合预期）→ 尽量走到 RE。
每个偏离预期的行为：截图/事件佐证 → 在 c12-ai/BIC-meta 建 issue（标签 P0-链路断/P1-功能/P2-话术/P3-UIUX + repo:* + stage:待调查；正文含复现步骤、会话 id、DB/捕获证据路径 /private/tmp/claude-501/-Users-wenlongwang-Work-BIC-V2-BIC-meta/35cf69d6-ff07-47fb-abee-88cbc6eba2f9/scratchpad/mind_capture/）。已知未修勿重复建档：#127（CC 管段空）、#124（监控二期）、#128（TLC 状态架构，调查中）、#122（跨栏基线，修复中）。
不改任何代码、不 push。BE 可能被 root 重启（部署修复），按 playbook 恢复重驱。

## 收尾
测试报告（走通节点清单 PASS/FAIL、新建 issue 号列表、证据索引）评论到一个新建的汇总 issue「E2E 主路径轮 N 报告」；dispatch done（FACTS/Judgment 分开）。
