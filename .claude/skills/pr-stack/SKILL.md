---
name: pr-stack
description: "Use when one topic/issue produces two or more PRs — in a single repo or across multiple c12-ai repos. Stacked PRs (gh stack) are the DEFAULT for multiple dependent PRs in the same repo; cross-repo topics use per-repo stacks plus a tracking issue. Triggers: multiple PRs, dependent PRs, stacked PRs, PR stack, split a big change into PRs, cross-repo change, 多个 PR, 拆 PR, PR 链, 跨仓库变更."
---

# PR Stack — default for multi-PR topics

Policy decided 2026-07-17. Enablement verified the same day: the GitHub Stacked PRs
preview is active for **all repos in the c12-ai org** (stacks API `GET
/repos/c12-ai/<repo>/stacks` returns 200 on all 50 repos; non-enrolled repos 404).

## Decision rule

0. **Never attach a PR to an existing stack by default** (product-owner ruling
   2026-07-23, incident lab#162). In a repo with the Stacked PRs preview enabled,
   `gh pr create` without an explicit base appends the new PR to the top of any
   open stack AND rebases the remote branch onto that stack — the base can no
   longer be changed afterwards, and a stack-semantics merge atomically merges
   every PR below. Therefore:
   - Always pass `--base main` explicitly when creating a plain (non-stack) PR.
   - After creating or recreating any PR, verify `--json commits,files` counts
     match expectations before reporting it ready.
   - If a PR was accidentally attached to a stack: close it, then rebuild from
     the local clean commit on a **fresh branch name** (the same-named remote
     branch may already be rebase-contaminated — never reuse it), and never
     touch someone else's stack (`gh stack unstack` tears down the whole stack).
   Joining another author's stack must be an explicit, author-approved decision,
   never a default.

1. **One topic/issue → ≥2 dependent PRs in the SAME repo** → create them as a
   **stack** (`gh stack`), not as independent PRs. This is the default, not an
   option to offer.
2. **One topic/issue → PRs across MULTIPLE repos** → stacks cannot cross
   repositories. Apply per repo:
   - a repo receiving ≥2 PRs gets **one stack** in that repo;
   - a repo receiving 1 PR gets a plain PR.
3. **Independent PRs that merely share a theme** (no ordering, no dependency)
   → do NOT stack them. A stack encodes a dependency chain; merging a PR
   atomically merges everything below it.

## Cross-repo coordination (replaces what a cross-repo stack would do)

- Open a **tracking issue in `c12-ai/BIC-meta`** listing every PR / stack in the
  topic, grouped by repo.
- Every PR body links the tracking issue (`c12-ai/BIC-meta#<n>`).
- State the **merge order** in the tracking issue. Default order is
  contracts-first: `BIC-shared-types` → services (`BIC-lab-service`,
  `BIC-agent-service`, `BIC-chem-service`) → `BIC-agent-portal`.
  A contract change ships with its spec update in the same change set (Rule 10).

## Mechanics

Use the `gh-stack` skill (vendored official skill from `github/gh-stack`,
`.claude/skills/gh-stack/SKILL.md`) for command mechanics. The rules that most
often break agents:

- Every command **non-interactive**: branch names as positional args to
  `init`/`add`/`checkout`; `submit --auto`; `view --json`. Bare invocations open
  TUIs/prompts that hang forever.
- Plan layers by dependency **before** coding: foundations (types, models,
  shared utils) in lower branches, consumers (UI, callers) in higher ones.
- To fix a lower layer: navigate down (`gh stack down` / `checkout`), commit
  there, `gh stack rebase --upstack`, then return up.
- `submit --auto` creates new PRs as **drafts**; pass `--open` (or mark ready
  later) when review should start.

## Caveats

- Stacked PRs is a **private preview** feature — behavior may change; if a
  stacks call starts returning 404 org-wide, the preview scope changed (re-run
  the verification probe, then fall back to plain PRs + tracking issue).
- Merging any PR in a stack **atomically merges all PRs below it** — tell
  reviewers, and never put droppable work below must-ship work.
- All changes still go through PRs and admin merge — a stack changes PR
  *structure*, not the review/merge discipline.
