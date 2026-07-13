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
- Attempt to read every shortlisted body; do not introduce a separate five-body
  cutoff. Continue after individual lookup failures and expose per-candidate
  hydration status. Preserve strong-reference overflow as ambiguity.
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
mutating Git state. A real GitHub list receives a read-only smoke check.

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
- Exclude local skill copies, backups, and independently discovered child
  repositories from duplicate root-repository test discovery.

Validation: fixture repositories must cover Python and TypeScript symbols,
imports/references, assertions, disabled tests, unrelated same-name files,
frontend tests, empty directories, explicit cross-repository inventory, and
repository isolation.

## 4. Skill and Documentation

- Update `SKILL.md`, references, config, README, and implementation notes with
  the changed-object and test-correspondence contract.
- Keep output as one concise `BIC Quality Brief` with module mapping,
  direct/indirect/possible test correspondence, and missing-test guidance.
  Omit `mapping_source` and a general next-step field while retaining the
  read-only boundary.
- Add Issue Context and an evidence-backed pre-test Risk Matrix without implying
  that any verification command ran.
- Reinstall source to `.agents` and `.claude` only after source verification.

## 5. Final Verification

- Run syntax/config validation and the temporary behavior fixture suite.
- Run the full `verify-install.sh` chain after installation.
- Compare source and installed skill directories.
- Confirm `git status` before and after analyzer runs is unchanged except for the
  intended task and kit edits.
- Confirm public test-analysis JSON contains no confidence fields,
  `evidence_type`, `coverage_gaps`, or `coverage_unconfirmed`.

## 6. Skill Discoverability

- Generate `agents/openai.yaml` in the source Skill with `display_name`,
  `short_description`, and a one-sentence `$bic-quality-guan-ping-ce` default
  prompt. Do not add unprovided icons, branding, MCP dependencies, or an
  unnecessary implicit-invocation override.
- Add one root SOP Index entry that points to the committed source Skill, not
  `.agents/skills` or `.claude/skills` generated copies.
- Document explicit and implicit invocation plus the responsibilities of
  `SKILL.md`, `agents/openai.yaml`, the SOP Index, and the installer.
- Add contract tests for metadata shape, Skill-name consistency, description
  length, default-prompt invocation, and the stable SOP route.
- Extend installation verification to require `agents/openai.yaml` in the
  source and in both installed copies.

Validation: run the unit suite, install the Skill, run the complete
`verify-install.sh` chain, run Skill Creator validation, and finish with
`git diff --check`.
