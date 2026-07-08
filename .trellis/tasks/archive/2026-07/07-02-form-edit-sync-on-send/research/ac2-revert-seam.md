# AC2 revert seam — investigation notes (2026-07-03)

Run 6 (session 3dafccb5) proved AC2 is still violated: chemist edited CC
`sample_quantity` to 2.5 on the form, sent "Looks good, please continue."
(no confirm).  The synced value (2.5) was committed to `trials.params` by
`UserMessageSubmittedEvent.apply` (leg 1 — working), and `reception_node.py:437`
re-seeded `params_draft` from it (working).  But within the SAME turn the CC
specialist LLM re-ran `update_cc_params → recommend_cc_params` and regenerated
`sample_quantity = 1.5` from the objective text in chat history
("purify a 1.5g sample"), then committed 1.5 through `TaskParamsSetEvent.apply`,
overwriting the synced 2.5.

---

## Ladder trace (CC collecting_params turn)

```
reception_node.py:437
  _extract_trial_flags_for_dispatch → out["params_draft"] = dict(trial.params)
    → params_draft["from_user"]["sample_quantity"] = 2.5   ← chemist-synced

dynamic_prompts.py:619-670  _maybe_chemist_draft_block
  → renders "sample_quantity: 2.5" in CHEMIST FORM EDITS block  ← leg 2 working

react_agent_node (CC LLM)
  call 1: update_cc_params(fields={from_user: {sample_quantity: 1.5, solvents: ..., ...}})
           ← LLM extracted "1.5g" from the OBJECTIVE TEXT in ctx.conversation_history
     → tools.py:948-975  _merge_draft_section("from_user", {sample_quantity: 1.5, ...})
     → returns Command(update={"params_draft": merged, ...})
     → _merge_params_draft reduces: {from_user: {sample_quantity: 1.5, ...}, ...}
     ← 2.5 overwritten to 1.5 here

  call 2: recommend_cc_params()
     → build_cc_param_request uses from_user.sample_quantity = 1.5
     → Mind returns CCParam for 1.5g
     → _set_draft_section("recommended", ...)
     → TaskParamsSetEvent.apply writes 1.5 to trials.params
```

The chemist-edits block in the prompt (leg 2) was rendered correctly at the
top of the turn.  The LLM read it, then proceeded to ignore it because the
objective text in chat history carries MORE gravity than the single-turn
system-prompt block.

---

## Files and functions a fix would touch

| File | Symbol | Role |
|---|---|---|
| `tools.py:932-975` | `update_cc_params` | the write tool — where 1.5 overwrites 2.5 |
| `tools.py:269-281` | `_merge_draft_section` | key-merge helper called by the tool |
| `specialist.py:32-61` | `_merge_params_draft` | LangGraph reducer on `params_draft` |
| `runtime_emitted.py:637-698` | `TaskParamsSetEvent.apply` | persists the merged draft |
| `dynamic_prompts.py:619-670` | `_maybe_chemist_draft_block` | existing leg 2 (prompt) |
| `reception_node.py:437` | `_extract_trial_flags_for_dispatch` | leg 1 re-seed (working) |

---

## Candidate seam evaluation

### (a) Reducer / state guard — pin from_user in `_merge_params_draft`

**Idea**: when a `from_user` field is already present in `old` (the chemist-synced
base), reject an LLM-sourced write to it unless the write is flagged as
"user-instructed".

**Why it does NOT work cleanly here**:

The `_merge_params_draft` reducer (`specialist.py:32-61`) operates on the
full draft dicts as opaque dicts — it has no way to know *why* a value changed.
The synced base landed on `params_draft` via `reception_node` before the turn
ran.  The LLM's `update_cc_params` tool call produces a NEW complete merged
dict (via `_merge_draft_section`), which the tool then returns as
`Command(update={"params_draft": merged_dict, ...})`.  LangGraph feeds this to
`_merge_params_draft(old=state.params_draft, new=merged_dict)`.  At reducer
time, `old` is already the chemist base (2.5) and `new` is the LLM's draft (1.5).
To pin at reducer level you would need the reducer to know "this field was set by
the chemist, ignore LLM overwrite" — that requires additional metadata (e.g. a
separate `pinned_from_user` dict on state), which:

- breaks the clean `Annotated[dict|None, _merge_params_draft]` single-key contract
- couples the reducer to business logic (which fields were chemist-set vs LLM-set)
- adds a second state field the LLM could accidentally write to

The 06-29 `target_window` precedent (`runtime_emitted.py:686-693`) pins at the
`TaskParamsSetEvent.apply` level (event persistence), NOT at the reducer level.
A reducer pin here would be a new pattern with no existing support infrastructure.

**Verdict**: structurally possible but heavier and messier than the apply-level
precedent.  Not the recommended seam.

---

### (b) Tool-write governance — `update_cc_params` refuses to overwrite a synced `from_user` field

**Idea**: `update_cc_params` detects that a field it's about to write was synced
from the chemist (e.g. `state.params_draft["from_user"]["sample_quantity"]`
already exists and equals the persisted value), and only allows the overwrite
if `ctx.chemist_form_draft` explicitly confirms the user's message asked for it.

**Problem — the discriminator**: `ctx.chemist_form_draft` is available in
`SpecialistState.ctx` at tool time (it was stashed by the orchestrator loader
before the turn started).  But discriminating "user's message instructed a change
to this specific field" is NOT trivially derivable from `chemist_form_draft`:

- `chemist_form_draft` contains what the FORM showed before the message was sent.
  It does NOT contain the user's message text or intent.
- To detect "the user's message asked to change sample_quantity", you would need
  to parse `ctx.conversation_history[-1].content` (the current user message) or
  ask the LLM to classify intent per field.

A non-LLM discriminator is not available here — you can know the synced form
value, but you cannot mechanically identify which fields the message text refers to.
Adding an LLM intent-classification step inside the tool would be a new pattern,
slow, and likely fragile.

Tool-body governance is possible but requires either (i) a fuzzy heuristic or
(ii) a new LLM call, both undesirable.

**Verdict**: technically feasible but the discriminator problem makes it heavy.
Not the recommended seam.

---

### (c) Flow: suppress the ladder re-derivation on a plain USER_MESSAGE turn

**Idea**: on a USER_MESSAGE turn where `from_user` fields are synced (i.e.
`ctx.chemist_form_draft` is non-null AND the params_draft has those values), the
CC specialist should NOT re-derive `from_user` from chat history — it should only
re-run the *recommendation* side (`recommend_cc_params`) if the from_user values
changed.

This is what the existing RE-RECOMMEND RULE says: "when the chemist changes ANY
from_user field after a recommendation exists, call recommend_cc_params again."
The problem is the LLM is re-running the full ladder from scratch on a
USER_MESSAGE ("continue") turn — it doesn't distinguish "the form already has
complete from_user; I should only do recommend" from "I need to extract from_user
from chat."

The RE-RECOMMEND RULE instructs: if from_user changes → re-recommend. But on a
plain "continue" message the from_user has NOT changed; the correct LLM behavior
is: no from_user update → just re-recommend (or, if already recommended, go
straight to confirmation).  The issue is the LLM sees the objective text
("purify a 1.5g sample") and treats it as the canonical from_user source —
overriding the form base.

This seam attack would require the prompt to explicitly say: "when from_user is
already populated in the draft (which you can see in the state), do NOT re-extract
it from the objective text — the draft is authoritative."  This is a prompt-only
fix.  Prompt-only fixes are what leg 2 (the chemist-draft block) already attempts,
and run 6 proves they are not reliable against chat-history gravity.

**Verdict**: prompt-only approach is already in place and insufficient.  A flow
change alone (prompt strengthening) is not the recommended fix.

---

### Recommended seam: `TaskParamsSetEvent.apply` field-level pin for synced `from_user` fields

The correct enforcement seam is **the same layer as the 06-29 `target_window`
pin** — `TaskParamsSetEvent.apply` in `runtime_emitted.py:658-698`.

**How it works today** (post-confirm guard at line 669-693):

```python
if trial is not None and trial.phase != "collecting_params":
    on_disk = trial.params or {}
    carried = dict(params)
    for section in ("recommended", "lab_logistics"):
        if not carried.get(section) and on_disk.get(section):
            carried[section] = on_disk[section]
    # pin target_window from confirmed on_disk
    on_disk_from_user = on_disk.get("from_user")
    if isinstance(on_disk_from_user, dict) and "target_window" in on_disk_from_user:
        ...
        merged_from_user["target_window"] = on_disk_from_user["target_window"]
    params = carried
```

This guard fires ONLY when `trial.phase != "collecting_params"`.  In the bug,
the trial IS in `collecting_params`, so the guard is a no-op.

**The new pin** — analogous to `target_window`, but for `from_user` fields that
were synced from the chemist's form on this turn:

On a `collecting_params` turn where the chemist sent a form draft
(`form_draft.params["from_user"]` non-empty), the `UserMessageSubmittedEvent.apply`
has ALREADY written those synced values into `trials.params` (leg 1).  When a
subsequent `TaskParamsSetEvent` arrives (from the LLM's tool call), it should
treat every `from_user` key that exists in the PERSISTED `trials.params` AND came
from the chemist (i.e. was written by `UserMessageSubmittedEvent.apply` this turn)
as PINNED — the LLM cannot silently overwrite it.

The discriminator is clean and mechanical:

> A `from_user` field is pinned iff it is present in `trials.params["from_user"]`
> as of the `TaskParamsSetEvent.apply` call AND the trial is in `collecting_params`
> AND the incoming blob also touches that field.

The pin merges like `target_window`: take the on-disk value regardless of what the
LLM's blob carries.

**What changes**:

`runtime_emitted.py` — `TaskParamsSetEvent.apply` gains a new guard branch for
the `collecting_params` phase (a twin to the existing post-confirm branch) that
carries forward ALL `from_user` fields that are already populated on disk.
Effectively: `incoming_from_user[key] = on_disk_from_user[key]` for every key
present in `on_disk_from_user` — never overwriting what the chemist (or the LLM
in a prior turn) already confirmed.

Wait — this is too broad.  If applied wholesale, the LLM can NEVER update a
`from_user` field on any turn where the field already has a value — even when the
user explicitly instructs "set the quantity to 3."

**The discriminator answer**:

The dispatch prompt asks: does `chemist_form_draft` / message text give us a clean
signal for "user instructed a change to this field"?

The answer is **YES, at the apply level, but only via message text, not form draft**.
The form draft tells us what the form showed BEFORE the message.  "User instructed
a change" means the user's chat text instructed it — not the form.  There is no
mechanical parser for that.

HOWEVER: the governing principle is:

> "The form value is CONTEXT; the user's chat MESSAGE is INSTRUCTION; instruction
> always wins."

The corollary is: when the user's message does NOT contain an instruction to change
a field (e.g. "Looks good, please continue."), the LLM should NOT change it.  The
LLM did change it — because it extracts from_user from chat history.  That is the
bug.

The apply-level pin has a fatal flaw: it cannot distinguish between:
- LLM extracts from chat history (wrong, violates chemist intent)
- LLM honors an explicit user instruction in THIS turn's message (correct)

Both produce the same `TaskParamsSetEvent.apply` call.  A blanket carry-forward
of on-disk `from_user` fields would BLOCK the legitimate "user said set it to 3"
path.

---

## Revised seam: `TaskParamsSetEvent.apply` — pin ONLY when there is an active form draft this turn

The form draft (`UserMessageSubmittedEvent` wrote it to `trials.params` this turn)
provides a per-field discriminator: **a field present in the chemist's submitted
form draft is pinned this turn only**.  If the LLM attempts to overwrite it, carry
forward the form-draft value.

This works because:
- `UserMessageSubmittedEvent.apply` wrote `form_draft.params` to `trials.params`
  before the turn ran.
- At `TaskParamsSetEvent.apply` time, `trials.params` already reflects the
  chemist's form state.
- The guard can read the ORIGINAL form-draft values from `trials.params` and
  compare them against the incoming LLM blob — any discrepancy in a `from_user`
  field means the LLM overwrote a chemist-set value.
- Pin that field back to the on-disk value.

**But the same problem persists**: if the user's message said "use 3g instead",
the LLM would legitimately write `sample_quantity = 3` via `update_cc_params`,
and the pin would revert it to 2.5 (the form value).  That violates D1 ("instruction
always wins").

---

## Root cause clarification and correct seam

The real problem is not apply-level governance but **prompt-level clarity about
the authority order**.  The existing `_maybe_chemist_draft_block` tells the LLM
"if this message's text contradicts a value below, the text instruction wins."
That wording is correct but insufficient — it focuses on contradiction.  What the
LLM does instead is treat the OBJECTIVE TEXT as the from_user extraction source
and silently prefer it over the form draft, without even recognizing a conflict.

The LLM is following the RE-RECOMMEND RULE correctly (it sees sample_quantity
is "1.5g" in context and updates it) — but it is wrong to call `update_cc_params`
at all on a "continue" turn when `from_user` is already populated.

**The structurally correct seam is (c) + a FLOW guard**:

On a turn where:
1. `params_draft["from_user"]` already has all recommend-gate fields populated
   (sample_quantity, solvents, solvent_ratio, product_rf — the Mind request
   prereqs), AND
2. The turn is a plain USER_MESSAGE (not a form_confirm), AND
3. `params_draft["recommended"]` is already populated

Then the LLM should NOT run `update_cc_params` at all — it should proceed directly
to recommendation consistency check or exit.  The prompt instruction is the only
lever.

But the existing instruction already tries to say this (it's baked into the
RE-RECOMMEND RULE phrasing) and it fails.

**The clean mechanical discriminator that DOES exist**:

`ctx.chemist_form_draft` is available on `SpecialistState.ctx` AND on the
frozen ctx that `_maybe_chemist_draft_block` reads.  When a field appears in
`ctx.chemist_form_draft.from_user`, it is the value the CHEMIST set on the form.
This is distinct from the OBJECTIVE TEXT which is the historical context.

The seam is: **strengthen the prompt block to explicitly forbid re-extracting
from_user fields that appear in `ctx.chemist_form_draft`**.  Specifically:

```
CHEMIST FORM EDITS — these from_user values came from the chemist's form, not
from the objective text. DO NOT re-extract these fields from the chat history
or the objective description. Use them as-is. Only change them if this
message's text EXPLICITLY INSTRUCTS a new value (e.g. "set quantity to 3").
```

This is a prompt-only fix — still vulnerable to LLM non-compliance.

---

## The apply-level pin IS achievable with a session-flag discriminator

Here is a way to make the apply-level pin safe:

`UserMessageSubmittedEvent.apply` already writes the form-draft keys.
It can also write a **per-field marker** — a separate set on `trials.params`
indicating which `from_user` keys came from the chemist's form this turn:

```json
{
  "from_user": {"sample_quantity": 2.5, ...},
  "_chemist_set_keys": ["sample_quantity"]
}
```

`TaskParamsSetEvent.apply` reads `_chemist_set_keys` and refuses to overwrite
those fields in `from_user` — UNLESS the incoming `from_user` blob was flagged
differently.  After the turn completes, `_chemist_set_keys` is cleared.

**The discriminator for "user instructed a change"**: the marker is CLEARED by
the same turn's `TaskParamsSetEvent.apply` that comes AFTER an EXPLICIT
`update_cc_params` call that is flagged.  The problem: the LLM's tool call has
no flag, and there is no reliable way to tag "LLM called this because of chat
instruction vs because of chat history."

This is the same impasse: without an LLM intent signal, the discriminator
between "legitimate user instruction" and "history-gravity extraction" is
not mechanical.

---

## Actual recommendation: DUAL seam

Given the constraint that a purely mechanical discriminator does not exist, the
correct fix is a combination:

### Seam A (apply-level, safe subset): protect form-synced fields WITHIN the same turn only

`TaskParamsSetEvent.apply` gains a guard: when `trial.phase == "collecting_params"`
AND a `_chemist_set_turn_id` marker is present on `trials.params` matching the
current `session_event_id` (or a simpler proxy: the marker is cleared by a
successful `request_params_confirmation` tool or phase advance), refuse to
overwrite those specific keys in `from_user`.

The marker is set by `UserMessageSubmittedEvent.apply` alongside the form values,
and cleared by `FormConfirmedEvent.apply` (phase advance removes it implicitly).

**Risk**: if the user's message in the SAME turn contains an instruction to change
the pinned field, the pin blocks it.  This is the D1 violation.

**Mitigation**: the marker can be per-field AND cleared when the LLM has provided
evidence the user asked.  But "evidence" is not mechanical — this requires the
LLM to emit a signal.

### Seam B (prompt-level, primary): explicit "synced field authority" instruction

Strengthen `_maybe_chemist_draft_block` in `dynamic_prompts.py:619-670` with a
stronger prohibition against re-extraction:

```
CHEMIST FORM EDITS (unconfirmed, sent with this message).
These values are AUTHORITATIVE for this turn — they came from the chemist's
form, NOT from the experiment objective or prior conversation.
If this message's text contradicts a value below, the text instruction wins.
DO NOT re-extract these fields from the objective text or prior messages:
use the form values as the base.
from_user edits — RE-RECOMMEND RULE applies (re-call recommend_* if any changed):
  sample_quantity: 2.5
  ...
```

Combined with Seam A, this is defense-in-depth: the prompt prevents the LLM
from overwriting in the normal case; the apply pin backstops it when the LLM
fails to comply.

---

## Recommended seam (single, clean fix)

After more careful analysis, a clean single-seam fix IS available:

**Seam: `TaskParamsSetEvent.apply` — carry forward ALL on-disk `from_user` fields when
`trials.phase == "collecting_params"` AND the on-disk `from_user` was written by
`UserMessageSubmittedEvent.apply` this same turn (i.e. differs from a pre-turn
snapshot).**

Simpler formulation without a session-flag marker:

`UserMessageSubmittedEvent.apply` stores the form draft in `trials.params`.
When `TaskParamsSetEvent.apply` fires subsequently within the SAME turn:

- For every field in `on_disk["from_user"]` (the chemist-synced form): carry it
  forward into the incoming blob ONLY if the incoming blob's value for that field
  DIFFERS from `on_disk["from_user"][field]`.

The D1 exception ("instruction wins"): the fix accepts this means an explicit
instruction in the chat text would ALSO be blocked.  Drake's governing principle
says "instruction always wins" — so **the apply-level pin cannot be the primary
enforcement**.

**Final recommendation**: the fix must live at the **prompt level (seam B)**
with an apply-level backstop as defense-in-depth.

### Exact files a fix touches:

1. **`dynamic_prompts.py:619-670` `_maybe_chemist_draft_block`** — the primary fix.
   Add explicit prohibition language:
   "DO NOT re-extract these from_user fields from prior chat or the objective
   description — they are the current form truth. Only update_cc_params with a
   NEW value if THIS message explicitly instructs it."

2. **`runtime_emitted.py:637-698` `TaskParamsSetEvent.apply`** — backstop pin
   (defense-in-depth).  When `trial.phase == "collecting_params"` AND
   `on_disk["from_user"]` is populated (was written by a form-draft sync this
   turn), carry forward each on-disk `from_user` field into the incoming blob,
   MAKING AN EXCEPTION for fields whose value in the incoming blob matches the
   chemist's message text.

   **Discriminator gap**: no mechanical way to detect "message text instructed
   this field."  The backstop WILL block D1 legitimate overrides.  This is
   acceptable as defense-in-depth ONLY if the prompt (seam B) correctly handles
   the D1 case.  If the prompt works, the backstop never fires.  If the prompt
   fails (LLM re-extracts from history), the backstop catches it.

   This is the same tradeoff as the 06-29 `target_window` pin: the chemist
   cannot change `target_window` mid-turn by chat text, only by a new form confirm.
   The equivalent ruling here: "a synced from_user field can only be changed
   within the collecting_params phase by an explicit chat instruction that the LLM
   routes through update_cc_params — if the LLM updates it due to history-gravity,
   the backstop reverts it; if the LLM updates it because of a real instruction,
   the backstop also reverts it, which violates D1."

   **Resolution**: the backstop is ONLY correct if Drake explicitly accepts that
   on a turn where a form draft is synced, a chat instruction to change a from_user
   field will be blocked, and the chemist must re-send without a draft (or confirm
   first).  This is a product decision.

---

## Summary for sign-off

**The bug**: `update_cc_params` extracts from_user from chat history (objective
text) and overwrites the chemist-synced form value on a "continue" turn, with
`TaskParamsSetEvent.apply` committing the overwrite.

**Available seams**:
- Reducer (`_merge_params_draft`): no authority over which writes are chemist vs LLM.
- Tool body (`update_cc_params`): no mechanical discriminator for "user instructed this."
- `TaskParamsSetEvent.apply`: clean backstop pattern, but BLOCKS D1 "instruction wins"
  in edge case (simultaneous form sync + chat instruction to the same field in one turn).
- Prompt (`_maybe_chemist_draft_block`): no mechanical guarantee, but handles D1 correctly.

**Recommended fix** (requires Drake sign-off on the D1 edge case):

Primary: **prompt strengthening** in `_maybe_chemist_draft_block` — stronger wording
that explicitly prohibits re-extracting synced fields from objective/history text.

Backstop: **`TaskParamsSetEvent.apply`** — on `collecting_params`, carry forward ALL
on-disk `from_user` fields from the chemist-synced state, KNOWING this blocks the
edge case of "same turn: form sync + chat instruction to same field".

**D1 edge-case ruling needed from Drake**: is it acceptable that on a turn where the
chemist sends a form draft, a chat instruction to change the same field (e.g. form
shows 2.5, chat says "use 3g") is blocked by the apply pin, and the chemist must
re-send without the draft?  If yes, the backstop is safe.  If no, the backstop must
be omitted and only the prompt is the fix.

**Exact functions a fix touches**:
- `dynamic_prompts.py:619-670` `_maybe_chemist_draft_block` — prompt wording change.
- `runtime_emitted.py:658-698` `TaskParamsSetEvent.apply` — optional backstop pin
  (symmetric to `target_window` at :686-693).

Both changes are surgical and confined to existing seams.  No new state fields,
no new tool surface, no reducer changes.
