# State authority and legacy architecture evidence

## Resolved authority model

The owner accepted this invariant on 2026-07-15:

| Concern | Authority | Role of other representations |
|---|---|---|
| Product workflow facts | Agent Service workflow model | Session Events project and audit these facts; Agent execution state may read a versioned snapshot but cannot become authoritative. |
| Physical execution facts | Nexus/Lab | Agent Service stores a product-side projection correlated by stable identifiers. |
| UI history and audit | Append-only Session Events | Live delivery, cold snapshots, and replay must be semantically equivalent. |
| Agent working state | LangGraph execution state/checkpoint | Non-authoritative and scoped to Agent execution. |

Canonical wording: **entity-authoritative, event-projected progress**. The architecture is not a strict event-sourced aggregate.

## Original L1-L4 responsibilities

- L1 is protocol ingress/egress for HTTP, SSE, MQ, and timers; it should not own business state or call L3/L4 directly (`32_layer_L1.md:48-53,69-120`).
- L2 owns cross-turn session coordination, per-session serialization, persistence coordination, broadcast, ingress routing, reconciliation, and failure closure (`33_layer_L2.md:56-102,182-216`).
- L3 owns one-turn Agent reasoning and emits runtime events; the original boundary prohibits persistence ownership and cross-turn business state (`34_layer_L3.md:59-121,292-310`).
- L4 provides infrastructure adapters through protocols and dependency injection and should not decide workflow policy (`35_layer_L4.md:57-79,96-170`).

## Original invariants worth separating from topology

- A session is long-lived; a turn is a single input execution unit.
- The accurate property is **turn-scoped Agent execution**, not a stateless process or stateless turn.
- Turns for one session are serialized; different sessions can run concurrently.
- L3 receives a frozen invocation context; changes return through events and are visible on a later turn.
- Non-delta runtime events follow `apply -> append -> commit -> broadcast`; `text_delta` is the explicit non-persisted exception.
- PostgreSQL entities are current workflow facts; Session Events serve audit, UI replay, and recent conversation reconstruction.
- LangGraph checkpoints do not carry authoritative business state.

## Original-design assumptions that are not cross-domain invariants

- The Y-4 graph topology and TLC/CC/FP/RE specialist sequence encode Chemistry workflow shape.
- `TaskSpec` YAML extends tasks within a similar workflow shape but does not prove cross-domain extensibility.
- Memory is only a placeholder; there is no lifecycle, namespace, promotion, or deletion contract.
- MCP is described as a narrow read-only seam and does not define a governed, effectful tool contract.
- The historical suggestion that replacing `InMemorySaver` with `PostgresSaver` would add cross-invocation state understates authority, recovery, idempotency, and versioning consequences.

## Live drift from the declared boundary

- Live L3 `Runtime` imports persistence and session-layer code and receives `Persistence`; the no-persistence dependency rule is not mechanically enforced.
- Live event reducers carry workflow transition behavior that the L4 spec currently classifies too broadly as events/domain types.
- Current code reconstructs each turn from entity rows plus recent events, confirming entity-first rather than event-sourced behavior.

Key live evidence is linked from [Agent Service PR #150's current proposal](https://github.com/c12-ai/BIC-agent-service/blob/86145692054ad06a74c00ffa81fcbfbaf9f835c4/docs/agent-foundation-refactor-design.md#L97-L152) and the live L3 charter at [main](https://github.com/c12-ai/BIC-agent-service/blob/12a84f3238a952f00eb95b24c1943f8303041350/.trellis/spec/backend/L3/charter.md#L19-L35).
