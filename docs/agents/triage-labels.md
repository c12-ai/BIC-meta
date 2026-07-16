# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Authority (ruled 2026-07-16)

The five labels above are **authoritative** for triage. The pre-existing `stage:*` vocabulary
(`stage:待调查` / `stage:已析根因` / `stage:待裁定` / `stage:待修复` / `stage:已实现待复测` /
`stage:已验证`) and `needs-drake` are **to be retired**.

**Not yet done — migration is outstanding.** As of the ruling the `stage:*` labels carry 186
applications across all-state issues (`stage:已实现待复测` alone: 139) and are referenced by
`ops/agent-improvement-workflow.md`, `ops/verification-window-runbook.md`, and every
`.dispatch/prompts/s2-*` / `s3-*` prompt. Until that migration lands, `stage:*` still describes the
live state of those issues — read it, don't assume it is dead.

Three `stage:*` states have **no equivalent** among the five triage roles, because the two
vocabularies sit on different axes — the five roles are an *intake* vocabulary, `stage:*` is a
*full-lifecycle* one:

| `stage:*` state         | Triage-role equivalent |
| ----------------------- | ---------------------- |
| `stage:待调查`          | `needs-triage`         |
| `stage:已析根因`        | *(none)*               |
| `stage:待裁定`          | `ready-for-human`      |
| `stage:待修复`          | `ready-for-agent`      |
| `stage:已实现待复测`    | *(none)*               |
| `stage:已验证`          | *(none)*               |

Retiring `stage:*` therefore requires deciding where those three post-triage states live first
(keep them as a separate lifecycle axis alongside the triage labels, or replace them with something
else). That decision is not made yet.
