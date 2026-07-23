# Implementation Plan

## 13. Dual-Scope Quality Workflow

- Emit an immutable technical scope before Issue collection and add regression
  invariants proving Issue input cannot remove repositories, objects, journeys,
  test relations, or technical test recommendations.
- Split risk output into technical risk, requirement alignment, assessment
  completeness, and an overall known-risk floor. Keep technical risk available
  when Issue context is missing or thematic only.
- Keep the existing open-only 100-to-10 discovery unchanged; do not add closed-
  Issue, timeline, comment, or second-body lookups.
- Add a lightweight evidence-reporting pass that compares each eligible
  acceptance item with changed objects, routes, journeys, and tests on separate
  scope, implementation, and test-status axes.
- Preserve scope fusion by union, report only evidence-supported divergence,
  and group suggested tests into requirement-traced, technical-regression, and
  exploratory guidance.
- Implement and verify in three local commits so technical isolation, Issue
  evidence, and final fusion can be reverted independently.

Validation: fixtures cover narrow/wrong/missing Issue inputs, acceptance-item
evidence contracts, frontend/backend journey gaps, and technical candidate-set
monotonicity. Run source tests after every stage and the complete install/mirror
verification at the end.

## 12. Issue Provenance Refinement

- Auto-detect current-PR provenance inside affected repositories; historical PR
  URLs remain background context rather than analyzer arguments.
- Label candidates as authoritative, reference hints, thematic candidates, or
  one-hop mentioned references; keep acceptance eligibility explicit.
- Follow a bounded affected-repository reference set from hydrated bodies
  without promoting those references.
- Update the Skill/risk/deliverable contract so thematic Issues cannot define
  requirements and umbrella acceptance items are scope-filtered.
- Add regression tests, synchronize both discovery mirrors, run the complete
  quality-kit verification chain, and commit locally only.


## 1. Repository and Diff Collection

- Replace the hard-coded repository list with bounded dynamic discovery.
- Add per-repository base resolution and comparison metadata.
- Parse NUL-delimited name-status output for committed, unstaged, and staged
  changes; merge untracked files and preserve all sources.
- Forward `--base-ref` and `--worktree-only` through all wrappers.
- Suppress root-level placeholders for discovered child repositories.

Validation: temporary Git repositories must demonstrate committed, dirty,
staged, untracked, rename, delete, missing-base, and child-repository behavior.

## 1.5 Issue Context and Pre-test Risk

- After Diff collection, list open Issues for every affected GitHub repository.
  Keep current PR links/closing text, Diff commit messages, and a strong
  branch-name pattern as higher-priority association evidence.
- Split Issue work into one metadata snapshot, deterministic shortlist, and
  full-body hydration stages. Scan at most 100 metadata records per affected
  repository and reuse the snapshot for the complete assessment.
- After module mapping and changed-object extraction, merge duplicate references
  and shortlist at most 10 ordinary candidates using explicit/strong references,
  repository identity, module/object tokens, labels, stable update ordering, and
  repository diversity. Preserve counts and exclusion reasons without returning
  excluded Issue content.
- Split authoritative current-PR links from commit/branch reference hints so a
  branch name cannot resolve an Issue without semantic confirmation.
- Add bounded Chinese tokenization/project aliases and changed-path signals.
  Require a real search signal for ordinary global shortlist filling and allow
  only one no-signal fallback per affected repository.
- Attempt to read every shortlisted body; do not introduce a separate five-body
  cutoff. Use one GraphQL batch for multiple bodies and a fixed-size fallback
  only for unresolved items. Continue after individual lookup failures and
  expose per-candidate hydration status. Preserve strong-reference overflow as ambiguity.
- Resolve a unique authoritative current-PR Issue through a fast path only when
  one affected GitHub repository exists. With multiple affected repositories,
  scan all repositories and keep the PR Issue repository-local.
- Add explicit timeouts to current-PR lookup, repository Issue listing, and Issue
  body lookup plus a 60-second total GitHub analysis deadline. Preserve input
  order and isolate timeout/failure warnings per candidate.
- Record per-repository scan status and derive aggregate `succeeded`, `failed`,
  `partial`, or `not-run` state. Map failed/partial scans to distinct analysis
  statuses and never emit a successful-empty message for failed queries.
- Preserve repository-qualified candidates, scan counts, source priority,
  selection reason, query failures, and ambiguity instead of choosing
  arbitrarily. Keep explicit references as overrides.
- Extract Issue goals, labels, repository, and acceptance items.
- Generate deterministic risk rows for Issue clarity, impact breadth,
  contract/state boundaries, test evidence, and change attribution.
- Require semantic acceptance-item alignment in the Skill report and preserve
  `unassessed` when Issue context is unavailable.

Validation: fixtures cover a 100-record scan limit, a 10-candidate shortlist,
all-shortlist hydration, repository diversity, strong-link precedence and
overflow, ambiguity, per-candidate query failure, exclusion accounting, and one
Issue-list call per affected repository during an end-to-end assessment without
mutating Git state. Add timeout, ordered limited-concurrency, `scan-failed`,
`partial-scan`, and successful-empty fixtures. A real GitHub list receives a
read-only smoke check when authentication is available.

Additional fixtures cover Chinese and mixed-language titles, commit/branch
reference hints that remain unresolved, and repository fallback quotas that do
not force the shortlist to its maximum size. Fast-path, one-request GraphQL
batching, bounded fallback, and total-deadline fixtures prevent request-count and
latency regressions.

## 2. Repository and Module Mapping

- Migrate explicit taxonomy from `capability_scope` plus risk metadata to a
  single `module_scope` for known BIC business modules.
- Remove path-derived risk scores, generic keyword-to-capability inference, and
  duplicate impact labels from module mapping and reports.
- Add structural module extraction for unmatched paths using stable source roots
  and repository-relative directory segments.
- Preserve `explicit`, `structural`, and `unmapped` mapping evidence and direct
  cross-repository facts.

Validation: table-driven paths must prove known BIC modules use explicit rules,
new repositories use structural paths, generic names do not invent semantics,
and root/unusual files remain visible.

## 3. Changed Objects and Test Correspondence

- Replace directory-existence checks with concrete test-asset discovery.
- Treat filename patterns as candidate discovery only; require parsed
  JavaScript/TypeScript test cases, and require Python cases plus a standard
  test directory, assertion, or pytest/unittest signal before emitting
  `asset_kind: test-file`.
- Keep unparseable test-like candidates out of coverage evidence, and preserve
  disabled but structurally valid tests as test files.
- Detect pytest, JavaScript unit-test, and Playwright configuration and commands.
- Extract changed Python and JavaScript/TypeScript source objects without
  importing project code, retaining a file-level fallback.
- Inspect concrete test files for imports, references, scenario names,
  assertions, and disabled state.
- Parse simple local `Path(__file__)` constants, dynamic `importlib` aliases,
  and local helper calls that wrap `subprocess.run`; attach exact target/object
  facts to the originating test case without executing analyzed content.
- Use proven local Python entrypoints as safe one-hop import sources while
  retaining assertion and object-specific evidence requirements.
- Attach assertion-link facts to dynamic target calls and helper-expanded local
  entrypoints. Add regression coverage proving `target(); assert True` needs
  strengthening while `result = target(); assert result` can clear the gap.
- Restrict command-entrypoint one-hop imports to imported aliases referenced by
  the selected branch's reachable functions. Add sibling-command fixtures that
  prevent whole-file imports from clearing unrelated gaps.
- Merge explicit repository-qualified inventory relations with discovered
  assets; reserve explicit cross-repository targets for deliberate E2E flows.
- Analyze direct, safe one-hop/explicit, and possible scenario relationships per
  repository/module without exposing confidence or evidence labels.
- Derive separate natural-language groups for tests to add, tests to strengthen,
  and modules with no obvious static gap.
- Filter documentation, Skill/reference, and planning-only objects before
  generating add/strengthen guidance, while preserving existing executable
  documentation relations and runtime-configuration analysis.
- Exclude local skill copies, backups, and independently discovered child
  repositories from duplicate root-repository test discovery.
- Route file-content reads through a shared guard that rejects symbolic links,
  outside-repository real paths, non-regular files, and sensitive credential
  paths. Carry skipped test-like candidates as scan warnings, and sanitize all
  CLI JSON strings for sensitive paths and common secret forms immediately
  before serialization. Keep file-size, file-count, and byte budgets outside
  this iteration.

Validation: fixture repositories must cover Python and TypeScript symbols,
imports/references, assertions, disabled tests, unrelated same-name files,
frontend tests, empty directories, explicit cross-repository inventory, and
repository isolation. Regression fixtures must also prove that test-named
implementation modules are not test assets and documentation-only changes do
not create missing-test guidance. Dynamic-import and subprocess-helper fixtures
must prove exact target mapping, one-hop entrypoint imports, assertion gating,
and that a target which would write a marker is never executed.
Additional safety fixtures must prove that test symlinks and sensitive paths are
not read, real-path containment rejects repository escapes, skipped candidates
remain warnings, example environment files remain eligible, and serialized
output contains neither credential values nor sensitive paths.

## 4. Skill and Documentation

- Update `SKILL.md`, references, config, README, and implementation notes with
  the changed-object and test-correspondence contract.
- Keep output as one concise `BIC Quality Brief` with module mapping,
  direct/indirect/possible test correspondence, and missing-test guidance.
  Omit `mapping_source` and a general next-step field while retaining the
  read-only boundary.
- Add Issue Context and an evidence-backed pre-test Risk Matrix without implying
  that any verification command ran.
- Add an explicit untrusted-content rule to the Skill boundary and a malicious
  Issue-body fixture proving embedded instructions remain inert data and do not
  trigger subprocess execution.
- Remove raw `test_inventory` from the final `assess` payload after correspondence
  and risk derivation; retain it in standalone inventory/suggest diagnostics.
- Synchronize source to the committed `.agents` and `.claude` mirrors only after
  source verification.

## 5. Final Verification

Controlled 62-Issue benchmark against commit `68be270`: final assessment JSON
decreased from 5,767,436 bytes to 179,034 bytes, and three-run median wall time
decreased from 4.58 seconds to 2.97 seconds. Both versions made 12 fixture `gh`
calls; the optimized assessment still hydrated all 10 shortlisted candidates.

Dynamic-test-relation forward check on the current worktree: the fixed review
prompt completed in 4.88 seconds. Missing-test guidance decreased from the prior
65 add plus 80 strengthen items to 22 add plus 0 strengthen items, while 139
changed objects gained active direct or safe-indirect assertion evidence.

- Run syntax/config validation and the temporary behavior fixture suite.
- Run the full `verify-install.sh` chain after synchronizing the mirrors.
- Compare the source and repository-tracked Skill mirrors.
- Confirm `git status` before and after analyzer runs is unchanged except for the
  intended task and kit edits.
- Confirm public test-analysis JSON contains no confidence fields,
  `evidence_type`, `coverage_gaps`, or `coverage_unconfirmed`.

## 6. Skill Discoverability

- Generate `agents/openai.yaml` in the source Skill with `display_name`,
  `short_description`, and a one-sentence `$bic-quality-guan-ping-ce` default
  prompt. Do not add unprovided icons, branding, MCP dependencies, or an
  unnecessary implicit-invocation override.
- Add one root SOP Index entry that points to the editable source Skill, while
  committing `.agents/skills` and `.claude/skills` discovery mirrors for
  zero-install use by new clones.
- Document explicit and implicit invocation plus the responsibilities of
  `SKILL.md`, `agents/openai.yaml`, the SOP Index, and mirror synchronization.
- Add contract tests for metadata shape, Skill-name consistency, description
  length, default-prompt invocation, and the stable SOP route.
- Extend verification to require `agents/openai.yaml` in the source and in both
  repository-tracked mirrors, and fail when either mirror is absent or stale.

Validation: run the unit suite, synchronize the Skill mirrors, run the complete
`verify-install.sh` chain, run Skill Creator validation, and finish with
`git diff --check`.

## 7. Real-Agent Evaluation

- Define a small smoke set and a broader full set of realistic prompts.
- Rebuild each Git fixture independently for `with_skill` and `no_skill`.
- Run `codex exec` ephemerally with user config ignored and a read-only sandbox.
- Grade the assessment call count, forbidden commands, required facts,
  warning/`unassessed` preservation, paired fact-score delta, and prompt-variant
  stability from raw JSONL and final-answer artifacts.
- Keep old-Skill comparisons out of the normal gate.

Validation: run the harness unit tests, run a dry-run smoke set, then run the
real smoke set when model access is available.

## 8. Required Multi-language Analyzer Runtime

- Pin `ast-outline` and its supported JSON schema in one runtime manifest.
- Add a lock-protected, interruption-recoverable first-use bootstrap into a BIC-owned user
  cache; invoke the managed absolute executable and never mutate global PATH.
- Fail the complete assessment when installation, capability probing, or schema
  validation fails; do not label a reduced analysis complete.

Validation: cover first install, reuse, version change, corruption, concurrent
install, interrupted install, incompatible JSON, and unchanged repository state.

## 9. Canonical Diff-to-Declaration Mapping

- Preserve committed/staged/unstaged/untracked provenance while deriving one
  canonical local-base-to-current Diff for old/new line coordinates.
- Parse current supported source files with `ast-outline outline --json` after
  containment checks and parse old blobs through ephemeral typed files.
- Recursively normalize declaration ranges and map every hunk to the smallest
  enclosing declaration, retaining ancestors and legitimate module-scope facts.
- Classify Python/JS/JSX/TS/TSX functions, methods, classes, React components,
  hooks, stores/actions, API clients, routes, types, and shared contracts.

Validation: fixtures cover modified bodies/signatures/decorators, overlapping
change provenance, cross-symbol hunks, module scope, add/delete/rename, TSX,
syntax failure, symlink escape, and malformed analyzer output.

## 10. User-Journey and Browser Evidence

- Feed exact objects/routes into module mapping, the existing bounded Issue
  shortlist, and test correspondence.
- Add bounded cross-repository edges for backend route/shared-contract to
  frontend client/hook/store/component and explicit E2E scenarios.
- Analyze Playwright actions/assertions/skip/fixme and CDP DOM/network/console/
  pass-fail checks; distinguish automated checks, manual observations, and
  diagnostics.
- Keep pytest, frontend unit/component, Playwright, and CDP evidence separate in
  the risk matrix; possible or manual-only evidence cannot clear an object gap.

Validation: fixtures cover route-to-browser journeys, action-only Playwright,
effective browser assertions, skipped/fixme tests, screenshot-only CDP, and CDP
with explicit machine checks.

## 11. Phase-Two Manifest and Skill Contract

- Emit a versioned Test Execution Manifest with local change fingerprints,
  selected tests, objects/journeys, prerequisites, mutation flags, and inert
  command hints.
- Keep output on stdout and temporary/cache writes outside repositories.
- Keep `SKILL.md` concise; move multi-language, browser, and manifest detail to
  direct references and refresh `agents/openai.yaml` only if its interface is
  stale.
- Synchronize both discovery mirrors only after source verification.

Validation: schema tests, stale-fingerprint fixtures, Skill Creator validation,
unit tests, agent evals, install verification, mirror comparison, and
`git diff --check`; then create local commits only.

## 14. Behavior-Scoped Phase-Two Execution

- Extract shared execution eligibility from strict public correspondence rules.
  Keep public display caps separate from the unbounded eligible execution set.
- Replace raw-relation file deduplication with case identity
  `(repo, framework, path, case)` and merge changed behaviors/module references.
- Emit schema-v2 `must_run`, `recommended`, `not_runnable`, and exclusion
  accounting while retaining compatibility aliases for existing consumers.
- Resolve safe case-level argv for pytest, Vitest, and Playwright. Resolve CDP
  only from a concrete configured project command.
- Include active asserted cases whose declarations intersect changed test-file
  hunks. Do not schedule unchanged sibling cases from the same file. Keep
  disabled, assertion-free, missing suggested tests, unsupported frameworks,
  and unresolved commands out of `must_run`.
- Add a separate executor that consumes an assessment/manifest file, verifies
  the workspace fingerprint, validates repository containment and argv, and
  executes backend, frontend, browser, then browser-diagnostic layers.
- Stop browser execution when a required foundation case fails, skips, blocks,
  or cannot run. Do not install dependencies, start services, mutate data,
  invoke live-bench runners, or query Phoenix.
- Emit a behavior-linked execution report with per-case and per-layer states,
  unresolved reasons, and a qualified final conclusion.
- Update the Skill and deliverable contract while preserving the existing
  phase-one public brief headings and default read-only behavior.

Validation: add focused fixtures for strict direct/indirect selection,
configured-module exclusion, changed tests, duplicate case merging, missing
commands, precise framework argv, stale fingerprints, path/argv rejection,
layer gating, skipped tests, and behavior result aggregation. Re-run the known
feedback worktree case only after focused tests pass; do not run the slow full
verification chain during iteration.

### 2026-07-22 quality-gap closure

- `test_correspondence.user_journey_graph` schema version 1 now exposes bounded
  nodes, auditable edges, completed paths, terminal/anchor-only partial paths,
  scan warnings, and conservative `clears_object_gap: false` semantics.
- Browser evidence is case-scoped and target-linked. Playwright request results,
  DOM/page matchers, and explicit CDP fail conditions count; unrelated/bare
  expectations, disabled cases, screenshots, comments, and quoted examples do
  not.
- `test_execution_manifest` expands completed and partial journey node/edge
  paths and preserves `not-run` status. Selected cases are relation-specific.
- The runtime regression matrix covers first install/reuse, version change,
  corrupt marker/executable, concurrent first use, interrupted cleanup,
  invalid JSON/schema, unchanged Git state, and live Python/JS/JSX/TS/TSX
  diff-hunk-to-declaration fixtures.
