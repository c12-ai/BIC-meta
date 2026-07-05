# Design — Form-edit sync on send via SessionContext

Evidence base: research/*.md (session-context-pattern, user-message-submission-path,
objective-draft-precedent, overwrite-policy-surface, spec-docs-to-update).

## Shape

One request, two legs on the BE:

```
FE dirty form ──(rides POST /sessions/{id}/messages)──► UserMessageSubmittedEvent.form_draft
                                                          │
                            leg 1 (state truth)           │ apply() writes trials.params
                            ─────────────────────────────►│ (phase-guarded)
                                                          ▼
                                     reception_node.py:437 re-seed → SpecialistState.params_draft
                                     (existing — zero new plumbing; tools merge on chemist base)

                            leg 2 (LLM awareness)
                            _load_session_context reads this turn's draft
                            → SessionContext.chemist_form_draft
                            → _maybe_chemist_draft_block in dynamic_prompts (cc/re/tlc shared)
```

Leg 1 alone would reproduce today's half-awareness (state has values, LLM not told); leg 2 alone
would leave tools merging on a stale base. Both legs are required and both reuse existing seams.

## FE (BIC-agent-portal)

1. **Expose values at send time**: extend `useFormDirtyRegistry` entry with `getValues()`,
   `trialId`, `markClean()` (values currently live only behind `formRef` in
   `ParameterDesignPanel.tsx:179`; the registry is the only surface spanning workspace→chat).
   `getValues` is ref-backed (stable identity, reads `draftRef.current`) to avoid both staleness
   and per-render registry churn. `markClean` (= `setTouched(false)`, draft untouched) is NEW —
   today the only touched-writer is `reset()`, which would visually revert the edits.
   `trialId` arrives by prop-drill along the existing `taskId` path (CC: one hop from
   `CcEditableBody`; TLC/RE: one hop from `ParamsEditableBody`).
2. **Attach on send**: `ChatPanel.handleSend` reads `selectDirtyDraft(useFormDirtyRegistry.getState())`
   imperatively (pattern of `ParameterDesignPanel.tsx:166`) → `sendLiveUserMessage` →
   `submitUserMessage`, both gaining the optional `form_draft: {trial_id, params}`. First-dirty-entry
   is provably safe: at most one params form can be dirty (only the active stage's form is mounted —
   `key={stage}` unmount unregisters — and the discard guard blocks dirty stage-switches;
   `ParameterDesignPanel.tsx:164-177, 564-598`).
3. **Clear `touched` via `markClean()` on 202** (`.then()` only — POST failure keeps `touched`).
   The unconditional re-sync effect (`useParamsFormHandle.ts:40-47`) stays as-is — the incoming
   `task_params_set` echo is now computed on the chemist-inclusive base, so overwrite is legitimate.
   A second rapid send before that echo carries no draft, which is correct: the values were
   already persisted by turn 1's apply, and turn 2's `params_draft` re-seed includes them; LLM
   awareness happened on turn 1's prompt block.
4. `agent-client.ts` header comment keeps citing `sessions.py` as DTO authority (portal convention);
   `types/events.ts` mirrors the fatter `user_message_submitted` payload.

## BE (BIC-agent-service)

1. **DTO — two definitions, not one shared model** (import gates verified): `turn_schemas.py`
   may import only `pydantic + app/core/enums` (module docstring) and `app/events/**` may import
   nothing app-side (test_import_hygiene Gate 2), so a single shared model is impossible.
   Convention precedent: the event already duplicates the route's 1..10k text contract by
   docstring citation. Therefore: `UserMessageFormDraft {trial_id, params: dict}` defined in
   `turn_schemas.py` (pydantic-only — allowed), reused by the router DTO (router already imports
   turn_schemas); `orch_emitted.py` defines its own duplicate, synced by docstring citation.
   Router DTO adds a size gate on `params` (serialized-length cap + top-level key allowlist
   `{from_user, recommended, lab_logistics}`) — `text` is capped at 10k; the draft must not be an
   unbounded blob. Validation authority stays at the edge; inner sections stay lenient.
2. **Carriage — both, mirroring `text`**: the draft rides `UserMessagePayload` (turn envelope —
   the ctx loader reads it there, no extra DB query) AND `UserMessageSubmittedEvent` (persisted
   synchronously before enqueue — survives refresh, replays over SSE). This is exactly how `text`
   travels today; if the process dies between persist and turn run, the draft is as durable as
   the message itself.
3. **Apply (leg 1) — collecting_params only, defensive**: `UserMessageSubmittedEvent.apply()`
   (today a noop) writes `trials.params = form_draft.params` ONLY when the trial exists and
   `trial.phase == "collecting_params"` (layer-neutral literal, precedent in
   `TaskParamsSetEvent.apply`, `runtime_emitted.py:669-670`) AND the trial belongs to the event's
   session (`tx.trials.resolve_session_id_by_trial`, the existing chokepoint from
   `event_ingress.py:92` — route auth pins the user to the session, but nothing else ties
   `form_draft.trial_id` to it; without this, a crafted POST could overwrite another session's
   collecting-phase trial. Step-2 check finding). Anything else — unknown trial, session
   mismatch, post-confirm phase — drops the draft with a `metric.*_total` warning log, matching the
   documented apply-layer convention ("defensive early-returns … never block the surrounding tx",
   `runtime_emitted.py:548-549`). NOT fail-loud-by-raise: apply runs inside `persist_event` on
   the API path, so raising would 500 the chemist's chat message over a stale draft. The
   06-28/06-29 carry-forward guard is NOT reused — it exists for stale LLM blobs; the FE form is
   frozen post-confirm, so the simple phase check covers the chemist case. No phase advance, no
   decision writes — confirm stays the only phase-advancing path (R5).
4. **SessionContext (leg 2)** — the 3 in-pattern touch points (research/session-context-pattern §Recommended):
   - `app/core/context.py:119`: add `chemist_form_draft: ChemistFormDraft | None`
     (`{trial_id, from_user: Mapping, lab_logistics: Mapping}` — both chemist-editable sections,
     per D2; dataclass defined in context.py + `__all__`).
   - `orchestrator.py:487-553` `_load_session_context`: read the draft off
     `turn_input.user_message.form_draft` (the `del turn_input` at `:521` goes away; docstring
     updated). Keyed to this turn's input, so the block appears exactly on the turn the chemist
     sent edits — no staleness bookkeeping, no extra query.
   - `dynamic_prompts.py`: `_maybe_chemist_draft_block(request, phase)` cloned from
     `_maybe_prior_step_block` (`:582-593`) — same signature, **gated on
     `phase == "collecting_params"`** so the prompt never asserts values that apply refused to
     persist (prompt/state consistency with §3). Shared by cc/re/tlc prompts. Renders via
     `_render_from_user` with `_PROSE_EXCLUDED_FROM_USER_KEYS` hygiene (no structured blobs in
     prose — `tlc_result`/`tlc_file_key` excluded). Block wording must ENCODE D1 and D2, not just
     cite them (round-2 review: a bare "treat as truth" could make the LLM refuse a contradicting
     chat instruction, and an undifferentiated lab_logistics line could trigger pointless
     re-recommends). Draft wording:

     ```
     CHEMIST FORM EDITS (unconfirmed, sent with this message).
     If this message's text contradicts a value below, the text instruction wins.
     from_user edits — current input truth; RE-RECOMMEND RULE applies:
       <_render_from_user lines>
     lab_logistics edits — bench facts, already in the draft; do NOT re-recommend
     for these alone and do NOT overwrite them unless the chemist asks:
       <lab_logistics lines>
     ```

     Either section is omitted when empty. Final wording confirmed with Drake at the Step 3
     review gate.

## Decisions & tradeoffs

- **Same-request over sibling draft POST**: one atomic contract, no FE ordering concerns, and the
  objective-draft precedent's FE→BE leg exists but its BE→LLM leg does not (research/objective-draft
  caveat) — so a sibling POST saves nothing on the hard part while adding an endpoint + event kind.
- **Whole-blob persist, chemist-sections-only prompt render**: persist keeps `reception_node.py:437`
  whole-blob re-seed semantics untouched; the prompt renders only the chemist-editable sections
  (`from_user` + `lab_logistics`, per D2) — never `recommended`.
- **No FE overwrite-contract flip**: research/overwrite-policy shows reversing it is a Rule-5
  contract flip touching `backend-contract.md:392` + product-contract comment; unnecessary once
  the base is synced. If the LLM deliberately overrides a chemist value, RE-RECOMMEND wording makes
  it explain — that's desired agent behavior, not a bug.

## Business decisions (Drake, 2026-07-02)

- **D1 — precedence on contradiction: CHAT TEXT WINS.** Form values become the base; an explicit
  chat instruction may overwrite them via the LLM's update tools, and the RE-RECOMMEND rule makes
  it explain. No apply-level pin.
- **D2 — lab_logistics visibility: RENDER BOTH.** `ChemistFormDraft` carries `from_user` AND
  `lab_logistics`; the prompt block renders both sections (short key:value lines, same
  `_PROSE_EXCLUDED_FROM_USER_KEYS` hygiene on from_user; lab_logistics fields are small scalars /
  location objects). Rationale: a bench-physical fact (e.g. `sample_cartridge_location`) must not
  be clobbered by an agent that never saw the edit.

## Rollback

Single optional field end-to-end; omitting `form_draft` reproduces today's behavior exactly.
FE and BE can revert independently (BE tolerates absent field; FE sending to an old BE would 422
on `extra="forbid"` — ship BE first).

## Leg-2 revision: tool-gated from_user write (run-6 AC2 fix)

### Root-cause confirmation (file:line proof)

**The bug is prompt-driven re-derivation, NOT a force-run tool call.**

`update_cc_params` is purely LLM-discretionary — no code in `cc.py` forces it
before or after the react loop. The `_auto_recommend` backstop (`cc.py:486-505`)
runs only when the LLM stops mid-ladder with a recommendable `from_user` and no
`recommended`; it writes ONLY the `recommended` section, never `from_user`.

The root cause is this line in `_cc_collecting_params_instructions`
(`dynamic_prompts.py:209-212`):

```
"Current phase: collecting_params. Drive the params draft to a HITL\n"
"form in ONE turn: extract every from_user field from chat\n"
+ ladder  # ladder = "(update_cc_params(fields={from_user: ...}); ..."
```

The phrase **"extract every from_user field from chat"** is a mandatory ladder
instruction that fires on EVERY collecting_params turn — including turns where
`from_user` is already fully populated (from the chemist's synced form) and the
message is a plain "continue." The LLM obeys: it reads the objective text ("purify
a 1.5g sample") and re-derives `sample_quantity = 1.5`, overwriting the chemist's
synced `2.5`.

The same phrase appears identically in:

- TLC prompt, `_TLC_PHASE_INSTRUCTIONS["collecting_params"]`
  (`dynamic_prompts.py:277-278`): `"extract every from_user field from chat"`
- RE prompt, `_RE_PHASE_INSTRUCTIONS["collecting_params"]`
  (`dynamic_prompts.py:345-351`): `"Extract every from_user field the chemist
  already gave you (chat text counts; ...)" → update_re_from_user`

All three specialists are affected. RE already has SPLIT tools
(`update_re_from_user` / `update_re_lab_logistics`) but this does NOT help — the
bug is in the prompt mandate to extract, not in the tool shape.

**The research file's recommended seam (apply-level pin / `TaskParamsSetEvent.apply`)
is REJECTED** by Drake's ruling: a blanket carry-forward blocks the legitimate
"use 3g instead" instruction path (D1 violation). The tool-split proposal
(merging vs splitting `update_cc_params`) is also NOT the fix — the bug is the
prompt telling the LLM to re-extract, not the tool structure.

### Change shape: prompt-only, surgical (three prompt blocks)

Drake's mechanism from `docs/project-prd.md §Precedence Mechanism`:

> Writing a `from_user` field is a discrete TOOL the LLM fires ONLY when the
> message instructs a change — never a mandatory step of the recommend/dispatch
> ladder. On a message with no `from_user` instruction (e.g. a bare "continue"),
> the tool is never called and the synced form value — already the base in graph
> state — stands.

The `_maybe_chemist_draft_block` already renders the synced values in the prompt.
What is missing is the ladder opening that says "if `from_user` fields are already
in the draft, do NOT re-extract them from chat." Three surgical prompt changes:

**1. CC — `_cc_collecting_params_instructions` (`dynamic_prompts.py:208-230`)**

Replace the opening:
```
"extract every from_user field from chat\n"
```
with:
```
"collect any from_user fields not yet in the draft from chat\n"
```

And add before the RE-RECOMMEND RULE line a new shared constant
`_FROM_USER_DRAFT_AUTHORITY_RULE` (single-source so CC/TLC/RE cannot desync):

```
FROM_USER DRAFT AUTHORITY: if from_user fields already appear in the
params_draft (the CHEMIST FORM EDITS block above shows them), treat them
as the base — do NOT re-extract those fields from the objective text or
prior conversation. Only call update_*_params(fields={from_user: ...})
when THIS message's text explicitly instructs a value change. Silence
preserves the draft; only an explicit instruction overwrites it.
```

This is placed in the prompt AFTER the `_maybe_chemist_draft_block` renders (the
block is appended at the end of `cc_dynamic_prompt`), so the rule references
"the CHEMIST FORM EDITS block above" correctly.

**2. TLC — `_TLC_PHASE_INSTRUCTIONS["collecting_params"]` (`dynamic_prompts.py:276-298`)**

Same two changes: "collect any from_user fields not yet in the draft from chat"
+ `_FROM_USER_DRAFT_AUTHORITY_RULE` before RE-RECOMMEND RULE.

**3. RE — `_RE_PHASE_INSTRUCTIONS["collecting_params"]` (`dynamic_prompts.py:343-381`)**

Same: replace "Extract every from_user field the chemist already gave you (chat
text counts; ...)" with "Collect any from_user fields not yet in the draft" + the
shared `_FROM_USER_DRAFT_AUTHORITY_RULE`.

RE is already split (`update_re_from_user` / `update_re_lab_logistics`) and
confirmed NOT needing a tool-structure change — only the prompt wording.

### Why this realizes "LLM only writes from_user when message instructs it"

The `_maybe_chemist_draft_block` (already shipped in Steps 1-4) renders the
synced `from_user` values. With the new authority rule:

- Turn with bare "continue": `from_user` fields appear in the draft block.
  The rule says "do NOT re-extract; silence preserves." The LLM skips
  `update_cc_params(from_user=...)` entirely. The synced value stands in
  `params_draft` (seeded by `reception_node.py:437`). The LLM goes straight to
  `recommend_cc_params()` if needed (RE-RECOMMEND RULE does NOT trigger because
  `from_user` did NOT change), then exits.
- Turn with "use 3g instead": The rule says "only call update_* when THIS
  message's text explicitly instructs a value change." The LLM sees the explicit
  instruction and calls `update_cc_params(fields={from_user: {sample_quantity: 3}})`.
  D1 honored.
- Cold first turn (no synced draft, no `_maybe_chemist_draft_block`): the block
  is absent. The "not yet in the draft" wording in the ladder still instructs
  extraction. No behavior change on first-turn.

### RE — not affected by tool-split question, needs same prompt fix

RE has split tools already. The prompt fix applies identically. No tool change.

### Spec updates (this leg adds one doc — Rule 10)

One spec document gains a new section:

- `.trellis/spec/BIC-agent-service/backend/L3/specialist_tools.md` — add an
  **"I-ST-F: from_user write authority"** entry (or subsection under §2) encoding:
  (a) `from_user` write tools are LLM-discretionary, never mandatory per ladder turn;
  (b) when a CHEMIST FORM EDITS block is present, the LLM must treat existing
  draft fields as the base and only call the write tool on an explicit instruction;
  (c) the authority source is `docs/project-prd.md §Precedence Mechanism`.
  This is the spec anchor the PRD already cites (`specialist_tools.md §I-ST-F`).

No other spec docs change for this leg (the prompt block wording was already
tracked in `graphs.md §2.1`; the tool contracts in §2 Table A are unchanged).

### Test plan

**BE unit test (pytest) — new file or extend `tests/unit/test_dynamic_prompts.py`:**

1. `test_continue_turn_no_from_user_rewrite`: build a `ModelRequest` with
   `params_draft={"from_user": {"sample_quantity": 2.5, ...}, "recommended": {...}}`
   and `ctx.chemist_form_draft` populated with `sample_quantity: 2.5`. Assert the
   rendered CC prompt contains the FROM_USER DRAFT AUTHORITY rule and does NOT
   contain phrasing that mandates re-extraction ("extract every from_user field").
   (Tests the prompt structure; the LLM behavior is proven by E2E.)

2. `test_authority_rule_present_iff_collecting_params`: assert the rule appears in
   `collecting_params` and is absent from `rts` / `conducting` / `done` prompts for
   CC, TLC, and RE.

3. `test_authority_rule_shared_source`: the rule string comes from a single constant
   (`_FROM_USER_DRAFT_AUTHORITY_RULE`) — assert CC, TLC, RE prompts all contain
   exactly the same rule text (prevents future desync).

**The E2E test (Playwright — `form-edit-sync-on-send.spec.ts` Leg A(c)) now passes because:**

The chemist edits `sample_quantity` to 2.5 and sends "Looks good, please continue."
The CC LLM sees the CHEMIST FORM EDITS block (sample_quantity: 2.5) and the new
authority rule ("do NOT re-extract; only call if this message instructs a change").
The message contains no change instruction. The LLM does not call
`update_cc_params(from_user=...)`. The `params_draft` retains `sample_quantity: 2.5`
(seeded by `reception_node:437` from `trials.params` which `UserMessageSubmittedEvent.apply`
wrote at turn receipt). The subsequent `TaskParamsSetEvent` (from `recommend_cc_params`
writing the `recommended` section) carries `from_user.sample_quantity = 2.5` — AC2
passes.

## Spec updates (Rule 10 — same change set)

- `.trellis/spec/BIC-agent-portal/backend-contract.md` — `/messages` row (:51) + note on §392 wording.
- `.trellis/spec/BIC-agent-service/backend/contracts.md` §3a (:125-159).
- `.trellis/spec/BIC-agent-service/backend/L4/events.md` — UserMessageSubmittedEvent apply no longer noop.
- `.trellis/spec/BIC-agent-service/backend/L4/domain-types.md` — SessionContext field roster +
  turn_schemas payload shape.
- `.trellis/spec/BIC-agent-service/backend/L2/facade.md` — `submit_user_message` contract
  (payload gains form_draft; signature row at :39-41).
- `.trellis/spec/BIC-agent-service/backend/L2/orchestrator.md` — loader section (:255-298), new
  ctx field.
- `.trellis/spec/BIC-agent-service/backend/L3/graphs.md` §2.1 — chemist-draft block joins the
  dynamic-prompt ownership roster.
- `.trellis/spec/BIC-agent-service/backend/L3/state.md` §1/§2 — only if seeding order text needs the
  new source mentioned (re-seed mechanism itself unchanged).
- Optional (route body changed, route unchanged): `L1/http-routes.md`, `L3/events.md`.
