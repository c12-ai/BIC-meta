# Claim-fencing evidence

Evidence baseline: BIC Agent Service live `main` at `12a84f3238a952f00eb95b24c1943f8303041350` plus current field deployment configuration.

## Current operational posture

- Field deployment runs one fixed Compose Agent Service container and one Uvicorn process; no replica count is configured.
- Field update uses `docker compose up -d`, so current production posture is approximately singleton rather than HA.
- queues and session workers are entirely process-local;
- Turn timeout is 900 seconds;
- shutdown ignores its requested 120-second grace and immediately cancels workers;
- written architecture specs anticipate rolling/SIGTERM overlap, but live code does not implement the described drain model.

Primary files:

- `ops/field/agent-service/docker-compose.yml`
- `ops/field/update.sh`
- `BIC-agent-service/Dockerfile`
- `app/session/orchestrator.py`
- `.trellis/spec/backend/L1/wiring-and-lifecycle.md`

## Why a fence appears when durable reclaim is introduced

The current singleton process does not have two durable claimants because it has no durable claim system. Once a queued/running Turn can be reclaimed, lease expiry does not prove that the former execution stopped. A stale worker can resume after:

- a slow LLM/query or event-loop stall;
- a DB/network partition that prevented lease renewal;
- old/new process overlap during deployment or shutdown;
- watchdog/operator recovery of a wedged Turn;
- delayed cooperative cancellation or thread-backed blocking work.

Row locking protects only the short claim transaction. Proposal uniqueness and terminal uniqueness prevent some duplicates, but do not select which claimant owns subsequent narration, event output, or the right to close the Turn.

## Minimal target

Store on the durable Turn row:

- `claim_generation BIGINT`;
- `lease_owner`;
- `lease_expires_at`;
- optionally `claimed_at` and `heartbeat_at` for operations.

Every claim/reclaim atomically increments `claim_generation`. L2 checks the current generation for:

- Proposal adjudication and Turn effect-slot closure;
- durable Agent-output/event persistence;
- Turn terminal CAS;
- user-visible live stream emission.

A stale claimant receives a typed internal `stale_claim` result and cannot write or broadcast. `claim_generation` is an internal fencing token, not a new business identity.

## Deliberately excluded from v1

- a `turn_attempts` table or aggregate;
- Attempt lifecycle Session Events;
- a Portal-visible attempt identifier;
- durable LangGraph/Agent checkpointing;
- treating internal model/tool retry as a new claim;
- querying historical claims as product data.

Per-claim trace spans and logs are sufficient until a named audit, cost-analysis, or mid-execution recovery requirement demonstrates the need for persisted claim history.

Fencing could be omitted only by making singleton, exclusive restart, and no automatic reclaim permanent operational constraints. That would conflict with automatic stuck-Turn recovery and future rolling/HA operation, so the row-level generation is the lower-cost boundary.
