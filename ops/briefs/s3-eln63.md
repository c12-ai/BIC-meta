# S3 任务：BIC-agent-service#63 对账 + 用户实测'反应式为空'根因修复

你是 S3（先对账后修，列车口径）。触发：用户 2026-07-11 实测下载 ELN 报告，**化学反应式仍为空**——尽管 eln183（BE#103→45c9886）声称反应图早已接线（#35/#75）并修了并行拉取。任务书 = BE#63（**读全部 7 条评论**——那里有报告目标字段清单/checklist）+ meta#183 台账 + #55 degrade 契约。

仓：BIC-agent-service，从 origin/main（≥89ac2bc）切工作树 `.wt/eln63`，分支 `fix/issue-63-eln-checklist`。
并行知会：s3-be212（话术）、s3-be216（rollup）同仓不同面；无交集预期，撞了 dispatch send 协调。

## A. 反应式为空的根因（先查，结论评论 #63）

用台架真实会话对账（bic-postgres:5432 talos_agent_db 只读 + BE 日志）：用户刚下载的报告，反应式空的路径是哪种——
1. 会话根本没有 rendered_rxn_url（goal-confirm/rxn-parse 响应未存或字段没落库）；
2. URL 在但拉取失败被 degrade 吞掉（presigned 过期？wait_for 超时墙太紧？trust_env 之外的网络因素？）——检查 #183 的 WARN 日志有没有留痕（若失败静默无日志，那本身违反可诊断性，一并修：degrade 仍静默但**必须留 WARN**）；
3. 模板有槽但装配漏了。
按根因修：过期就在生成时重签/即取即用；超时就调参+并发已有；没落库就补链路。

## B. #63 checklist 全量对账

逐条核对 #63 评论里的目标字段清单 vs 当前报告实际输出（生成一份真报告核验）：已实现打勾、缺失的修（可得数据）或标注 absent-by-design（不可得，引 #55 契约）；对账表评论 #63。与 #183 的字段盘点合并视角，别重复造表。

## 二元验收

- 台架同条件重下报告：反应式图在场（或若数据真缺，#63 评论给出确切缺失链路与上游责任方）；
- #63 checklist 对账表落 issue；新增/修复项有具名测试（含'拉取失败必留 WARN'负向断言）；
- 全量 pytest + CI 绿 admin-merge 留痕。**不重启台架**（部署归 root）。

## 收尾

根因 + 对账表 + PR sha 评论 #63；dispatch done（FACTS/JUDGMENT 分开）。
