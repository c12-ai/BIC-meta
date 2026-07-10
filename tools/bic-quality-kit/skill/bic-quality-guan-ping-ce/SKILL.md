---
name: bic-quality-guan-ping-ce
description: >-
  Use when asked to perform BIC quality review, Guan/Ping/Ce analysis, current
  diff module analysis, test correspondence analysis, test scope recommendation,
  or missing-test review. This skill performs read-only analysis only: it
  inspects complete local branch/worktree changes, maps repositories and modules,
  relates changed source objects to existing tests, and returns a structured BIC
  Quality Brief.
---

# BIC Quality Guan/Ping/Ce

Use this skill when the user asks to review the current BIC diff, locate changed repositories and modules, determine which existing tests correspond to changed behavior, or identify missing tests.

## Boundary

This skill is a read-only quality analysis layer.

Do:
- Read local branch/worktree changes, branches, repositories, scope taxonomy,
  changed source objects, and test assets.
- Identify the changed repository and module for every file.
- Explain which existing tests directly, indirectly, or possibly correspond to
  changed behavior.
- Identify tests to add or strengthen by static source inspection.
- Output one structured `BIC Quality Brief`.

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
   - `scripts/collect-quality-context.sh`
   - `scripts/detect-impact-scope.sh`
   - `scripts/inspect-test-inventory.sh`
   - `scripts/suggest-test-scope.sh`
   The default is the checked-out `HEAD` relative to an automatically selected
   local base plus unstaged, staged, and untracked changes. Never fetch or
   checkout a ref. If the user says “相对 main” or “以 release/x 为基线”, pass
   that value as `--base-ref main` or `--base-ref release/x`. The explicit base
   applies to every discovered repository; missing refs must remain warnings.
   Use `--worktree-only` only when the user explicitly wants uncommitted changes.
2. Read references only as needed:
   - `references/workspace-map.md` for repository map.
   - `references/scope-taxonomy.md` for scope taxonomy meaning.
   - `references/test-analysis-rules.md` for changed-object and test correspondence rules.
   - `references/deliverables.md` for output format.
3. Report the comparison metadata (`base_ref`, `merge_base`, change sources, and warnings) before module mapping.
4. Use repository identity from Git discovery. Report `affected_repositories`,
   group module evidence under `modules_by_repository`, and expose only the
   factual `direct_cross_repository` flag. Map known BIC paths with explicit
   `module_scope` rules; otherwise derive a repository-relative structural
   module such as `app/inference` or `src/pages/chat`. Never translate generic
   path words into guessed business capabilities.
5. Use discovered concrete test files first. Read imports, referenced objects,
   scenario names, assertions, and disabled state without importing project
   code. Treat `config/test-inventory.yaml` as an optional semantic relation,
   mainly for E2E and cross-repository flows. Module identity is
   `(repo, module_scope)`: `relates_modules` applies only to the entry's own
   repository, while `relates_repository_modules` is the only allowed explicit
   cross-repository declaration.
6. Keep relation facts separate from add-test guidance. Report direct and safe
   indirect relations, possible candidates, tests to add, tests to strengthen,
   and modules with no obvious static gap. Do not output confidence, risk,
   priority, evidence-type, or coverage-percentage labels.
7. Produce one `BIC Quality Brief`.

## Output

Return exactly one structured report unless the user asks for raw JSON.

```text
BIC Quality Brief

Change Set
- 变更摘要：
- 变更仓库：
- 是否直接跨仓：

Module Mapping
- Repo / Module：
- 映射来源：
- 文件证据：

Test Correspondence
- 直接相关测试：
- 间接相关测试：
- 可能相关测试：
- 对应依据：

Missing Tests & Next Step
- 建议新增测试：
- 建议完善测试：
- 暂未发现明显缺口：
- 下一步建议：
```

Every conclusion should cite concrete facts: changed file paths and objects,
module ids, test paths, imports/references, scenarios, assertions, disabled
state, or explicit repository-qualified relations. State the selected base and
whether module evidence is `explicit`, `structural`, or `unmapped`. Static test
correspondence never proves that a test ran or passed.
