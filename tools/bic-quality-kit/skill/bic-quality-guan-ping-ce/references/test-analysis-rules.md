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
`.trellis`, including installed skill copies and backups. When the workspace
root contains independently discovered child Git repositories, scan each child
under its own repository identity and do not scan it again as part of the root
repository.

Inspect concrete test files as text or syntax trees. Record imports, referenced
identifiers, test/describe names, assertions, and skip/xfail/todo state without
importing the file.

## Correspondence

- Direct: an active test imports or references a changed file or object.
- Indirect: a test imports a local source entry that imports/references the
  changed object, or an explicit inventory relation links the test to the
  changed module/object.
- Possible: scenario text, meaningful filename tokens, or structural proximity
  suggests relevance but no code relation is established.

Filename or directory similarity alone never establishes coverage. Repository
names and generic directories such as `src`, `tests`, `stores`, `api`, and
`services` cannot create a direct relation.

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
