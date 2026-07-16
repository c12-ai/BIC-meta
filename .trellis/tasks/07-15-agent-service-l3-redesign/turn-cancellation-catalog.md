# User Turn cancellation catalog

Status: architecture-level cancellation review closed. Product boundary, race and deadline ordering, immediate authoritative closure, projection, authorization, eligibility, durable-only output, exact-Turn API semantics, and minimal internal audit data are confirmed. Exact response spellings, cooperative provider interruption, and mixed-version release mechanics are delegated to the separately releasable cancellation slice.

## Confirmed product boundary

- A user must be able to explicitly cancel the exact current user-triggered Turn, like a normal chatbot Stop action.
- Cancellation is a durable Agent Service operation. Closing SSE, navigating away, aborting a browser request, or disabling input does not cancel a Turn.
- Portal needs the server-assigned `turn_id` from durable input admission so it never targets a later Turn through a mutable `current` alias.
- Agent Turn cancellation stops further Agent work/output. It does not roll back a committed Proposal, erase an Outbox Command, or mean Lab/Nexus Task cancellation.
- This is a separately releasable Agent Service + Portal slice and the explicit exception to the core refactor's zero-coordinated-external-change goal.

## Current-code baseline

- Agent Service currently admits user work through `POST /sessions/{session_id}/messages`, `POST /sessions/{session_id}/forms/confirm`, and `POST /sessions/{session_id}/decisions`; all three return HTTP 202 with `accepted` and `event_id`, not `turn_id`.
- `turn_id` currently lives in the in-process `TurnInput`; there is no durable Turn lifecycle row or Turn cancel/status endpoint.
- Portal has no Stop callback/control and has tests that deliberately reject a fake Stop action while streaming.
- Portal route `AbortController` and SSE teardown stop local work/reception only. Backend Turn execution continues.
- Current lifecycle projection has `turn_started`, `turn_completed`, and `turn_failed`; there is no non-error cancellation event.

## Confirmed API semantics

```http
POST /sessions/{session_id}/turns/{turn_id}/cancel
```

- The request body is empty. The actor comes only from the authenticated Principal.
- The existing HTTP 202 receipts for user message, form confirmation, and genuine user decision response each add the server-assigned stable Turn identity committed by Input Admission. The proposed wire spelling is `turn_id`.
- Cancellation returns HTTP 200 only after the immediate terminal transaction commits or L2 reads the already committed terminal winner; it never acknowledges a mere interruption request with 202.
- One response disposition has exactly two accepted semantic branches:
  - `cancelled`: this request or an earlier idempotent request durably produced the cancellation terminal;
  - `already_terminal`: completion, failure, or timeout had already won, so cancellation did not happen.
- The response does not copy the full terminal outcome. Portal consumes terminal detail through SSE/history/replay.
- Unknown Turn and Session/Turn mismatch return 404; insufficient authority returns 403; a known System-Triggered or otherwise ineligible Turn returns 409.
- Exact JSON response field and enum spellings remain provisional; the route, status timing, two semantic branches, and error meanings are confirmed.

This is recorded in ADR 0024.

### Field Necessity Record: stable Turn identity in admission receipts

```text
Field: stable Turn identity in eligible HTTP Input Admission receipts
Status: accepted semantically; proposed wire spelling turn_id remains provisional until contract freeze

Q1 Named consumer:
- Portal message, form-confirmation, and decision-response admission handlers.
- Portal Stop control and cancellation client.

Q2 Decision/action driven:
- Correlate the optimistic user interaction with the exact durable queued Turn.
- Address cancellation before a later turn_started event arrives.
- Prevent a Stop click from targeting a newer Turn in the same Session.

Q3 Why existing facts/trace are insufficient:
- The current event_id identifies the admitted input event, not the Turn execution unit accepted with it.
- turn_started can arrive later or never arrive before a queued cancellation.
- A Session-level current lookup races with later admission and multi-tab activity.
- Trace data is not a client addressing contract.

Q4 Compatibility exposure and migration:
- Additive on the existing HTTP 202 response for all three eligible user admission routes.
- Existing clients can ignore the new field; Portal cancellation remains hidden until it consumes it.
- Contract tests must prove each receipt returns the identity from the same committed admission transaction.

Q5 Cross-domain/topology stability:
- Stable. Turn identity belongs to L2 admission and does not depend on Chemistry/Biology, Agent graph shape, model provider, or tool topology.

Decision:
- Require the semantic stable Turn identity in every eligible admission receipt.
- Use the canonical Turn identity rather than introducing a cancellation token or Session current alias.
- Keep exact JSON spelling under contract-freeze review; turn_id is the current proposal.

Validation/test required:
- User-message, form-confirm, and genuine decision-response receipt contract tests.
- Queued cancellation before turn_started.
- Two rapid admissions and multi-tab addressing cannot redirect cancellation.
- Existing response consumers tolerate the additive field.

Review owner/date:
- Architecture grilling decision, 2026-07-15.
```

### Field Necessity Record: cancellation response disposition

```text
Field: idempotent cancellation response disposition
Status: accepted semantically; exact JSON field and enum spellings remain provisional

Q1 Named consumer:
- Portal Stop request handler and its reconnect/reconciliation path.
- API integration and race tests.

Q2 Decision/action driven:
- Confirm that this or an earlier request actually produced a cancellation terminal.
- Avoid displaying a false cancellation when completion, failure, or timeout had already won.
- Trigger history/SSE reconciliation when the Turn was already terminal without copying its full outcome into this response.

Q3 Why existing facts/trace are insufficient:
- HTTP 200 alone cannot distinguish an idempotent cancellation success from a lost cancellation race.
- SSE may be delivered before or after the HTTP response or temporarily disconnected.
- Trace data is neither durable client state nor an API result.

Q4 Compatibility exposure and migration:
- This is a new endpoint with no legacy response consumer.
- The two semantic branches can freeze before their exact field/value spelling.
- Portal hidden support and contract tests deploy before Stop is enabled.

Q5 Cross-domain/topology stability:
- Stable. The distinction is between the cancellation terminal and a prior non-cancellation terminal, independent of domain and execution topology.

Decision:
- Return cancelled when this or a prior request durably cancelled the Turn.
- Return already_terminal when completion, failure, or timeout had already won and cancellation did not occur.
- Do not add a requested or cancelling response state.

Validation/test required:
- Duplicate and concurrent cancellation requests.
- Cancellation races completion, failure, timeout, and Proposal acceptance.
- HTTP 200 is impossible before durable closure is committed or observed.
- Portal never presents already_terminal as a successful cancellation.

Review owner/date:
- Architecture grilling decision, 2026-07-15.
```

### Field Necessity Record: full terminal outcome in cancellation response

```text
Field: full typed terminal outcome copied into the cancellation HTTP response
Status: dropped

Q1 Named consumer:
- None. Portal consumes terminal detail from persisted Session Event/history projection.

Q2 Decision/action driven:
- No cancellation API decision needs the full outcome after the accepted two-branch disposition is known.

Q3 Why existing facts/trace are insufficient:
- Existing persisted terminal projection is sufficient and authoritative for user-visible detail.
- The narrow disposition already tells the cancellation caller whether cancellation occurred.

Q4 Compatibility exposure and migration:
- Copying the outcome would couple the new endpoint to every later terminal-schema change and create two payloads that must remain synchronized.
- Omitting it requires no legacy migration because the endpoint is new.

Q5 Cross-domain/topology stability:
- The full terminal schema remains deliberately provisional and may gain consumer-driven domain-neutral detail; duplicating it here would make the cancellation API less stable.

Decision:
- Do not copy the full typed terminal outcome into the cancellation response.
- Keep terminal detail authoritative in Session Event/history/replay.

Validation/test required:
- Response schema rejects accidental terminal-detail expansion before Field Necessity review.
- SSE/history still converge when their event arrives before or after the HTTP response.

Review owner/date:
- Architecture grilling decision, 2026-07-15.
```

## Case catalog

| Case | Required authority result | Agent work/output | Proposal/Command consequence | Projection question |
|---|---|---|---|---|
| Cancel queued Turn | L2 closes the identified queued Turn exactly once | Foundation never starts | no Proposal can commit | distinct cancelled terminal versus compatibility mapping |
| Cancel running before Proposal acceptance | cancellation and Proposal admission serialize on the same Turn/effect authority | current claimant receives cooperative stop and loses later output authority | if cancellation wins, later Proposal is rejected | retain completed segments; discard active emit-only fragment |
| Cancellation races Proposal commit | exactly one transaction wins the relevant authority decision | depends on winner | must never report effect prevented while silently committing it | response/event ordering across tabs |
| Cancel after Proposal/Outbox commit | close/stop the Turn without undoing committed facts | stop further model/query/narration work | accepted Proposal and Command continue independently | cancelled Turn plus committed workflow progress must both remain visible |
| Duplicate cancel | idempotently return current cancellation/terminal result | no new work | no duplicate mutation | no duplicate terminal event |
| Cancel already-terminal Turn | return `cancelled` for an existing cancellation terminal, otherwise `already_terminal` | none | none | reconcile terminal detail from SSE/history without claiming a new cancellation |
| Stale claimant resumes after cancel | fence all writes and broadcasts | may clean up locally only | no Proposal or terminal authority | internal telemetry only |
| Cancellation races deadline | before the cutoff cancellation may win; at/after the cutoff timeout is the only eligible terminal | stop component work | committed effects remain | post-deadline request returns `already_terminal` and timeout projection |
| Browser navigation or SSE disconnect | no cancellation | backend continues unless explicit cancel was admitted | unchanged | reconnect/replay remains correct |
| Service shutdown | operational drain/recovery, not user cancellation | reclaim or closure policy applies | unchanged | must not impersonate user intent |
| User wants to stop an existing Lab Task | new authorized domain Proposal/Command, not Turn Cancellation | originating Turn semantics irrelevant | Lab owns physical cancellation outcome | separate product flow |

## Confirmed race decision

User cancellation and Proposal acceptance use **transactional first-commit wins** on the shared L2 Turn/effect authority:

- cancellation-first irrevocably closes future effect authority, so every later Proposal candidate is non-mutating;
- Proposal-first preserves the committed business action, Workflow Fact changes, Session Events, and Outbox Commands;
- a later cancellation in the Proposal-first case stops only remaining model, query, narration, and output work;
- neither path attempts compensation or Lab Task cancellation;
- duplicate participants observe the already committed winner rather than creating another outcome.

This is recorded in ADR 0018.

## Confirmed authorization decision

The Turn Initiator may cancel their own Turn while retaining current Session `CHAT`. Any current owner/collaborator with `EXECUTE` may cancel another member's cancellable Turn. An observer can cancel their own Turn but not another member's; former and non-members cannot cancel.

### Considered options

| Option | Benefit | Failure mode |
|---|---|---|
| Initiator only | strongest protection from peer interruption | a disconnected initiator can leave every collaborator locked until deadline/recovery |
| Any member with `CHAT` | mirrors message admission and is simple | observers may cancel another user's Agent work despite lacking `EXECUTE` |
| Initiator for own Turn; any `EXECUTE` member for another Turn | self-service plus owner/collaborator recovery control | selected; requires a trusted durable Turn initiator reference and an explicit two-branch authorization test |

This is recorded in ADR 0021.

### Field Necessity Record: trusted Turn Initiator reference

```text
Field: trusted Turn Initiator principal reference (semantic field; exact name/type provisional)
Status: accepted as internal persisted admission data; external exposure not accepted

Q1 Named consumer:
- L2 cancellation authorization.
- Security/audit investigation of who initiated the cancelled Turn.

Q2 Decision/action driven:
- Select the self-cancellation branch requiring current CHAT versus the peer-cancellation branch requiring current EXECUTE.
- Reject an observer cancelling another member's Turn without blocking that observer from cancelling their own.

Q3 Why existing facts/trace are insufficient:
- Current Session membership says who the caller is now, not who initiated the Turn.
- Collaboration focus and Session owner are different concepts.
- Current UserMessageSubmittedEvent/TurnInput do not retain initiating user_id.
- Trace data is non-authoritative and cannot drive an authorization decision.

Q4 Compatibility exposure and migration:
- Persisted internally with durable user-input admission; not required in SSE, snapshot, cancel request, or turn_cancelled payload.
- Derived only from authenticated current_user_id, never a client-supplied initiator field.
- Cancellation remains disabled until the new durable Turn model can supply this reference; pre-feature in-memory Turns are drained rather than assigned a guessed initiator.

Q5 Cross-domain/topology stability:
- Stable for every user-triggered domain Turn. It identifies the authenticated admitting Principal independent of Chemistry/Biology, focus changes, graph shape, or model/tool topology.

Decision:
- Require the semantic reference in durable user-triggered Turn admission.
- Do not freeze its physical column name, identifier encoding, or wire exposure yet.
- Keep it distinct from the Principal who later requests cancellation.

Validation/test required:
- Payload spoofing cannot override the initiator.
- Role changes between admission and cancellation use current capabilities.
- Self/peer/observer/former/non-member authorization matrix.
- Focus transfer and owner transfer do not rewrite historical initiator identity.

Review owner/date:
- Architecture grilling decision, 2026-07-15.
```

## Confirmed deadline-ordering decision

The absolute execution deadline is a semantic cutoff, not the time at which a watchdog happens to run.

- L2 evaluates the terminal decision using an authoritative clock.
- Strictly before `execution_deadline_at`, an authorized cancellation may compete and commit `cancelled`.
- At equality or afterwards, timeout is the only eligible terminal. The cancellation path may help persist or observe timeout closure but returns `already_terminal`; it cannot relabel the Turn as cancelled.
- Proposal/Outbox effects already committed before either terminal remain independent.
- This rule needs no durable `cancel_requested_at` because request arrival is not the authoritative terminal decision.

This is recorded in ADR 0026.

## Confirmed partial-output decision

V1 retains already persisted completed output segments and discards only the currently unfinished emit-only fragment:

- keep persisted `text_done`, `reasoning_done`, and completed tool results;
- remove the active `text_delta`, `reasoning_delta`, or tool-call-delta fragment in every Portal projection;
- mark open reasoning/tool presentation interrupted;
- render a non-error cancellation marker;
- add no `partial_text`, output-draft field, or high-frequency response accumulator in v1.

This is recorded in ADR 0023 and the completed Field Necessity Record in `turn-terminal-outcome-catalog.md`.

## Confirmed eligibility decision

V1 Portal Stop and the user cancellation API apply only to trusted User-Triggered Turns admitted with `source=USER`:

- `USER_MESSAGE`;
- `FORM_CONFIRM`;
- genuine user `DECISION_RESPONSE`.

They reject System-Triggered Turns from MQ, scheduler, and reconciliation, including `TASK_TERMINAL`, `DECISION_EXPIRED`, and reconciliation continuations. Operational shutdown and administrator recovery are separate controls.

- L2 assigns source/kind and Turn Initiator; Portal cannot opt a Turn into the cancellable set.
- Cancelling a form/decision continuation never reverses deterministic Input Admission facts.
- Current scheduler behavior that can represent expiry as `DECISION_RESPONSE/USER` is migration debt and must be corrected before this gate becomes authoritative.

This is recorded in ADR 0022.

## Confirmed closure decision

An accepted user-cancellation transaction immediately writes the unique cancellation terminal and its terminal projection, closes still-open effect authority, and revokes all later Proposal, persistence, and broadcast authority. Cooperative model/tool interruption and resource cleanup follow asynchronously; they do not keep the durable Turn running.

- no `cancelling` Turn operational state is added;
- no durable `cancel_requested` phase is required for correctness;
- a stuck provider/tool may temporarily consume resources but cannot produce authoritative output or effects;
- duplicate cancellation and late worker completion observe the existing terminal and emit nothing new.

This is recorded in ADR 0019.

## Confirmed projection decision

Cancellation appends one persisted, replayable, non-error `turn_cancelled` Session Event in the same L2 transaction as Turn terminal closure.

- Portal treats it as terminal, clears the shared `turnRunning` lock, and finalizes the matching assistant Turn as cancelled;
- it must not create a failed bubble or invoke failure-only workflow projection such as `onAnalysisFailed()`;
- additional event fields are not accepted merely because the event kind is accepted;
- Portal support is deployed hidden before Agent Service emission and Stop enablement;
- mixed-version tabs must be tested or prevented by the rollout gate because old Portal code drops unregistered named SSE events.

This is recorded in ADR 0020 and the completed Field Necessity Record in `turn-terminal-outcome-catalog.md`.

## Confirmed cancellation-audit decision

The authenticated Principal whose request first commits the cancellation terminal is retained durably as the Cancellation Actor in that same transaction.

- It is distinct from the Turn Initiator: one member may start a Turn and another member with `EXECUTE` may stop it.
- A duplicate cancellation observes the existing actor and never replaces it with the later caller.
- The reference is internal-only in v1 and is absent from `turn_cancelled`, SSE, snapshot/history, and the cancellation HTTP response.
- Exact storage name/type and authorized audit-query mechanism remain provisional.
- No free-text reason, separate cancellation-source field, or `cancel_requested_at` is added; terminal kind and commit time already carry the selected v1 semantics.

This is recorded in ADR 0025.

### Field Necessity Record: Cancellation Actor Principal reference

```text
Field: trusted Cancellation Actor Principal reference (semantic field; exact name/type provisional)
Status: accepted as internal persisted audit data; external exposure not accepted

Q1 Named consumer:
- Authorized security/incident reviewer investigating peer interruption of shared Agent work.
- Internal audit query/export correlating the Turn Initiator with the member who stopped the Turn.

Q2 Decision/action driven:
- Distinguish self-cancellation from an owner/collaborator using EXECUTE to cancel another member's Turn.
- Attribute a disputed or unexpected peer cancellation to the authenticated actor for incident follow-up and access review.

Q3 Why existing facts/trace are insufficient:
- Turn Initiator identifies who admitted the user input, not who later cancelled it.
- Current Session membership and authorization context are transient and may change after closure.
- Application logs and traces may expire, sample, or be unavailable and are not the durable audit fact of record.

Q4 Compatibility exposure and migration:
- Written in the same L2 transaction as the cancellation terminal and retained internally.
- Not exposed in turn_cancelled, SSE, snapshot/history, or cancellation HTTP responses in v1.
- Cancellation is enabled only for durable Turns that can store the trusted actor; no guessed backfill is allowed.
- Exact column, identifier encoding, retention, and authorized audit access remain implementation-design decisions.

Q5 Cross-domain/topology stability:
- Stable. It identifies the authenticated Principal whose authorized request won cancellation, independent of Chemistry/Biology, graph shape, model provider, or tool topology.

Decision:
- Persist the winning authenticated Cancellation Actor with the cancellation terminal.
- Keep it distinct from the Turn Initiator.
- Never overwrite it when a later idempotent cancellation observes the existing terminal.
- Keep it private to authorized internal audit in v1.

Validation/test required:
- Self-cancellation and peer-cancellation attribution.
- Concurrent requests from different authorized members preserve only the winning actor.
- Client payload cannot spoof the actor.
- Role/focus changes after closure do not rewrite either identity.
- Portal-facing schemas contain no actor field.

Review owner/date:
- Architecture grilling decision, 2026-07-15.
```

### Field Necessity Record: `cancel_requested_at`

```text
Field: cancel_requested_at
Status: dropped for v1

Q1 Named consumer:
- None under the confirmed immediate-closure contract.

Q2 Decision/action driven:
- None. Portal, recovery, authorization, and audit use the durable terminal result and its commit timestamp.

Q3 Why existing facts/trace are insufficient:
- They are sufficient. A successful cancellation request does not create a durable requested/cancelling phase; it commits the terminal immediately.
- HTTP arrival time before authorization/transaction success is not an authoritative cancellation fact.

Q4 Compatibility exposure and migration:
- Adding it would introduce an internal field whose meaning differs from the authoritative closure time and invite exposure through REST/SSE.
- V1 requires no migration/default because the field is omitted.

Q5 Cross-domain/topology stability:
- A request timestamp is domain-neutral, but its meaning depends on introducing an asynchronous cancellation-request lifecycle that this design explicitly rejects.

Decision:
- Do not persist cancel_requested_at in v1.
- Use the terminal commit timestamp for the accepted cancellation fact.

Validation/test required:
- Durable schema and event payload contain no cancel_requested_at.
- Metrics may measure HTTP/transaction latency from telemetry without promoting request time into product state.

Review owner/date:
- Architecture grilling decision, 2026-07-15.
```

### Field Necessity Record: cancellation source or free-text reason

```text
Field: cancellation source and free-text cancellation reason
Status: dropped for v1

Q1 Named consumer:
- None for the user-facing cancellation slice.

Q2 Decision/action driven:
- None. Authorization and closure do not branch on a user-entered explanation, and the user endpoint already establishes the semantic source.

Q3 Why existing facts/trace are insufficient:
- They are sufficient. The cancellation terminal identifies the action, the trusted actor identifies who performed it, and telemetry can describe cleanup/provider diagnostics.
- Free text would not be safe deterministic input for authorization, recovery, or outcome mapping.

Q4 Compatibility exposure and migration:
- The request remains empty and no reason/source is added to REST, SSE, snapshot/history, or the durable terminal contract.
- A later product need must separately define validation, privacy/retention, localization, and compatibility behavior.

Q5 Cross-domain/topology stability:
- A fixed user-cancellation source is already implicit in this endpoint, while free-text reason semantics would be ungoverned and unstable across domains and products.

Decision:
- Add neither a separate source field nor a free-text reason in v1.
- Reopen only for a named product, audit, or policy consumer with a new Field Necessity Record.

Validation/test required:
- Cancellation request schema rejects a body rather than silently accepting reason/actor metadata.
- Portal does not solicit or project a cancellation reason.

Review owner/date:
- Architecture grilling decision, 2026-07-15.
```

## Remaining field-necessity gate

No cancellation terminal payload field beyond the accepted event kind has blanket approval. Any new candidate must complete a Field Necessity Record before schema freeze; the actor, request timestamp, source/reason, response disposition, full-response outcome, and partial-output candidates now have explicit dispositions.

## Parent-architecture handoff

No further cancellation question remains in the parent L3 architecture interview. Exact wire spellings, cooperative interruption mechanics, and deployment choreography belong to the independently verifiable cancellation child slice.

## Evidence

- `research/user-turn-cancellation-evidence.md`
- `turn-terminal-outcome-catalog.md`
- `turn-execution-isolation.md`
