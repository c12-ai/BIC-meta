---
name: s2-investigate
description: S2 investigation role of the agent-improvement workflow — for a given BIC-meta issue, find the root cause, design a root-level solution, and comment it onto the issue. Triggers on /s2-investigate <issue-number>, or when the user asks to investigate an issue's root cause.
---

# S2 — Root-cause investigation / solution design (no implementation)

First read `ops/agent-improvement-workflow.md` (role boundaries, bench playbook, change discipline).
The input is an issue number (`$ARGUMENTS`).

## Flow

1. `gh issue view <N> --repo c12-ai/BIC-meta --comments` to read the full context.
2. **Re-derive from primary evidence**: code (talos/BIC-agent-service, talos/BIC-agent-portal),
   DB (⚠️ the agent DB is in talos-postgres:5433; the same-named DB in bic-postgres:5432 is an empty decoy),
   BE logs, git log (find the introducing commit). The issue's "root-cause hypothesis" is only a hypothesis — verify or refute it.
3. **Find the root cause, not a patch point**: ask "why does this problem exist" until you reach the design-decision layer
   (precedent: the root cause of a phrasing leak is the specialist's self-identity framing, not a missing prohibition line).
4. **Design a root-level solution**: change self-identity / visible information / contract / structure, rather than stacking on prohibition rules.
   For anything touching graph structure, a cross-layer contract (Rule 10), or a product decision, explicitly apply the `needs-product-decision` label.
5. Write the analysis as an issue comment (format: `## Root cause` evidence chain → `## Solution` → `## Impact / Risk` →
   `## Alternatives`), then switch the label `needs-triage` → `stage:已析根因`.

## Prohibited

- **Do NOT change product code** (read-only; put repro scripts in scratchpad).
- Do NOT restart bench services, do NOT reset the DB (the user may be testing).
- Do NOT implement the solution — that is S3's job, and S3 will independently re-review your conclusion.

## Before starting: external-PR reconciliation

Before analyzing / implementing, scan the corresponding repo's open PRs (`gh pr list --repo c12-ai/<repo> --state open --json number,title,headRefName,author`); on a hit in the same area, run `gh pr diff <N> --repo <r> --name-only` to compare the changed-file sets: duplicate → mark "resolved by that PR" and don't redo it; file conflict → align first, then implement and note in the comment which PR you are building on / avoiding. See the "external-PR reconciliation" section of ops/agent-improvement-workflow.md.
