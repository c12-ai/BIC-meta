# Stage-label migration record

**Summary**: on 2026-07-16, `stage:待调查` / `stage:待裁定` / `stage:待修复` were deleted from the
`c12-ai/BIC-meta` tracker — they duplicated the triage axis (see `docs/agents/triage-labels.md`).
Their 20 live open issues were migrated first; recovery paths below. This is a historical record,
not a living instruction file.

| Retired label   | Replaced by       | Open issues migrated |
| --------------- | ----------------- | -------------------- |
| `stage:待调查`  | `needs-triage`    | 13                   |
| `stage:待裁定`  | `ready-for-human` | 6                    |
| `stage:待修复`  | `ready-for-agent` | 1                    |

Five closed issues (#323 #197 #132 #194 #195) carried a retired label and were **not** relabelled —
their state is history, not a live queue.

**Recovery**: `ops/stage-labels-snapshot-2026-07-16.json` records every issue→label pairing (188
issues) as of just before the migration. GitHub also keeps `labeled`/`unlabeled` timeline events
after a label is deleted (verified empirically), so `gh api repos/c12-ai/BIC-meta/issues/<n>/timeline`
can reconstruct history independently. Note that re-creating a deleted label does **not** re-apply
it to any issue.
