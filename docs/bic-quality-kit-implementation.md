# BIC Quality Skill Kit Implementation Notes

This document records how the current-phase BIC Quality Skill Kit was implemented.

## 1. Kept The Scope To Read-only Analysis

The implementation follows the current MVP boundary: the skill performs only read-only quality analysis. It does not execute tests, start services, reset data, kill ports, modify business code, or invoke E2E.

The long-term product goal is still preserved in the skill language, but the shipped implementation focuses on:

- dynamically discovering BIC repositories;
- reading committed branch changes relative to a local base plus worktree changes;
- locating every changed file in its discovered repository and module;
- deriving stable structural modules when explicit BIC rules are absent;
- discovering concrete test assets and inspecting imports, references,
  scenarios, assertions, and disabled state;
- relating changed source objects to existing tests within each repository and
  functional module;
- reporting tests to add or strengthen without calculating coverage rates;
- producing one `BIC Quality Brief`.

## 2. Created The Skill Kit Layout

The source kit was added under:

```text
tools/bic-quality-kit/
```

The skill source lives at:

```text
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/
```

This keeps the committed source separate from locally installed Claude/Codex skill copies.

## 3. Added The Skill Entry Point

`SKILL.md` defines when the skill should trigger and the exact read-only workflow.

It tells the agent to:

- collect quality context;
- map diff to scope taxonomy;
- scan open Issues in the affected repositories, prioritize strong links, and
  analyze plausible candidates against changed modules and objects;
- inspect test inventory;
- generate an evidence-backed pre-test Risk Matrix;
- produce one structured `BIC Quality Brief`;
- avoid test execution and environment mutation.

## 4. Added Progressive Reference Files

Reference files were placed under `references/` so the skill can load only what it needs:

```text
workspace-map.md
scope-taxonomy.md
test-analysis-rules.md
risk-model.md
deliverables.md
```

This keeps `SKILL.md` concise while still preserving project-specific rules.

## 5. Added Repository And Module Mapping

Repository identity comes from Git discovery. Explicit rules remain authoritative
for known BIC modules. Other source files retain repository-relative structural
modules, and files without a stable source root remain visible as unmapped.
The public JSON exposes `affected_repositories`, `modules_by_repository`, and
the factual `direct_cross_repository` boolean.

The analysis chain is:

```text
changed file -> discovered repository -> explicit or structural module
      -> affected-repository Issues -> changed object -> test correspondence
      -> pre-test Risk Matrix
      -> missing-test guidance
```

The machine-readable config is:

```text
config/scope-taxonomy.yaml
```

It is JSON-compatible YAML so the scripts can parse it without external dependencies.

## 6. Added Test Correspondence Analysis

Optional semantic test relations are represented in:

```text
config/test-inventory.yaml
```

Each entry declares:

- test id;
- repo;
- type;
- path patterns;
- command hint;
- related modules.

The scripts discover concrete Python and JavaScript/TypeScript test files,
runner configuration, and command hints. Concrete test files are inspected for
imports, referenced objects, scenarios, assertions, and disabled state without
importing or executing project code.

Local tool state (`.agents`, `.claude`, `.codex`, and `.trellis`) is excluded
from test discovery. Independently discovered child Git repositories are also
excluded from the root repository scan and analyzed once under their own
repository identity.

The inventory adds project-specific `relates_modules` relationships; it is not
the only source of test knowledge and never proves that tests pass. Relation
identity is repository-qualified. `relates_modules` targets the entry's own
repository; explicit cross-repository targets use
`relates_repository_modules` objects.

Test relation and add-test need are reported separately. Direct and safe
indirect relations describe facts. Possible candidates remain visible without
being treated as coverage. Changed objects with no active related assertion
produce a recommendation to add a test; disabled, assertion-free, or
object-specific filename candidates produce a recommendation to strengthen
tests. Broad module/scenario candidates and module-only configuration do not
clear every changed object.

## 7. Added Issue-aware Pre-test Risk Assessment

`issue_context.py` runs after change collection has identified affected
repositories. It scans open Issues in each affected GitHub repository and keeps
their repository, number, title, labels, URL, and update time as candidate
metadata. Current-PR links, PR/commit closing text, and a strong `issue-123`
branch-name pattern remain higher-priority association evidence. Without a
strong link, the Skill compares candidates with modules and changed objects,
then reads only plausible Issue bodies. An explicit Issue remains an override.
Failed queries and ambiguous candidates remain visible and prevent a guessed
overall risk conclusion.

`risk_assessment.py` combines Issue availability, affected repositories/modules,
configured contract/state boundaries, changed-object attribution, and static
test evidence. It emits a deterministic risk floor and matrix rows. The final
Skill adds one semantic alignment row per Issue acceptance item; semantic review
may raise but cannot lower the deterministic floor.

This is a pre-test matrix. It does not execute tests or represent residual
release risk.

## 8. Added Read-only Scripts

The following script wrappers were added:

```text
scripts/collect-quality-context.sh
scripts/detect-impact-scope.sh
scripts/inspect-test-inventory.sh
scripts/suggest-test-scope.sh
scripts/assess-risk-matrix.sh
```

They call a dependency-free Python analysis pipeline:

```text
scripts/quality_context.py     # orchestration and CLI
scripts/issue_context.py       # GitHub/local Issue collection
scripts/risk_assessment.py     # deterministic pre-test risk floor
scripts/test_assets.py         # test discovery and per-test facts
scripts/symbol_extraction.py   # changed objects and source references
scripts/test_relations.py      # direct/indirect/possible correspondence
```

The helper dynamically discovers the root and immediate child Git repositories.
For each repository it resolves a local base, reads
`merge-base(base, HEAD)..HEAD`, merges unstaged, staged, and untracked changes,
then performs module mapping, changed-object extraction, and test
correspondence analysis. It never fetches or checks out refs.

## 9. Added Install And Verify

`install.sh` installs the skill into local project skill locations:

```text
.agents/skills/bic-quality-guan-ping-ce
.claude/skills/bic-quality-guan-ping-ce
```

`verify-install.sh` checks required files, validates JSON-compatible config, and runs every read-only script.

It also runs temporary multi-repository Git fixtures covering committed and
worktree changes, rename/delete, missing bases, dynamic repositories, scope
inference, test discovery, recommendation isolation, and read-only Git state.

The verification script also checks that source and installed scripts resolve `workspace_root` back to `BIC-meta`. This prevents installed skill copies under `.agents/skills` or `.claude/skills` from silently analyzing the wrong parent directory.

## 10. Added User Documentation

`README.md` explains install, usage, read-only boundaries, and direct script debugging commands.

The intended user prompt is:

```text
用 BIC quality 看下当前 diff
```

Users may optionally provide a base through conversation, for example:

```text
用 BIC quality 看当前分支相对 main 的 diff
```

The Skill translates this to `--base-ref main`; `HEAD` remains the checked-out
branch. Automatic base selection remains the default.

The expected output is one structured report:

```text
BIC Quality Brief
- Change Set
- Issue Context
- Module Mapping
- Test Correspondence
- Risk Matrix
- Missing Tests
```

The raw JSON retains `mapping_source` for diagnostics, but the default brief
does not print it. Direct/indirect/possible relations remain visible as separate
test-correspondence fields, possible candidates never count as coverage, and no
general next-step recommendation is added. The static-analysis limitation is
stated once at the end.

## 11. Current Acceptance Criteria

The current implementation is considered ready when:

- the skill source exists under `tools/bic-quality-kit/skill/bic-quality-guan-ping-ce`;
- config files parse without dependencies;
- repositories and concrete test assets are discovered without hard-coded repo lists;
- the default change set includes committed and worktree changes;
- module output preserves repository identity and test conclusions cite concrete
  changed objects, imports/references, scenarios, assertions, or explicit
  relations;
- generated skill copies, backups, and separately discovered child repositories
  are not duplicated as root-repository test assets;
- test conclusions separate tests to add, tests to strengthen, and modules with
  no obvious static gap without confidence or priority labels;
- the default brief shows module evidence and direct/indirect/possible test
  correspondence without `mapping_source` or a general next-step field;
- open Issues are scanned read-only for every affected repository, strong
  association evidence remains prioritized, and ambiguous semantic candidates
  yield `unassessed` rather than guessed risk;
- the pre-test Risk Matrix binds every row to Issue, Diff, and test evidence and
  never claims that tests ran or passed;
- scripts run without mutating project state;
- install script can sync the skill into Claude/Codex project skill paths;
- verification script passes;
- the skill can support a read-only diff quality analysis conversation.

## 12. Review Hardening

During implementation review, several issues were tightened:

- Workspace root detection was changed from fixed parent traversal to marker-based discovery using `CLAUDE.md` and `Production-PRD.md`, with optional `BIC_WORKSPACE_ROOT` override.
- Installed skill scripts are now verified, not only source scripts.
- Local runtime noise such as `.phoenix/**`, `artifacts/**`, and `__pycache__` is ignored during changed-file analysis.
- `agent/session` was added as a first-class module for `BIC-agent-service/app/session/**`.
- Agent database mapping was expanded to cover `app/data/**` and `app/repositories/**`.
- Documentation and test-only modules do not create misleading test gaps.
- Repository discovery is dynamic and bounded to immediate Git children of `BIC-meta`.
- Diff collection preserves committed, worktree, staged, untracked, rename, and delete evidence per repository.
- Module mapping distinguishes explicit, structural, and unmapped evidence without translating generic path words into business semantics.
- Test discovery requires concrete files or configuration; empty directories do not count as coverage evidence.
- Test correspondence uses direct imports/references, safe indirect or explicit
  relations, and possible scenario/path candidates. Repository names, common
  directories, test types, and unrelated modules cannot clear real gaps.
