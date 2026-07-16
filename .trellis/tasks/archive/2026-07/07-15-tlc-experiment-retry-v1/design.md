# Design — TLC user-initiated experiment retry V1

## Boundary

Implement two entry paths that converge on the existing `trials` attempt model:

1. Result review: keep the existing `result_review {accept:false}` action and
   specialize only the TLC reject branch to mint a fresh attempt.
2. Terminal execution failure: add one narrow session route that mints the same
   fresh TLC attempt without requiring a result-review decision.

No Lab Service or robot-protocol schema change is required in V1. A TLC result
review retry does call the existing idempotent Lab cleanup operation before
creating the new attempt, because a 3-fail aggregator otherwise remains in
`AWAITING_CONFIRMATION` and blocks the Lab single-TLC gate.

## Retry draft

Build the new TLC draft from the source trial:

- preserve: `from_user.rxn`, `from_user.target_window`,
  `from_user.recognition_mode`, and `recommended`;
- clear: `from_user.tlc_file_key`, `tlc_round_image_url`, `tlc_result`,
  `product_rf`, plus all `lab_logistics.sample_tubes`;
- do not copy any trial lifecycle, Lab Task, progress, result, analysis, or
  readiness state (new row defaults already provide the clean lifecycle).

## Event seam

Extend the existing `task_created` event with optional retry metadata and an
optional initial params payload. Existing producers omit both fields and remain
wire-compatible. Event apply inserts the new trial with its clean params in one
transaction, avoiding a created-without-seed partial state.

`retry_of_trial_id` lets the Portal distinguish a manual whole-trial retry from
the automatic TLC Rf round retry and open Material Preparation only for the
manual case.

## Idempotency

- Result-review retries put `FormConfirmedEvent` and the fresh
  `TaskCreatedEvent` behind the same decision CAS transaction. The worker turn
  is narration-only, so queue pressure cannot confirm a decision without also
  creating its retry.
- Failure-route retries use the deterministic next trial id and latest-attempt
  validation. A repeated request returns the already-created next attempt; a
  concurrent insert conflict is recovered by reading that deterministic row.

## Portal flow

- Rename the TLC-only review action to “Retry experiment”; other specialists keep
  “Request rework”.
- Add the same action to the active TLC terminal-failure monitor state.
- On a `task_created` event carrying `retry_of_trial_id`, foreground the new TLC
  trial and open its existing Material Preparation dialog with the clean draft.
- The existing dialog/reconcile/confirm path remains the only material write and
  dispatch path.

## Safety

- A result-review retry first calls the existing Lab cleanup for the source TLC
  aggregator. Lab `409 conflict` means it is already closed; any other cleanup
  failure aborts before decision CAS and retry creation. The terminal execution
  failure route makes no Lab call. Neither path edits source material rows.
- Unknown or stale/non-latest source trials are rejected.
- Only execute-capable session members can use the failure retry route.
- Automatic TLC Rf retries keep their shared Lab Task and existing behavior; they
  do not carry `retry_of_trial_id`.

## Rollback

Remove the failure retry route, the optional event fields, and the two Portal
entry/opening hooks. Existing result-review rejection then returns to guidance-only
behavior and existing trial/event storage remains valid.
