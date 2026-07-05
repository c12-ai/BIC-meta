# Bind params FORM_CONFIRM turns to their decision trial

## Problem (live incident, 2026-06-12, found by bic-e2e-runner)

A params FORM_CONFIRM POST raced a user chat message by 4 ms. The BE serialized
the chat turn first (it ran rts → dispatch → the lab task completed), so the
FORM_CONFIRM turn dequeued ~60s late — when its trial was already terminal.

`reception_node`'s dispatch picking is `task_terminal → in_flight → planned`
for EVERY turn kind. The late params-confirm turn missed `in_flight` (trial
terminal) and fell into `_pick_next_planned_step`, which **minted an
attempt-2 trial on the same job** (cursor only advances on review accept),
seeded the confirm payload as its draft, and re-entered `collecting_params`.
The zombie trial then hijacked post-review routing: instead of advancing to
job-1 (RE), the session kept re-emitting CC params forms. Job-0 never
advanced despite its trial completing.

Evidence: session `ee79651b` (13:22–13:27 UTC) — duplicate `task_created` on
job-0 at 13:24:49, trials `1102ad3e` (done/completed) + `3948f54c`
(collecting_params/pending), both jobs stuck `pending`.

## Fix (design approved by Drake)

1. **L1/L2 contract** — `FormConfirmPayload` (app/data/turn_schemas.py) gains
   `task_id: str | None = None`. `SessionService.submit_form_confirm` already
   loads the pending decision and resolves `original_action.task_id` for
   validation — populate the field when enqueuing the FORM_CONFIRM turn.
   Update `.trellis/spec/backend/L4/domain-types.md` (and any L2/L3 spec rows
   describing FormConfirmPayload) in the same change set (Rule 10).
2. **L3 reception_node** — new FIRST dispatch branch (before
   task_terminal/in_flight/planned): if `turn.kind == FORM_CONFIRM` and
   `turn.form_confirm.confirm_kind == params` and
   `ctx.find_trial(payload.task_id)` hits → bind dispatch to THAT trial
   (`source="form_confirm"`, kind from its parent job's executor, phase from
   the trial — already advanced by the L2 apply). `new_task_minted=False`.
   A params confirm can NEVER mint a trial. If the trial is missing → fall
   through to existing behavior (ends in `no_plan`, fails loud).
3. **Deliberately unchanged**: `result_review` confirms keep the existing
   fall-through — that IS the chained-dispatch mechanism (review accept →
   cursor advance → planned path creates the next job's trial). Plan confirms
   are routed before reception and untouched.

## Acceptance criteria

- [ ] Unit: a FORM_CONFIRM(params) turn whose trial is TERMINAL binds to that
      trial (source `form_confirm`, no minting) — regression for the incident.
- [ ] Unit: a FORM_CONFIRM(params) turn whose trial is in `rts` binds to it
      (normal same-turn path unchanged in outcome).
- [ ] Unit: FORM_CONFIRM(result_review) still falls through to the planned
      path (chaining preserved).
- [ ] Full BE suite green; ruff/pyright clean.
- [ ] Spec docs updated: domain-types.md FormConfirmPayload row + reception
      dispatch-source description in graphs.md.
- [ ] Live chained CC→RE E2E green.
