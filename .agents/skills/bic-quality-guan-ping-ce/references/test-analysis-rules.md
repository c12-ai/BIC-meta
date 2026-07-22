# Test Correspondence Rules

The analyzer answers whether existing tests correspond to changed behavior and
which tests appear to be missing. It never executes project code or test
commands and does not calculate coverage percentages.

## Identity and explicit relations

Every relation keeps the pair `(repo, module_scope)`. `relates_modules` applies
only to the inventory entry's own repository. A deliberate cross-repository
relationship must use `relates_repository_modules` with explicit `repo` and
`module_scope` targets. Equal module or path names in different repositories
are independent.

Configured relations add business or E2E meaning that static imports cannot
show. They do not prove that a concrete test exists, contains an assertion,
runs, or passes.

An entry may add `relates_objects` when it deliberately maps to named changed
objects. Cross-repository targets may add an `objects` list. A module-only
relation remains useful context but cannot clear an object-level missing-test
recommendation.

## Test assets

Discover concrete Python and JavaScript/TypeScript test files plus runner
configuration and command hints. Empty directories are not assets. Configuration
and commands describe how tests may be run later; they are never test evidence.

Exclude generated/local tool state such as `.agents`, `.claude`, `.codex`, and
`.trellis`, including committed discovery mirrors and backups. Analyze the
editable source under `tools/bic-quality-kit` instead. When the workspace
root contains independently discovered child Git repositories, scan each child
under its own repository identity and do not scan it again as part of the root
repository.

Treat a test-like filename as a discovery candidate, not test evidence. Inspect
the candidate as text or syntax trees. JavaScript/TypeScript requires at least
one parsed `test`/`it` case. Python requires a parsed `test_*` case plus either a
standard test directory, an assertion, or a pytest/unittest framework signal.
Keep an unparseable candidate diagnostic-only; an implementation module does
not become a test because its filename or helper function starts with `test_`.
Record imports, referenced identifiers, test/describe names, assertions, and
skip/xfail/todo state without importing the file. A disabled but structurally
valid test remains a test asset.

Treat Playwright and CDP as browser evidence, not merely JavaScript tests.
Record navigation/input actions, DOM/network observations, scenario names,
disabled state, and machine-checkable assertions separately. A screenshot,
console trace, wait, click, or successful script completion is not an assertion.
A standalone CDP script may be a `browser-scenario` search asset even when it is
not a runner test; without an active assertion it cannot clear a test gap.

Before reading content, reject symbolic links, any path component implemented as
a symbolic link, files whose resolved path leaves their discovered repository,
and credential-bearing paths such as live `.env` variants, credential stores,
private-key files, and repository-root secret directories. Keep skipped
test-like candidates in `scan_warnings`; they are incomplete inspection evidence
and cannot prove either correspondence or absence. Example/template environment
files remain eligible when they are ordinary repository artifacts.

Before emitting CLI JSON, redact sensitive paths, private-key blocks, common
credential assignments, bearer credentials, credential-bearing URLs, and known
token formats. Redaction happens only at the output boundary so internal Issue
and Diff matching can retain its evidence while secrets do not enter the Agent
context.

## Correspondence

Changed objects come from canonical base-to-current diff hunks intersected with
the pinned `ast-outline` declaration ranges. Prefer the smallest qualified
declaration, so a changed method does not collapse to its class. Analyze old-side
base content for deletions and renames. Route decorators belong to their
function/route declaration. Changes outside any declaration are `module-scope`.
Unsupported file types remain changed-file objects and are never represented as
invented language symbols.

- Direct: an active test imports or references a changed file or object. For
  Python, this also includes a local file resolved through
  `importlib.util.spec_from_file_location` or a local `.py` entrypoint passed to
  `subprocess.run`, including through a local test helper.
- Indirect: a test imports a local source entry that imports/references the
  changed object, or an explicit inventory relation links the test to the
  changed module/object.
- Possible: scenario text, meaningful filename tokens, or structural proximity
  suggests relevance but no code relation is established.

Filename or directory similarity alone never establishes coverage. Repository
names and generic directories such as `src`, `tests`, `stores`, `api`, and
`services` cannot create a direct relation.

Resolve only a small static subset of `Path(__file__)`, parent, join, and local
helper expressions. Never evaluate an expression or execute a discovered
target. When an asserted test invokes a local Python entrypoint with a literal
command, follow only that command's selected branch and the statically reachable
local functions/constants. Restrict safe one-hop imports to imported aliases
actually referenced by that reachable branch; a whole-file import used only by
a sibling command is not test evidence. A directly called dynamic-module
function may also establish relations to its statically reachable local helpers.
Do not mark unselected command branches or unrelated same-file objects as tested.

Keep target reachability separate from assertion linkage. A target call clears
a gap only when it occurs inside an assertion or expected-exception context, or
when its direct/helper return value flows into an asserted expression. An
unrelated assertion such as `target(); assert True` retains the relation but
requires strengthening.

## Add-test guidance

Keep correspondence facts separate from the need to add tests:

- Recommend a new test when a changed object has no active direct or indirect
  test with an assertion.
- Recommend strengthening a test when an object-specific relation is
  assertion-free, skipped, xfailed, todo, or based only on a matching file.
- State that no obvious static gap was found when an active direct,
  safe-one-hop, or explicitly object-mapped test contains an assertion for the
  changed object or behavior.

Broad module/scenario candidates remain useful search context but do not clear
an object-level gap.

Do not generate add/strengthen guidance for documentation, Skill/reference, or
planning-only paths. An existing concrete relation may still describe an
executable documentation contract. Do not exclude YAML or JSON by extension
alone because it may define runtime behavior.

## Public brief

Report module mapping, direct relations, safe indirect relations, possible
candidates, relation evidence, and missing-test guidance as separate fields.
Possible candidates remain visible search clues but never count as coverage.
Do not print `mapping_source`; when a module is unmapped, say only that the
functional module is not yet identified and cite the changed files. Do not add
a general next-step recommendation field. Do not recommend tests for
documentation or planning files without an executable documentation contract.

These outcomes are not risk, priority, confidence, pass/fail, or proof of
runtime coverage. Describe the concrete missing object or scenario in natural
language.

## Phase 2 handoff

The assessment emits a `test_execution_manifest` but does not execute it.
Direct and safe-indirect candidates are required candidates; possible relations
remain optional. Each entry retains repository/path, framework, selected cases,
command source, prerequisites, assertion/browser evidence, and `not-run` status.
Safely derivable commands are also represented as an argv array; consumers must
not pass a free-form hint through a shell.
The manifest is bound to repository change fingerprints. A separate executor
must reject a stale fingerprint and obtain distinct authorization for test
execution and for any state-changing setup or cleanup.
