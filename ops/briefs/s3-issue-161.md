# S3 任务：BIC-meta#161 — mock rxn-parse 对非金标输入 echo 派生（消除 mock 档 objective 污染）

你是 S3（实现 + PR，列车口径）。任务书 = BIC-meta#161（读全 issue，含 Facts/建议修复）。

仓：BIC-agent-service，从 origin/main 切工作树 `.wt/issue-161`，分支 `fix/issue-161-mock-rxn-echo`。

## 范围

- `app/data/med005_fixture.py`：mock material-parse 默认分支改为——输入 rxn 含 `>>` 时按 SMILES 拆分 echo 派生材料行（左侧 `.` 分量→substrate（末位若语义上是试剂可全记 substrate，别过度设计）、右侧→product；名称留空/None，**不造假名**，走 #95 chem/LLM 兜底链）；纯文本输入保留现 sketch 分支（既有快照测试续绿）；Sonogashira 金标分支不动。
- rxn-parse 沿用"从 material-parse 派生"（#94 一致性不变式），确认两桶同源后不需独立改。
- goal-confirm 的 mock 分支若按 SMILES 匹配材料行（#27 名称串线问题），确认 echo 行同样走通，必要时同步。
- structure_url 用既有 data-URI 占位函数（#25 模式），不要引入不可达 URL。

## 二元验收

- 具名测试：任意含 `>>` 的非金标 rxn 在 mock 档 parse → 材料行 SMILES 与输入分量一致、名称字段为空、objective 草稿可确认（无 'Equivalents is required' 死锁路径的单测级复现：baseline 自动判定在单 substrate 时生效）。
- 既有 sketch/Sonogashira 快照测试零回归；全量单测绿；ruff/pyright 干净；CI 绿 admin-merge 留痕。
- **不重启台架**（部署归 root）。

## 收尾

PR sha 评论 BIC-meta#161；dispatch done（FACTS/JUDGMENT 分开）。
