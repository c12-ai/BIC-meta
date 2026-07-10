# S3 任务：c12-ai/BIC-meta#121 — CC 分析失败 fail-loud（P0）

你是 S3（独立复核 + 实现 + 提交）。issue #121 正文是任务书（捕获证据 225747_540 对，路径 /private/tmp/claude-501/-Users-wenlongwang-Work-BIC-V2-BIC-meta/35cf69d6-ff07-47fb-abee-88cbc6eba2f9/scratchpad/mind_capture/）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（66e9a99）切工作树 .wt/be-121 开分支 fix/issue-121-cc-analysis-fail-loud（不 push/不 PR/不重启）。

## 要点
- 断点：#112 调查标注的 D16 降级链 tools.py:1130-1133 + 1044-1078；下游哪句 narrate 产出「过柱分析已完成」也要定位并按失败分支改写。
- 对照 TLC 识别失败是怎么 fail-loud 的（#91/#98 时代那些 500 是透出的），同构不造新形；话术走既有 display/失败卡模式。
- 复现会话 82479c08（DB 佐证）。并行 child .wt/be-119 在修 presign（同区 tools.py CC 路径！）——你只动失败分支/narrate，别碰 pic_urls 构造与 presign；冲突 root 兜底。
- 注意 bench-verify 带 #115 TEMP shared-types 覆盖，别动依赖。

## 二元验收
issue #121 三条照抄执行，每条具名测试。全量 `uv run pytest tests/unit -m 'not real_llm'` 绿。

## 收尾
修复摘要评论 issue #121，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
