# Research: Every way `recommended` can be MISSING on a terminal TLC trial (D2 scope)

- **Query**: Enumerate EVERY way `trials.params["recommended"]` (a `TLCParam`) can end up missing/empty by the time `_evaluate_tlc_result_node` (`tlc.py:719-724`) runs on a terminal TLC trial. Is D2 a pure D1-race backstop, or is `recommended` legitimately optional for some TLC flow?
- **Scope**: internal (BIC-agent-service), READ-ONLY
- **Date**: 2026-06-28
- **Repo root for all code paths below**: `/Users/drakezhou/Development/BIC/BIC-agent-service`

## Verdict (lead)

**D2 is a PURE defensive backstop for the D1 clobber-race (and its siblings) — `recommended` is NEVER legitimately absent on a terminal TLC trial.** A TLC trial can only reach `conducting`/terminal by going through `rts`, and the ONLY way to reach `rts` is `FormConfirmedEvent.apply` for a `confirm_kind=params` — which is gated at API time by `_validate_params_form_values` → `tlc_params_form_problems`, which **requires `recommended`** (`form_payloads.py:570-571`) and raises `FormValidationError` (HTTP 422) otherwise (`service.py:347-349`). Every retry attempt likewise writes its own concrete `recommended` (`tlc.py:834-838`). No TLC flow (chemist hand-fill, thin-draft, MED005 mock, retry) reaches terminal without `recommended`. **So post-confirm absence is ALWAYS a bug → D2 SHOULD fail loud** (the absence is unrecoverable for recognition; D2 must surface it, not "handle it gracefully" by inventing a default). The MED005 mock fallback is for the `rxn` field only, never for `recommended`.

The ONLY way `recommended` is missing on disk at eval time is a **persistence-overwrite** of the confirmed blob: D1 (the proven race) plus two narrower variants of the same write — all "stale whole-blob `task_params_set` strips a confirmed section." There is no by-design optional path.

---

## Findings

### 1. Who WRITES `recommended` for a TLC trial — three writers, all write a concrete value, none clears

| Writer | File:line | What it writes | Clobber risk to a confirmed `recommended`? |
|---|---|---|---|
| `recommend_tlc_params` (LLM tool) | `tools.py:1350-1354` | `_set_draft_section(draft, "recommended", recommended.model_dump())` from Mind's `response.recommendation.param`, then `emit_event(TaskParamsSetEvent, params=merged)` | Carries the section it sets PLUS the rest of `draft` it read — non-clobbering of OTHER turns, but its OWN emit is a whole-blob `TaskParamsSetEvent` (see §2) |
| `FormConfirmedEvent.apply` (API-time confirm) | `runtime_emitted.py:602-605` | `update_fields["params"] = dict(self.form_values)` — the full `{from_user, recommended, lab_logistics}` confirmed blob — AND `phase → rts` | This is THE authoritative `recommended` writer; reaching `rts` ⇔ a confirm just persisted `recommended` |
| `_auto_retry_node` (deterministic retry) | `tlc.py:834-838` | `retry_draft = {**draft, "recommended": recommended_param.model_dump()}` (Mind re-recommendation), then `emit_event(TaskParamsSetEvent, trial_id=new_trial_id, params=retry_draft)` on the **NEW attempt trial** | Writes a fresh concrete `recommended` for the new attempt; never clears |

`recommend_tlc_params`'s quoted body:
```python
# tools.py:1350-1354
response = await mind.recommend_tlc_mixcase(mind_request)
recommended = response.recommendation.param
merged = _set_draft_section(draft, "recommended", recommended.model_dump())
emit_event(runtime, TaskParamsSetEvent, trial_id=state.task_id, params=merged)
```

`_evaluate_tlc_result_node` ALSO emits a `TaskParamsSetEvent` (Rf write-through, `tlc.py:745-751`) but it carries `{**draft, "from_user": merged_from_user}` — i.e. it preserves whatever `recommended` is in `draft`; it does not write/clear `recommended`.

**Exhaustive grep (source only, logs excluded): NO statement ever clears `recommended`.** `pop("recommended")`, `del ...recommended`, `"recommended": None/null` → ZERO source hits. All five `_set_draft_section(..., "recommended", ...)` calls (`tools.py:1052/1353/1918`, `cc.py:500`, `re.py:415`) write a concrete `.model_dump()`. (Corroborates `option-b-blast-radius-verification.md` §1, §4.)

### 2. The known race (D1) — confirmed, summarized

(Full derivation in `option-b-blast-radius-verification.md` and `06-27-lab-bench-box-selector/research/post-dispatch-turn-failed-diagnosis.md`; not re-derived here.)

`TaskParamsSetEvent.apply` (`runtime_emitted.py:658-662`) is an **unconditional whole-blob replace**:
```python
async def apply(self, tx: TransactionLike) -> None:
    await tx.trials.update_fields(trial_id=self.trial_id, fields={"params": self.params})
```
Race: (1) `FormConfirmedEvent.apply` writes `recommended` + flips `phase→rts` at API time (seq36). (2) A still-running LLM turn admitted while the trial was `collecting_params` had `state.params_draft` with NO `recommended`; its `update_tlc_params` emits `{from_user: ...}` (no `recommended`), whose `apply` lands AFTER the confirm (seq37) and **whole-blob-strips the confirmed `recommended` from disk**. (3) Dispatch still succeeds because it reads from the in-memory FORM_CONFIRM draft, not disk (§5). (4) The autonomous TASK_TERMINAL turn re-seeds `params_draft` from the **stripped disk blob** → `recommended` absent → `tlc.py:722-724` falls to `TLCParam.model_validate({})` → crash.

### 3. Are there OTHER causes besides D1? — Yes, but all are the SAME "stale whole-blob set clobbers a confirmed section" failure class

Because `recommended` is never cleared and is required at confirm time, the only way disk loses it post-confirm is a `TaskParamsSetEvent` whole-blob replace carrying a blob WITHOUT `recommended`. Every emitter that can produce such a blob:

- **D1a — late `update_tlc_params` from a collecting-era turn** (the proven wedge). Emits `{from_user}` only (no `recommended`) because its `state.params_draft` was seeded before the confirm wrote `recommended`. `tools.py:1290-1306`.
- **D1b — late `recognize_tlc_plate` / any other collecting-era `from_user` writer** carrying a `recommended`-less draft. Same shape, same clobber. (TLC's only such tool is `update_tlc_params`; CC has `recognize_tlc_plate` at `tools.py:999`. Listed for completeness across the shared event.)
- **D1c — the `specialist_dispatcher` carry-forward seed emit** (`specialist_dispatcher.py:~207-219`) emits `{"from_user": carried}` (partial by design). But this fires RIGHT AFTER `TaskCreatedEvent` on a FRESH `collecting_params` trial that has no `recommended` yet — so it cannot strip a confirmed one. **Not a real cause** (documented in `option-b-blast-radius-verification.md` §1).

All real causes are the same class: **a `collecting_params`-era whole-blob set applied after the trial advanced to `rts`+**. There is no second, independent mechanism. (The clobber is timing/ordering, not a distinct code path.)

### 4. `recommend_tlc_params` failure modes — does a failure leave `recommended` absent?

`recommend_tlc_params` (`tools.py:1328-1369`) has two failure modes:

- **(a) Soft no-write return** when the Mind request can't be built (`tools.py:1338-1346`):
  ```python
  try:
      from_user = TLCFromUserFields.model_validate(draft.get("from_user") or {})
      mind_request = build_tlc_param_request(from_user)
  except ValidationError as exc:
      problems = "; ".join(format_validation_problems(exc))
      return (f"recommend_tlc_params: cannot build the Mind request -- missing/invalid fields: {problems}. "
              "Collect these from the chemist (update_tlc_params) and retry.")
  ```
  `build_tlc_param_request` (`form_payloads.py:466-481`) requires `rxn` + `target_window` and enforces `0 <= lo < hi <= 1`. **A null/invalid `target_window` raises here** → the tool returns a string and emits NO `TaskParamsSetEvent`, so `recommended` is simply never written this turn. This is the "contributing oddity" in the diagnosis (the bench turn's `target_window` was null, so `recommend_tlc_params` no-op'd and the draft never got its own `recommended`). The failure is **SURFACED** (returned to the LLM as an actionable string), not swallowed.
- **(b) Hard raise** on a Mind call/response failure (`tools.py:1348-1350`, D47): `await mind.recommend_tlc_mixcase(...)` propagates → `TurnFailedEvent`. Again no `recommended` written, failure surfaced loudly.

**Net for D2**: a failed `recommend_tlc_params` leaves `recommended` ABSENT *in the draft for that turn*, but it canNOT produce a terminal trial with no `recommended`, because the confirm gate (§below) blocks dispatch until `recommended` is present. The failure is the reason the *chemist-supplied* `form_values.recommended` was the only `recommended` that ever existed in the bench incident — but that one still satisfied the confirm gate. So `recommend_tlc_params` failure is a CONTRIBUTOR to the D1 race window (the draft stayed `recommended`-less longer), not an independent way for a terminal trial to lack `recommended`.

### 5. Is `recommended` ever LEGITIMATELY absent on a terminal trial? — NO. The confirm gate REQUIRES it.

The decisive chokepoint: **a TLC params confirm cannot be accepted without `recommended`.**

- `submit_form_confirm` (`service.py:234-239`) calls `_validate_params_form_values` at **API time, BEFORE any event is appended** (event persisted at line 275):
  ```python
  if confirm_kind is ConfirmKind.PARAMS:
      resolved_task_id = await self._validate_params_form_values(...)
  ```
- `_validate_params_form_values` (`service.py:347-349`) raises on any problem:
  ```python
  problems = problems_fn(form_values or {})   # tlc -> tlc_params_form_problems_from_values
  if problems:
      raise FormValidationError(problems)      # HTTP 422
  ```
- `tlc_params_form_problems` (`form_payloads.py:565-572`) **requires `recommended`**:
  ```python
  if form.recommended is None:
      problems.append("recommended: missing -- run recommend_tlc_params or fill manually")
  ```

So even the "chemist hand-fills the form and skips the recommend step" case is covered: the chemist must either run `recommend_tlc_params` OR hand-fill `recommended` in the form; an empty `recommended` is rejected at confirm. **A chemist CANNOT confirm/dispatch a TLC trial with no `recommended`.**

The reachability chain leaves no gap:
- Dispatch fires only via `_pre_react_route` → `auto_submit` when `_is_params_confirm_dispatch` is true, i.e. `current_phase == "rts"` AND a PARAMS confirm payload (`tlc.py:322-334`).
- The ONLY writer of `phase=rts` is `FormConfirmedEvent.apply` (`_FORM_CONFIRM_PHASE_ADVANCE[("collecting_params","params")]="rts"`, `runtime_emitted.py:60-63`), which is gated by the §5 422 check.
- → every dispatched (hence terminal) first-attempt trial passed a confirm that required `recommended`.
- Retry attempts (`_auto_retry_node`) mint their own trial and write a concrete Mind `recommended` (`tlc.py:834-838`) before dispatching — so they too always carry it.

**MED005 / thin-draft is NOT a counterexample.** The `MED005_RXN` fallback at `tlc.py:729` (`rxn = from_user.rxn or MED005_RXN`) defaults only the `rxn` field of the recognition REQUEST, and it executes AFTER the `recommended` read at `tlc.py:722-724` — the crash happens first. There is no MED005 / mock fallback for `recommended`. "So a thin draft still runs" in the docstring refers to `rxn`, not `recommended`.

### 6. Dispatch-time read — reads in-memory, not disk; does enforce `recommended` (against the in-memory copy)

`_submit_l4` (`tools.py:452-566`) builds the lab request from `state.params_draft` (in-memory), NOT from disk:
```python
# tools.py:492, 551, 558
draft = state.params_draft or {}
...
tlc_form = TLCParamsForm.model_validate(draft)
tlc_problems = tlc_params_form_problems(tlc_form)
...
if tlc_problems or tlc_form.recommended is None:
    raise RuntimeError("submit_l4_execution: params not dispatchable: ...")
```
On the dispatch turn, `state.params_draft` is seeded from the FORM_CONFIRM `form_values` (`reception_node._validate_form_values_and_seed_drafts:381` `update["params_draft"] = form.model_dump()`), which carries `recommended`. So the `tlc_form.recommended is None` guard PASSES against the in-memory copy even when disk was clobbered — **dispatch enforces `recommended`, but only against the in-memory draft, masking the on-disk strip.** The dispatch turn emits only `ToolResultEvent` + `TaskDispatchedEvent` (`tlc.py:589-643`); it does NOT re-persist `params` to disk, so the clobbered disk blob is never healed.

The terminal turn, by contrast, has `form_confirm = None`, so `_validate_form_values_and_seed_drafts` returns `{}` (`reception_node.py:362-363`) and the draft is re-seeded from disk (`reception_node.py:437-438` `out["params_draft"] = dict(trial.params)`) — the stripped blob → crash.

---

## The decision this informs — verdict

**D2 = pure defensive backstop for the D1-class race. Fail loud is correct.**

- There is NO legitimate TLC flow where a terminal trial has no `recommended` (the confirm gate at `service.py:347` / `form_payloads.py:570` makes `recommended` mandatory before dispatch; retries write their own). So D2's "if `recommended` genuinely absent on a terminal TLC trial" branch is, by construction, **always a bug** (D1-class persistence loss).
- Therefore D2 must NOT invent a graceful default (e.g. `TLCParam.model_validate({})` or a MED005 stub) — doing so would silently dispatch/recognize against a meaningless solvent system and mask the real D1 corruption. D2 should **raise an actionable error** (Rule 9): name the trial, that a terminal TLC trial reached Rf-eval with no persisted `recommended`, and that this indicates a `task_params_set` clobber (point at D1). This converts the current bare pydantic `ValidationError` (from `TLCParam({})`) into a diagnosable failure.
- D1 remains the real fix (stop the clobber). D2 is the "this should never happen post-D1" tripwire that catches any future regression or untested clobber variant. D3 (the missing `analysis_completed` gate on TLC `_post_react_route`, `tlc.py:382-385`) is orthogonal hardening so a re-driven terminal turn doesn't re-enter the eval loop.

## Caveats / Not Found

- `task.py current` resolves to a stale/unrelated task (`05-22-cc-subpackage-split`); the active task dir from the prompt exists at the **repo root** `.trellis/tasks/06-28-fix-params-set-clobber-recommended/` (NOT under BIC-agent-service). Wrote this file there as instructed.
- I did not exhaustively prove the retry path (`_auto_retry_node`) can never produce a `recommended`-less terminal trial under an adversarial `draft`, but `tlc.py:836` sets `recommended` from `recommended_param.model_dump()` (Mind's `response.recommendation.param`, `tlc.py:818-819`) which is a required field of the Mind response — so the retry attempt's emitted blob always contains a concrete `recommended`. A subsequent stale whole-blob set on the retry trial COULD still clobber it (same D1-class race), which is exactly why D2 is the right backstop and not a special-cased default.
- I did not re-verify the FE side; the confirm completeness authority is BE-only (`form_payloads.py` docstring: "BE is the single validation authority — the FE does NOT replicate these rules"), so the gate cannot be bypassed from the FE.
