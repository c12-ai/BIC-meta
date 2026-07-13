# BIC Quality Skill Kit

This kit provides the current-phase BIC quality analysis skill.

It is intentionally read-only:

- It dynamically discovers the root and immediate child Git repositories.
- It reads committed changes relative to a local base plus worktree changes.
- It combines explicit BIC module rules with repository-relative structural modules.
- It inspects concrete tests and relates them to changed source objects by
  repository and functional module.
- After the Diff identifies affected repositories, it scans their open GitHub
  Issues, preserves strong PR/commit/branch links, and generates an
  evidence-backed pre-test Risk Matrix from Issue, Diff, contract-boundary,
  and test evidence.
- It explains which tests appear to correspond, which should be strengthened,
  and which changed behaviors have no matching test.
- It outputs one `BIC Quality Brief`.
- It does not execute tests, start services, reset data, kill processes, or invoke E2E.

## Install

From `BIC-meta`:

```bash
./tools/bic-quality-kit/install.sh
./tools/bic-quality-kit/verify-install.sh
```

The installer copies the skill to:

```text
.agents/skills/bic-quality-guan-ping-ce
.claude/skills/bic-quality-guan-ping-ce
```

Those installed copies are local tool state. The source of truth remains under `tools/bic-quality-kit/skill/`.
Existing installed copies and legacy in-directory backups are preserved under
`.trellis/.runtime/skill-backups/`, outside Codex and Claude skill discovery.

Skill discovery has three complementary entry points:

- `SKILL.md` defines the workflow and its natural-language trigger description.
- `agents/openai.yaml` defines the Codex UI name, short description, and default
  prompt.
- The root `AGENTS.md` / `CLAUDE.md` SOP Index provides a stable project route
  to the committed source Skill.

## Use

In Claude or Codex, ask:

```text
用 BIC quality 看下当前 diff
```

Codex also supports explicit Skill invocation:

```text
Use $bic-quality-guan-ping-ce to review the current BIC diff.
```

or:

```text
帮我分析这次改动涉及哪些模块和测试 scope
```

Issue-aware Diff risk assessment is automatic:

```text
用 BIC quality 看当前 diff，分析测试和风险
```

An explicit Issue remains available as an override:

```text
用 BIC quality 看当前 diff 和 c12-ai/BIC-meta#150，生成风险矩阵
```

By default the Skill first identifies repositories changed by the Diff, then
scans open Issues in each affected repository. Current PR links, PR/commit
closing references, and a strong `issue-123` branch-name pattern take priority.
Without a strong link, the Skill scans at most 100 metadata records per affected
repository, compares them with changed modules and objects, shortlists at most
10 ordinary candidates, and reads every shortlisted body before semantic
alignment. It reports exclusion and hydration counts; ambiguous candidates
remain visible and keep overall risk `unassessed`. An explicit reference is
translated to `--issue` and overrides discovery.

An explicit local base can be supplied through conversation:

```text
用 BIC quality 看当前分支相对 main 的 diff
```

The Skill translates this to `--base-ref main`. The checked-out `HEAD` remains
the head. A missing ref is reported per repository and never silently replaced.

The expected output is one structured `BIC Quality Brief` with:

- `Change Set`
- `Issue Context`
- `Module Mapping`
- `Test Correspondence`
- `Risk Matrix`
- `Missing Tests`

`mapping_source` remains available in raw JSON for diagnostics but is omitted
from the default brief. Direct, indirect, and possible test relations remain
visible; the report does not add a general next-step recommendation.

## Read-only Scripts

For a normal end-to-end review, run the assessment entry once so context,
module, test, Issue, and risk stages share one live Issue snapshot:

```bash
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/assess-risk-matrix.sh
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/assess-risk-matrix.sh --issue <override>
```

The other bundled scripts are standalone diagnostic entry points. Do not chain
all of them to build one final brief because separate processes perform separate
metadata collections:

```bash
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/collect-quality-context.sh
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/detect-impact-scope.sh
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/inspect-test-inventory.sh
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/suggest-test-scope.sh
```

All wrappers accept `--base-ref <local-ref>` or `--worktree-only`; Issue-aware
commands also accept `--issue <number-or-url-or-owner/repo#number>`. By default,
each repository selects the first locally available CI base, `origin/main`,
`main`, `origin/master`, or `master`, then combines
`merge-base(base, HEAD)..HEAD` with unstaged, staged, and untracked changes.
The scripts do not fetch Git refs, checkout, execute discovered commands, or run
tests. GitHub Issue listing and lookup are read-only metadata requests through
`gh` and are limited to repositories affected by the Diff.

## Source Verification

```bash
python3 -m unittest discover -s tools/bic-quality-kit/tests -v
./tools/bic-quality-kit/verify-install.sh
```
