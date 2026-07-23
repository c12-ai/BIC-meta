# Technical Design

## Boundaries

The editable implementation remains inside `tools/bic-quality-kit`. It reads Git
and filesystem metadata only. It does not execute discovered commands or tests.
Generated mirrors under `.agents/skills` and `.claude/skills` are committed so
new clones receive native Codex and Claude discovery without an installation
step. Verification treats missing or stale mirrors as a failure; maintainers
edit only the source Skill and synchronize both mirrors before committing.
Change collection ignores the two exact mirror paths while continuing to
analyze the editable source. This prevents synchronized files from inflating
change counts, modules, test gaps, or risk evidence threefold.

Issue and PR bodies plus analyzed source, comments, tests, and ordinary
documentation are untrusted evidence, not workflow instructions. Their content
may be stored and summarized but cannot change permissions, tool selection, or
the read-only boundary. The deterministic parser treats these values as strings;
it never evaluates them or interpolates them into subprocess commands.

All repository content reads pass through one repository-containment guard. The guard
rejects symbolic links and symbolic-link path components, verifies the strict
real path remains below the discovered repository root, requires a regular
file, and excludes credential-bearing paths. Explicit user-selected Issue files
remain separate inputs and are sanitized at the output boundary. Test-like files skipped by this
guard become structured scan warnings rather than missing-test evidence. A
recursive serializer-boundary sanitizer redacts sensitive paths and common
credential forms from every CLI JSON mode. This iteration deliberately leaves
file-size, file-count, and cumulative-read budgets unchanged.

## Analysis Pipeline

The pipeline has two one-way evidence lanes followed by a lightweight reporting
pass. The technical lane performs
workspace discovery, change collection, module inference, changed-object and
journey extraction, test-asset inspection, and technical test correspondence
without consuming Issue context. The requirement lane consumes that immutable
technical context only to locate Issues and extract requirement
evidence. It cannot return exclusion filters to the technical lane.

A final scope-fusion stage takes the union of technical test candidates and
requirement-driven additions. The reporting pass then compares eligible
acceptance items with existing objects/routes/journeys/tests, records supported
Issue-to-Diff divergence, and presents grouped test guidance. It consumes the
frozen snapshot and performs no second Issue lookup, semantic search, or code
scan.

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

Issue collection is Diff-driven and staged. After change collection identifies
repositories with `change_count > 0`, `collect_issue_snapshot` first captures
current-PR links, PR closing text, Diff-commit references, and strong
`issue-123` branch references in the same immutable analysis snapshot. Exactly
one authoritative current-PR reference activates a fast path only when exactly
one affected GitHub repository exists. With multiple affected repositories,
every repository is scanned and the current-PR Issue remains repository-local;
it cannot resolve workspace Issue alignment. The snapshot otherwise lists at
most 100 open-Issue metadata records per corresponding GitHub repository.
Ordinary discovery does not scan closed Issues or hydrate timelines/comments.
Historical PR URLs supplied in conversation are background context and are not
analyzer inputs.

Module mapping and changed-object extraction run before candidate reduction.
`shortlist_issue_candidates` merges duplicate references, protects explicit and
strong association evidence, applies deterministic repository/module/object/
label ordering, preserves repository diversity, and returns at most 10 ordinary
candidates. It reports excluded counts and categorized reasons without carrying
excluded Issue titles or bodies into Agent-facing JSON. Keyword or repository
membership remains a search hint and never selects an Issue.

Explicit overrides can be selected authoritatively. A unique current-PR
linked/closing reference can be selected automatically only for a
single-affected-repository workspace. Commit-message and branch-name references
stay ahead of ordinary candidates but require later semantic confirmation. Candidate terms
support English plus bounded Chinese n-grams and project aliases. Ordinary
candidates require a module, object, changed-path, or label signal; repository
diversity may add one no-signal fallback per affected repository, but unused
shortlist capacity is not filled with unrelated recent Issues.

`hydrate_issue_candidates` attempts a read-only full-body lookup for every
shortlisted candidate. There is no second five-body selection gate. Multiple
references use one GraphQL batch request; only missing or failed batch items use
the fixed-size ordered fallback. Per-candidate failure remains visible while
other lookups continue. Strong-reference overflow
is reported as ambiguity rather than silently discarded or automatically
selected. An explicit number, URL, `owner/repo#number`, or local Issue file
continues to override discovery.

The normal Skill path uses the end-to-end assessment wrapper once and reuses the
snapshot through Issue, module, test, and risk analysis. Intermediate wrappers
remain diagnostic entry points and may perform their own standalone collection.
No persistent live-Issue cache or repository artifact is introduced.

All `gh` subprocesses have bounded timeouts and the complete GitHub analysis has
a 60-second monotonic deadline. Metadata/PR lookup and full-body lookup may use
different per-request limits, but no new request starts after the shared
deadline. GraphQL batch hydration is primary; a fixed-size thread pool with
ordered collection is only the fallback. A timeout or lookup failure becomes
candidate-local warning data and does not erase successful results.

The snapshot records a per-repository scan status in addition to counts. A
successful empty response is `succeeded` with zero candidates. A single-repository
fast-path scan is `skipped-authoritative`, never an empty result. A request error
or timeout is `failed`. The aggregate status is `failed` when every attempted
repository fails, `partial` when success and failure coexist, `succeeded` when
all attempted scans succeed, and `not-run` when no GitHub repository can be
identified. Final Issue analysis maps those states to `scan-failed`,
`partial-scan`, normal semantic review, or `no-candidates` without conflating
query failure with an empty repository.

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
Local tool-state directories and generated Skill mirrors are excluded. A child
Git repository discovered independently is scanned only under its own identity,
not again as part of the root repository.

Concrete test files are inspected for imports, referenced identifiers, test and
scenario names, assertions, and skip/xfail/todo state. The analyzer never
imports test modules or invokes a test runner.

Test-like filenames are only discovery candidates. JavaScript/TypeScript needs
a parsed `test`/`it` case. Python additionally needs a standard test directory,
an assertion, or a pytest/unittest framework signal. A candidate that cannot be
parsed may remain diagnostic metadata, but it cannot count as test evidence.
This prevents implementation modules such as `scripts/test_assets.py` from
being mistaken for pytest files solely because of names such as
`test_type_for_path`.

Explicit test inventory entries add semantic module relations, especially for
cross-repository E2E flows. Automatic correspondence uses direct imports or
symbol references first, then safe one-hop or explicit relations, then
scenario/path candidates. Filename or directory similarity alone never proves
that a changed behavior has a test.

Python test parsing also records two bounded static facts. First, it resolves
simple local `Path(__file__)` expressions used by
`importlib.util.spec_from_file_location`, then associates calls on the resulting
module alias with the exact target file and object. Second, it follows local
test-helper calls to a `subprocess.run` argv list and records only local `.py`
targets. These expressions and command strings are parsed as AST data and are
never evaluated or executed. A proven entrypoint may contribute safe one-hop
relations through its static imports; an active assertion in the originating
test case is still required to clear a gap.

Dynamic target calls carry a separate assertion-link fact. The parser marks a
target assertion-linked only when the target call is inside an assertion or
expected-exception context, or when its direct/helper return value flows into
an asserted expression. Merely placing any assertion in the same test case does
not upgrade a dynamic relation to no-obvious-gap evidence.

For command-selected Python entrypoints, safe one-hop imports are derived from
the statically reachable entrypoint functions and the imported aliases those
functions actually reference. Whole-file import presence remains diagnostic
context but cannot make a sibling command's dependency object-related evidence.

Relation facts and add-test guidance are separate. Each affected repository and
module retains its changed files and objects plus directly related tests,
indirectly related tests, and possible candidates. Missing active assertions
produce a concrete recommendation to add or strengthen tests. Only an active
object-specific direct, safe-one-hop, or explicitly object-mapped test with an
assertion produces a statement that no obvious static gap was found. A
module-only configured relation or broad scenario candidate cannot clear every
changed object. None of these conclusions proves execution or pass/fail.

Before producing add/strengthen guidance, changed objects pass a deterministic
test-applicability filter. Documentation, Skill/reference, and planning-only
paths are ineligible for new-test guidance unless a concrete existing test
relation already establishes an executable documentation contract. Runtime
configuration is not excluded by extension alone.

The complete discovered inventory is an internal intermediate for `suggest` and
`assess`. The standalone `inventory` wrapper and `suggest` diagnostic output
retain it. After `assess` derives test correspondence and risk, it removes the
raw inventory from its public payload and returns only the correspondence and
risk contracts needed by the Agent-facing final analysis.

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
Matrix. Deterministic technical rows establish a risk floor; semantic
Issue-to-Diff-to-test alignment may raise but not lower it. Missing,
non-authoritative, or ambiguous Issue provenance makes requirement alignment
`unassessed` and assessment completeness partial while preserving the known
technical risk. A unique thematic match is still non-authoritative.

## Scope Fusion

`technical_scope` is immutable after Diff/object/journey/test analysis.
`requirement_scope` may contribute source provenance, eligible acceptance
items, and additional test candidates. `effective_scope` is their union. A
machine-checkable invariant records technical candidate identities before and
after fusion and fails validation if any disappear.

Each eligible acceptance item is reported on three independent axes: scope
(`in-scope`, `adjacent`, `out-of-scope`, `cannot-determine`), implementation
(`static-evidence-found`, `static-evidence-missing`, `cannot-verify`), and test
status (`asserted`, `weak-or-disabled`, `missing`, `not-applicable`,
`cannot-verify`). Matching is evidence-bearing and conservative: positive
implementation claims cite an exact changed object/route/path/journey, and every
in-scope item cites an exact test/assertion or an explicit missing-test fact.
Explicit source text may establish out-of-scope; absence of evidence alone does
not. Thematic candidates receive no acceptance-item comparison.

The report groups additional guidance as `requirement-traced`,
`technical-regression`, and `exploratory`. Their union is the effective set,
and technical-regression guidance is immutable under every Issue outcome. Since
this phase runs no tests, it never calls an item satisfied, passed, complete, or
verified.

## Rollback

All behavior is contained in the kit source and committed mirrors. Reverting the
task changes restores the previous hard-coded collector. No database or runtime
state migration is involved.

## Multi-language Analyzer Runtime

`ast-outline` is a required phase-one analyzer pinned by repository-owned
runtime metadata. A bootstrap module installs it under a lock, cleans up
incomplete installs, and writes its completion marker last into
`~/.cache/bic-quality/tools/ast-outline/<version>/`, guarded by an inter-process
lock. The Skill invokes the absolute managed executable and validates the
machine JSON envelope and schema before reading any project content. It does
not call the tool's setup helpers, alter global PATH, or update agent config.

Changed-object mapping consumes `outline --json` declarations and preserves
the upstream native kind alongside BIC classifications. Current files are
parsed in place only after repository containment checks. Old Git blobs for
deleted/renamed content are parsed through an ephemeral file outside the
workspace with the original extension. Parser failure on an affected supported
source file makes analysis incomplete rather than silently lowering precision.

Change provenance and attribution coordinates are separate contracts. Existing
committed/staged/unstaged/untracked facts remain visible, while symbol mapping
uses one canonical local-base-to-current-tree Diff so overlapping changes do
not mix incompatible line coordinates.

## User Journeys and Browser Evidence

Bounded static edges connect backend routes and shared contracts to frontend
API clients, hooks/stores, components/pages, and explicit browser scenarios.
Framework adapters keep backend tests, frontend unit/component tests,
Playwright E2E, and CDP/browser scripts separate. Actions alone do not prove a
journey; a browser asset contributes positive static evidence only when it has
a machine-checkable DOM, network, console, or explicit pass/fail condition.

## Phase-Two Handoff

Phase one emits a versioned Test Execution Manifest in the assessment JSON. The
manifest fingerprints every repository's local HEAD/base and dirty/untracked
state, identifies selected tests and user journeys, and records environment and
state-mutation prerequisites. Commands are inert data and must be revalidated
by the future executor. No phase-one code starts services, resets datasets, or
executes a command from the manifest.

The manifest selection boundary is behavior evidence, not the raw relation
inventory. One shared eligibility predicate feeds both the public test
correspondence and the execution manifest: the public view applies bounded
display limits after eligibility, while the manifest retains every eligible
case. Candidate identity is `(repo, framework, path, case)` and merges changed
behaviors and module references from duplicate relations.

Direct behavior-asserted and route-contract cases are must-run. Indirect cases
are must-run only when they are behavior-asserted through an explainable
result-linked import/reference chain. A completed browser path may be must-run
only when the exact selected scenario has a target-linked machine check.
Configured-module-only, import-only, possible, disabled, and assertion-free
relations remain diagnostic. A changed test file contributes only active
asserted test declarations intersecting a diff hunk; unchanged sibling cases
remain excluded. Suggested tests that do not yet exist remain planning gaps
rather than executable commands.

The separately authorized executor consumes the frozen assessment rather than
rerunning issue or correspondence analysis. It recomputes the same local change
fingerprint, validates repository-contained paths and allowlisted structured
argv, and runs layers in this order:

1. pytest backend/service cases;
2. Vitest frontend unit/component cases;
3. targeted Playwright scenarios with one worker;
4. repository-configured CDP diagnostics.

The executor never uses a shell command string. It does not install
dependencies, start the live bench, reset/seed/migrate/clean data, dispatch
`bic-e2e-runner`, or query Phoenix. Foundation-layer failure, skip, block, or
unresolved required command stops browser execution. Results are mapped back to
changed behavior and retain explicit passed/failed/skipped/blocked/not-run
states.

## Real-Agent Evaluation

Agent evals live outside the runtime Skill under `tools/bic-quality-kit/evals`.
Every run creates a fresh temporary Git workspace. The `with_skill` workspace
contains the current `.agents` Skill and SOP route; the `no_skill` workspace
contains the same business Diff and prompt without either discovery surface.
Codex runs ephemerally with user config ignored and a read-only sandbox.

The grader uses JSONL command events and normalized final-answer facts. It
checks the assessment wrapper count, forbidden commands, required warnings and
`unassessed` states, repository/module/Issue/test facts, and paired fact-score
deltas. The no-Skill result is comparative evidence rather than a gate. An old
Skill is intentionally excluded from routine evaluation.
