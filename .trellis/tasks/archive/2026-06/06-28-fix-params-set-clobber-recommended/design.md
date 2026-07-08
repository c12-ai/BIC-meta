# Design — fix late `task_params_set` clobbering confirmed `recommended`

Implements `prd.md`. **Plan-only**: this doc decides the D1 approach + blast radius
for owner review BEFORE implementation. Grounded in
`../06-27-lab-bench-box-selector/research/post-dispatch-turn-failed-diagnosis.md`.

## Key reframing (read first)

The emitter is NOT the naive bug it first looks like. Every params-mutating tool
emits **ONE `TaskParamsSetEvent` carrying the FULL merged draft** (`tools.py:894`,
`:929`, `:999`, `:1053`, …: `params=merged`), and `TaskParamsSetEvent.apply`
(`runtime_emitted.py:658-662`) is a **deliberate whole-blob replace** matching that
contract. So a blind "section-merge in apply" would FIGHT the emitter (which
already merged in-memory and expects its blob to be authoritative).

The real defect is a **stale-writer race across turns**, not a within-event bug:

- The params-confirm landed at **API time** (`FormConfirmedEvent.apply`, seq36) and
  wrote `recommended` to `trials.params` — but it happened in a DIFFERENT turn
  (`2f382694`) while turn `3d080e9e` was **still running** with an in-memory
  `params_draft` that NEVER contained `recommended` (its own `recommend_tlc_params`
  had failed on null `target_window`, seq39).
- When `3d080e9e` later emitted its full-merged-draft `task_params_set` (seq37),
  that `merged` was missing `recommended` → its whole-blob replace **reverted** the
  newer confirmed state.

So: **an older turn's draft overwrote a newer turn's confirmed persistence.** Any
fix must make the persisted `recommended` survive a stale in-flight turn's blob.

## D1 — the three options + blast radius

`TaskParamsSetEvent` is SHARED by CC, RE, and TLC. Any change is cross-specialist —
this is the dominant constraint (Rule 8: don't fork TLC behavior silently).

### Option A — section-merge in `TaskParamsSetEvent.apply`
Apply merges the event's sections into existing `trials.params` instead of
replacing (preserve `recommended`/`lab_logistics` the event doesn't carry).
- **Pro**: small, localized to one apply; fixes the symptom for all specialists.
- **Con**: CONTRADICTS the emitter contract ("full merged draft is authoritative",
  `tools.py:894`). If a tool ever *intends* to clear a section (e.g. drop
  `recommended` on a re-recommend), merge would silently keep stale data. Changes
  the meaning of every `task_params_set` for CC/RE too — wide blast radius, subtle.

### Option B — confirm-wins / phase-guard (RECOMMENDED, pending review)
Don't let a `task_params_set` from an in-flight turn overwrite sections written by a
LATER form-confirm / phase advance. Concretely: once a trial has advanced to `rts`
(params confirmed), a `collecting_params`-era `task_params_set` blob must not strip
confirmed sections. Implement as either:
- a guard in `apply` that refuses to null `recommended`/`lab_logistics` when the
  trial phase is already `rts` (the confirm already happened), or
- carry the source turn's phase on the event and no-op a stale write.
- **Pro**: targets the actual race (stale writer vs newer confirm); preserves the
  whole-blob contract for the normal in-turn case; CC/RE unaffected unless they hit
  the same race (which this also fixes).
- **Con**: needs a phase/staleness signal at apply time; more design than A.

### Option C — serialize the API-time confirm against the in-flight turn
Make `submit_form_confirm` not apply mid-flight while the trial's turn is running
(queue the confirm apply behind the turn).
- **Pro**: removes the race at the source.
- **Con**: largest change (touches the orchestrator/confirm ordering); risks
  latency/deadlock; the confirm-at-API-time design is load-bearing elsewhere.

**Recommendation: Option B** (confirm-wins phase-guard) as the primary fix —
smallest change that targets the real race without breaking the emitter contract.
Confirm with owner before implementing; A is the fallback if B's phase signal is
unavailable at apply time.

## ✅ Blast-radius verification (source-grounded, 2026-06-28)

Full report: `research/option-b-blast-radius-verification.md`. **Verdict: Option B
is feasible AND safe — recommendation stands, no flip to A.** Key source facts:

- **Phase signal IS available at apply time.** `TaskParamsSetEvent.apply`
  (`runtime_emitted.py:658-662`) receives `tx`. The sibling `FormConfirmedEvent.apply`
  already does `trial = await tx.trials.get(trial_id=...)` (`runtime_emitted.py:574`)
  and reads `trial.phase` (`:583`). So `apply` can read the current trial phase with
  **zero new event fields** — the guard sits inside `apply` (variant 1). The
  "event-carries-phase" variant is NOT needed.
- **`rts` ⇔ a confirm just persisted `recommended`.** Phase enum
  `TrialPhase.{COLLECTING_PARAMS,RTS,CONDUCTING,DONE}` (`enums.py:122-125`).
  `FormConfirmedEvent.apply` is BOTH the `recommended` writer (`:604-605`) and the
  `collecting_params → rts` advance (`_FORM_CONFIRM_PHASE_ADVANCE`, `:60-63`). Reaching
  `rts` means the chemist-confirmed payload (incl. `recommended`) is already on disk.
- **No emit site ever clears a section.** Grep for `recommended = None` / section-clear
  across `app/` = zero hits. The merge helpers always carry untouched sections forward
  (`tools.py:278-280`, `:295-297`). The one intentionally-partial emit is
  `specialist_dispatcher`'s carry-forward seed (`{from_user: carried}`) — but it fires
  at `collecting_params` on a fresh trial, so the phase-guard ignores it. **Option B
  cannot mask an intentional clear because no intentional clear exists.**
- **CC/RE are safe.** Every `recommended` write is `_set_draft_section(..., <value>)`
  (`cc.py:500`, `re.py:415`, `tools.py:1052`, `tools.py:1918`); all consumption is
  read-only guards (`tools.py:512/532/558`, `:637-638`, `:655-656`). No CC/RE flow
  relies on a post-`rts` whole-blob clear. Option B is a no-op for their normal
  in-turn case.

### Finalized D1 (Option B, variant 1)

In `TaskParamsSetEvent.apply`: before the existing `update_fields(params=self.params)`,
fetch the trial (`await tx.trials.get(trial_id=self.trial_id)`). If the trial phase is
already past `collecting_params` (i.e. `rts`/`conducting`/`done` — params confirmed)
AND the incoming `self.params` is MISSING a section that the on-disk
`trial.params` HAS (`recommended` and/or `lab_logistics`), **carry the on-disk
section forward into the blob** rather than letting the stale blob drop it. The normal
in-turn case (trial still `collecting_params`) keeps the verbatim whole-blob replace —
the emitter contract is preserved exactly where it matters.

Rationale for "carry-forward-on-stale" over "hard refuse": it keeps the FE-sync
write-through semantics intact (the event still updates the sections it DOES carry,
e.g. a late `from_user` edit) while protecting only the confirmed sections an older
turn never had. A blanket "ignore the event when phase>collecting_params" would also
drop legitimate post-confirm `from_user` mirror updates.

## D2 — fail-loud backstop (`tlc.py:722-724`)
Independent of D1. Replace `... or TLCParam.model_validate(... or {})` with an
explicit guard: a terminal TLC trial missing `recommended` (in both `trial.params`
and `draft`) is unrecoverable for Rf-eval → raise an actionable `RuntimeError`
(Rule 9), not a bare `TLCParam({})` ValidationError.

**Research finding (`research/d2-why-recommended-missing.md`): `recommended` is NEVER
legitimately absent on a terminal TLC trial — D2 is a PURE backstop for the D1 race.**
The API confirm gate makes it mandatory: `_validate_params_form_values`
(`service.py:234-239`) runs BEFORE any event is appended and rejects a missing
`recommended` with HTTP 422 (`form_payloads.py:570-571`, `service.py:347-349`). Only a
confirm reaches `rts`; dispatch only fires from `rts` (`tlc.py:322-334`); retries write
their own concrete Mind `recommended` (`tlc.py:834-838`). No code anywhere CLEARS
`recommended` (exhaustive grep = zero). MED005 mock only defaults `rxn`, not
`recommended`, and runs after the crash point. **The sole disk-loss path is the D1
clobber race** (stale `recommended`-less blob applied post-confirm).

→ Therefore D2 must RAISE (never invent a default), and the message must POINT AT D1:
name the trial + phase and state "terminal TLC trial reached Rf-eval with no persisted
`recommended` → likely `task_params_set` clobber (see D1)". If this ever fires after
D1 ships, the race reopened.

## D3 — analysis_completed gate parity (`tlc.py:382-384`) — VALID, ship it

> Self-correction (owner-flagged, source-confirmed 2026-06-28): an earlier revision of
> this doc claimed TLC never writes `analysis_completed` and that D3 was a no-op. **That
> was wrong** — I trusted the stale comment at `tlc.py:360` ("TLC has no analyze tool…
> no analysis_completed gate") and a grep that missed the real emit site. Ground truth
> below.

**TLC DOES write `analysis_completed`.** The deterministic recognition path is TLC's
analyze equivalent (no *LLM* analyze tool, but the work happens):

1. Robot uploads the UV-lit TLC plate image to S3 after execution.
2. The terminal turn routes to `_evaluate_tlc_result_node` (`tlc.py:382-385` →
   `evaluate_tlc_result`), which calls `mind.recognize_tlc_plate(request, attempt=...)`
   with that image + params (`tlc.py:737`) → returns **product Rf**.
3. Deterministic window check: product Rf ∈ user `target_window` → `in_window` = **go**,
   else **fail** (`_post_evaluate_route`, `tlc.py:389-408`).
4. `_emit_result_review_node` emits **`TaskAnalysisCompletedEvent`** (`tlc.py:892`) —
   apply sets `trials.analysis_completed=true` (`runtime_emitted.py:766`) — then opens
   the result-review form. The node's own docstring says it flips this flag "so the
   reconciler does not re-fire the terminal turn" (`tlc.py:871-873`).

So `not trial.analysis_completed` is a **live, correct** re-entry guard for TLC — once
recognition has run, the flag is set and a re-driven terminal turn must NOT re-enter the
eval loop. The CC/RE gates (`cc.py:248`, `re.py:220`) gate on the same flag; TLC's
`_post_react_route` (`tlc.py:382-384`) is simply **missing it**, which is the real gap.

**Research upgrade (`research/d3-tlc-analyze-tool-status.md`): D3 is not just parity —
it fixes a CONTRACT VIOLATION.** The reconciler contract (`reconciler.py:5-11`) requires
every subgraph to honor the entry-time `analysis_completed` check, and MQ-redelivery
dedup depends on it (`event_ingress.py:124-126`). CC/RE honor it; **TLC currently
violates it.** Also confirmed: TLC's recognition path is fully wired (fixture-stubbed at
the Mind layer, same maturity as CC/RE — `mind_client.py:186`), and there is NO ordering
risk (`ctx.analysis_completed` is loaded fresh from DB at turn start,
`orchestrator.py:484,538`; the flag commits during the recognizing turn,
`orchestrator.py:375`; so only LATER re-driven turns read the guard — it can't self-block
the first recognition).

**D3 = SHIP.** Add `and not trial.analysis_completed` to the terminal-trial branch of
`_post_react_route` (`tlc.py:382-384`), matching cc.py/re.py exactly:
```python
if state.current_phase == "conducting":
    trial = state.ctx.find_trial(state.task_id)
    if (
        trial is not None
        and trial.status.lower() in TERMINAL_TASK_STATUSES
        and not trial.analysis_completed          # <-- add (parity with cc.py:248 / re.py:220)
    ):
        return "evaluate_tlc_result"
```
Also fix the now-false comment at `tlc.py:360-361` (Rule 8/Rule 3 — it actively
misleads; it caused this very mis-analysis). Note `TrialSnapshot.analysis_completed`
must be readable from `state.ctx.find_trial(...)` — confirm the snapshot carries it
(it must, since cc.py/re.py already read it the same way).

## Rule 10 — contract / spec impact (verified locations)
- D1 changes the persisted effect of `task_params_set` (a runtime-emitter↔trial-store
  contract). Spec docs that state the current "full replace" wording and MUST be
  updated in the same change set:
  - `BIC-agent-service/.trellis/spec/backend/L3/events.md` (lines ~86, 139/142, 153, 242)
  - `BIC-agent-service/.trellis/spec/backend/L4/events.md` (lines ~153, 155)
  New wording: `TaskParamsSetEvent.apply` is whole-blob replace **while the trial is in
  `collecting_params`**; once params are confirmed (`phase >= rts`) the apply preserves
  confirmed sections (`recommended`, `lab_logistics`) an in-flight blob omits.
- Apply-intent test that encodes the old contract and must be updated:
  `BIC-agent-service/tests/unit/test_runtime_emitted_apply.py:612-644`.
- D2 is internal node behavior; spec touch only if the TLC eval contract is documented.
  D3 is dropped (see above).

## Reuse note (Rule 6)
`TrialsRepo.merge_params_from_user_keys` (`trials_repo.py:306-358`) already implements a
section-preserving JSONB merge, but only for `from_user` keys today. D1's carry-forward
may either extend this primitive or do the carry-forward in `apply` before calling
`update_fields`. `implement.md` picks one — prefer the smallest correct shape (Rule 2).

## Verification plan
- Unit: a `task_params_set` with only `from_user` applied AFTER a confirm that wrote
  `recommended` must leave `recommended` intact (the exact seq36→seq37 race).
- CC/RE regression: their `task_params_set` flows unchanged (Option B should be a
  no-op for the normal in-turn case).
- E2E: re-run the TLC UI→lab flow and assert it proceeds PAST dispatch to
  result-review (no `turn_failed`, trial reaches `analysis_completed`, plan cursor
  advances).

## Blast-radius summary for the owner

The fix touches a CC/RE/TLC-shared event (`TaskParamsSetEvent.apply`). Option B is the
narrowest fix and is **verified safe for CC/RE** (no flow relies on a post-`rts`
whole-blob clear; no emit site clears a section). Decisions for review:

1. **D1 = Option B, variant 1** (phase-guarded carry-forward inside `apply`). ✅ verified
   feasible & safe. Approve?
2. **D2 = ship** (fail-loud when `recommended` genuinely absent on a terminal TLC trial,
   replacing the silent `TLCParam({})`). Approve?
3. **D3 = SHIP** (add `and not trial.analysis_completed` to `_post_react_route`,
   `tlc.py:382-384`, + fix the stale comment at `:360`). ✅ Confirmed valid: TLC's
   recognition node DOES set `analysis_completed` via `TaskAnalysisCompletedEvent`
   (`tlc.py:892`); the gate prevents re-running recognition on an already-recognized
   trial — true parity with cc.py/re.py. (An earlier draft wrongly called this a no-op;
   corrected after owner flag.)
4. Rule 10 spec updates: `L3/events.md` + `L4/events.md` + apply-intent test — in the
   same change set.

No code until these four are reviewed.
