# Implement — fix late `task_params_set` clobbering confirmed `recommended`

Execution plan for `design.md`. **Do NOT start until owner approves the 4 decisions in
design.md § "Blast-radius summary for the owner"** (D1=Option B, D2=ship, D3=drop, spec
updates). All work is in `BIC-agent-service` (single repo; no FE/lab change).

Branch: continue on `feat/tlc-objectlocation-passthrough` (current) unless owner says
otherwise — do NOT create a branch or commit without explicit instruction (per Drake's
global rule + project conventions).

## Pre-flight
- [ ] Run `BIC-agent-service:trellis-before-dev` for the L3/L4 events + specialists layer
      to load coding specs (Rule 6).
- [ ] Confirm owner sign-off on D1/D2/D3/spec recorded in this task.

## Step 1 — D1: phase-guarded carry-forward in `TaskParamsSetEvent.apply`
File: `app/events/runtime_emitted.py:658-662`.
- [ ] Before the existing `update_fields`, fetch the trial:
      `trial = await tx.trials.get(trial_id=self.trial_id)`.
- [ ] If `trial is not None` and `trial.phase != TrialPhase.COLLECTING_PARAMS` (params
      already confirmed): build the effective params by starting from `self.params` and
      carrying forward any of `recommended` / `lab_logistics` that the on-disk
      `trial.params` HAS but `self.params` is missing/empty. Else use `self.params`
      verbatim (preserve the whole-blob contract for the in-turn case).
- [ ] Decide carry-forward locus (Rule 2 — smallest correct): inline in `apply`, OR
      extend `TrialsRepo.merge_params_from_user_keys` (`trials_repo.py:306-358`) to a
      generic section-preserving merge. Prefer inline unless the repo merge is a clean
      drop-in. Mirror the existing typed style (Rule 11 — operate on parsed sections,
      not raw dict-poking, where the surrounding code does).
- [ ] Match the `FormConfirmedEvent.apply` precedent for the `tx.trials.get` call shape
      and the `# type: ignore[attr-defined]` convention already used at `:574`.
- Validation: `cd BIC-agent-service && uv run ruff check app/ && uv run pyright app/`.

## Step 2 — D1 unit test (the exact seq36→seq37 race)
File: `tests/unit/test_runtime_emitted_apply.py` (alongside the existing apply-intent
tests near `:612-644`).
- [ ] Test: trial in `rts` with on-disk `params={from_user, recommended, lab_logistics}`;
      apply a `TaskParamsSetEvent` carrying only `{from_user:{...}}` → assert `recommended`
      and `lab_logistics` survive, AND the new `from_user` IS written (carry-forward, not
      blanket-ignore). Encode WHY in the test name/docstring (Rule 7): "stale in-flight
      blob must not revert a confirmed recommendation".
- [ ] Test: trial in `collecting_params` → apply replaces whole blob verbatim (contract
      preserved for the normal case).
- [ ] Update the existing apply-intent test at `:612-644` if it asserts the old
      unconditional-replace contract.
- Validation: `uv run pytest tests/unit/test_runtime_emitted_apply.py -q`.

## Step 3 — D2: fail-loud in `_evaluate_tlc_result_node`
File: `app/runtime/graphs/specialists/tlc.py:722-724`.
- [ ] Replace `_trial_recommended_param(trial) or TLCParam.model_validate(... or {})`
      with: prefer trial `recommended`, fall back to `draft["recommended"]` ONLY if
      non-empty; if neither yields a usable `recommended`, `raise RuntimeError(...)`
      (Rule 9) — mirror the existing `RuntimeError` at `tlc.py:715-717`. Research
      (`research/d2-why-recommended-missing.md`) confirms `recommended` is NEVER
      legitimately absent post-confirm, so the message must name `task_id` + phase AND
      point at the D1 race ("…no persisted recommended → likely task_params_set clobber
      (D1)"). Do NOT invent a default — raise.
- Validation: `uv run pyright app/`; add/extend a TLC node unit test asserting the
      RuntimeError message when `recommended` is absent (not a bare pydantic
      ValidationError).

## Step 4 — D3: add the `analysis_completed` re-entry gate (`tlc.py:382-384`)
TLC's recognition node DOES set `analysis_completed` (`TaskAnalysisCompletedEvent`,
`tlc.py:892`). Research (`research/d3-tlc-analyze-tool-status.md`): this is a CONTRACT
fix, not just parity — the reconciler (`reconciler.py:5-11`) + MQ-redelivery dedup
(`event_ingress.py:124-126`) require the gate; CC/RE honor it, TLC violates it. No
ordering risk (flag committed during the recognizing turn; only later turns read it).
- [ ] Add `and not trial.analysis_completed` to the terminal-trial branch of
      `_post_react_route` (`tlc.py:382-384`) — exact shape in design.md § D3.
- [ ] Fix the now-false comment at `tlc.py:360-361` ("TLC has no … analysis_completed
      gate") — it actively misled this analysis (Rule 8/Rule 3: correct the lie, don't
      expand scope).
- [ ] Verify `TrialSnapshot.analysis_completed` is readable from
      `state.ctx.find_trial(...)` (cc.py/re.py already read it this way, so it should be).
- [ ] Test (Rule 7 — lock the per-attempt intent): a re-driven terminal turn on an
      already-recognized trial (`analysis_completed=true`) routes to `narrate`, NOT
      `evaluate_tlc_result` (no double-recognition of the SAME scored attempt).
- [ ] Test (Rule 7 — the retry case MUST still work): a NEW attempt trial row
      (`job-trial-2`, fresh `analysis_completed=false`) on a terminal turn DOES route to
      `evaluate_tlc_result` — the new plate image gets re-recognized. Encode WHY: the gate
      dedupes a redelivered/already-scored attempt, it must NOT block re-recognition of a
      new retry attempt (new solvent ratio → new plate → must re-score). `analysis_completed`
      is per-trial-row (`trials_repo.py:130,152`), so attempt 2 starts false.
- Validation: `uv run pyright app/`; TLC router unit test.

## Step 5 — Rule 10 spec update (same change set)
- [ ] `.trellis/spec/backend/L3/events.md` (~86, 139/142, 153, 242): amend the
      `TaskParamsSetEvent` "full replace" wording to the phase-conditional contract.
- [ ] `.trellis/spec/backend/L4/events.md` (~153, 155): same.
- [ ] Keep wording aligned with the implemented behavior (replace while
      `collecting_params`; preserve confirmed sections once `phase >= rts`).

## Step 6 — Quality gate (full)
- [ ] `cd BIC-agent-service && uv run ruff check app/ && uv run pyright app/ && uv run pytest -q`
- [ ] CC/RE regression: confirm their `task_params_set` apply path is unchanged for the
      in-turn case (their trials mutate params while `collecting_params`, so the guard is
      a no-op) — run the CC/RE apply + specialist tests specifically.
- [ ] Dispatch `BIC-agent-service:trellis-check` on the diff (spec compliance + cross-layer).

## Step 7 — E2E (the leg the wedge blocked)
- [ ] Per `CLAUDE.local.md`: dispatch the `bic-e2e-runner` agent — do NOT re-derive the
      bench protocol inline. Goal: TLC UI→lab flow proceeds PAST dispatch to result-review
      (no `turn_failed`; trial advances out of `conducting`; plan cursor advances so
      CC/FP/RE proceed). This also closes child `06-27`'s blocked E2E acceptance criterion.

## Rollback points
- D1, D2, spec are independent commits-worth of change; if E2E reveals D1's carry-forward
  is wrong, revert Step 1 alone (D2 fail-loud is independently safe).
- No DB migration involved (behavior-only change to an event apply) → rollback is a code
  revert, no data fixup.

## Acceptance (from prd.md — restated)
- [ ] Late `from_user`-only `task_params_set` does NOT strip confirmed `recommended`/`lab_logistics`.
- [ ] TLC Rf-eval finds `recommended`, proceeds to result-review; no `turn_failed`, no wedge.
- [ ] Genuinely-absent `recommended` on a terminal TLC trial fails loud (not `TLCParam({})`).
- [ ] CC/RE `task_params_set` unaffected (regression-checked).
- [ ] Spec updated (Rule 10); agent gate green (ruff, pyright, pytest).
- [ ] TLC E2E re-run through to result-review.
