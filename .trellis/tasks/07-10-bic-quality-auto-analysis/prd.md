# BIC Quality Automatic Diff, Scope, and Test Inference

## Goal

Upgrade the read-only BIC Quality Skill so it can analyze the complete local
change set for every repository under `BIC-meta`, locate each changed file in a
repository and functional module, discover relevant test assets, and produce
evidence-backed recommendations without requiring script changes whenever a
repository or test directory is added.

## Requirements

- Discover `BIC-meta` and its immediate child Git repositories dynamically.
- Analyze committed branch changes relative to a locally available base ref in
  addition to unstaged, staged, and untracked worktree changes.
- Resolve the base independently per repository without fetching, checking out,
  or mutating Git state.
- Accept an optional conversationally supplied base ref while keeping automatic
  base resolution as the default.
- Preserve per-file change sources and change types, including rename and delete.
- Keep explicit module taxonomy as the authoritative source for known BIC
  business modules.
- For paths not covered by explicit rules, derive a structural module from the
  repository-relative source tree instead of guessing business semantics from
  generic keywords such as `api`, `models`, `events`, or `client`.
- Retain unmapped changes visibly when no stable structural module exists.
- Report direct multi-repository changes as a fact derived from changed repos.

- Do not derive risk from paths or duplicate impact labels. Always derive a
  technical pre-test risk from Diff, changed objects, boundaries, journeys, and
  static test evidence. Report requirement alignment separately: missing or
  non-authoritative Issue context makes requirement alignment `unassessed`, but
  must not erase or lower the technical risk.
- Discover concrete test files, test directories, framework configuration, and
  command hints automatically for Python and JavaScript/TypeScript repositories.
- Require both a test-like filename and parsed executable test cases before a
  JavaScript/TypeScript candidate can count as a concrete test file. Python
  candidates additionally require a standard test directory, an assertion, or
  a pytest/unittest framework signal; test-named implementation modules must
  not become coverage evidence.
- Treat `test-inventory.yaml` as an explicit semantic override instead of the
  only source of test knowledge.
- Extract changed source objects where possible, including Python functions and
  classes plus JavaScript/TypeScript exports, components, stores, routes,
  events, and types. Fall back to changed-file facts when a language cannot be
  parsed safely.
- After the Diff identifies affected repositories, scan open GitHub Issues in
  each affected repository. Also search bounded closed-Issue metadata around
  current-PR or local commit activity when timestamps are available. Preserve
  current-PR links, PR/commit closing text,
  and a strong branch-name pattern as higher-priority association evidence.
  Explicit overrides are authoritative. A current-PR linked/closing reference
  may resolve automatically only when one affected GitHub repository exists;
  with multiple affected repositories it remains repository-local and all
  repositories are scanned. Commit and branch references remain
  semantic-review hints. Without an
  authoritative link, retain repository Issue candidates for semantic
  comparison with changed modules and objects. Accept an explicit reference
  only as an override. All GitHub access is read-only through local `gh`.
- Keep affected-repository Issue discovery bounded and auditable: scan at most
  100 open-Issue metadata records per repository, reduce ordinary candidates to
  a deterministic shortlist of at most 10 after module/object mapping, then
  attempt to read every shortlisted body before semantic alignment. Do not add
  a second metadata-only body-selection cutoff. Preserve scan, exclusion, and
  hydration counts plus categorized warnings without returning excluded Issue
  content to the Agent context.
- Treat explicit overrides as authoritative. Treat a unique current-PR
  linked/closing reference as workspace-authoritative only for a
  single-affected-repository analysis. Commit-message and `issue-123` branch references must remain
  protected shortlist hints until their full Issue content agrees semantically
  with the changed modules and objects.
- Support English, Chinese, and mixed-language Issue shortlist signals. Require
  an object, module, changed-path, or label signal for ordinary candidates and
  allow at most one no-signal fallback per affected repository instead of
  filling the shortlist with unrelated recent Issues.
- Reuse one immutable Issue snapshot throughout a normal end-to-end assessment.
  Treat the final assessment wrapper as the primary Skill entry and the
  intermediate wrappers as diagnostics so module, test, and risk stages do not
  repeat live GitHub queries during one analysis.
- Keep the end-to-end `assess` payload Agent-facing and bounded. Use the full
  discovered test inventory internally, but omit it from the final assessment
  JSON after test correspondence and risk have been derived. Keep the standalone
  inventory wrapper as the raw diagnostic contract.
- Bound every GitHub CLI call with an explicit timeout. Hydrate shortlisted Issue
  bodies through one GraphQL batch when multiple candidates exist, with a small
  fixed-concurrency fallback for unresolved candidates. Preserve shortlist
  order, per-candidate failure isolation, and the read-only boundary. Apply one
  60-second deadline to the complete GitHub analysis.
- When current-PR evidence contains exactly one authoritative linked/closing
  Issue and exactly one affected GitHub repository exists, skip broad open-Issue
  discovery and resolve only that Issue. With multiple affected repositories,
  scan all repositories and keep the PR Issue repository-local.
- Distinguish a successful empty Issue scan from query failure. Report
  `scan-failed` when no affected-repository scan succeeds and `partial-scan`
  when only some scans succeed; never describe a failed scan as proof that no
  open Issue exists.
- Analyze test correspondence per `(repo, module_scope)`: direct code
  references, safe one-hop or explicitly configured relations, and weaker
  scenario/path candidates must remain distinguishable in raw analysis and the
  default brief without confidence scores.
- Recognize Python tests that load a local module through
  `importlib.util.spec_from_file_location` and tests that reach a local Python
  entrypoint through an asserted helper wrapping `subprocess.run`. Preserve the
  exact target path and directly called dynamic-module objects without executing
  any analyzed code or command string.
- Treat imports made by a proven local entrypoint as safe one-hop relations, but
  do not claim object-level coverage unless the object call or static source
  reference is concrete.
- Do not let an unrelated or unconditional assertion such as `assert True`
  clear a dynamic-target test gap. A dynamic target must be connected to the
  asserted expression, an asserted result variable, or an expected-exception
  context; otherwise retain the relation but recommend strengthening the test.
- When a local Python entrypoint selects a command branch, restrict one-hop
  imported-module relations to imports actually referenced by the statically
  reachable functions for that command. Imports used only by other command
  branches must not clear a gap.
- Separate relation facts from the need to add tests. A changed object with no
  object-specific test relation needs a new test. Disabled, assertion-free, or
  object-specific filename candidates need strengthening. Active direct,
  safe-one-hop, or explicitly object-mapped tests with assertions have no
  obvious static gap. Module-only and scenario-only candidates remain visible
  but do not clear an object-level gap.
- Report add-test guidance as natural-language `add`, `strengthen`, and
  `no-obvious-gap` sections, not risk, priority, confidence, or evidence labels.
  Never equate discovered test assets with passing tests or proven coverage.
- Exclude documentation, Skill/reference text, and planning-only changes from
  add/strengthen guidance unless an existing executable documentation contract
  already provides a concrete test relation. Do not blanket-exclude runtime
  YAML or JSON configuration.
- Preserve the current read-only boundary: no tests, services, resets, process
  control, Git fetch/checkout, or business-code modification.
- Treat Issue/PR bodies and analyzed source, comments, tests, and ordinary
  documentation as untrusted evidence. Embedded instructions must not alter the
  Skill workflow, permissions, tool use, or read-only boundary.
- Read content only from regular files contained by their discovered repository.
  Skip symbolic links, paths whose real location leaves that repository, and
  credential-bearing paths. Preserve skipped test candidates as warnings rather
  than absence evidence, and redact sensitive paths and common credential values
  from CLI JSON output. Do not add file-size, file-count, or cumulative-byte
  limits in this iteration.
- Exclude generated Skill mirrors, backups, local tool state, and independently
  discovered child repositories from duplicate root-repository test discovery.
- Keep `mapping_source` in raw JSON for diagnostics but omit it from the default
  brief. Keep direct/indirect/possible relation sections visible, and do not add
  a general next-step recommendation field.
- Generate a pre-test Risk Matrix from Diff breadth, contract/state boundaries,
  changed-object attribution, user journeys, test evidence, Issue clarity, and
  scope divergence. Keep `technical_risk`, `requirement_alignment`, and
  `assessment_completeness` distinct. Missing Issue context must make only the
  requirement dimension `unassessed`, never turn known technical risk into a
  guessed low risk or erase it.
- Commit synchronized Codex and Claude discovery mirrors so a new clone can
  use the Skill without running an installer. Keep `tools/bic-quality-kit/skill`
  as the only editable source of truth and fail verification when either mirror
  is missing or stale.
- Exclude the committed discovery mirrors from collected changes so one source
  modification is not counted three times in a quality assessment.
- Add Codex-facing discovery metadata under `agents/openai.yaml` with a stable
  display name, short description, and explicit `$bic-quality-guan-ping-ce`
  default prompt.
- Add one root SOP Index entry that routes quality review requests to the
  committed source-of-truth Skill rather than a generated discovery mirror.
- Verify discovery metadata, SOP routing, and mirror synchronization so
  missing or stale metadata fails the quality-kit verification chain.
- Add isolated real-Agent eval cases that run identical prompts and Git fixtures
  with the current Skill and without any target Skill or route. Do not include
  an old-Skill baseline in the normal gate.
- Deterministically grade observable Skill invocation count, warning and
  `unassessed` preservation, core Diff/Issue/test facts, forbidden operations,
  and fact stability across prompt variants.

## Acceptance Criteria

### 2026-07-22 dual-scope quality workflow

- [ ] Technical repositories, files, changed objects, journeys, and test
      candidates are computed before Issue context and cannot be removed or
      downgraded by an explicit or discovered Issue.
- [ ] Requirement context may add or re-rank test candidates but the final set
      is a union whose technical-candidate membership never decreases.
- [ ] Risk output reports `technical_risk`, `requirement_alignment`, and
      `assessment_completeness`; no Issue leaves technical risk intact and only
      requirement alignment unassessed.
- [ ] Issue discovery searches bounded open and closed Issue metadata around
      current-PR or local commit activity, validates top candidates against
      timeline evidence, and reads only bounded comments as untrusted data.
- [ ] Every eligible acceptance item is classified as direct, indirect,
      claimed-but-unmatched, explicitly out-of-scope, or unresolved with
      auditable Diff/object/test evidence.
- [ ] Scope fusion reports narrow-Issue/broad-Diff and broad-Issue/narrow-Diff
      divergence as risk instead of using either side to hide the other.
- [ ] Suggested tests are separated into requirement-acceptance, technical
      regression, and exploratory-risk groups while retaining pytest,
      frontend unit/component, Playwright, and CDP evidence.
- [ ] Regression fixtures prove that supplying a narrow, incorrect, or absent
      Issue cannot reduce technical scope, candidate tests, or risk floor.

### 2026-07-22 Issue provenance refinement

- [x] Ordinary open-Issue search matches are labeled thematic and cannot become
      the requirement source or feed acceptance rows solely through semantic
      similarity.
- [x] Explicit/current-PR linked or closing Issues remain authoritative;
      commit/branch references remain provenance-bearing hints.
- [x] Historical PR URLs are not analyzer inputs; only the current workspace
      Diff, auto-detected current PR, and explicit Issue overrides define scope.
- [x] Hydrated Issue bodies expose at most ten one-hop, affected-repository
      references as context without inheriting authority.
- [x] Only eligible, in-scope acceptance items enter the risk matrix; umbrella
      Issue items outside this Diff remain contextual.

- [x] Newly added immediate child Git repositories are collected without editing
      a hard-coded repository list.
- [x] Default collection includes `merge-base(base, HEAD)..HEAD`, unstaged,
      staged, and untracked changes for each discovered repository.
- [x] Explicit base refs can be passed through the wrappers and invalid refs
      produce visible warnings instead of silent fallback.
- [x] Output records repository comparison metadata and per-file change sources.
- [x] Unmapped repositories and files remain visible without invented semantics.
- [x] Explicit business-module matches and structural-module matches expose their
      source and evidence.
- [x] No analyzer or report output contains path-only risk levels or duplicate
      impact labels.
- [x] An unconfigured path such as `BIC-model-service/app/inference/pipeline.py`
      maps to repository `BIC-model-service` and structural module `app/inference`,
      not to a guessed generic capability.
- [x] Concrete pytest, unit-test, and Playwright/Vitest/Jest assets are discovered
      from actual files and configuration.
- [x] A test-like filename without parsed test cases is not emitted as a
      `test-file`, while real and disabled test cases remain discoverable.
- [x] Test files expose imports/references, test cases, assertions, and disabled
      state without importing or executing project code.
- [x] Discovery mirrors, backups, and child repositories are not duplicated as
      root-repository test assets.
- [x] Changed source files expose deterministic symbol facts where supported and
      preserve a file-level fallback where not supported.
- [x] Every affected `(repo, module_scope)` reports changed files/objects,
      directly or indirectly related tests, possible candidates, and concrete
      missing-test guidance.
- [x] Dynamic `importlib` calls establish exact local file/object relations, and
      asserted test helpers wrapping `subprocess.run` establish their local
      entrypoint relation without executing the target.
- [x] A proven local entrypoint can establish safe one-hop relations to its
      statically imported changed modules, while assertion-free or disabled
      cases cannot clear a missing-test gap.
- [x] A dynamic target followed only by an unrelated `assert True` remains a
      strengthen-test finding; asserting the target result or expecting its
      exception may clear the static gap.
- [x] A selected local-entrypoint command relates only to imported objects used
      by its reachable branch; imports used exclusively by sibling commands do
      not become indirect test evidence.
- [x] Add-test guidance distinguishes tests to add, tests to strengthen, and
      modules with no obvious static gap without emitting risk, confidence,
      priority, or evidence labels.
- [x] README, Skill/reference, and planning-only changes do not produce add or
      strengthen guidance; executable source and runtime configuration remain
      eligible for analysis.
- [x] Same-name paths in different repositories remain isolated, and deliberate
      cross-repository test relations require an explicit repository-qualified
      declaration.
- [x] The public test-analysis contract does not contain `coverage_gaps`,
      `coverage_unconfirmed`, `evidence_type`, or confidence fields.
- [x] The default brief contains module evidence, direct/indirect/possible test
      relations, and missing-test guidance without mapping-source or a general
      next-step field.
- [x] Auto-discovered or explicitly overridden Issue references produce
      structured context with candidates/selection evidence without mutating
      repository state.
- [x] When no strong reference exists, every affected GitHub repository is
      scanned for open Issues and returns repository-qualified candidate
      metadata plus query warnings for semantic Diff/module comparison.
- [x] Each affected repository scans at most 100 open-Issue metadata records;
      ordinary Agent-facing candidates are deterministically shortlisted to at
      most 10 after module/object mapping, and excluded Issue content is omitted.
- [x] English, Chinese, and mixed-language Issue titles can contribute bounded
      module/object/path signals; ordinary global shortlist filling requires a
      real signal and each affected repository receives at most one no-signal
      fallback candidate.
- [x] A unique current-PR linked/closing reference may resolve automatically for
      one affected GitHub repository. Multi-repository analysis scans every
      repository and does not apply that reference to the whole workspace;
      commit-message and branch-name references remain unresolved until semantic
      Issue-to-Diff comparison confirms them.
- [x] Every shortlisted candidate is attempted with a read-only full-body lookup;
      lookup failures remain visible and do not stop hydration of other candidates.
- [x] One complete `assess` invocation lists Issues once per affected repository,
      reuses that snapshot through module/test/risk analysis, and does not apply
      a separate five-body cutoff.
- [x] Issue scan output reports per-repository counts, shortlist and exclusion
      counts/reasons, hydration attempted/succeeded/failed counts, and protected
      strong-reference overflow without selecting from keyword rank alone.
- [x] The `assess` payload omits raw `test_inventory` while retaining
      `test_correspondence` and `risk_assessment`; the `inventory` and `suggest`
      diagnostic contracts retain their detailed inventory output.
- [x] Current-PR lookup, Issue listing, and Issue body lookup all use bounded
      timeouts; the complete GitHub analysis has a 60-second deadline.
- [x] A unique current-PR authoritative Issue skips open-Issue listing only in a
      single-affected-repository analysis and records an auditable fast-path status.
- [x] Multiple shortlisted Issue bodies use one GraphQL request, preserve
      deterministic order, and fall back with fixed limited concurrency only
      for unresolved candidates.
- [x] A timed-out or failed Issue scan reports `scan-failed`, a mixed multi-repo
      result reports `partial-scan`, and only a successful empty scan reports
      `no-candidates` / no open Issue.
- [x] Regression fixtures prove timeout warnings, concurrent failure isolation,
      final-payload reduction, and the three scan-status paths without live
      GitHub access.
- [x] The Skill explicitly marks analyzed Issue/PR/source/test/documentation
      content as untrusted evidence, and a regression fixture proves an embedded
      instruction remains inert parsed data without subprocess execution.
- [x] Content inspection rejects symbolic links, outside-repository real paths,
      and sensitive credential paths; skipped test candidates remain visible as
      warnings, CLI JSON redacts sensitive paths and common secrets, and example
      environment files remain inspectable.
- [x] The default brief includes an Issue-aware pre-test Risk Matrix with an
      evidence-backed risk floor and `unassessed` behavior when Issue context is
      missing.
- [x] Temporary Git fixtures verify committed, dirty, staged, untracked, rename,
      delete, missing-base, and dynamic child-repository behavior.
- [x] Verification confirms the analyzer leaves Git state unchanged.
- [x] `verify-install.sh` passes for source, Codex, and Claude skill copies.
- [x] A fresh clone contains non-ignored `.agents` and `.claude` Skill mirrors;
      installation is not required before native Skill discovery.
- [x] Changed discovery mirrors are omitted from assessment Diff facts while
      the editable `tools/bic-quality-kit` source remains analyzable.
- [x] Codex discovery metadata exposes a human-facing name, a 25-64 character
      short description, and a one-sentence default prompt containing the exact
      `$bic-quality-guan-ping-ce` invocation.
- [x] The root SOP Index contains one quality Skill entry that links to
      `tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/SKILL.md`.
- [x] Tests and `verify-install.sh` reject missing, inconsistent, or unsynchronized
      discovery metadata.
- [x] Real-Agent eval fixtures support paired `with_skill` and `no_skill` runs
      with identical target Git changes and fresh context for every run.
- [x] Relevant prompts require exactly one assessment invocation, unrelated
      prompts require none, and the deterministic grader reports factual and
      command-trace differences without using an old-Skill baseline.

## Notes

- The MVP analyzes the checked-out `HEAD`. Arbitrary remote PR lookup is deferred.
- Repository discovery is limited to immediate children of `BIC-meta`; deeper
  nested repositories can be added later through explicit discovery settings.
- Local refs are authoritative for the MVP. The analyzer must not fetch remotes.

## Phase-One Multi-language Extension (2026-07-22)

The read-only assessment now requires a pinned `ast-outline` runtime so changed
objects can be attributed from Diff hunks across Python, JavaScript, JSX,
TypeScript, and TSX. The Skill bootstraps that runtime into a BIC-owned user
cache on first use; it never installs into the repository or the user's global
PATH. A missing or incompatible required analyzer stops the assessment instead
of silently producing a reduced file-level brief.

The assessment must map changed backend routes, frontend API clients, hooks,
stores, components, shared contracts, and browser-test scenarios into bounded,
auditable user-journey evidence. Pytest, JavaScript unit/component tests,
Playwright E2E tests, and CDP/browser scripts remain separate evidence layers.
Static presence is not runtime verification, and a browser script without a
machine-checkable outcome cannot clear a test gap.

The phase-one output adds a machine-readable Test Execution Manifest for a
future phase-two executor. It records the exact local change fingerprint,
selected test assets, relation strength, affected objects and journeys,
environment prerequisites, state-mutation requirements, and controlled command
hints. Phase one still does not start services, reset data, execute project
code, or execute tests.

### Extension Acceptance Criteria

- [x] First use installs the pinned `ast-outline` runtime into an isolated
      BIC-owned cache with concurrency safety and a stable JSON-schema probe.
- [x] Analyzer installation or schema failure prevents a complete brief; no
      Python-only or file-level fallback is reported as complete.
- [x] A canonical local-base-to-current Diff supplies one consistent old/new
      line coordinate system while preserving committed/staged/unstaged/
      untracked provenance separately.
- [x] Python, JavaScript, JSX, TypeScript, and TSX modified files expose the
      smallest enclosing changed function, method, class, component, hook,
      store/action, route, API client, or module-scope declaration.
- [x] Deleted and renamed declarations are attributed from the local base
      without fetch or checkout.
- [x] Exact changed objects and routes improve module, Issue, and test
      correspondence inputs without changing the bounded 100-to-10 Issue
      discovery contract.
- [x] Playwright and CDP/browser scenarios report actions, machine-checkable
      assertions, disabled/manual-only state, and affected user journeys as
      distinct evidence from pytest and frontend unit/component tests.
- [x] The public assessment includes a versioned Test Execution Manifest and a
      local change fingerprint while executing no command hint or test.
- [x] Source repositories remain unchanged; only the explicitly documented
      analyzer cache and ephemeral system-temp files may be written.
- [x] Unit, integration, install, Skill validation, and agent-eval gates pass
      after source/mirror synchronization.
