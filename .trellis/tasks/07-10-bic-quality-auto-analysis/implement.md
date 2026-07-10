# Implementation Plan

## 1. Repository and Diff Collection

- Replace the hard-coded repository list with bounded dynamic discovery.
- Add per-repository base resolution and comparison metadata.
- Parse NUL-delimited name-status output for committed, unstaged, and staged
  changes; merge untracked files and preserve all sources.
- Forward `--base-ref` and `--worktree-only` through all wrappers.
- Suppress root-level placeholders for discovered child repositories.

Validation: temporary Git repositories must demonstrate committed, dirty,
staged, untracked, rename, delete, missing-base, and child-repository behavior.

## 2. Repository and Module Mapping

- Migrate explicit taxonomy from `capability_scope` plus risk metadata to a
  single `module_scope` for known BIC business modules.
- Remove risk scores, generic keyword-to-capability inference, and duplicate
  impact labels from configuration, analyzer output, references, and reports.
- Add structural module extraction for unmatched paths using stable source roots
  and repository-relative directory segments.
- Preserve `explicit`, `structural`, and `unmapped` mapping evidence and direct
  cross-repository facts.

Validation: table-driven paths must prove known BIC modules use explicit rules,
new repositories use structural paths, generic names do not invent semantics,
and root/unusual files remain visible.

## 3. Changed Objects and Test Correspondence

- Replace directory-existence checks with concrete test-asset discovery.
- Detect pytest, JavaScript unit-test, and Playwright configuration and commands.
- Extract changed Python and JavaScript/TypeScript source objects without
  importing project code, retaining a file-level fallback.
- Inspect concrete test files for imports, references, scenario names,
  assertions, and disabled state.
- Merge explicit repository-qualified inventory relations with discovered
  assets; reserve explicit cross-repository targets for deliberate E2E flows.
- Analyze direct, safe one-hop/explicit, and possible scenario relationships per
  repository/module without exposing confidence or evidence labels.
- Derive separate natural-language groups for tests to add, tests to strengthen,
  and modules with no obvious static gap.

Validation: fixture repositories must cover Python and TypeScript symbols,
imports/references, assertions, disabled tests, unrelated same-name files,
frontend tests, empty directories, explicit cross-repository inventory, and
repository isolation.

## 4. Skill and Documentation

- Update `SKILL.md`, references, config, README, and implementation notes with
  the changed-object and test-correspondence contract.
- Keep output as one concise `BIC Quality Brief` and retain the read-only boundary.
- Reinstall source to `.agents` and `.claude` only after source verification.

## 5. Final Verification

- Run syntax/config validation and the temporary behavior fixture suite.
- Run the full `verify-install.sh` chain after installation.
- Compare source and installed skill directories.
- Confirm `git status` before and after analyzer runs is unchanged except for the
  intended task and kit edits.
- Confirm public test-analysis JSON contains no confidence fields,
  `evidence_type`, `coverage_gaps`, or `coverage_unconfirmed`.
