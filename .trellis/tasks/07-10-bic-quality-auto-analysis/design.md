# Technical Design

## Boundaries

The implementation remains inside `tools/bic-quality-kit`. It reads Git and
filesystem metadata only. It does not execute discovered commands or tests.
Installed copies under `.agents/skills` and `.claude/skills` remain generated
copies of the source skill.

## Analysis Pipeline

The pipeline is organized into a Diff-driven sequence: workspace discovery,
change-set collection, affected-repository Issue candidate collection, module
inference, changed-object extraction, semantic Issue analysis, test-asset
inspection, test-correspondence analysis, and pre-test risk assessment.
Every stage emits structured JSON with evidence so later stages do not need to
re-scan or invent facts.

## Repository Discovery

The workspace root remains marker-based. The root repository and immediate
child directories are probed with `git rev-parse --show-toplevel`. Results are
deduplicated by resolved top-level path. Known generated and dependency
directories are excluded. When a child repository is discovered, the root
repository's untracked placeholder for that child is suppressed.

## Change Set

Each repository resolves a base independently. Resolution order is: explicit
base, CI base environment, `origin/main`, `main`, `origin/master`, `master`.
Explicit bases never silently fall back. Automatic resolution may continue down
the candidate list. A valid base is converted to a merge base with `HEAD` and
the committed range is read with NUL-delimited `git diff --name-status` output.

Committed, unstaged, staged, and untracked records are merged by repository and
path. Each record retains `change_sources`, `change_types`, and `old_path` for
renames. Repository metadata records branch, head, base, merge base, resolution
source, and warnings.

## Issue Context

Issue collection is Diff-driven. After change collection identifies repositories
with `change_count > 0`, the collector lists open Issues for each corresponding
GitHub repository. It retains repository, number, title, labels, URL, and update
time for bounded semantic analysis. Current-PR links, PR closing text, Diff
commit references, and a strong `issue-123` branch pattern remain authoritative
when uniquely present. Without a strong link, the Skill compares candidates
with mapped modules and changed objects and reads only plausible Issue bodies.
An explicit number, URL, or `owner/repo#number` overrides discovery. Query
failure or ambiguity remains visible rather than producing a guessed Issue.

## Repository and Module Mapping

Repository identity comes from the discovered Git worktree and is not inferred
from file names. Explicit taxonomy rules remain authoritative for known BIC
business modules such as Agent SSE, Lab MQ, and shared contracts.

When no explicit rule matches, the analyzer derives a structural module from the
repository-relative source tree. It recognizes source roots such as `app`,
`src`, `packages`, `services`, `lib`, and `bic_shared_types`, then preserves the
nearest stable module path (for example `app/inference`, `app/api/routers`, or
`src/pages/chat`). It must not translate generic path words into invented
business capabilities.

Mappings expose `module_scope`, `mapping_source` (`explicit`, `structural`, or
`unmapped`), and path evidence. Direct cross-repository impact is the factual
condition that changed files exist in multiple repositories. The analyzer does
not output risk scores or impact labels. `mapping_source` remains raw diagnostic
metadata and is not printed in the default brief.

## Changed Objects

Changed-object extraction reads current source files and local Git diff facts
without importing project modules. Python uses the standard-library AST;
JavaScript and TypeScript use bounded syntax patterns for imports, exports,
tests, and assertions. Unsupported or deleted files retain file-level facts so
the report never invents symbols.

## Test Discovery and Correspondence

The scanner collects actual test files plus pytest, JavaScript test-runner, and
Playwright configuration. It reads `pyproject.toml` and `package.json` only for
framework and command hints. Empty directories do not count as test assets.
Local tool-state directories and installed skill copies are excluded. A child
Git repository discovered independently is scanned only under its own identity,
not again as part of the root repository.

Concrete test files are inspected for imports, referenced identifiers, test and
scenario names, assertions, and skip/xfail/todo state. The analyzer never
imports test modules or invokes a test runner.

Explicit test inventory entries add semantic module relations, especially for
cross-repository E2E flows. Automatic correspondence uses direct imports or
symbol references first, then safe one-hop or explicit relations, then
scenario/path candidates. Filename or directory similarity alone never proves
that a changed behavior has a test.

Relation facts and add-test guidance are separate. Each affected repository and
module retains its changed files and objects plus directly related tests,
indirectly related tests, and possible candidates. Missing active assertions
produce a concrete recommendation to add or strengthen tests. Only an active
object-specific direct, safe-one-hop, or explicitly object-mapped test with an
assertion produces a statement that no obvious static gap was found. A
module-only configured relation or broad scenario candidate cannot clear every
changed object. None of these conclusions proves execution or pass/fail.

## Compatibility

Existing diff and module keys are retained. The old confidence/evidence-based
test recommendation keys are replaced because they represented a misleading
coverage contract rather than compatibility-worthy behavior.
Shell wrappers forward CLI arguments. Default invocation requires no new input.
The Skill continues to produce exactly one `BIC Quality Brief`.
The default brief restores separate module mapping, direct/indirect/possible
test-correspondence, and missing-test sections. `mapping_source` remains raw
diagnostic metadata, and no general next-step recommendation is emitted.
The brief also includes affected-repository Issue candidates and a pre-test Risk
Matrix. Deterministic rows establish a risk floor; semantic
Issue-to-Diff-to-test alignment may raise but not lower it. Missing or
non-unique Issue context makes overall risk `unassessed`.

## Rollback

All behavior is contained in the kit source and installed copies. Reverting the
task changes restores the previous hard-coded collector. No database or runtime
state migration is involved.
