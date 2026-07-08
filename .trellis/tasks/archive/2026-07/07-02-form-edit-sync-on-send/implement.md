# Implementation plan — Form-edit sync on send

Order: BE first (BE tolerates absent field; FE sending to an old BE 422s on `extra="forbid"`).
Each step ends with its validation command; stop and re-plan on red (Rule 4 / 2.3 rollback points).

## Step 1 — BE contract + durability

- [x] `app/data/turn_schemas.py`: `UserMessageFormDraft {trial_id, params: dict}` (pydantic-only,
      per module import constraint) + optional `form_draft` on `UserMessagePayload`.
- [x] `app/api/routers/sessions.py`: add `form_draft: UserMessageFormDraft | None = None`
      EXPLICITLY to `SubmitUserMessageRequest` (`extra="forbid"` — without the field the FE POST
      422s); add router-level size gate (serialized-length cap + top-level key allowlist
      `{from_user, recommended, lab_logistics}`); pass `form_draft=body.form_draft` into
      `UserMessagePayload` when minting `TurnInput`.
- [x] `app/session/service.py:145-149`: the event is constructed FIELD-BY-FIELD — explicitly
      forward the draft, converting payload model → event's duplicate model:
      `form_draft=EventDraft(**payload.form_draft.model_dump()) if payload.form_draft else None`.
      Skipping this silently drops the draft from every persisted event (review round-2 blocker).
- [x] `app/events/orch_emitted.py`: duplicate `UserMessageFormDraft` locally (Gate 2 — events
      import nothing app-side; docstring cites turn_schemas as the mirrored authority) + optional
      `form_draft` on `UserMessageSubmittedEvent`.
- [x] Tests: route accepts with/without draft; oversized/wrong-section draft ⇒ 422; event payload
      round-trips; absent field ⇒ byte-identical legacy payload.
- Validate: `uv run pytest tests/ -k "user_message or submit_message" -q`
      and `uv run pytest tests/unit/test_import_hygiene.py -q`

## Step 2 — BE apply (leg 1: state truth)

- [x] `UserMessageSubmittedEvent.apply()`: write `trials.params = form_draft.params` ONLY when
      trial exists and `trial.phase == "collecting_params"` (layer-neutral literal). Unknown
      trial / other phase ⇒ defensive early-return + `metric.*_total` warning (apply-layer
      convention, `runtime_emitted.py:548-549`) — apply must NEVER raise on the API persist path
      (a stale draft must not 500 the chat message). No 06-28/06-29 guard reuse. No phase
      advance, no decision writes.
- [x] Session-scope guard (Step-2 check finding): trial must resolve to the event's
      `session_id` via `tx.trials.resolve_session_id_by_trial` (chokepoint from
      `event_ingress.py:92`); mismatch ⇒ `metric.user_message_form_draft_session_mismatch_total`
      warning + drop.
- [x] Tests: collecting_params write; post-confirm drop (params untouched, warning logged);
      unknown trial drop; session-mismatch drop (other session's collecting trial untouched);
      POST /messages still 202 with a stale draft;
      re-seed integration (`reception_node.py:437` picks up the draft next turn).
- Validate: `uv run pytest tests/ -k "orch_emitted or reception" -q`

## Step 3 — BE SessionContext + prompt (leg 2: awareness)

- [x] `app/core/context.py`: define `ChemistFormDraft` frozen dataclass HERE (`{trial_id,
      from_user, lab_logistics}` per D2 — context.py cannot import turn_schemas), add it to the
      module `__all__`, and add `chemist_form_draft: ChemistFormDraft | None = None` to
      `SessionContext`.
- [x] `orchestrator.py::_load_session_context`: populate BOTH sections from
      `turn_input.user_message.form_draft` (remove `del turn_input` at `:521`; update docstring —
      loader shape is no longer turn-agnostic).
- [x] `dynamic_prompts.py`: `_maybe_chemist_draft_block(request, phase)` gated on
      `collecting_params` (clone `_maybe_prior_step_block`); renders from_user via
      `_render_from_user` (+`_PROSE_EXCLUDED_FROM_USER_KEYS` hygiene) AND lab_logistics lines
      (D2), appended in cc/re/tlc prompts.
- [x] Tests: loader populates/omits both sections; block renders only on draft turn in
      collecting_params; excluded keys never in prose; lab_logistics edit appears in block;
      non-collecting phase ⇒ no block.
- Validate: `uv run pytest tests/ -k "context or dynamic_prompt or orchestrator" -q`
      then full: `uv run pytest -q`

## Step 4 — FE wiring

- [x] `useFormDirtyRegistry.ts`: entry gains `getValues?`, `trialId?`, `markClean?`; add
      `selectDirtyDraft` selector (first entry with `isDirty && getValues && trialId` — safe:
      at most one params form is dirty, verified round-2: only the active stage's form mounts,
      `key={stage}` unmount unregisters, discard guard blocks dirty stage-switches,
      `ParameterDesignPanel.tsx:164-177, 564-598`).
- [x] `useParamsFormHandle.ts`: NEW `markClean = () => setTouched(false)` exposed on
      `DynamicFormHandle` (interface in `DynamicForm.tsx`) + the registry entry — it does not
      exist today (round-2 blocker); `reset()` must NOT be used post-send (rebuilds from the old
      agent proposal → visually reverts edits). `getValues` registered via a draft ref
      (`draftRef.current = draft` each render; `getValues = useCallback(() =>
      toValues(draftRef.current), [])`) — stable identity, no per-render registry churn, never
      stale (round-2 defect: a plain closure over `draft` goes stale under the current
      update-effect deps).
- [x] `trialId` threading (prop-drill, matches existing `taskId` flow): CC —
      `CcEditableBody` already holds `taskId`, forward one prop into `CcParamsForm`; TLC/RE —
      `ParamsEditableBody` forwards `taskId` into `TlcParamsForm` / `ReParamsForm` (today they
      receive none). All three pass it into `useParamsFormHandle` for registration.
- [x] `agent-client.ts::submitUserMessage` AND `session-bootstrap.ts::sendLiveUserMessage`: both
      gain the optional `form_draft` param (header comment cites `sessions.py`).
- [x] `ChatPanel.handleSend`: read the registry IMPERATIVELY —
      `selectDirtyDraft(useFormDirtyRegistry.getState())` (same pattern as
      `ParameterDesignPanel.tsx:166`; a reactive subscription would re-render chat per keystroke).
      Attach on the live branch only (draft-mode has no workspace); `markClean()` in `.then()`
      only — POST failure leaves `touched` intact. Second rapid send before the
      `task_params_set` echo carries no draft — CORRECT, values already synced turn-1 (documented
      in design.md).
- [x] `src/types/events.ts`: `user_message_submitted` payload mirror gains
      `form_draft?: { trial_id: string; params: Record<string, unknown> } | null` (exact BE DTO
      shape; dispatcher reads only text/event_id — verified `event-dispatcher.ts:53-55`).
- Validate: `pnpm typecheck && pnpm check`

## Step 5 — E2E + specs + wrap

> FINAL E2E STATUS (2026-07-03, 8 bench cycles — task CLOSED as done, Drake's ruling):
> Leg A VALIDATED at the contract level: run 7 DB evidence shows the chemist's edit (2.5)
> synced, survived the agent turn, and was COMMITTED (echo trace 1.5→2.5→2.5, trials.params
> = 2.5, form draft 2.5) — vs pre-fix run 6 which committed 1.5. Ship-bar ruling: committed
> value is the contract; the transient first-echo blip is accepted (cosmetic follow-up
> candidate). Spec assertion aligned to committed-value semantics (portal 28c5465).
> Run 8 (green-record rerun) SKIPPED: bench occupied by concurrent PR-74 lab work + wedged
> BE; Drake ruled the task done on the run-7 evidence. Leg B (post-confirm stale-draft
> guard) remains live-unverified — covered by unit+integration tests (Step 2); its live leg
> rides the 07-02-stale-plan-first-specs-cleanup follow-up when the bench frees.
>
> HISTORY (2026-07-02, first 6 runs): spec written + validated (tests/form-edit-sync-on-send.spec.ts);
> every red was UPSTREAM of Legs A/B — run 1 stale pre-objective prompt (fixed), run 2 TLC-first
> shape (fixed), run 3 stale robot mock vs R7 photo contract (mock patched, verified),
> run 4a external bench contention (invalidated), run 4b lab round-2 resolver IndexError
> (FIXED in 07-02-tlc-round2-resolver-fix; live AC validated via direct API in run 5 — round-2
> submit green), run 5a manual-TLC plan draw (spec prompt pinned all-robot), run 5b TWO NEW
> product bugs: agent hallucinates lab_logistics.sample_tubes (box_01/t001..t004 — violates
> clarify-not-fabricate) + FE toggleTubeSelection silently drops clicks at the 4-tube cap
> (TubeSelectorGrid.tsx:59), so the garbage dispatched and lab 400'd. Legs A/B remain
> E2E-unverified pending those two fixes; leg-level coverage exists in Steps 1-4
> unit/integration tests (all green). Secondary recorded findings: lab /preparations/validate
> vs create asymmetry; manual-TLC path seeds CC with a canned tlc_result in live flows.

- [ ] Playwright: extend a live-backend spec — edit CC field, send chat message w/o confirm,
      then assert BOTH: (a) backend `trials.params` has the edited value (leg 1, API truth via
      `GET /sessions/:id/events` / snapshot), AND (b) the next `task_params_set` EVENT PAYLOAD
      contains the chemist's value (proves the LLM worked from the synced base, not its stale
      draft — cc-re-chained-flow.spec.ts intercept pattern).
      (Services via tmux `bic-services`; `VITE_HIDE_DEVTOOLS=1`; LLM specs `--workers=1`.)
- [ ] Playwright: post-confirm guard leg — after CC confirm, send a message with a (stale) dirty
      draft and assert confirmed `trials.params` state is NOT reverted (E2E cover for the R5 AC;
      unit test in Step 2 covers the apply in isolation).
- [ ] Spec updates per design.md §Spec-updates (Rule 10, same change set).
- [ ] Full suites green: BE `uv run pytest -q`; FE suite `pnpm exec playwright test`.
- Validate: suites + `trellis-check` dispatch.

## Step 6 — Leg-2 revision: from_user draft authority prompt fix (AC2)

> Drake's ruling 2026-07-03: prompt-only fix. No tool split, no apply-level pin.
> Steps 1-4 (already complete) provide the infrastructure (form sync + draft block).
> This step fixes the prompt wording that caused run-6 AC2 failure.

### 6a — Add shared authority rule constant (`dynamic_prompts.py`)

Add a new module-level string constant (near `_NO_PROSE_ONLY_RULE` /
`_LAB_LOGISTICS_NO_FABRICATE_RULE`, single source so CC/TLC/RE cannot desync):

```python
_FROM_USER_DRAFT_AUTHORITY_RULE = (
    "FROM_USER DRAFT AUTHORITY: if from_user fields already appear in the\n"
    "params_draft (the CHEMIST FORM EDITS block above shows them), treat them\n"
    "as the base — do NOT re-extract those fields from the objective text or\n"
    "prior conversation. Only call update_*_params(fields={from_user: ...})\n"
    "when THIS message's text explicitly instructs a value change. Silence\n"
    "preserves the draft; only an explicit instruction overwrites it.\n"
)
```

Place this constant alongside the other shared rules.

### 6b — CC prompt: `_cc_collecting_params_instructions` (`dynamic_prompts.py:208-230`)

Two surgical changes:

1. Replace the ladder opening line:
   - OLD: `"form in ONE turn: extract every from_user field from chat\n"`
   - NEW: `"form in ONE turn: collect any from_user fields not yet in the draft from chat\n"`
   (Both `_CC_COLLECTING_LADDER_DEFAULT` and `_CC_COLLECTING_LADDER_ROBOT_TLC` start with
   `"(update_cc_params(fields={from_user: ...})"` — the opening sentence is the fix target,
   not the ladder constants themselves.)

2. Insert `+ _FROM_USER_DRAFT_AUTHORITY_RULE + "\n"` immediately before the
   `"RE-RECOMMEND RULE: ..."` line in the returned string. This places the authority
   rule in the prompt AFTER the `_maybe_chemist_draft_block` is appended
   (`cc_dynamic_prompt` appends blocks after `instructions`), so "the CHEMIST FORM
   EDITS block above" refers correctly.

### 6c — TLC prompt: `_TLC_PHASE_INSTRUCTIONS["collecting_params"]` (`dynamic_prompts.py:276-298`)

Same two changes:

1. Replace:
   - OLD: `"form in ONE turn: extract every from_user field from chat\n"`
   - NEW: `"form in ONE turn: collect any from_user fields not yet in the draft from chat\n"`

2. Insert `+ _FROM_USER_DRAFT_AUTHORITY_RULE + "\n"` before the RE-RECOMMEND RULE line.
   Since `_TLC_PHASE_INSTRUCTIONS["collecting_params"]` is a string literal (not a
   function), convert it to a concatenation expression or use an f-string so the
   constant can be inserted. Match the existing style of `_CC_COLLECTING_LADDER_DEFAULT`
   (string concatenation via `+`).

### 6d — RE prompt: `_RE_PHASE_INSTRUCTIONS["collecting_params"]` (`dynamic_prompts.py:343-381`)

Same two changes:

1. Replace:
   - OLD: `"  1. Extract every from_user field the chemist already gave you\n"
           "     (chat text counts; a chained CC run usually implies the\n"
           "     volume + solvent system) → update_re_from_user(fields=...).\n"`
   - NEW: `"  1. Collect any from_user fields not yet in the draft from chat\n"
           "     (a chained CC run usually implies the volume + solvent system)\n"
           "     → update_re_from_user(fields=...).\n"`

2. Insert `+ _FROM_USER_DRAFT_AUTHORITY_RULE + "\n"` before the RE-RECOMMEND RULE
   line. Same string-literal-to-concatenation conversion as TLC if needed.

### 6e — Spec update: `specialist_tools.md` (Rule 10)

Add a subsection **"I-ST-F: from_user write authority"** to
`.trellis/spec/BIC-agent-service/backend/L3/specialist_tools.md` §2 (Table A,
after the existing content for `update_cc_params`):

> **I-ST-F — from_user write tools are LLM-discretionary, never mandatory per
> ladder turn.** When a CHEMIST FORM EDITS block is present in the prompt (i.e.
> `ctx.chemist_form_draft` is non-null for this turn), the LLM must treat existing
> `from_user` draft fields as the authoritative base and only call the write tool
> (`update_cc_params` / `update_tlc_params` / `update_re_from_user`) when the
> current message's text explicitly instructs a value change. Silence preserves
> the draft. This is the structural realization of `docs/project-prd.md §Precedence
> Mechanism` ("Writing a from_user field is a discrete TOOL the LLM fires ONLY when
> the message instructs a change — never a mandatory step of the recommend/dispatch
> ladder"). The authority rule is a shared prompt constant
> `_FROM_USER_DRAFT_AUTHORITY_RULE` (`dynamic_prompts.py`) so CC / TLC / RE cannot
> desync.

### 6f — Tests (new or extend `tests/unit/test_dynamic_prompts.py`)

Three unit tests:

1. **`test_from_user_authority_rule_present_in_collecting_params`**: for each
   specialist (CC default, CC robot-TLC, TLC, RE), call the prompt compose function
   with `phase="collecting_params"` and assert the rendered string contains the
   `_FROM_USER_DRAFT_AUTHORITY_RULE` text. Purpose: the rule cannot be silently
   removed.

2. **`test_from_user_authority_rule_absent_outside_collecting_params`**: for each
   specialist, call with `phase="rts"` and `phase="conducting"` and assert the rule
   text is NOT present. Purpose: no prompt pollution in non-collecting phases.

3. **`test_from_user_authority_rule_shared_text`**: assert the text embedded in the
   CC, TLC, and RE `collecting_params` prompts is identical (all reference the same
   constant, not inline copies). Purpose: desync prevention.

4. **`test_extract_every_field_phrase_gone`**: assert the old
   `"extract every from_user field from chat"` phrase does NOT appear anywhere in
   the CC, TLC, or RE collecting_params prompts. Purpose: regression guard on the
   root-cause phrase.

### Validation commands

```
uv run pytest tests/unit/test_dynamic_prompts.py -q
uv run pytest -q
```

No FE changes, no new endpoints, no migration.

### Rollback

Reverting the four string changes to `dynamic_prompts.py` fully restores prior
behavior. No DB schema, no event-contract, no FE changes. Risk: low.

## Review gates

- After Step 3 (BE complete): confirm prompt block wording with Drake before FE lands (chemist-visible
  agent behavior change).
- Step 5 commit only on Drake's go (no auto-commit).
