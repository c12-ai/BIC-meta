# Manual experiment retry after mid-run Lab failure

Tracking: BIC-meta#310 · Task: 07-14-manual-experiment-retry

## Goal

When a dispatched experiment runs partway and the Lab reports a terminal
`FAILED`/`CANCELLED` (robot / instrument / material error), let the chemist
**manually retry** that experiment — as a brand-new attempt that carries the
prior parameters forward and reuses the physical sample tubes that never moved,
while the failed attempt's record stays frozen for audit.

## Guiding principle (Drake ruling 2026-07-14)

Physical failure is irreversible — you cannot revert time. So "retry" is **not**
reopening the dead trial. It is a new attempt, and the failed trial's record
must stay **frozen** (never mutated) so "what was used when it failed" is
permanently auditable. This is the closed-loop requirement that rules out
mutating the failed trial's params.

## Confirmed facts (from codebase investigation)

- **Lab has no re-dispatch endpoint.** `FAILED` is a hard terminal: one step's
  failure marks that step FAILED, cancels the rest, and the whole task → FAILED
  (`BIC-lab-service task_service.py:918`). Only `POST /` create-task, `cancel`,
  and TLC `rounds`/`observation`/`cleanup` (AWAITING_CONFIRMATION-only) exist.
  So a retry's new trial dispatches as a brand-new lab task.
- **Agent: a lab-failed trial is stuck.** `apply_terminal_from_lab`
  (`trials_repo.py:541-618`) writes terminal status guarded by
  `WHERE status NOT IN (completed, failed)` — un-reopenable — and never touches
  `trials.phase`. A lab-failed trial's `phase` stays at `conducting` forever;
  the only phase-advance table (`runtime_emitted.py:64-67`) has no edge back to
  `collecting_params`/`rts`, so `submit_l4_execution` (gated `phase == rts`,
  `guardrail.py:48-70`) is permanently refused.
- **Only TLC Rf-retry mints new attempts today.** `tlc.py` `_auto_retry_node`
  (out-of-Rf-window loop) is the sole production path that mints a new attempt
  for an existing job. CC/RE/FP have **zero** reopen-after-failure path. That
  loop is unrelated to a lab dispatch/execution failure and does not copy
  `lab_logistics` forward.
- **`UNIQUE(job_id, attempt)`**; `TrialsRepo.next_attempt` returns
  `max(attempt)+1` (`trials_repo.py:329`). `derive_job_status` projects the
  MAX-attempt trial, so a fresh `pending` attempt rolls the job out of `failed`
  (`jobs_repo.py:51-82`) — job status is a live projection, not sticky.
- **Params draft lives per-trial** (`Trial.params` JSONB `{from_user,
  recommended, lab_logistics}`, `models.py:375`). The failed trial's draft is
  intact on its row but orphaned: its tubes are stamped `properties.trial_id ==
  <dead trial>` and the reconcile removal-diff skips other trials' tubes
  (`material_reconcile.py:371`).
- **Tube reassignment already relocates in place, preserving `tube_id`** (07-11
  atomic Lab Service location-update; reconcile is material-generic).
- **Portal already models `attempt`** (`workspaceStore.ts:224`, retry mints
  `max+1`), but `MaterialPreparationPanel` receives only an opaque `taskId` — no
  `attempt` / `isRetry` — and occupied grid cells are structurally inert (no
  `onClick`; `SampleTubeBoxGrid.tsx:237` routes `cell.filled` to a `<span>`).
- **Failure narration makes no lab call.** `_narrate_pipeline.py:142-170`
  narrates from conversation context only; `query_l4_status` exists for CC/RE
  scopes (`tools.py:1647`, `2732`) but is never invoked by the narrate pipeline.

## Requirements

1. **User-triggered retry entry.** After a trial reaches a lab terminal
   `failed`/`cancelled`, the chemist can trigger a retry of that experiment from
   the product surface. Retry is explicit and user-driven — no automatic
   re-dispatch (consistent with the existing "do not promise an automatic
   retry" narration).

2. **New attempt, copied params.** Retry mints a new trial attempt
   (`max(attempt)+1`) for the same job, copying the failed trial's `from_user`
   and `recommended` params forward. The new trial's phase is
   `collecting_params` so the chemist re-confirms lab-logistics before dispatch.

3. **Failed trial frozen.** The failed trial's row (status, params including
   `lab_logistics`, error, result) is never mutated by the retry. Its record
   remains a complete, auditable snapshot of the failed attempt.

4. **Physical tubes reused via stamp relocation.** The physical sample tubes
   that never moved are a single lab record each — not moved, not copied, not
   deleted. On retry their trial-stamp (`properties.trial_id`) is relocated in
   place from the dead trial to the new trial (preserving `tube_id`, reusing the
   existing atomic relocate mechanism). The new trial owns cleanup authority.

5. **No occupied-slot rule change (supersedes #310's original direction).**
   Because the tubes are re-stamped to the new trial, they appear on the new
   trial's lab-logistics panel as **already-selected items** (editable /
   removable via their item card), not as occupied slots the user must click.
   The 07-12 insert-and-assign-on-EMPTY-only panel rule is unchanged;
   `select-existing` (#188) stays retired. BIC-meta#310 is updated to record that
   stamp-relocation supersedes the "occupied-slot selectable" approach.

6. **Retry dispatches as a new lab task.** The new trial's dispatch creates a
   brand-new lab task; the failed lab task stays failed. No lab re-dispatch
   endpoint is introduced.

7. **Failure narration grounded in real lab state.** On a lab
   `failed`/`cancelled` terminal, the failure narration first reads real lab
   state via `query_l4_status` and narrates from it (not only the tool-return
   error string), then surfaces the retry affordance.

8. **Scope: TLC only** (Drake ruling 2026-07-14). This task implements retry for
   TLC only. The ruled tube-reuse semantics (Req 4, 5) are TLC-specific and match
   the original scenario. CC/RE/FP retry (which would need a generic
   mint-attempt + phase-reset path, and for which "retry" is largely re-dispatch
   with no manual material reuse) is a deliberate follow-up, out of scope here.

## Acceptance Criteria

- [ ] A trial that reached lab `failed`/`cancelled` exposes a chemist-triggered
      retry action; there is no automatic re-dispatch.
- [ ] Triggering retry creates a new trial with `attempt = max(attempt)+1` for
      the same job, and the job status rolls off `failed` to reflect the new
      pending attempt.
- [ ] The new trial's `params.from_user` and `params.recommended` equal the
      failed trial's, and its phase is `collecting_params`.
- [ ] The failed trial's row is byte-for-byte unchanged after the retry
      (status, params incl. `lab_logistics`, error_message, result, finished_at).
- [ ] Each reused physical tube remains a single lab inventory record with its
      original `tube_id`; after retry its `properties.trial_id` equals the new
      trial, and no duplicate tube record is created.
- [ ] On the new trial's lab-logistics panel, the reused tubes render as
      already-selected editable items (correct purity + position); the panel
      still rejects clicking occupied cells for fresh insertion (07-12 rule
      intact).
- [ ] Confirming + dispatching the new trial creates a new lab task; the failed
      lab task remains failed.
- [ ] After the new trial's reconcile, removing a reused tube on the new trial
      deletes it (new trial owns it); the failed trial's frozen record is
      unaffected.
- [ ] A lab `failed`/`cancelled` terminal narration cites real lab state
      obtained from `query_l4_status`, not only the tool-return error.
- [ ] BIC-meta#310 is updated to record the stamp-relocation supersession.

## Out of Scope

- Automatic (system-initiated) retry of any kind.
- Reopening / mutating the failed trial in place.
- A lab-service re-dispatch endpoint for a FAILED task.
- Reintroducing the retired `select-existing` (#188) panel interaction.
- Tank / solvent-reuse retry choreography (that is the separate TLC round loop).

## Open Questions

None blocking. All product decisions resolved by Drake rulings 2026-07-14
(retry semantics, tube-stamp relocation, TLC-only scope).
