# BIC Quality Skill Kit

This kit provides the current-phase BIC quality analysis skill.

It is intentionally read-only:

- It dynamically discovers the root and immediate child Git repositories.
- It reads committed changes relative to a local base plus worktree changes.
- It combines explicit BIC module rules with repository-relative structural modules.
- It inspects concrete tests and relates them to changed source objects by
  repository and functional module.
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

## Use

In Claude or Codex, ask:

```text
用 BIC quality 看下当前 diff
```

or:

```text
帮我分析这次改动涉及哪些模块和测试 scope
```

An explicit local base can be supplied through conversation:

```text
用 BIC quality 看当前分支相对 main 的 diff
```

The Skill translates this to `--base-ref main`. The checked-out `HEAD` remains
the head. A missing ref is reported per repository and never silently replaced.

The expected output is one structured `BIC Quality Brief` with:

- `Change Set`
- `Module Mapping`
- `Test Correspondence`
- `Missing Tests & Next Step`

## Read-only Scripts

The bundled scripts can be run directly for debugging:

```bash
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/collect-quality-context.sh
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/detect-impact-scope.sh
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/inspect-test-inventory.sh
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/suggest-test-scope.sh
```

All wrappers accept `--base-ref <local-ref>` or `--worktree-only`. By default,
each repository selects the first locally available CI base, `origin/main`,
`main`, `origin/master`, or `master`, then combines
`merge-base(base, HEAD)..HEAD` with unstaged, staged, and untracked changes.
The scripts do not fetch, checkout, execute discovered commands, or run tests.

## Source Verification

```bash
python3 -m unittest discover -s tools/bic-quality-kit/tests -v
./tools/bic-quality-kit/verify-install.sh
```
