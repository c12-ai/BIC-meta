# Current input-admission evidence

Evidence baseline: BIC Agent Service live `main` at `12a84f3238a952f00eb95b24c1943f8303041350`.

## Common queue behavior

- `turn_id` is generated when a `TurnInput` object is constructed.
- `submit_turn` performs `put_nowait` into an in-process per-session `asyncio.Queue(maxsize=50)`.
- Worker claim is an in-memory `queue.get`; shutdown cancels workers without durably draining queued inputs.
- There is no Turn work-item row, claim lease, admission uniqueness constraint, or terminal uniqueness constraint.
- `TurnRootSpan` is observability metadata and cannot recover queued work.
- The schema comment requires exactly one kind-matching payload, but no validator enforces it.

Primary code:

- `app/data/turn_schemas.py:110-132`
- `app/session/worker.py:25-51`
- `app/session/orchestrator.py:271-348`
- `app/data/models.py:119-164`

## Per-input behavior

| Input | Durable work before in-memory enqueue | Current acknowledgement and crash behavior |
|---|---|---|
| User message | Constructs Turn first, then applies/appends `UserMessageSubmittedEvent`; broadcast occurs before enqueue. | HTTP 202 waits for queue insertion, but a full queue can return 429 after the message event already committed. A retry creates a new event and Turn because no request idempotency key exists. Crash after event commit or enqueue can leave a durable message without recoverable Turn execution. |
| Form confirmation | Decision CAS, event reduction, and event append commit before enqueue. | Broadcast failure is swallowed. Queue insertion is bounded-retried and failure can be swallowed while HTTP still returns 202. A confirmed form can therefore have no follow-up Turn. Standard `decision_id` duplicates collapse through CAS; user-initiated confirmation without one may mint distinct decisions. |
| Decision response | Decision resolution and bypass event commit before `_submit_follow_up` constructs a Turn. | Queue failure can be swallowed while HTTP returns 202. Startup reconciliation may recreate follow-up work, but with a new `turn_id`; business transition identity and Turn identity are not atomic. |
| Decision expiry | Production scheduler resolves expiry first, then constructs `DECISION_RESPONSE(REJECT)` with source `USER`. | The declared `DECISION_EXPIRED` / scheduler input is not used in production. Recovery repeats the response-shaped behavior. This is contract drift to correct explicitly, not preserve accidentally. |
| Task terminal / MQ | Trial terminal or TLC-round fact update commits, then a progress event commits separately, then `TASK_TERMINAL` is constructed/enqueued. | RabbitMQ ACK occurs after in-memory queue insertion. Crash after ACK can still lose the Turn. Redelivery before ACK can create another Turn; some entity updates resist regression, but admission identity is not deduplicated. Non-terminal TLC round recovery has additional gaps. |

Ordinary non-terminal task progress updates do not create a Turn.

Primary code:

- `app/api/routers/sessions.py`
- `app/session/service.py`
- `app/session/fast_path_handlers.py`
- `app/session/event_ingress.py`
- `app/session/reconciler.py`
- `app/scheduler/decision_expiry.py`
- `app/mq/consumer.py`
- `app/infrastructure/mq_client.py`

## Compatibility-preserving target

The minimal correction is internal: persist the existing normalized Turn Input and `turn_id` atomically with each accepted input fact/event transaction, and make PostgreSQL the work-claim authority. Existing HTTP 202 and MQ wire contracts need not change.

- HTTP acknowledges after PostgreSQL admission commit, not in-memory queue insertion.
- MQ ACK hands responsibility to PostgreSQL only after admission commit.
- `asyncio.Queue` may remain as a low-latency wake-up hint, never as correctness authority.
- startup and periodic polling claim queued or safely reclaimable work.
- per-session admission order is durable and only one Turn executes per session.
- terminal row update and the compatible terminal Session Event commit together.

## Source deduplication limits

- Form confirmation and decision response can use decision identity and action as natural source keys.
- Expiry can use decision identity plus expiry action after its contract is corrected.
- Task terminal needs trial/attempt identity plus a stable terminal generation.
- TLC round dedupe requires a stable Lab event or round identifier; the current ingress contract does not yet prove one.
- User-message Portal requests carry no request idempotency key. Identical messages must remain distinct in v1; durable admission closes server-side loss gaps but cannot claim exactly-once behavior for ambiguous client retries without an optional future client key.
