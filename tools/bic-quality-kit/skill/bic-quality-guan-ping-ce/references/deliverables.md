# Deliverable Format

Current phase returns one report: `BIC Quality Brief`.

```text
BIC Quality Brief

Change Set
- 比较基线：
- 变更摘要：
- 变更仓库：
- 是否直接跨仓：

Issue Context
- 发现方式：
- 受影响仓库 Issue 扫描：
- 候选 Issue：
- 候选对应分析：
- 选择依据：
- 关联 Issue：
- 目标：
- 验收项：
- 获取 warning：

Module Mapping
- Repo / Module：
- 文件证据：

Test Correspondence
- 直接相关测试：
- 间接相关测试：
- 可能相关测试：
- 对应依据：

Risk Matrix
| 风险项 | Issue 依据 | Diff 依据 | 测试依据 | 等级 | 判断 |
|---|---|---|---|---|---|
| <dimension or acceptance item> | <issue fact> | <changed file/object> | <test fact or missing evidence> | high/medium/low/unassessed | <reason> |
- 整体风险：
- 评估阶段：真正测试前（pre-test）

Missing Tests
- 建议新增测试：
- 建议完善测试：
- 暂未发现明显缺口：

说明：本次仅做静态分析，未执行测试；静态对应关系不代表测试已通过。
```

Repeat module and test evidence for every affected repository/module. Keep the
brief concise:

- Do not print `mapping_source`; it is raw diagnostic metadata. If the module is
  unmapped, write `功能模块：暂未识别` and cite the changed files.
- Keep direct, indirect, and possible relations in their own fields. Cite the
  concrete import, call, reference, scenario, assertion, disabled state, or
  explicit relation that produced each conclusion.
- Possible candidates remain visible search clues but never count as proof that
  a changed behavior has an existing test.
- Start the Risk Matrix with the deterministic rows from
  `assess-risk-matrix.sh`. Add one Issue-alignment row per acceptance item using
  semantic reading of Issue, Diff, and tests. Missing Diff or test evidence may
  raise the risk; never lower the deterministic risk floor.
- Use `unassessed` when Issue context is missing/unresolved or an acceptance item
  cannot be compared with concrete evidence. This is a pre-test matrix, not a
  claim about executed verification or residual release risk.
- Collect open Issue candidates only from repositories identified by the Diff.
  Prefer strong links from the current PR, PR closing text, Diff commits, or an
  `issue-123` branch. Without a strong link, compare repository candidates with
  modules and changed objects, then read only plausible Issue bodies. Show why
  candidates do or do not correspond. Leave risk `unassessed` when more than one
  candidate remains plausible; do not infer identity from repository membership,
  a general keyword, or filename similarity alone.
- Do not recommend tests for pure documentation or planning records unless the
  repository defines an executable documentation contract.
- Do not emit confidence, priority, evidence-type, coverage-percentage,
  `mapping_source`, or a next-step recommendation. State the static-analysis
  limitation once, at the end.
