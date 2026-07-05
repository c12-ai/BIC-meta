# Research: Option B (confirm-wins / phase-guard) blast-radius verification

- **Query**: Verify the proposed Option B fix for `task_params_set` clobbering a confirmed `recommended` section, against ACTUAL source in BIC-agent-service.
- **Scope**: internal
- **Date**: 2026-06-28
- **Repo root for all paths below**: `/Users/drakezhou/Development/BIC/BIC-agent-service`

## Verdict (lead)

**Option B is feasible AND safe for CC/RE, but it CANNOT be implemented purely "inside `apply` reading event state" — `apply` must read the trial's CURRENT phase from the DB (`await tx.trials.get(...)`), exactly like `FormConfirmedEvent.apply` already does.** The phase signal is NOT on the `TaskParamsSetEvent` payload today (it carries only `trial_id` + `params`), so the guard must do a read inside `apply`. No CC/RE flow legitimately clears `recommended` after `rts` — verified, nothing in the codebase ever sets `recommended` to None/null. One caveat that argues for caring about implementation shape: a section-preserving JSONB merge helper already exists (`merge_params_from_user_keys`), which is a cleaner primitive than a phase-gate-then-replace.

---

## Findings

### 1. Emitter contract — every emit carries the FULL merged draft (one exception is a topology seed)

Every `TaskParamsSetEvent` is constructed via `emit_event(runtime, TaskParamsSetEvent, trial_id=..., params=<merged>)`. The merge helpers (`tools.py:278-280` `_merge_draft_section`, `tools.py:295-297` `_set_draft_section`) BOTH start from the existing `draft` and only touch ONE named section, carrying the other two sections over untouched — so each emit is "full draft as the emitter currently sees it."

| Emit site | File:line | Section mutated | Partial / clears a section? |
|---|---|---|---|
| `update_cc_params` (from_user + lab_logistics) | `tools.py:929` | from_user / lab_logistics | No — merges into existing draft |
| CC agent-tool `recognize_tlc_plate` | `tools.py:999` | from_user | No |
| `recommend_cc_params` | `tools.py:1053` | recommended (WRITE) | No — sets a value |
| `update_tlc_params` | `tools.py:1306` | from_user / lab_logistics | No |
| `recommend_tlc_params` | `tools.py:1354` | recommended (WRITE) | No |
| `update_re_from_user` | `tools.py:1840` | from_user | No |
| `update_re_lab_logistics` | `tools.py:1869` | lab_logistics | No |
| `recommend_re_params` | `tools.py:1919` (set at 1918) | recommended (WRITE) | No |
| CC `auto_recommend` node | `cc.py:501` (set at 500) | recommended (WRITE) | No |
| RE `auto_recommend` node | `re.py:416` (set at 415) | recommended (WRITE) | No |
| TLC `_evaluate_tlc_result_node` | `tlc.py:751` (built at 750) | from_user (Rf write-through) | No — merges `{...draft, from_user: merged_from_user}` |
| TLC retry path | `tlc.py:838` | retry_draft | (retry-loop, see caveat) |
| `specialist_dispatcher` carry-forward persist | `specialist_dispatcher.py:~219` | from_user seed | **Intentionally partial** — see below |

**The ONE intentionally-partial emit**: `specialist_dispatcher` (Fix 1, task 06-21-cc-carryforward; documented at `L4/events.md:153` and `specialist_dispatcher.py:207-219`). RIGHT AFTER `TaskCreatedEvent` on a fresh planned CC dispatch carrying a TLC→CC seed, it emits a `TaskParamsSetEvent` whose `params` is `{"from_user": carried}` (only `from_user`). This is a FRESH trial (phase `collecting_params`, no `recommended` yet), so it does NOT clobber anything. **Important for Option B**: this legitimately-partial emit happens at `collecting_params`, so a phase-guard keyed on "stale collecting-era write hitting an `rts`+ trial" would NOT block it.

**No emit site intentionally CLEARS a section.** `grep` for any `recommended = None`, `_set_draft_section(..., None)`, `del ...recommended`, `pop("recommended"...)`, `recommended: null` across `app/` returns ZERO hits (the only `recommended ... None` match is the defensive read at `tlc.py:723`).

#### Where the bug's partial blob comes from
The seed source of `params_draft` per turn:
- Cross-turn re-entry (`reception_node.py:437-438`): `out["params_draft"] = dict(trial.params)` — FULL persisted blob incl. `recommended`.
- Fresh planned CC dispatch (`reception_node.py:696-698`): `bundle["params_draft"] = {"from_user": carried}` — partial, but `collecting_params`.

The wedge in the report is an **in-flight / late LLM turn**: the model's tool call (`update_*`) merges into whatever `state.params_draft` that turn was built from. If that turn was admitted while still in `collecting_params` (before the API-time form-confirm flipped the trial to `rts` and wrote `recommended`), its `state.params_draft` has no `recommended`, and its `update_*` emit produces `{from_user: ...}` (no `recommended`). When that stale emit's `apply` lands AFTER the confirm already persisted `recommended`, the whole-blob replace strips it.

### 2. The apply — blind whole-blob replace, NO phase access on the payload (but reachable via tx)

`TaskParamsSetEvent` (`runtime_emitted.py:637-662`):
```python
kind = "task_params_set"
trial_id: str = ""
params: dict[str, Any] = {}

async def apply(self, tx: TransactionLike) -> None:
    await tx.trials.update_fields(
        trial_id=self.trial_id,
        fields={"params": self.params},   # <-- whole-blob replace
    )
```
- The event carries ONLY `trial_id` + `params`. It does NOT carry the source-turn phase, nor any `collecting_params`/`rts` discriminator.
- **BUT** `apply` receives `tx: TransactionLike` and `tx.trials.get(...)` is available and already used by a sibling apply: `FormConfirmedEvent.apply` does `trial = await tx.trials.get(trial_id=target_trial_id_raw)` at `runtime_emitted.py:574` and reads `trial.phase` at line 583. So **`TaskParamsSetEvent.apply` CAN read the trial's current persisted phase** by adding the same `tx.trials.get(self.trial_id)` call — no new event field is strictly required for the phase signal.

### 3. Phase enum / lifecycle / where `recommended` + phase are written

- Enum: `app/core/enums.py:110-125` `class TrialPhase(StrEnum)` — values `COLLECTING_PARAMS="collecting_params"`, `RTS="rts"`, `CONDUCTING="conducting"`, `DONE="done"`. Durable DB value (also the L3 `SpecialistPhase` literal at `app/runtime/types/specialist.py:169-171`).
- Transition map: `runtime_emitted.py:60-63` `_FORM_CONFIRM_PHASE_ADVANCE = {("collecting_params","params"):"rts", ("conducting","result_review"):"done"}`.
- **`FormConfirmedEvent.apply` (`runtime_emitted.py:583-613`) is the params-confirmed transition AND the `recommended` writer**: on `confirm_kind=="params"` with a non-empty payload it writes `update_fields["params"] = dict(self.form_values)` (line 604-605) — the full `{from_user, recommended, lab_logistics}` blob — AND advances `phase → rts` (line 602 `update_fields={"phase": new_phase}`, applied together at lines 610-613). So **reaching `rts` ⇔ a confirm just persisted `recommended`.** Phase `rts` (or later) is a reliable "params confirmed, sections are authoritative" signal.
- Corroborating read-side signal: `reception_node.py:421-423` already treats `trial.phase in ("rts","conducting","done")` as "params were already confirmed" (`params_confirmed=True`).

### 4. CC/RE shared usage — does any CC/RE flow rely on a whole-blob CLEAR after `rts`? NO.

- Every CC/RE `recommended` write is `_set_draft_section(draft, "recommended", <model_dump()>)` with a concrete value: `cc.py:500`, `re.py:415`, `tools.py:1052` (`recommend_cc_params`), `tools.py:1918` (`recommend_re_params`). Never a clear.
- CC/RE consume `recommended` only by READING it: `submit_l4_execution` gate (`tools.py:512`, `tools.py:532`, `tools.py:558` — `*_form.recommended is None` → soft block), and `analyze_*_result` (`tools.py:637-638` `if params.recommended is None: raise`, `tools.py:655-656` same for RE). These are reads/guards, not clears.
- The `auto_recommend` promotion routers (`cc.py:238`, `re.py:210`) only fire when `not draft.get("recommended")` AND only in `collecting_params` (the router runs pre-rts). They never null an existing `recommended`.
- Exhaustive grep for any recommended-clearing statement across `app/` = ZERO hits (§1).

**Conclusion: no CC or RE flow legitimately relies on a `task_params_set` whole-blob replace to clear/null a section after `rts`. Option B's guard does NOT break CC/RE.** A guard that says "a `collecting_params`-era `task_params_set` must not strip `recommended`/`lab_logistics` once the trial is at `rts`+" is invisible to every real CC/RE write, because every real write either (a) happens at `collecting_params`, or (b) carries the section it's touching plus the others it read from the (already-confirmed) draft.

### 5. Where the guard sits — must read trial phase inside `apply`

Two variants:

- **(Feasible, recommended) Guard inside `apply` reading the trial's current phase.** `apply` does `trial = await tx.trials.get(self.trial_id)`; if `trial.phase in ("rts","conducting","done")`, do NOT do a blind whole-blob replace. Instead either (i) skip the write if the incoming `params` lacks a `recommended` the trial already has, or (ii) merge so confirmed sections survive. This needs NO new event field — `tx.trials.get` is proven available (`FormConfirmedEvent.apply:574`).
- **(Also feasible, heavier) Event carries the source-turn phase.** Add `source_phase: str` to `TaskParamsSetEvent`, set by the emitter from `state.current_phase`. Lets `apply` decide without a DB read. NOT required given variant 1 works; only worth it if a same-transaction read of the just-written phase is a concern (it isn't — apply runs after the confirm's apply committed in a prior turn/transaction).

**Data NOT available at apply time that would force the event-carries-phase variant: none.** The phase is durably on the trial row and reachable via `tx.trials.get`. So the simplest correct implementation is variant 1.

**Cleaner primitive note (Rule 2 / Rule 8):** `TrialsRepo.merge_params_from_user_keys` (`trials_repo.py:306-358`) already does a section-preserving JSONB merge (`jsonb_set` into `from_user`, leaving `recommended`/`lab_logistics` untouched). The merge philosophy Option B wants already exists in the repo; the design should decide between a phase-gate-then-replace vs. a section-merge on this existing primitive. (Adversarial note: that helper only merges `from_user`; a general "preserve confirmed sections" guard for `recommended`+`lab_logistics` would need a small extension or an apply-level merge.)

### 6. D2 / D3 confirmation — VERIFIED, quoted

**D2 — `tlc.py:722-724` (fail-loud target, the `or {}` swallows a missing recommended):**
```python
recommended = _trial_recommended_param(trial) or TLCParam.model_validate(
    (draft.get("recommended") if isinstance(draft, dict) else None) or {}
)
```
This reads `recommended` from `trial.params` (`_trial_recommended_param`, `tlc.py:230-243`, reads `trial.params["recommended"]`) — i.e. the DB blob that the clobber strips — then falls back to `TLCParam.model_validate({})` when both the trial AND the draft lack it. The `or {}` means a clobbered `recommended` does NOT raise; it silently validates an empty `TLCParam`, which is the wedge masquerading as "valid." This is the fail-loud candidate.

**D3 — `tlc.py:382-385` `_post_react_route` LACKS the `and not trial.analysis_completed` guard:**
```python
if state.current_phase == "conducting":
    trial = state.ctx.find_trial(state.task_id)
    if trial is not None and trial.status.lower() in TERMINAL_TASK_STATUSES:
        return "evaluate_tlc_result"
```
Compare the CC and RE siblings, which BOTH carry the extra guard:

`cc.py:246-249`:
```python
if state.current_phase == "conducting" and tool_name != "analyze_cc_result":
    trial = state.ctx.find_trial(state.task_id)
    if trial is not None and trial.status.lower() in TERMINAL_TASK_STATUSES and not trial.analysis_completed:
        return "auto_analyze"
```

`re.py:218-221`:
```python
if state.current_phase == "conducting" and tool_name != "analyze_re_result":
    trial = state.ctx.find_trial(state.task_id)
    if trial is not None and trial.status.lower() in TERMINAL_TASK_STATUSES and not trial.analysis_completed:
        return "auto_analyze"
```
TLC's `evaluate_tlc_result` promotion re-fires every `conducting`+terminal turn (no `analysis_completed` idempotency gate), so a re-entry after the Rf-eval already ran can re-run `_evaluate_tlc_result_node`, which is the node that hits the D2 `or {}` read. The two issues compound.

### 7. Rule 10 spec docs to update in the same change set

| Spec file | What it documents (must update if the apply contract changes) |
|---|---|
| `.trellis/spec/backend/L3/events.md` | Line 86 (roster row: `TaskParamsSetEvent` "UPDATE `trials.params` (full replace)"), line 153 (FormConfirmed apply incl. "replace semantics"), line 139/142 reduction notes, line 242 (specialist emit list). The "full replace" wording is the contract Option B changes. |
| `.trellis/spec/backend/L4/events.md` | Line 153 (`TaskParamsSetEvent` → "apply: UPDATE `trials.params` (full replace ...)"), line 155 (`FormConfirmedEvent` replace+empty-payload-fallback). |

Both files state the contract as **"full replace"** — Option B turns it into a **phase-conditional / section-preserving** write, which is a contract change and MUST be reflected in both docs (and the apply-intent unit test at `tests/unit/test_runtime_emitted_apply.py:612-644`, whose docstring asserts "writes the FULL merged draft" / "a partial write here would desync").

---

## Caveats / Not Found

- **TLC retry path emit (`tlc.py:838`)**: I confirmed the emit exists with `params=retry_draft` but did not fully trace `retry_draft`'s composition for whether it can be partial at `rts`+. It is part of the deterministic Rf-retry loop (a NEW trial / attempt), so it is unlikely to clobber a confirmed sibling, but the design should glance at it. (Low risk; not the reported wedge.)
- **`task.py current` returned "none"** — no active task is registered, but the task dir exists at the path given in the prompt; I wrote the file there as instructed.
- **Same-transaction read concern**: variant-1 (`tx.trials.get` inside apply) reads the trial phase within the apply transaction. The confirm that set `rts` runs in an earlier turn's transaction (API-time `FormConfirmedEvent`), so by the time a stale `task_params_set` applies, `rts` is already committed and visible. No intra-transaction ordering hazard. (If a confirm and a stale set ever landed in the SAME transaction, ordering would matter — I did not find such a path, but the design should not assume it can't happen.)
- **Not adversarially disproven**: I could not find any flaw that flips the recommendation to Option A. The phase signal IS available at apply time, and no CC/RE flow relies on a post-`rts` whole-blob clear. Option B stands.
