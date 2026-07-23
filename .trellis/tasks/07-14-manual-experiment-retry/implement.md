# Implement — Manual experiment retry after mid-run Lab failure (TLC)

Scope: TLC only. See prd.md + design.md. Dependency order is bottom-up
(contract producers before consumers): lab → shared-types → agent → portal →
docs/spec.

## Pre-flight

- [ ] `trellis-before-dev` for each package before editing it (load
      `.trellis/spec/<layer>/`).
- [ ] Bench up (`make doctor` green) for the eventual E2E check.

## Stage 1 — Lab: re-stamp capability (D1a)

- [ ] Extend `SampleTubeRelocateRequest` (shared-types) with an optional
      `properties` patch, OR confirm relocate can already carry it. If the model
      lives in shared-types, this stage starts there.
- [ ] `preparation_service.relocate_sample_tube` (`preparation_service.py:810`):
      when a `properties` patch is present, merge it into the tube's properties
      in the same atomic location-update (same-location allowed = re-stamp only).
- [ ] Route `preparations.py:108`: accept the optional patch.
- [ ] Tests: re-stamp changes `properties.trial_id`, preserves `tube_id` and
      location; same-location re-stamp is a valid no-move update; occupied-target
      move + restamp still atomic. (Rule 7 — assert the WHY: the tube keeps
      identity so the new trial owns it.)
- [ ] Validate: `cd BIC-lab-service && uv run pytest tests/ -k "relocate or restamp or tube"`

## Stage 2 — Shared-types (if a contract shape changed)

- [ ] Add/adjust the relocate request model + any retry response model.
- [ ] `uv version --bump ...` (ask bump level per rule 12) + commit lock.
- [ ] Validate: shared-types test suite.

## Stage 3 — Agent: retry action (D2, D3)

- [ ] L2 service method `retry_failed_trial(session_id, trial_id)`:
      gate status ∈ {failed, cancelled} AND target is job's max attempt (R2);
      else 409. In ONE unit of work: `next_attempt(job_id)` → insert new Trial
      (phase=collecting_params); copy `from_user` + `recommended` +
      `lab_logistics.sample_tubes`; for each reused tube call lab relocate with
      same-location + `properties.trial_id=<new>`. Failed trial row untouched
      (assert in test). Mid-flush lab failure → abort + loud error (R1).
- [ ] L1 route `POST .../trials/{trial_id}/retry` returning the new trial
      snapshot.
- [ ] Narration (D4): in `_narrate_pipeline.py` failure branch
      (~325-337), call the lab-status client for the failed lab task and feed
      state into the prompt fact-block; surface the retry affordance; keep
      "no automatic retry" wording.
- [ ] Tests: retry mints attempt+1 with copied params at collecting_params;
      failed trial byte-for-byte unchanged; tubes re-stamped to new trial, no
      duplicate lab record; double-retry off a non-max failed trial → 409;
      narration cites lab state.
- [ ] Validate: `cd BIC-agent-service && uv run pytest tests/ -k "retry or narrate"`
      then the full unit suite for touched layers.

## Stage 4 — Portal: retry affordance (D5)

- [ ] Add a Retry control on a failed TLC trial's result/progress surface.
- [ ] Wire it to the new endpoint; on success open the new attempt in the
      workspace (reuse existing attempt-switch path).
- [ ] Confirm Material Prep renders the reused tubes as already-selected items
      (they arrive stamped + in the draft) — NO change to `SampleTubeBoxGrid`
      occupied-cell inertness.
- [ ] i18n: retry control text zh/en.
- [ ] Validate: `cd BIC-agent-portal && pnpm test` + typecheck/lint.

## Stage 5 — Docs / spec / contracts (Rule 10 — same change set)

- [ ] Root `Production-PRD.md`: add the retry rules (new attempt + copy params +
      tube stamp relocation + failed trial frozen + failure narration reads lab
      state) and matching acceptance criteria; Change Log entry.
- [ ] Update `BIC-meta#310`: stamp-relocation supersedes the occupied-slot
      approach; the panel rule is unchanged.
- [ ] Lab spec: relocate `properties` patch.
- [ ] Agent spec: L1 retry route, L2 retry method, L3 narrate lab-status read.
- [ ] Agent Project PRD (`docs/project-prd.md`) if copilot-visible behavior
      changed (the retry affordance narration).

## Stage 6 — End-to-end verification

- [ ] Live bench: dispatch a TLC trial, force a lab FAILED terminal, click
      Retry, confirm the new attempt reuses the same tubes and dispatches a new
      lab task; failed attempt still visible + frozen in the attempt switcher.
      (Dispatch `bic-e2e-runner` per CLAUDE.md rather than hand-driving.)

## Rollback points

- Each stage is additive and independently revertible. Dropping Stage 4 leaves a
  working backend retry with no UI. Dropping Stage 1's `properties` patch blocks
  re-stamp — do not ship Stage 3 without Stage 1.

## Open validation targets (from design §7)

- R1 re-stamp atomicity across N tubes · R2 double/concurrent retry gate ·
  R3 failed trial's frozen tubes not read live elsewhere (check ELN/history) ·
  R4 no attempt-number race with the TLC Rf-retry loop.
