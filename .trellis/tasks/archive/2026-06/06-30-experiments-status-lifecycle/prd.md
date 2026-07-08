# PRD — experiments.status: investigate → propose (DECISION GATE)

Repo: BIC-agent-service (+ snapshot contract → BIC-agent-portal). Research:
`research/experiments-status-semantics.md`.

## Finding (verified)

`experiments.status` is a **vestigial fossil**, not a designed lifecycle:
- Bare `String(32)` default `'recommended'` (`models.py:111`) — NO enum, unlike
  `stage` which is the real typed lifecycle (`ExperimentStage`, `enums.py:96-107`).
- **No writer** — all three experiment `apply()` methods touch only
  `stage`/`objective`/`name` (`bypass_emitted.py:128-140`,
  `runtime_emitted.py:391-397`, `:711-715`).
- **No meaningful consumer** — snapshot passes it through (`sessions.py:471,650`,
  always `'recommended'`); the one BE branch `_pick_active_experiment`
  (`orchestrator.py:611-629`) is a dead no-op (always matches); FE declares
  `SnapshotExperiment.status` (`agent-client.ts:451`) but **never reads it**
  (portal drives off `stage`, `workspaceStore.ts:888`).
- **Origin**: inherited from `agent_plans.status` via in-place table rename
  (`3338598ac5cd`). The new `plans` table got the real lifecycle; the experiment
  level never did. The `recommended→running` flow exists ONLY in a test docstring.

## Recommendation

**DROP the dead column** (+ likely co-fossil `started_at` — see caveat). `stage`
is the lifecycle authority; `status` adds a misleading always-`recommended` field
to the FE↔BE contract. Removing it is simpler than inventing a lifecycle nothing
consumes (YAGNI / Rule 2).

## Decision gate for Drake — pick one

- **A. DROP (recommended).** Alembic migration to drop `experiments.status`
  (+ `started_at` if confirmed unused); remove from model, `_UPDATABLE_FIELDS`,
  snapshot DTO (BE `SnapshotExperiment` + FE `SnapshotExperiment.status`); delete
  the dead `_pick_active_experiment` status branch. Rule 10: update snapshot spec
  (`events.md`/`backend-contract.md`). Blast radius: 1 migration + ~5 files +
  spec; FE one-line DTO trim.
- **B. ADVANCE.** Define an `ExperimentStatus` enum + wire writers
  (recommended→active at objective-confirm, →completed at final result). More
  code, and nothing reads it yet — only worth it if a real consumer is coming.
- **C. LEAVE + document.** Annotate the column as reserved/unused, no code change.
  Cheapest, but keeps the misleading field in the contract.

## Caveat to resolve before implementing A

`started_at` looks like a co-fossil but the research did not exhaustively verify
every writer. Confirm `started_at` is genuinely unused before bundling its drop.

## Acceptance criteria (apply once a path is chosen)

- [ ] (A) Column dropped via migration; no read/write of `status` remains; snapshot
  contract updated both sides; full BE test suite green; FE typecheck green.
- [ ] (A) `_pick_active_experiment` dead branch removed without behavior change
  (it always returned the first row anyway).
- [ ] Spec updated same change set (Rule 10).

---

## DECISION (Drake, 2026-06-30): Option A — DROP `status`, scope to status ONLY

Spec archaeology confirmed no designed ExperimentStatus lifecycle (the `06-05`
schema design gave the lifecycle to `plans`, left experiments.status inherited &
un-transitioned). Drop it.

### started_at is DEFERRED (not bundled)
Investigation found `started_at` is RISKIER than `status`:
- It is the experiment **sort key** — `experiments_repo.py:107`
  `order_by(Experiment.started_at.desc().nulls_last())` (active query, not a dead
  branch).
- It is exposed in the snapshot (`sessions.py:473,652`) and declared in the FE DTO
  (`agent-client.ts:453`).
Although never written (always NULL), dropping it changes a live sort + contract.
That is a separate, larger call — DO NOT touch started_at in this task. Track
separately if desired.

### Implementation scope (status ONLY)
BIC-agent-service:
1. `app/data/models.py` — drop the `status` column from the Experiment model.
2. Alembic — `alembic revision --autogenerate` → drop `experiments.status`;
   verify the migration drops ONLY that column (not started_at). `alembic upgrade
   head`.
3. `app/repositories/experiments_repo.py` — remove `status` from
   `_UPDATABLE_FIELDS` (line 33), the row dataclass/reader (lines ~50,123), and
   any `status=` construction.
4. `app/api/routers/sessions.py` — remove `status` from the snapshot
   `SnapshotExperiment` DTO (line ~471) + its construction (line ~650).
5. `app/session/orchestrator.py` — delete the dead `_pick_active_experiment`
   status branch (611-629) + the unused status constant (~571). It always matched
   (status always 'recommended'), so "return first row" behavior is preserved —
   prove via test.
6. Grep for any other `experiment.status` / `\.status` read on an experiment;
   remove.

BIC-agent-portal:
7. `src/lib/agent-client.ts` — remove `status` from `SnapshotExperiment` (line
   ~451). Confirm nothing reads it (research: FE never reads it; `workspaceStore`
   drives off `stage`).

Spec (Rule 10, same change set):
8. Update the snapshot contract docs (`events.md` snapshot section +
   `backend-contract.md` `SnapshotExperiment`) to drop the `status` field.

### Acceptance (status-only)
- [ ] Migration drops ONLY experiments.status; `alembic upgrade head` + downgrade
  both clean.
- [ ] No read/write of experiment.status remains (grep clean).
- [ ] `_pick_active_experiment` behavior unchanged (first-row), proven by a test.
- [ ] Full BE suite green (`uv run pytest`), pyright clean; FE typecheck green.
- [ ] Snapshot spec updated both sides; no FE↔BE contract drift.
