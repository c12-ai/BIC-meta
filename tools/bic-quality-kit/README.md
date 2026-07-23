# BIC Quality Skill Kit

This kit provides the two-phase BIC quality review and selected-test execution
skill.

Phase 1 is intentionally read-only:

- It dynamically discovers the root and immediate child Git repositories.
- It reads committed changes relative to a local base plus worktree changes.
- It combines explicit BIC module rules with repository-relative structural modules.
- It installs the manifest-pinned `ast-outline` release into a BIC-owned user
  cache on first use, validates its JSON schema, and maps canonical diff hunks
  to qualified declarations across supported backend and frontend languages.
- It inspects concrete tests and relates them to changed source objects by
  repository and functional module.
- It recognizes local Python modules loaded through `importlib` and asserted
  test helpers that launch a local Python entrypoint, without executing either;
  unrelated assertions and imports used only by sibling command branches do not
  clear a test gap.
- It freezes a Diff/AST/test-derived technical scope before Issue analysis,
  uses authoritative Issue context additively, and generates a behavior-facing
  pre-test Quality Evidence Matrix.
- It performs requirement verification as a separate static pass only for an
  authoritative or explicitly justified strong-related Issue. Each eligible
  acceptance item keeps independent scope, implementation-evidence, and test-
  evidence states with exact Diff and test citations; thematic search matches
  remain context and are not formally aligned.
- It reports Issue-to-Diff scope divergence and groups test guidance as
  requirement-traced, technical-regression, or exploratory. These groups are
  combined by union, so Issue context cannot remove technical regression work.
- It explains which tests appear to correspond, which should be strengthened,
  and which changed behaviors have no matching test.
- It treats each Playwright/CDP case as independent browser/user-journey
  evidence, links machine checks to request/page/CDP outcomes, and rejects bare
  or unrelated assertions as positive evidence.
- It emits a bounded, auditable user-journey graph from changed routes/shared
  contracts through frontend imports and route literals, preserving both
  completed paths and dead-end/anchor-only partial paths.
- It emits a fingerprint-bound, `not-run` Phase 2 execution manifest with
  behavior-scoped `must_run`, `recommended`, and `not_runnable` cases. Raw
  possible/module/import relations do not become an execution queue.
- It outputs one `BIC Quality Brief`.
- It reads content only from regular files contained by their discovered
  repository, skips symbolic links and credential-bearing paths, and redacts
  common credential values and sensitive paths from CLI JSON output.
- It does not execute tests, start services, reset data, kill processes, or
  invoke E2E.

Phase 2 requires explicit authorization. It verifies the frozen change
fingerprint, then runs exact pytest, Vitest, Playwright, and
repository-configured CDP cases in layers. It never installs dependencies,
starts the live bench, resets data, invokes `bic-e2e-runner`, or queries
Phoenix.

## Repository Availability

The source of truth is committed under:

```text
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce
```

Two synchronized discovery mirrors are also committed:

```text
.agents/skills/bic-quality-guan-ping-ce
.claude/skills/bic-quality-guan-ping-ce
```

New clones therefore expose the Skill directly to Codex and Claude without an
installation step. The source of truth remains under
`tools/bic-quality-kit/skill/`; do not edit either discovery mirror directly.

After changing the source, maintainers synchronize and verify the committed
mirrors with:

```bash
./tools/bic-quality-kit/install.sh
./tools/bic-quality-kit/verify-install.sh
```

The synchronization command preserves replaced copies under
`.trellis/.runtime/skill-backups/`, outside Skill discovery. Commit source and
mirror changes together. Verification fails when either mirror is absent or
different from the source.

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
inspects current-PR Issue evidence. An explicit override is authoritative. A
unique current-PR linked/closing reference skips broad open-Issue discovery only
when exactly one affected GitHub repository exists. With multiple affected
repositories, every repository is scanned and the current-PR Issue remains a
repository-local candidate rather than resolving workspace Issue alignment.
Diff-commit references and
an `issue-123` branch-name pattern are protected hints that still need semantic
confirmation. Without an authoritative link, the Skill scans at most 100
metadata records per affected repository, compares English/Chinese/mixed titles
and labels with changed modules, objects, and paths, shortlists at most 10
ordinary candidates, keeps at most one no-signal fallback per affected
repository, and reads every shortlisted body before semantic
alignment. Multiple bodies use one read-only GraphQL batch; unresolved batch
items fall back to at most three concurrent lookups. All GitHub calls have
bounded timeouts and the complete GitHub analysis has a 60-second deadline. It
preserves shortlist order and reports exclusion,
hydration, and scan-status data; `scan-failed` and `partial-scan` remain distinct
from a successful empty scan. Ordinary matches remain `thematic-candidate`
context even when only one looks similar; they cannot define the requirement or
supply risk-matrix acceptance rows. Commit/branch references remain
`reference-hint` evidence, and bounded one-hop body references remain
`mentioned-reference` context. Ambiguous or incomplete provenance keeps
requirement alignment `unassessed` without erasing technical risk. An explicit
reference is translated to `--issue` and overrides discovery.

PR URLs supplied in conversation are background context, not analyzer inputs.
The Skill evaluates only code changes present in the current workspace snapshot.
It auto-detects a current PR when available; use `--issue` or `--issue-file` when
an explicit requirement source is needed.

The analyzer currently returns one workspace-level Issue context, test
correspondence, and risk assessment. Repository count is reported only as a
multi-repository change fact; it is not evidence that the changes form one
business or contract chain.

An explicit local base can be supplied through conversation:

```text
用 BIC quality 看当前分支相对 main 的 diff
```

The Skill translates this to `--base-ref main`. The checked-out `HEAD` remains
the head. A missing ref is reported per repository and never silently replaced.

The expected output is one structured `BIC Quality Brief` with:

- `Core Conclusion`
- `Change Set`
- optional authoritative `Issue Context`
- `Module Mapping`
- `Test Correspondence`
- `Pre-test Quality Evidence Matrix`
- `Tests to Add`
- `Tests to Strengthen`
- `Phase 2 Test Execution Handoff (not run)`

Within `Issue Context`, formal acceptance-item comparison is present only when
the selected Issue has eligible provenance. Each item is reported on three
independent axes (`scope`, `implementation`, and `test_status`) with exact
static evidence. The brief uses `cannot-determine` or `cannot-verify` when that
evidence is incomplete and never describes an item as passed, satisfied, or
complete because this phase does not execute tests. Missing-test guidance is
shown in requirement-traced, technical-regression, and exploratory groups; the
combined result preserves every technical recommendation.

`mapping_source` remains available in raw JSON for diagnostics but is omitted
from the default brief. The default brief shows bounded direct, indirect, and
possible relations; the machine handoff independently retains every strictly
eligible case without the display cap.

## Read-only Scripts

For a normal end-to-end review, run the assessment entry once so context,
module, test, Issue, and risk stages share one live Issue snapshot:

```bash
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/assess-risk-matrix.sh
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/assess-risk-matrix.sh --issue <override>
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/assess-risk-matrix.sh --worktree-only
```

The assessment uses the complete test inventory internally but omits that raw,
large intermediate from its final JSON. It returns derived test correspondence
and quality evidence plus `test_execution_manifest`. The manifest is static
guidance, includes expanded completed/partial journey paths, never clears an
object-level test gap, and becomes stale when its workspace change fingerprint
no longer matches. Use the inventory or suggest diagnostics below only when raw
test-asset details are required.

After the user explicitly authorizes Phase 2, run the frozen assessment:

```bash
tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts/execute-selected-tests.sh \
  /path/to/phase-one-assessment.json --execute
```

This runs `must_run` only. Add `--include-recommended` only for explicitly
requested broader regression. The command returns a behavior-linked execution
result; render it using the `BIC 分层测试执行报告` template in the Skill.

On the first structural-analysis run, the Skill uses `uv` to create a pinned
`ast-outline` environment under the platform user cache (for example,
`~/Library/Caches/bic-quality/tools` on macOS). It never writes that dependency
into a BIC repository or project virtual environment. Set the absolute
`BIC_QUALITY_TOOL_CACHE` path to relocate the managed cache, or
`BIC_QUALITY_AST_OUTLINE` to a compatible executable; either path is capability-
probed before use. Missing `uv`, unavailable Python 3.12/package access, or an
incompatible JSON schema is reported as an incomplete required analyzer rather
than silently changing the analysis method.

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
commands also accept `--issue <number-or-url-or-owner/repo#number>` or
`--issue-file <path>`. By default,
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

## Real Agent Eval

The script/unit suite validates deterministic analyzers. The Agent evals use
fresh Git fixtures and run the same prompt in two isolated modes:

- `with_skill`: the current repository Skill is installed and routed.
- `no_skill`: the Skill and its route are absent.

There is no old-Skill baseline in the normal gate. It can be added temporarily
only when diagnosing a regression.

```bash
# Show the small PR/smoke case set without calling a model.
python3 tools/bic-quality-kit/evals/run_agent_evals.py --list
python3 tools/bic-quality-kit/evals/run_agent_evals.py --suite smoke --dry-run

# Run paired real-Agent smoke evals.
python3 tools/bic-quality-kit/evals/run_agent_evals.py --suite smoke

# Run all prompt variants three times for a stability check.
python3 tools/bic-quality-kit/evals/run_agent_evals.py --suite full --repetitions 3
```

Each run records Codex JSONL events, the final brief, deterministic grading, and
a `with_skill`/`no_skill` fact-score comparison under `evals/results/`. The gate
checks trigger behavior through the observable `assess-risk-matrix.sh` call
count, preserves `warning`/`unassessed` facts, and rejects test execution or
other write-oriented commands. Baseline results are comparative evidence; only
the `with_skill` contract is a release gate.
