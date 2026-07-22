# Design — Manual experiment retry after mid-run Lab failure (TLC)

Scope: TLC only (prd.md Req 8). Tracking BIC-meta#310.

## 1. The core problem, restated (first principles)

A lab-failed TLC trial is a dead end: its `phase` is stuck at `conducting`,
un-reopenable, and the physical tubes it created are stamped to it. The chemist
wants to run the experiment again with the same design and the same tubes.

Fundamental truths that constrain the design:

- **T1 — Physical failure is irreversible.** The failed trial's record must stay
  frozen; the retry cannot mutate it (prd Guiding principle).
- **T2 — One physical tube = one lab record.** The tubes did not move, so there
  must remain exactly one lab inventory record per tube; the retry must not
  create a duplicate (root PRD rule 6 — TLC physical inventory integrity).
- **T3 — A trial owns its tubes via `properties.trial_id`.** Reconcile removals
  only touch this-trial-stamped tubes (`material_reconcile.py:371`). For the new
  trial to own (edit / remove / clean up) the reused tubes, they must carry the
  new trial's stamp.
- **T4 — Dispatch requires `phase == rts`, reached only from `collecting_params`
  via a confirmed params form.** So the new trial must start at
  `collecting_params` and go through the normal confirm→rts→dispatch ladder.
- **T5 — Lab has no re-dispatch; a new trial = a new lab task.**

From these: the retry mints a new attempt, COPIES the failed trial's design
params, RELOCATES each reused tube's stamp (not the tube) to the new trial, and
re-enters the normal collecting_params ladder. Nothing about the failed trial or
the physical tubes is destroyed.

## 2. Layer boundaries and what changes

| Layer | Change | Why |
|---|---|---|
| BIC-lab-service | Add a **re-stamp** capability: update a tube's `properties.trial_id` (and purity/exp fields) WITHOUT moving it. | `relocate_sample_tube` only moves location and preserves properties (`material_reconcile.py:318`); no existing op re-stamps in place (T3). |
| BIC-agent-service | New **retry action**: mint attempt, copy params, re-stamp the prior tubes to the new trial, set phase `collecting_params`. Plus failure narration reads `query_l4_status`. | No reopen path exists today (prd facts); narration makes no lab call. |
| BIC-agent-portal | **Retry affordance** on a failed TLC trial's surface; thread it to the new-trial workspace so Material Prep shows the reused tubes as already-selected. | Portal has `attempt` but no retry trigger and no re-dispatch state (explore Q5). |
| BIC-shared-types | Request/response model for the re-stamp lab op + the retry endpoint, if the lab contract needs a new shape. | Rule 10 — contract change needs a shared-types + spec update. |

## 3. Data flow

```
[failed TLC trial]  status=failed, phase=conducting, params={from_user, recommended, lab_logistics{sample_tubes:[t1,t2]}}
        │  tubes t1,t2 in lab, properties.trial_id = <failed trial>
        ▼
chemist clicks "Retry" (portal)  ──►  POST /sessions/{sid}/.../retry  (agent, NEW endpoint)
        ▼  agent, one transaction:
  1. next_attempt(job_id) → mint new Trial row (attempt = max+1, phase=collecting_params)
  2. copy failed.params.from_user + failed.params.recommended → new.params
     (lab_logistics.sample_tubes copied too — the selection the chemist starts from)
  3. re-stamp t1,t2 in lab: properties.trial_id = <new trial>   (lab RE-STAMP op, no move)
  4. failed trial row: UNTOUCHED (T1)
        ▼
portal opens new trial at collecting_params; Material Prep renders t1,t2 as
already-selected items (they are stamped to this trial, live in the draft)
        ▼
chemist edits (optional) → Validate Readiness (reconcile, existing path) → confirm params
→ phase rts → submit_l4_execution → NEW lab task
```

## 4. Key design decisions

### D1 — Re-stamp is a distinct lab op, not overloading relocate

`relocate_sample_tube` (`preparations.py:108`, `preparation_service.py:810`)
changes location and preserves properties. Re-stamp is the inverse: change
`properties.trial_id`, keep location. Two options:

- **D1a (recommended): extend the existing relocate op to accept an optional
  `properties` patch**, so one atomic call can move-and-restamp OR restamp-only
  (same-location). Reuses the atomic location-update machinery the reconcile
  already trusts; the retry passes same-location + new stamp. Minimal new
  surface.
- D1b: add a separate `re-stamp` endpoint. Cleaner name, but a second op that
  duplicates the atomic-update plumbing and a second reconcile branch. Rejected
  as more surface for the same effect (Rule 2).

Decision: **D1a** — extend relocate to carry an optional properties patch;
retry issues a same-location relocate with `properties.trial_id = new`.

### D2 — Retry is an agent endpoint that mints + copies + re-stamps atomically

A single `POST .../retry` on the failed trial. It does NOT go through the
specialist ReAct loop (there is no chemist turn to react to yet) — it is a
deterministic state transition, like the existing deterministic event-apply
paths (`TaskCreatedEvent.apply` already calls `next_attempt`,
`runtime_emitted.py:1256`). The re-stamp lab calls run inside the same unit of
work as the trial insert + param copy; a mid-flush lab failure aborts the whole
retry loudly (Rule 9), leaving the failed trial and the tubes untouched.

Gate: retry is allowed ONLY when the target trial's status is a lab terminal
`failed`/`cancelled` (mirror of the `AWAITING_CONFIRMATION`-only gate on TLC
append). Any other state → 409.

### D3 — Copy semantics: design params yes, execution state no

Copied forward: `params.from_user`, `params.recommended`,
`params.lab_logistics.sample_tubes` (so the reused tubes are the starting
selection). NOT copied: status, execution_status, result, error_message,
analysis, finished_at — the new trial starts clean at `collecting_params`.
Readiness is NOT copied (root PRD rule 12 — readiness never persists across a
reload; a fresh Validate Readiness is required before dispatch).

### D4 — Failure narration reads real lab state

On a lab `failed`/`cancelled` terminal, before narrating, the narrate pipeline
calls `query_l4_status` for the failed lab task and feeds its state into the
prompt fact-block (`_narrate_pipeline.py` prompt-selection ~325-337). Two
sub-points:

- TLC has **no** `query_l4_status` tool today (`tools.py:1938`, TLC conducting
  is owned by the deterministic loop). The narrate pipeline is deterministic
  code, not the ReAct loop, so it can call the lab client directly rather than
  needing the tool in the TLC catalogue — preferred, keeps TLC's tool surface
  unchanged.
- The narration then surfaces the retry affordance instead of only "you may
  edit params and ask to retry". It still must NOT promise an automatic retry
  (existing contract).

### D5 — Portal: thread `attempt`/retry into Material Prep, no panel rule change

The portal already mints `attempt = max+1` for a new trial
(`workspaceStore.ts:1522`). The retry action calls the new agent endpoint, then
the workspace loads the new trial like any other attempt. Because the reused
tubes are now stamped to the new trial and present in its `lab_logistics`
draft, they render through the EXISTING already-selected item-card path — no
change to `SampleTubeBoxGrid`'s occupied-cell inertness, no `select-existing`
revival (prd Req 5). The only portal additions are: (a) a Retry control on a
failed TLC trial, (b) wiring it to the endpoint + opening the new attempt.

## 5. Contracts touched (Rule 10 — spec updates required in the same change)

- **Lab HTTP**: `relocate_sample_tube` request gains optional `properties`
  patch (D1a). Spec: `BIC-lab-service .trellis/spec/backend/.../preparations`.
- **Agent HTTP**: new `POST /sessions/{sid}/experiments/.../trials/{trial_id}/retry`
  (exact path TBD in implement). Spec: `BIC-agent-service
  .trellis/spec/backend/L1/http-routes.md`.
- **Agent L2/L3**: retry service method (mint+copy+re-stamp) and the narrate
  pipeline lab-status read. Spec: L2 session service, L3 graphs/narrate.
- **Shared-types**: relocate request model change (+ retry response if it
  returns a trial snapshot). Version bump per shared-types SOP.
- **Root Production PRD**: add the retry rules; **BIC-meta#310** updated to
  record stamp-relocation supersedes the occupied-slot-selectable approach.

## 6. Compatibility / rollback

- Additive: a new endpoint + an optional request field + a narrate branch.
  Nothing existing changes shape, so a partial rollback (drop the portal control)
  degrades to "no retry UI" without breaking dispatch or reconcile.
- The failed-trial-frozen invariant means retry can be re-run safely: a second
  retry off the same failed trial would mint attempt+1 again — guard against
  double-mint by gating on the failed trial still being the max attempt (an
  already-retried failed trial is no longer max, so its retry is refused). Detail
  to nail in implement.

## 7. Risks / weakest points (to validate in implement)

- **R1 — re-stamp atomicity across N tubes.** If tube 1 re-stamps and tube 2's
  call fails, we must not leave a half-migrated set. Mitigation: run re-stamps
  inside the retry unit of work; on any failure, abort and surface loudly
  (tubes stay stamped to the failed trial, new trial not committed). Confirm the
  lab op + agent tx boundary actually gives this.
- **R2 — double retry / concurrent retry.** Two retry clicks. Gate on
  max-attempt + the failed status (D2, §6).
- **R3 — the reused tube's cleanup lifecycle.** After re-stamp, the failed
  trial's frozen `lab_logistics` still NAMES t1,t2 but no longer owns them.
  Confirm nothing in ELN/history reads the failed trial's tubes expecting them
  live-stamped to it. (Failed trials are not ELN-eligible — ELN gates on
  phase=done — so likely safe; verify.)
- **R4 — TLC round loop vs retry.** The TLC Rf-retry `_auto_retry_node` already
  mints attempts for the in-Rf-window loop. A lab-FAILED terminal is a different
  trigger. Confirm the two mint paths don't collide on attempt numbering
  (both use `next_attempt`/max+1, so they serialize — verify no race).
