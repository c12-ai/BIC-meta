# Deliverable Format

Current phase returns one report: `BIC 质量简报`.

```text
BIC 质量简报

核心结论
- 影响范围：<affected repositories, core modules, and change size>
- 跨仓判断：<single/multi-repository; whether the changes form one direct business or contract chain>
- Issue 对齐：<repository -> selected Issue, unresolved, or no unique Issue>
- 测试判断：<strongest existing test evidence and the key behavior gaps>
- 风险结论：<pre-test risk per independent change stream; do not hide an assessed stream behind an unrelated unassessed stream>

变更集
- 比较基线：
- 变更摘要：
- 变更仓库：
- 是否直接跨仓：

需求与问题单
- 发现方式：
- 受影响仓库 Issue 扫描：
- 候选初筛：
- 初筛排除：
- 正文读取：
- 候选 Issue：
- 候选对应分析：
- 选择依据：
- 关联 Issue：
- 目标：
- 验收项：
- 获取 warning：

模块映射
- Repo / Module：
- 文件证据：

测试对应性
- 直接相关测试：
- 间接相关测试：
- 可能相关测试：
- 对应依据：

测试前风险矩阵
| 风险项 | Issue 依据 | Diff 依据 | 测试依据 | 等级 | 判断 |
|---|---|---|---|---|---|
| <dimension or acceptance item> | <issue fact> | <changed file/object> | <test fact or missing evidence> | high/medium/low/unassessed | <reason> |
- 整体风险：
- 评估阶段：真正测试前（pre-test）

测试缺口
- 建议新增测试：
- 建议完善测试：
- 暂未发现明显缺口：

说明：本次仅做静态分析，未执行测试；静态对应关系不代表测试已通过。
```

Repeat module and test evidence for every affected repository/module. Keep the
brief concise:

- Write `核心结论` first as a three-to-five-bullet executive summary. Derive every
  statement from evidence repeated in the detailed sections; do not introduce a
  new conclusion, label, or recommendation there. Name affected repositories and
  core modules, distinguish a multi-repository change set from one direct
  business/contract chain, summarize Issue alignment and the strongest existing
  test evidence plus key gaps, and state pre-test risk per independent change
  stream. When one stream is assessed and another is unresolved, show both
  statuses instead of replacing the assessed result with one ambiguous workspace
  verdict.
- Do not print `mapping_source`; it is raw diagnostic metadata. If the module is
  unmapped, write `功能模块：暂未识别` and cite the changed files.
- Keep direct, indirect, and possible relations in their own fields. Cite the
  concrete import, call, reference, scenario, assertion, disabled state, or
  explicit relation that produced each conclusion.
- Possible candidates remain visible search clues but never count as proof that
  a changed behavior has an existing test.
- Start `测试前风险矩阵` with the deterministic rows from
  `assess-risk-matrix.sh`. Add one Issue-alignment row per acceptance item using
  semantic reading of Issue, Diff, and tests. Missing Diff or test evidence may
  raise the risk; never lower the deterministic risk floor.
- Use `unassessed` when Issue context is missing/unresolved or an acceptance item
  cannot be compared with concrete evidence. This is a pre-test matrix, not a
  claim about executed verification or residual release risk.
- Collect open Issue candidates only from repositories identified by the Diff.
  Prefer strong links from the current PR, PR closing text, Diff commits, or an
  `issue-123` branch. Scan at most 100 metadata records per affected repository,
  compare them with modules and changed objects, and retain at most 10 ordinary
  shortlist candidates. Read every shortlisted body before semantic alignment;
  do not perform a second five-body or metadata-only cutoff. Report scanned,
  shortlisted, excluded, hydration attempted/succeeded/failed, and strong
  overflow counts plus categorized reasons. Show why candidates do or do not
  correspond. Leave risk `unassessed` when more than one candidate remains
  plausible; do not infer identity from repository membership, a general
  keyword, or filename similarity alone.
- Do not recommend tests for pure documentation or planning records unless the
  repository defines an executable documentation contract.
- Do not emit confidence, priority, evidence-type, coverage-percentage,
  `mapping_source`, or a next-step recommendation. State the static-analysis
  limitation once, at the end.
