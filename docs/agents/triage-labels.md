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

## Two axes

Labels in this repo run on **two orthogonal axes**. The five triage roles above are the *intake*
axis and are authoritative for triage. They do **not** replace the S1/S2/S3 lifecycle — that is a
separate axis, because the five roles have no way to express a post-triage state like
"implemented, awaiting retest".

| Axis          | Labels                                                                       | Owner                                            |
| ------------- | ---------------------------------------------------------------------------- | ------------------------------------------------ |
| **Triage**    | `needs-triage` `needs-info` `ready-for-agent` `ready-for-human` `wontfix`     | mattpocock engineering skills (`/triage` et al.) |
| **Lifecycle** | `stage:已析根因` `stage:已实现待复测` `stage:已验证`                          | S1/S2/S3 (`ops/agent-improvement-workflow.md`)   |
| **Flag**      | `needs-drake` (product ruling needed), `P0-链路断`…`P3-UIUX`, `repo:*`        | S1/S2/S3                                         |

Typical flow: `needs-triage` (S1 files it) → `stage:已析根因` (S2 lands a root cause) →
`ready-for-human` (awaiting the product owner's ruling) or `ready-for-agent` (ready to dispatch S3)
→ `stage:已实现待复测` (S3 implemented) → `stage:已验证` (independently verified).

### Retired labels

Three earlier `stage:*` labels were deleted because they duplicated the triage axis. Migration
details and recovery paths: `ops/stage-labels-migration.md`.
