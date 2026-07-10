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
- Do not calculate or expose high/medium/low risk levels or duplicate impact
  labels. Repository, module, test evidence, and next-step verification are the
  complete MVP contract.
- Discover concrete test files, test directories, framework configuration, and
  command hints automatically for Python and JavaScript/TypeScript repositories.
- Treat `test-inventory.yaml` as an explicit semantic override instead of the
  only source of test knowledge.
- Extract changed source objects where possible, including Python functions and
  classes plus JavaScript/TypeScript exports, components, stores, routes,
  events, and types. Fall back to changed-file facts when a language cannot be
  parsed safely.
- Analyze test correspondence per `(repo, module_scope)`: direct code
  references, safe one-hop or explicitly configured relations, and weaker
  scenario/path candidates must remain distinguishable without confidence
  scores.
- Separate relation facts from the need to add tests. A changed object with no
  object-specific test relation needs a new test. Disabled, assertion-free, or
  object-specific filename candidates need strengthening. Active direct,
  safe-one-hop, or explicitly object-mapped tests with assertions have no
  obvious static gap. Module-only and scenario-only candidates remain visible
  but do not clear an object-level gap.
- Report add-test guidance as natural-language `add`, `strengthen`, and
  `no-obvious-gap` sections, not risk, priority, confidence, or evidence labels.
  Never equate discovered test assets with passing tests or proven coverage.
- Preserve the current read-only boundary: no tests, services, resets, process
  control, Git fetch/checkout, or business-code modification.
- Keep source and installed Claude/Codex skill copies synchronized.

## Acceptance Criteria

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
- [x] No analyzer or report output contains path-derived risk levels or duplicate
      impact labels.
- [x] An unconfigured path such as `BIC-model-service/app/inference/pipeline.py`
      maps to repository `BIC-model-service` and structural module `app/inference`,
      not to a guessed generic capability.
- [x] Concrete pytest, unit-test, and Playwright/Vitest/Jest assets are discovered
      from actual files and configuration.
- [x] Test files expose imports/references, test cases, assertions, and disabled
      state without importing or executing project code.
- [x] Changed source files expose deterministic symbol facts where supported and
      preserve a file-level fallback where not supported.
- [x] Every affected `(repo, module_scope)` reports changed files/objects,
      directly or indirectly related tests, possible candidates, and concrete
      missing-test guidance.
- [x] Add-test guidance distinguishes tests to add, tests to strengthen, and
      modules with no obvious static gap without emitting risk, confidence,
      priority, or evidence labels.
- [x] Same-name paths in different repositories remain isolated, and deliberate
      cross-repository test relations require an explicit repository-qualified
      declaration.
- [x] The public test-analysis contract does not contain `coverage_gaps`,
      `coverage_unconfirmed`, `evidence_type`, or confidence fields.
- [x] Temporary Git fixtures verify committed, dirty, staged, untracked, rename,
      delete, missing-base, and dynamic child-repository behavior.
- [x] Verification confirms the analyzer leaves Git state unchanged.
- [x] `verify-install.sh` passes for source, Codex, and Claude skill copies.

## Notes

- The MVP analyzes the checked-out `HEAD`. Arbitrary remote PR lookup is deferred.
- Repository discovery is limited to immediate children of `BIC-meta`; deeper
  nested repositories can be added later through explicit discovery settings.
- Local refs are authoritative for the MVP. The analyzer must not fetch remotes.
