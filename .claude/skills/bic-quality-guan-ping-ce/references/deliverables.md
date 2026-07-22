# Deliverable Format

Current phase returns one report: `BIC 质量简报`.

```text
BIC 质量简报

核心结论
- 影响范围：<affected repositories, core modules, and change size>
- 多仓事实：<single/multi-repository only; repository count is not business-chain evidence>
- Issue 对齐：<repository -> selected Issue, unresolved, or no unique Issue>
- 测试判断：<strongest existing test evidence and the key behavior gaps>
- 风险结论：<workspace-level pre-test risk; do not invent per-stream attribution>

变更集
- 比较基线：
- 变更摘要：
- 变更仓库：
- 是否多仓发生改动：

需求与问题单
- 发现方式：
- 扫描状态：<succeeded, scan-failed, partial-scan, or scan-not-run>
- 受影响仓库 Issue 扫描：
- 候选初筛：
- 初筛排除：
- 正文读取：
- 候选 Issue：
- 关联等级：<authoritative, strong-related, reference-hint, thematic-candidate, or mentioned-reference>
- 一跳引用：<bounded mentioned references; context only>
- 候选对应分析：
- 选择依据：
- 关联 Issue：
- 目标：
- 验收项：
- 正式对齐资格：<eligible/not-eligible and the provenance reason>
- 验收项静态证据：
| 验收项 | 范围 | 实现证据 | 测试状态 | Diff/对象证据 | 测试证据 | 判断 |
|---|---|---|---|---|---|---|
| <one eligible item> | in-scope/adjacent/out-of-scope/cannot-determine | static-evidence-found/static-evidence-missing/cannot-verify | asserted/weak-or-disabled/missing/not-applicable/cannot-verify | <exact changed file/object/route/journey> | <exact test/assertion or explicit missing-test statement> | <static pre-test interpretation> |
- 范围分歧：<narrow-issue-broad-diff, broad-issue-narrow-diff, bidirectional-divergence, none-observed, or cannot-determine>
- 获取 warning：

模块映射
- Repo / Module：
- 文件证据：

测试对应性
- 直接相关测试：
- 间接相关测试：
- 可能相关测试：
- 对应依据：
- 扫描 warning：<skipped symlink/outside-repository/sensitive candidates, if any>

测试前风险矩阵
| 风险项 | Issue 依据 | Diff 依据 | 测试依据 | 等级 | 判断 |
|---|---|---|---|---|---|
| <dimension or acceptance item> | <issue fact> | <changed file/object> | <test fact or missing evidence> | high/medium/low/unassessed | <reason> |
- 技术风险：
- 需求对齐：<aligned, partial, conflict, pending-review, insufficient-definition, or unassessed>
- 评估完整度：<technical scope, requirement scope, and test execution status>
- 整体已知风险：<must not be lower than technical risk>
- 评估阶段：真正测试前（pre-test）

测试缺口
- 需求验收测试（requirement-traced）：
- 技术回归测试（technical-regression）：
- 探索性风险测试（exploratory）：
- 暂未发现明显缺口：

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

- Write `核心结论` first as a three-to-five-bullet executive summary. Derive every
  statement from evidence repeated in the detailed sections; do not introduce a
  new conclusion, label, or recommendation there. Name affected repositories and
  core modules, report multi-repository change only as a workspace fact, and do
  not infer one business/contract chain from repository count. Summarize the
  workspace Issue alignment, strongest existing test evidence, key gaps, and
  workspace-level pre-test risk. If changes appear unrelated, state that
  business-flow attribution is unresolved rather than inventing streams or
  assigning global counts to them.
- Do not print `mapping_source`; it is raw diagnostic metadata. If the module is
  unmapped, write `功能模块：暂未识别` and cite the changed files.
- Keep direct, indirect, and possible relations in their own fields. Cite the
  concrete import, call, reference, scenario, assertion, disabled state, or
  explicit relation that produced each conclusion.
- Possible candidates remain visible search clues but never count as proof that
  a changed behavior has an existing test.
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
- Start `测试前风险矩阵` with the deterministic rows from
  `assess-risk-matrix.sh`. Add one Issue-alignment row per eligible, in-scope
  acceptance item using semantic reading of Issue, Diff, and tests. Requirement
  review is a separate pass after technical review. For each item, report
  independent `scope`, `implementation`, and `test_status` values exactly as
  defined in `references/risk-model.md`; never replace them with one blanket
  verdict for several items. A positive implementation statement cites one
  exact changed file/object/route/journey. Every in-scope item cites one exact
  test/assertion or explicitly states that no test was found. Keep adjacent and
  out-of-scope items outside the matrix. Missing Diff or test evidence may raise
  the risk; never lower the deterministic risk floor.
- Use `unassessed` for requirement alignment when Issue context is
  missing/unresolved or an acceptance item cannot be compared with concrete
  evidence. Preserve the technical risk derived from Diff/test facts. This is a
  pre-test matrix, not a claim about executed verification or residual release
  risk.
- Collect open Issue candidates only from repositories identified by the Diff.
  Treat an explicit Issue override as authoritative. Auto-detect the current PR
  when available, but do not treat historical PR URLs supplied in conversation
  as analyzer inputs. A unique current-PR
  linked/closing reference may use the authoritative fast path only when exactly
  one affected GitHub repository exists. With multiple affected repositories,
  scan every repository and keep the current-PR Issue as a repository-local
  candidate without resolving workspace Issue alignment. Preserve Diff-commit
  and `issue-123` branch references as shortlist hints that still require
  semantic confirmation. Scan at most 100
  metadata records per affected repository, compare them with multilingual
  module, changed-object, changed-path, and label signals, and retain at most 10
  ordinary shortlist candidates. Keep at most one no-signal fallback per
  affected repository and do not fill unused budget with unrelated Issues. Read
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
  commit/branch references `reference-hint`; promote one to `strong-related`
  only when its preserved provenance and hydrated body both agree with concrete
  changed objects. Follow at most ten repository-contained Issue references
  from hydrated bodies for one hop and label them `mentioned-reference`; they do
  not inherit authority. Leave requirement alignment `unassessed` without
  authoritative or explicitly justified strong-related provenance; do not
  infer identity from repository membership, a general keyword, or filename
  similarity alone, and do not erase technical risk.
- Report Issue-to-Diff divergence only when the eligible item evidence supports
  it. Preserve technical objects and recommendations that an Issue does not
  mention. If attribution is incomplete, use `cannot-determine` instead of
  treating absence as proof of out-of-scope work.
- Group test guidance as `requirement-traced`, `technical-regression`, and
  `exploratory`. The effective guidance is their union. A single asset may carry
  multiple labels but is described once; Issue alignment never removes or
  downgrades technical-regression guidance.
- Do not include the raw `test_inventory` in the final `assess` payload or
  brief. Use derived test correspondence and risk evidence. Raw inventory
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
  test was executed. Do not emit confidence, priority, evidence-type, coverage-percentage,
  `mapping_source`, or a next-step recommendation. State the static-analysis
  limitation once, at the end.
