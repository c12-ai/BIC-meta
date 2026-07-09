# S3 任务：c12-ai/BIC-meta#107 — mixcase observed_rf 规范形 SMILES（P0）

你是 S3（独立复核 + 实现 + 提交）。issue #107 正文是任务书（含捕获证据路径与规范形对照）。仓：/Users/wenlongwang/Work/BIC/talos/BIC-agent-service，从 bench-verify（e5c5a12+）切工作树 .wt/be-107 开分支 fix/issue-107-canonical-mixcase-key（不 push/不 PR/不重启）。

## 要点
- 捕获件：/private/tmp/claude-501/-Users-wenlongwang-Work-BIC-V2-BIC-meta/35cf69d6-ff07-47fb-abee-88cbc6eba2f9/scratchpad/mind_capture/ 下 200619_830（500 对）、200502_989（200 对）、200254_084（rxn-parse 规范形）。
- 规范形来源优先用 #94 落的 rxn-parse 契约（rxn_parse_contract.py）；注意 #102（.wt/be-102，动 clarify/基线）与 #103（.wt/be-103，动补名）在同区域——你只动 mixcase trials 构造路径。
- 真 Mind 热验证可走台架捕获代理 127.0.0.1:8011（等价 192.168.12.104:8002）；一次即可，测试用 fake。
- 透出治理按 issue 任务 3：先看 #106 调查（进行中）是否已给统一挂点，有就登记引用。

## 二元验收
issue #107 四条照抄执行，每条具名测试/验证记录。全量 `uv run pytest tests/unit -m 'not real_llm'` 绿（#101 已知闪失单跑复核）。

## 收尾
修复摘要评论 issue #107，标签 stage:待调查 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
