# S3 任务：c12-ai/BIC-meta#115 BE 侧 — CC captured images 入 trials.result

你是 S3（独立复核 + 实现 + 提交）。issue #115 正文是任务书（BE 侧那半）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（87d33d9）切工作树 .wt/be-115 开分支 fix/issue-115-cc-images-ingest（不 push/不 PR/不重启）。

## 要点
- 断点 event_ingress.py:244,250（trials.result={steps} 无 images）；读取点 tools.py:897-906 `_extract_pic_urls`。对齐 TLC 既有的 captured-images 写入形态（先读 TLC 是怎么落 trials.result 的）。
- lab 侧 child 在并行改透传（.wt/lab-115）；两侧以 TLC 既有载荷形态为共同契约，别发明新形状。**若需改 bic_shared_types → 停下 dispatch ask root。**
- 并行 child .wt/be-110 动 SSE 下发层——你只动 ingress 写库与 CC 取图路径，无重叠。

## 二元验收
issue #115 BE 侧：注入含 images 的 CC 状态消息 → trials.result 含图 → _extract_pic_urls 返回两键（具名测试）；TLC 路径不回归；全量 `uv run pytest tests/unit -m 'not real_llm'` 绿。

## 收尾
修复摘要评论 issue #115（注明 BE 侧完成），dispatch done（FACTS/Judgment 分开）。
