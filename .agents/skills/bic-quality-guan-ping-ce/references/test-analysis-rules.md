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
disabled state, and target-linked machine checks separately. Each test case is
an independent browser scenario, even when names or URL literals repeat. A
request-result assertion, page/locator matcher, or explicit CDP failure
condition may be a machine check. A bare `expect(value)` without a matcher,
unrelated `expect(true)`, screenshot, console trace, wait, click, or successful
script completion is not one. Multiline `expect`, `expect.soft`, and
`expect.poll` retain their matcher and target linkage.
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

Classify assertion evidence independently from direct/indirect reachability:

- `object-asserted`: the case directly consumes the changed object's result or
  asserted state;
- `behavior-asserted`: the case enters through a public object, statically
  reaches the changed helper, and its substantive result/state assertion names
  the same behavior;
- `contract-asserted`: the case pins only a declaration contract such as route
  method/path/status, without exercising its downstream behavior;
- `related-only`: an import, call chain, module relation, or assertion exists,
  but no changed-object/behavior assertion is established.

Only `object-asserted` and `behavior-asserted` close an object gap.
`contract-asserted` remains visible evidence but generates a focused
strengthening recommendation. `related-only` stays diagnostic and must not be
shown as proof in the public matrix.

For a large changed function/class whose diff touches only a small part of its
line range, require the relevant case/assertion to overlap identifiers from the
changed lines. A test of an unrelated branch in the same container does not
close the gap.

When a broad frontend store factory is selected only as the outer container of
a changed store action, do not emit a second container-level gap after that
exact action already has object-level evidence.

## User-journey graph

Build bounded reverse-import paths from changed backend routes and shared
contracts through frontend API clients, hooks/stores, components/pages, route
configuration, and explicit browser scenarios. Package names from contained
`package.json` files may resolve shared-contract imports across repositories.
Every edge must retain a concrete import or literal as evidence. Do not infer a
business journey from repository co-change, filename similarity, or an action
without an outcome check.

Emit completed `paths` and terminal `partial_paths`, including an anchor-only
`no-static-bridge` partial when no edge exists. Preserve dead branches even when
the same anchor has another completed path. The graph never clears an
object-level gap and never proves that runtime wiring works. The Agent-facing
node list contains only nodes referenced by an edge or completed/partial path;
the complete source scan count remains visible without serializing disconnected
scan-only nodes.

For browser guidance, keep the changed backend route as the behavior source but
place the suggested Playwright test in the browser-owning repository. When a
completed static path reaches an existing scenario, strengthen that exact
scenario file. Otherwise, if a partial path reaches a frontend repository,
create the suggested `tests/*.spec.ts` target there. Fall back to the source
repository only when no frontend or browser repository can be identified.

## Add-test guidance

Keep correspondence facts separate from the need to add tests:

- Recommend a new test when changed behavior has no active direct or safe
  indirect test with a target-linked assertion.
- Recommend strengthening a test only when a concrete object-specific relation
  is assertion-free, skipped, xfailed, todo, or has an assertion that does not
  consume the changed behavior's result.
- State that no obvious static gap was found when an active direct,
  safe-one-hop, or explicitly object-mapped test contains an assertion for the
  changed object or behavior.

Before emitting `add`, check whether the source-paired test file already exists.
If it exists, emit `strengthen`. Prefer an existing source-paired test over an
alphabetically earlier module candidate. Repository behavior must target a
repository/persistence test; a service test backed by a fake repository cannot
stand in for real SQL evidence.

Broad module/scenario candidates, file-only objects, `__all__`, and possible
relations remain diagnostic search context. They neither clear an object-level
gap nor create a standalone strengthening recommendation.

Group guidance by source file and target behavior. Several related private
helpers in one file should produce one recommendation, with their symbols
listed as evidence, rather than one line per declaration. Every structured item
contains:

- `action`: `add` or `strengthen`;
- `target_behavior`;
- `test_layer`;
- `recommended_framework` and any `alternative_frameworks`;
- `existing_tests` and concrete `evidence_gaps`;
- `suggested_assertions` describing observable outcomes.

Keep guidance concise: show at most five existing weak test paths together with
`existing_test_count` and `existing_test_overflow`. The complete untruncated
relation evidence remains available in the direct/indirect correspondence
fields. Before treating a weak relation as something to strengthen, require a
concrete behavior match from the test path, case name, exact referenced
identifier, or assertion-linked object. A test that merely imports a class or
module whose declaration contains the changed method remains raw indirect
evidence; do not list a whole suite of unrelated tests as strengthening targets.
Every guidance item also names one `suggested_test_target`.

Choose the test layer from the behavior under change:

- backend route/service/repository behavior: pytest;
- frontend store/hook/API-client behavior: Vitest, optionally React Testing
  Library when component integration matters;
- frontend component behavior: Vitest plus React Testing Library;
- a user-visible frontend-to-backend journey: Playwright;
- protocol-level browser/network/console/streaming diagnostics: CDP, usually as
  an alternative or companion to Playwright rather than the default UI test.

For changed backend routes, emit separate browser-journey guidance. Strengthen a
completed static path when its browser scenario lacks a target-linked machine
check; add a Playwright journey when no completed static path exists. Suggested
assertions should cover the triggering action/request, the user-visible result,
and an important failure or reload/state transition.

Do not generate add/strengthen guidance for documentation, Skill/reference, or
planning-only paths. An existing concrete relation may still describe an
executable documentation contract. Do not exclude YAML or JSON by extension
alone because it may define runtime behavior.

## Public brief

Preserve raw module relations for diagnostics. Build a separate bounded
`public_summary` for the default brief:

- direct tests retain the strongest object/assertion-linked evidence;
- indirect tests require a concrete changed object and an explainable
  test → source entry → changed object import/reference chain;
- possible tests are grouped by changed behavior with at most three candidates
  per behavior and an explicit match reason.

The public quality matrix is behavior/object scoped, not module scoped. Each row
shows the exact changed objects, the strongest matching test case, evidence
strength, the remaining unproved behavior, and one concrete recommendation.
Never borrow a test from another changed object merely because both belong to
the same module.

Do not print raw aggregate relation counts in the default brief. Possible
candidates remain visible search clues but never count as coverage.
Do not print `mapping_source`; when a module is unmapped, say only that the
functional module is not yet identified and cite the changed files. Do not add
a general next-step recommendation field. Do not recommend tests for
documentation or planning files without an executable documentation contract.

These outcomes are not risk, priority, confidence, pass/fail, or proof of
runtime coverage. Describe the concrete behavior and assertion in natural
language.

## Execution-scope selection

The Phase 2 list is a third projection over the same static facts. It is neither
the raw relation inventory nor the display-capped public brief.

- A direct case enters `must_run` only when an active assertion is bound to the
  changed behavior or its exact contract.
- An indirect case enters `must_run` only when an active assertion is bound to
  a result reached through a concrete test → source → changed-object
  import/reference chain.
- An exact Playwright/CDP case on a completed static journey enters `must_run`
  only when it has a target-linked machine check. Other exact browser clues may
  enter `recommended`; broad token/module matches do not.
- Active asserted cases in changed test files enter `must_run` only when the
  concrete test declaration intersects a current diff hunk. Unchanged sibling
  cases in the same file are excluded.
- Deduplicate using `(repo, framework, repository-qualified path, case name)`.
  Merge the changed behaviors and relation reasons attached to that case.
- Public display limits never remove an otherwise eligible execution case, and
  raw relation volume never adds one.
- Disabled, skipped, assertion-free, unresolved, unsafe, or not-yet-created
  tests remain `not_runnable` or excluded; they are never silently counted as
  executed coverage.

Derive a concrete case command for pytest (exact file/node id), Vitest (`-t`),
and Playwright (`-g`, one worker). CDP is runnable only when the owning
repository exposes a real CDP package script. Never derive a generic CDP command
from a file name.

## Phase 2 handoff

The Phase 1 assessment emits a schema-version-2 `test_execution_manifest` but
does not execute it. It separates `must_run`, `recommended`, `not_runnable`,
and `excluded_summary`. Each entry retains repository/path, framework, one
exact selected case, changed behaviors, command source, assertion/browser
evidence, and `not-run` status.
Safely derivable commands are also represented as an argv array; consumers must
not pass a free-form hint through a shell.
The manifest is bound to repository change fingerprints. The Phase 2 executor
must reject a stale fingerprint and requires explicit `--execute`
authorization. It runs backend pytest, frontend Vitest, Playwright, and
configured CDP in that order. A required backend/frontend failure, skip, block,
or missing command stops later browser layers. Phase 2 never installs
dependencies, starts services, resets/seeds data, invokes `bic-e2e-runner`, or
queries Phoenix.
It also exposes `completed_user_journey_paths` and
`partial_user_journey_paths`; both expand the exact graph nodes/edges and remain
static `not-run` evidence with `clears_object_gap: false`.
