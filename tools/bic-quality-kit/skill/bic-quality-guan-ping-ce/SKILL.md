---
name: bic-quality-guan-ping-ce
description: >-
  Use when asked to perform BIC quality review, Guan/Ping/Ce analysis, current
  diff module analysis, test correspondence analysis, test scope recommendation,
  issue-aware diff risk assessment, risk matrix generation, or missing-test
  review. This skill performs read-only analysis only: it inspects complete
  local branch/worktree changes, maps affected repositories and modules, scans
  their GitHub Issues, relates changed source objects to existing tests, and
  returns a structured `BIC 质量简报` with a pre-test risk matrix.
---

# BIC Quality Guan/Ping/Ce

Use this skill when the user asks to review the current BIC diff, locate changed repositories and modules, determine which existing tests correspond to changed behavior, or identify missing tests.

## Boundary

This skill is a read-only quality analysis layer.

Do:
- Read local branch/worktree changes, branches, repositories, scope taxonomy,
  changed source objects, and test assets.
- After locating affected repositories, scan their open Issues and analyze them
  against changed modules and objects. Prefer a strong PR/commit/branch link and
  accept an explicit Issue only as an override.
- Identify the changed repository and module for every file.
- Explain which existing tests directly, indirectly, or possibly correspond to
  changed behavior.
- Identify tests to add or strengthen by static source inspection.
- Generate an evidence-backed pre-test Risk Matrix from Issue, Diff, module,
  contract-boundary, and test evidence.
- Output one structured `BIC 质量简报`.

Do not:
- Execute tests.
- Start services.
- Reset databases.
- Kill ports or processes.
- Modify business code.
- Invoke live bench or E2E runners.

If the user asks to execute tests, state that this skill only provides read-only analysis in the current phase and provide suggested commands or next-step guidance.

## Workflow

1. Collect context with bundled scripts when available:
   - Use `scripts/assess-risk-matrix.sh` once as the primary entry for a normal
     end-to-end Quality review. It reuses one Issue snapshot across context,
     module, test, and risk analysis.
   - Treat the other wrappers as standalone diagnostics; do not run all wrappers
     sequentially for one final brief because each diagnostic invocation may
     perform its own live metadata collection.
   - `scripts/collect-quality-context.sh`
   - `scripts/detect-impact-scope.sh`
   - `scripts/inspect-test-inventory.sh`
   - `scripts/suggest-test-scope.sh`
   - `scripts/assess-risk-matrix.sh`
   The default is the checked-out `HEAD` relative to an automatically selected
   local base plus unstaged, staged, and untracked changes. Never fetch or
   checkout a ref. If the user says “相对 main” or “以 release/x 为基线”, pass
   that value as `--base-ref main` or `--base-ref release/x`. The explicit base
   applies to every discovered repository; missing refs must remain warnings.
   Use `--worktree-only` only when the user explicitly wants uncommitted changes.
   Issue handling is Diff-driven. First collect changed files and identify every
   repository with `change_count > 0`. For each affected GitHub repository, scan
   its open Issues. Separately preserve strong association evidence in this
   order: the current PR's linked/closing Issue, a `Fixes/Closes/Resolves`
   reference in the PR body, the same strong reference in Diff commits, then an
   `issue-123` branch-name pattern. A unique strong link is authoritative. When
   no strong link exists, scan at most 100 open-Issue metadata records per
   affected repository. After module mapping and changed-object extraction,
   deterministically shortlist at most 10 ordinary candidates using repository,
   module, object, label, and stable update-order signals. Read the full body of
   every shortlisted candidate with `gh issue view`; do not apply a second
   metadata-only body cutoff. Preserve repository diversity, exclusion counts
   and reasons, hydration failures, and strong-reference overflow.
   Repository membership or keyword overlap alone cannot select an Issue;
   require concrete agreement between its goal/acceptance items and the changed
   module or object. Keep multiple plausible candidates visible and mark Issue
   alignment `unassessed`. When the user supplies an Issue number, URL, or
   `owner/repo#number`, pass it as `--issue` to override discovery. A bare number
   resolves in `BIC-meta`; use a repository-qualified reference for child Issues.
   All GitHub access is read-only through the local `gh` CLI. Preserve query
   warnings. Use `--issue-file` only for an explicitly supplied local
   JSON/Markdown Issue or deterministic fixture.
2. Read references only as needed, but always read `references/deliverables.md`
   before writing the final brief:
   - `references/workspace-map.md` for repository map.
   - `references/scope-taxonomy.md` for scope taxonomy meaning.
   - `references/test-analysis-rules.md` for changed-object and test correspondence rules.
   - `references/risk-model.md` for Issue alignment and pre-test risk rules.
   - `references/deliverables.md` for output format.
3. Report affected-repository Issue scan counts, shortlist/exclusion counts and
   reasons, hydration attempted/succeeded/failed counts, relevant candidates and
   their Diff/module correspondence, selection reason, selected Issue metadata
   and acceptance items, then comparison metadata
   (`base_ref`, `merge_base`, change sources, and warnings) before module mapping.
4. Use repository identity from Git discovery. Report `affected_repositories`,
   group module evidence under `modules_by_repository`, and expose only the
   factual `direct_cross_repository` flag. Map known BIC paths with explicit
   `module_scope` rules; otherwise derive a repository-relative structural
   module such as `app/inference` or `src/pages/chat`. Never translate generic
   path words into guessed business capabilities. Keep `mapping_source` in raw
   JSON for diagnostics; do not print it in the default brief. If no module can
   be identified, say that the functional module is not yet identified and cite
   the changed files.
5. Use discovered concrete test files first. Read imports, referenced objects,
   scenario names, assertions, and disabled state without importing project
   code. Treat `config/test-inventory.yaml` as an optional semantic relation,
   mainly for E2E and cross-repository flows. Module identity is
   `(repo, module_scope)`: `relates_modules` applies only to the entry's own
   repository, while `relates_repository_modules` is the only allowed explicit
   cross-repository declaration.
6. Keep relation facts separate from add-test guidance. Report direct and safe
   indirect relations, possible candidates, tests to add, tests to strengthen,
   and modules with no obvious static gap. Possible candidates are search clues,
   not proof of coverage. Do not output confidence, risk, priority,
   evidence-type, or coverage-percentage labels.
7. Treat the `scripts/assess-risk-matrix.sh` result from step 1 as the
   deterministic risk floor; do not run the wrapper again. Compare every Issue
   acceptance item semantically with concrete Diff and test evidence, add an
   Issue-alignment row for each item, and only raise the floor when evidence is
   missing. If repository scanning yields exactly one semantically supported
   candidate, read it fully and use it for the final alignment; otherwise keep
   the overall result `unassessed`. Never lower the risk floor or infer alignment
   from keyword overlap alone. This matrix describes pre-test verification risk,
   not residual risk.
8. Produce one `BIC 质量简报`.

## Output

Return exactly one structured report unless the user asks for raw JSON. Follow
the template and selection rules in `references/deliverables.md`. Every
conclusion should cite concrete facts: changed file paths and objects, test
paths, imports/references, scenarios, assertions, disabled state, or explicit
repository-qualified relations. Start with the concise `核心结论` required by the
template; it must summarize rather than add evidence, labels, or recommendations.
Report risk separately for independent change streams when their Issue alignment
differs. State the selected base once. State once at the end that tests were not
executed and static correspondence does not prove pass/fail. Do not add a
next-step recommendation field beyond the missing-test guidance defined by the
template. If Issue context is absent or unresolved, state that Issue alignment
and the corresponding stream's risk are unassessed.
