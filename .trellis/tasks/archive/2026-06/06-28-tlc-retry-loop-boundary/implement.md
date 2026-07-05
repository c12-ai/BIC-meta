# Implement — TLC Rf-retry loop (parent execution plan)

Parent-level ordered plan. Each child carries its own detailed `implement.md`;
this is the cross-service sequence, the integration gates, and the rollback points.
Children must be implemented in order (hard dependency chain — §4 of design.md).

## Phase 0 — Pre-flight (before any child starts)

- [ ] Confirm the three child tasks exist and are linked under the parent.
- [ ] Re-read both research files (lab + agent) — they hold the file:line map.
- [ ] Snapshot the current red E2E (`tlc-retry-flow.spec.ts`) as the regression target.

## Phase 1 — Child 06-29-tlc-round-contracts (shared-types) — FIRST

- [ ] Add `AWAITING_CONFIRMATION` to the shared `TaskStatus` enum.
- [ ] Add `target_window` (`TLCRfGoal`) to the TLC create request; define the append-round
  request shape (carries the round's `TLCParam`).
- [ ] Add optional `image_url` to `TaskStatusMsgPayload`.
- [ ] Regenerate contract artifacts (schemas / openapi / CHANGELOG) per shared-types AGENTS.md.
- [ ] Bump shared-types version; both consumers pin the new version.
- **Validation:** shared-types build + type-export scripts pass; both repos resolve the new pin.
- **Rollback point:** additive enum value + fields; revert the version bump if downstream stalls.

## Phase 2 — Child 06-29-tlc-lab-round-split (lab-service) — SECOND

The aggregator-Task engine work (1 trial = 1 Task; rounds = appended skills):
- [ ] **Append-skill route + service method** — agent appends a round skill (+ ratio on
  `task.params["rounds"]`) and a cleanup skill to the SAME Task. (No append path exists today.)
- [ ] **Terminal-detection edit** (`task_service.py:249-266`): last completed skill == cleanup
  → `COMPLETED`; else → park `AWAITING_CONFIRMATION` (instead of auto-complete-when-no-PENDING).
- [ ] **Plate-memory on `task.params`**: PREP allocates plate/tank/boxes ONCE → write
  `session_binding`; round/cleanup op-build READS it (replace `_first_available`). Pin
  `tank_slot` explicitly (don't let it default to `round_index`).
- [ ] Reuse `plan_round` per appended round (round-1 prep / round-≥2 dispose-previous branching);
  activate the dead `observe_view`/`observe_uv`/`take_photo` ops inside the round skill.
- [ ] Surface the captured-image URL on `TaskStatusMsgPayload` when a round skill completes.
- **Validation:** `ruff check` + `uv run pyright app/` + `uv run pytest` (lab). Manual: create
  Task → append round → append round → cleanup; assert ONE Task/`task_id`, one material-fetch,
  N rounds reuse the same plate/tank, one dispose, park between rounds, `image_url` per round.
- **Rollback point:** the engine edit is the riskiest change; keep focused tests for the
  park/append/complete transitions; revert the terminal-detection edit alone if it misfires.

## Phase 3 — Child 06-29-tlc-agent-round-loop (agent-service) — THIRD

- [ ] Rebuild the L3 TLC loop: CREATE one Task (tubes + window) → APPEND a round skill per
  attempt → APPEND cleanup on in-window success. N agent Trials (one per attempt) all SHARE
  the one `lab_task_id=T` (many-to-one — grill Q9); `_auto_retry_node` still mints a trial per
  attempt but calls `append_round(T, ratio)` instead of dispatching a new full task.
- [ ] **Resolution edit (induced by shared lab_task_id):** `resolve_trial_id` must map
  `lab_task_id=T` → the MAX(attempt) trial (the live round), not error on N matches
  (`trials_repo.py:385`).
- [ ] **INDUCED BY CHILD 1 (must not be missed — grill Q4):** add `AWAITING_CONFIRMATION` to
  the agent ingress routing alphabet `NON_TERMINAL_STATUSES` (`event_ingress.py:40`). Without
  it the new status is in NEITHER the non-terminal NOR terminal set → falls through to
  `UnacceptableStatusError` → NACK → 5-retry dead-letter → the round's photo-ready signal is
  LOST and the loop silently breaks. It is robot-free, NOT busy (§2.5) — route it as a
  progress signal, not a bench-busy flag.
- [ ] Read the photo URL off the MQ `TaskStatusMsgPayload` (event_ingress) on each round's
  `AWAITING_CONFIRMATION` status → fast-path "round done → `recognize_tlc_plate(url)`".
- [ ] L4 `recommend_tlc_mixcase` stub → history-aware (adjust ratio from observed-Rf); L4
  `recognize_tlc_plate` stub → scripted by round (1→0.25 OUT, 2→0.51 IN). INDEPENDENT, L4-only.
- [ ] Keep `_evaluate_route` / cap / result_review-on-terminal; append cleanup only on in-window.
- [ ] Rewrite `tlc-retry-flow.spec.ts` to the aggregator-Task shape (AC1–AC3).
- [ ] **Migrate** `tlc-e2e-final-chain.spec.ts` to the new flow (preserve the tube
  chain-of-custody DB assertions).
- **Validation:** `pnpm typecheck`/agent `uv run pytest`; then the round-based E2E green on the bench.
- **Rollback point:** the L3 loop change is self-contained to the TLC subgraph + mind_client.

## Phase 3b — Stage the old-path removal LAST (after Phases 1–3 green)

- [ ] Delete the old single-shot `CreateTLCTaskRequest` (the `THIN_LAYER_CHROMATOGRAPHY`
  single START→END task) across all 3 repos (~16 source files) — no back-compat.
- [ ] Delete the now-dead old-shape tests (lab `tests/tlc/*`, integration/e2e that drove the
  single-shot path) — keep only the migrated specs.
- **Validation:** all 3 repos' suites green AFTER removal (one short red window expected during).
- **Rollback point:** removal is the final commit; revert it alone if anything depends on the
  old shape we missed.

## Phase 4 — Integration & acceptance (parent)

- [ ] **AC1** round-based E2E green (prep once, ≥2 rounds w/ differing ratio, recognize OUT→IN,
  one cleanup after success, one result_review SUCCESS, accept, no turn_failed).
- [ ] **AC2** prep-once / cleanup-once proven (assertion or lab test).
- [ ] **AC3** ratio adapts (round-2 ratio ≠ round-1 ratio asserted).
- [ ] **AC4** every changed cross-layer surface has its spec doc updated (Rule 10) — audit.
- [ ] **AC5** both BE suites green (agent + lab).
- [ ] Re-fix `helpers.ts` reset SQL already landed (outbox removed) — confirm still clean.

## Risky files / watch list

- shared-types contract artifacts (regeneration must match the new models exactly).
- lab `task_service.py` step-advance + `planner.py` round branching (occupancy + dispose-once).
- agent `tlc.py` loop topology + `mind_client.py` (the ONLY place mocks may live — R7).
- `event_ingress` (reading `image_url` off MQ) — keep the SSE/event mapping in sync.

## Validation command quick-reference

- shared-types: build + export scripts (per AGENTS.md).
- lab: `ruff check && uv run pyright app/ && uv run pytest`
- agent: `uv run pytest -q`
- portal E2E: `VITE_HIDE_DEVTOOLS=1 pnpm exec playwright test tests/tlc-retry-flow.spec.ts --workers=1`
