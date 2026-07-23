# Deliverable Format

Current phase returns one report: `BIC 质量简报`.

```text
BIC 质量简报

核心结论
- 影响范围：<affected repositories, core modules, and change size>
- 多仓事实：<single/multi-repository only; repository count is not business-chain evidence>
- 需求对齐：<仅当 requirement_alignment_enabled=true 时输出 authoritative Issue and origin；false 时整行省略>
- 测试判断：<strongest existing test evidence and the key behavior gaps>
- 证据结论：<strongest established fact and most important open evidence; no severity label>

变更集
- 比较基线：
- 变更摘要：
- 变更仓库：
- 是否多仓发生改动：

<以下“需求与问题单”区块仅当 requirement_alignment_enabled=true 时输出；false 时连标题一起省略>
需求与问题单
- 权威来源：<用户明确指定 / 当前 PR 唯一 linked-or-closing Issue>
- 关联 Issue：
- 目标：
- 验收项静态证据：
| 验收项 | 范围 | 实现证据 | 测试状态 | Diff/对象证据 | 测试证据 | 判断 |
|---|---|---|---|---|---|---|
| <one eligible item> | in-scope/adjacent/out-of-scope/cannot-determine | static-evidence-found/static-evidence-missing/cannot-verify | asserted/weak-or-disabled/missing/not-applicable/cannot-verify | <exact changed file/object/route/journey> | <exact test/assertion or explicit missing-test statement> | <static pre-test interpretation> |
- 范围分歧：<narrow-issue-broad-diff, broad-issue-narrow-diff, bidirectional-divergence, none-observed, or cannot-determine>

模块映射
- Repo / Module：
- 文件证据：

测试对应性
- 直接相关测试：
  - <repository-qualified test file>：<one plain-language sentence describing the changed behavior this test exercises>
- 间接相关测试：
  - <repository-qualified test file>：<one plain-language sentence describing the concrete import/reference chain and its limitation>
- 可能相关测试：
  - <repository-qualified test file>：<one plain-language sentence explaining why it is only a search clue>
- 扫描 warning：<only when symlink/outside-repository/sensitive candidates were skipped>

测试前质量证据矩阵
| 检查内容 | 现有测试能说明什么 | 还缺什么 | 建议 |
|---|---|---|---|
| <plain behavior plus exact changed route/object/path> | <specific matching test case/assertion, or none found> | <specific missing assertion/runtime evidence> | <none or one concrete add/strengthen target> |
- 同模块但不对应本行 changed object/behavior 的测试不得进入“现有测试能说明什么”。

建议新增
| 建议补什么 | 建议测试文件 | 测试方式 | 重点验证 |
|---|---|---|---|
| <plain behavior description plus exact object> | <suggested_test_target> | <pytest / Vitest / Vitest + React Testing Library / Playwright / CDP> | <observable outcomes> |
- 无建议新增时：未发现需要新增的行为级测试。

建议加强
| 要加强什么 | 改哪个现有测试 | 当前还没验证什么 | 建议补充的断言 |
|---|---|---|---|
| <plain behavior description plus exact object> | <suggested_test_target; optionally mention other relevant tests> | <disabled, skipped, assertion-free, or not target-linked> | <observable outcomes> |
- 无建议加强时：未发现需要加强的现有测试。

第二阶段测试执行交接（本阶段不执行）
- 变更指纹：
- 必跑候选：<direct and indirect candidates>
- 可选候选：<possible candidates>
- 浏览器/用户旅程证据：<Playwright/CDP scenarios, actions, observations, machine checks>
- 完整静态旅程：<completed_user_journey_paths with node_path and edge_path>
- 未闭合静态旅程：<partial_user_journey_paths with terminal and reason>
- 环境前置条件：
- 执行状态：not-run

说明：本次仅做静态分析，未执行测试；静态对应关系不代表测试已通过。
```

Repeat module and test evidence for every affected repository/module. Keep the
brief concise:

- Preserve the public report structure. Render these non-conditional headings
  exactly once and in this order: `核心结论`, `变更集`, `模块映射`,
  `测试对应性`, `测试前质量证据矩阵`, `建议新增`, `建议加强`,
  `第二阶段测试执行交接（本阶段不执行）`, then the final static-analysis
  statement. Insert `需求与问题单` between `变更集` and `模块映射` only when
  `requirement_alignment_enabled=true`. Do not collapse or rename the
  non-conditional sections merely to shorten the brief. The two intentional replacements from the earlier report are:
  `测试前风险矩阵` → `测试前质量证据矩阵`, and `测试缺口` →
  the separate `建议新增` plus `建议加强` sections.
- Write `核心结论` first as a three-to-five-bullet executive summary. Derive every
  statement from evidence repeated in the detailed sections; do not introduce a
  new conclusion, label, or recommendation there. Name affected repositories and
  core modules, report multi-repository change only as a workspace fact, and do
  not infer one business/contract chain from repository count. Summarize the
  requirement-alignment mode, strongest existing test evidence, key gaps, and
  the most important open evidence. If changes appear unrelated, state that
  business-flow attribution is unresolved rather than inventing streams or
  assigning global counts to them.
- Do not print `mapping_source`; it is raw diagnostic metadata. If the module is
  unmapped, write `功能模块：暂未识别` and cite the changed files.
- Keep direct, indirect, and possible relations in their own fields. Render the
  bounded `test_correspondence.public_summary`, not the raw module arrays. Cite
  the concrete import, call, reference, scenario, assertion, disabled state, or
  explicit relation that produced each conclusion. For every displayed item,
  print only the repository-qualified test file and its `public_explanation`
  sentence. Do not render separate `对应` or `状态` fields and do
  not print `assertion_status` or `evidence_level`. An indirect entry must name
  the test, changed object, and import/reference chain in that sentence;
  otherwise omit it from the default brief while retaining it in raw JSON.
  Group possible candidates by changed behavior, show no more than three
  candidates per behavior, and explain each candidate's
  filename/scenario/token match. Do not print raw aggregate relation counts.
  Possible candidates remain search clues and never count as proof that a
  changed behavior has an existing test.
- For Playwright/CDP evidence, distinguish actions and observations from active
  target-linked machine checks. A request check must consume that request's
  result; a page check must inspect the page/locator after the action; standalone
  CDP requires a conditional failure branch or explicit nonzero/assert-fail
  outcome. An unrelated `expect(true)`, bare `expect(value)` without a matcher,
  screenshot, or click is not a machine check. Never describe a screenshot-only or click-only
  scenario as verified. Backend/unit evidence and browser evidence are separate
  layers; neither alone proves the complete user journey.
- Report `user_journey_graph` as schema version 1. Its bounded `nodes` identify
  changed backend routes/shared contracts, frontend source layers, and connected
  browser test cases that participate in an edge or completed/partial path.
  Disconnected scan-only source and scenario nodes are omitted. Its `edges`
  preserve exact route literals, package-name
  imports, reverse imports, frontend route literals, and browser target evidence.
  `paths` are completed static paths; `partial_paths` retain anchor-only and
  terminal branches that do not reach a browser scenario. Hop, edge, and path
  limits are explicit in `limits`. Every path has `clears_object_gap: false`:
  this graph is auditable relation evidence, never proof of runtime wiring.
- Report `scan_warnings` when content inspection intentionally skipped a test-like
  symbolic link, outside-repository path, or sensitive path. Do not turn the
  skipped candidate into either positive test evidence or proof of a missing
  test. Sensitive paths and credential values must remain redacted.
- Use `issue_context.requirement_alignment_enabled` as a hard presentation gate.
  If the gate is false, omit the entire `需求与问题单` section and the
  requirement-alignment bullet in `核心结论`; do not render an empty section or
  a “not enabled” placeholder. Do not render thematic/reference candidates, scan budgets, shortlist or
  hydration details, Issue lookup warnings, acceptance placeholders, divergence,
  or requirement-traced guidance in the default brief. Those fields remain in
  raw JSON for an explicitly requested Issue-matching diagnostic.
- Render `测试前质量证据矩阵` from
  `quality_evidence.brief_evidence_matrix`, using the four fixed public columns
  in the template. Combine `quality_focus` and `changed_behavior` in
  `检查内容`; do not split them into extra columns. Keep the generic diagnostic
  dimension rows in raw JSON. Add requirement comparison only inside
  `需求与问题单`, not as an Issue column in the technical matrix. Requirement
  review is a separate pass after technical review. For each eligible item, report
  independent `scope`, `implementation`, and `test_status` values exactly as
  defined in `references/risk-model.md`; never replace them with one blanket
  verdict for several items. A positive implementation statement cites one
  exact changed file/object/route/journey. Every in-scope item cites one exact
  test/assertion or explicitly states that no test was found. Keep adjacent and
  out-of-scope items outside the matrix. Report missing evidence explicitly;
  never translate it into a severity label.
- Do not add a standalone evidence-strength column. Internal labels such as
  `object-asserted`, `behavior-asserted`, `contract-asserted`, `none`, and
  `static-browser-path` may guide selection, but the matrix must explain the
  useful proof in plain language under `现有测试能说明什么`. Do not print
  `evidence-only` or another decision-model label below the public matrix.
- Keep `not-enabled` in raw JSON for requirement alignment when there is no
  authoritative Issue, but do not print it in the default brief. Omit
  `issue-clarity` and all requirement rows in that mode; the remaining matrix is
  a complete technical pre-test assessment. This is not a claim about
  executed verification or residual release risk.
- Collect open Issue candidates only from repositories identified by the Diff.
  Treat an explicit Issue override as authoritative. Auto-detect the current PR
  when available, but do not treat historical PR URLs supplied in conversation
  as analyzer inputs. A unique current-PR
  linked/closing reference may use the authoritative fast path only when exactly
  one affected GitHub repository exists. With multiple affected repositories,
  scan every repository and use one unique current-PR linked/closing Issue as an
  additive requirement overlay without narrowing technical scope. Preserve Diff-commit
  and `issue-123` branch references as shortlist hints that still require
  semantic confirmation. Scan at most 100
  metadata records per affected repository, compare them with multilingual
  module, changed-object, changed-path, and label signals, and retain at most 10
  ordinary shortlist candidates. Exclude no-signal Issues even when their
  repository is affected, report that repository as unmatched, and do not fill
  unused budget with unrelated Issues. Read
  every shortlisted body before semantic alignment;
  do not perform a second five-body or metadata-only cutoff. Batch multiple
  bodies into one read-only GraphQL request, then use at most three concurrent
  fallback lookups only for unresolved candidates. Apply bounded per-request
  timeouts and a shared 60-second GitHub deadline while preserving shortlist
  order. Report fast-path use, hydration mode, request counts, deadline state,
  per-repository and aggregate scan status, scanned, shortlisted,
  excluded, hydration attempted/succeeded/failed, and strong overflow counts
  plus categorized reasons. Use `scan-failed` when every attempted scan fails,
  `partial-scan` when only some repositories succeed, and `no-candidates` only
  after successful empty scans. Show why candidates do or do not correspond.
  Label ordinary search matches `thematic-candidate`; even one unique semantic
  match remains background context, receives no acceptance-item comparison or
  requirement-traced guidance, and cannot supply acceptance rows. Label
  commit/branch references `reference-hint`; keep them diagnostic-only until the
  user explicitly supplies one as `--issue`. Follow at most ten repository-contained Issue references
  from hydrated bodies for one hop and label them `mentioned-reference`; they do
  not inherit authority. Leave requirement alignment `not-enabled` without
  authoritative provenance; do not
  infer identity from repository membership, a general keyword, or filename
  similarity alone.
- Report Issue-to-Diff divergence only when the eligible item evidence supports
  it. Preserve technical objects and recommendations that an Issue does not
  mention. If attribution is incomplete, use `cannot-determine` instead of
  treating absence as proof of out-of-scope work.
- Group test guidance internally as `requirement-traced`,
  `technical-regression`, and `exploratory`; the effective guidance is their
  union. In the public brief, route every `action: add` item to `建议新增` and
  every `action: strengthen` item to `建议加强`. A single asset may carry
  multiple internal labels but is described once; Issue alignment never removes
  or downgrades technical-regression guidance.
- Render every add/strengthen item as an actionable behavior-level suggestion:
  use plain language first, then cite the exact changed object. Include
  `suggested_test_target`, `public_test_method`, the concrete gap, and suggested
  observable assertions. The internal `test_layer`, `recommended_framework`,
  and `alternative_frameworks` remain structured analysis metadata and must not
  be printed in the default brief. `public_test_method` is restricted to real
  tool names: `pytest`, `Vitest`, `Vitest + React Testing Library`,
  `Playwright`, `CDP`, or `项目原生测试命令`. Never append internal values such
  as `frontend-component`, `repository`, `service-unit`, `backend-route`, or
  `browser-user-journey`. For strengthen items, show only existing
  tests whose path, case name, or exact reference chain matches the behavior;
  broad class/module imports stay out of the public suggestion. Group related private
  helpers in the same source file instead of printing one item per symbol.
  Show no more than five weak test paths in one guidance item and report the
  total/overflow count; keep the full path set in raw correspondence evidence.
  Backend behavior normally uses pytest; frontend unit/component behavior uses
  Vitest and React Testing Library; browser user journeys use Playwright; CDP is
  suggested only for protocol-level evidence such as streaming/network/console
  diagnostics, not as the default UI test layer.
- Do not include the raw `test_inventory` in the final `assess` payload or
  brief. Use derived test correspondence and quality evidence. Raw inventory
  remains available through the standalone inventory/suggest diagnostics.
- Summarize the emitted `test_execution_manifest` without executing it. State
  its change fingerprint, required/optional candidates, unresolved commands,
  prerequisites, browser journey evidence, completed and partial journey paths,
  and `not-run` status. Each manifest path expands both `node_path` and
  `edge_path`, keeps `execution_status: not-run`, and repeats that it cannot
  clear an object-level gap. It is invalid
  for execution if the workspace fingerprint changes.
- Do not recommend tests for pure documentation or planning records unless the
  repository defines an executable documentation contract.
- Do not call an acceptance item satisfied, passed, complete, or verified: no
  test was executed. Do not emit confidence, priority, evidence-type,
  coverage-percentage, severity, `technical_risk`, `overall_risk`,
  `risk_floor`, `mapping_source`, or a general next-step recommendation. State
  the static-analysis limitation once, at the end.
