# Turn terminal outcome catalog

Status: schema-discovery artifact. Architecture semantics and the explicitly accepted/dropped cancellation records below are decided; remaining candidate terminal fields, enum spellings, and storage shape are not frozen.

## Confirmed constraints

- Every admitted Turn reaches exactly one durable terminal closure.
- Turn terminal remains orthogonal to Proposal, Outbox Command, and external Task outcomes.
- The terminal representation stays small and compositional; it does not create one enum variant for every effect/response/failure combination.
- L2 owns the durable Turn Terminal Outcome and persistence closure. Foundation supplies a Foundation Execution Outcome but cannot declare durable closure.
- A schema field is added only when a named runtime, Portal, operations, audit, or compatibility consumer needs to distinguish cases and cannot derive the distinction safely.

## Starting hypothesis, not contract

The current discussion hypothesis is:

- a small terminal category such as completed, failed, timed out, or cancelled;
- a stable semantic reason when a consumer needs it;
- optional information about whether required user output was complete;
- trace correlation rather than raw exception persistence.

Names, values, requiredness, and storage shape remain open until the case catalog and consumer matrix are reviewed.

## Why `failure_stage` is not yet accepted

The live implementation defines seven topology-oriented stages and documents a 9 × 7 failure matrix, but `_classify` produces only a small subset and maps most errors to `runtime_invoke`. Values such as apply, append, emit, and drain are not reliably attached by the actual exception path. This creates several problems:

- one error can cross query, model, Proposal, persistence, and narration boundaries;
- package/graph refactoring changes topology labels without changing user or recovery semantics;
- retry/recovery should use durable state and semantic reason, not the stack location where an exception surfaced;
- metrics can usually attach component/operation attributes to traces without making them a persisted product contract.

Until a named consumer demonstrates otherwise, component/stage belongs in telemetry. A stable semantic reason is a better candidate for persisted discrimination.

## Case catalog

| Case | Effect slot at closure | Candidate Turn interpretation | Recovery before terminal | Named consumers to verify | Compatibility question |
|---|---|---|---|---|---|
| Foundation completes, no Proposal | open | normal completion | none | Portal, metrics | map to existing `turn_completed` |
| Proposal rejected and explained | open | normal completion | corrected candidate may occur before closure | Portal, audit | rejection event/message versus terminal |
| Proposal accepted, narration completes | closed | normal completion | command continues independently | Portal, audit | ordering of domain event and `turn_completed` |
| Model failure before accepted effect | open | failure candidate | reclaim only if Turn is not terminalized | Portal, operations | safe display key and existing `turn_failed` |
| Required Query fails or times out | open | handled completion or failure depends on query contract | governed fallback may continue | Domain Pack, Portal, metrics | fail-soft versus fail-loud behavior |
| Proposal adjudication infrastructure fails before commit | open | failure/timeout candidate | safe same-candidate retry may occur before closure | L2, operations | no business event may claim acceptance |
| Proposal accepted, post-commit narration fails | closed | unsuccessful Agent closure with committed effect | no second Proposal; command continues | Portal, operations | avoid displaying business action as failed |
| Turn deadline before accepted effect | open | timeout candidate | none after terminal | scheduler, Portal | existing timeout failure mapping |
| Turn deadline after accepted effect | closed | timeout candidate with committed effect | command continues | Portal, operations | preserve committed structured progress |
| Cancellation while queued | open | cancellation candidate | cancellation transaction immediately terminalizes; Foundation never invokes | Portal user-cancellation control, L2 | distinct cancelled terminal versus compatibility mapping |
| Cancellation while running before effect | open | cancellation candidate | cancel and Proposal acceptance use first-commit-wins; cancel-first immediately terminalizes and rejects later Proposal | Portal user-cancellation control, L2 | partial optimistic text behavior |
| Cancellation while running after effect | closed | cancellation candidate with committed effect | Proposal-first preserves command; cancellation immediately terminalizes and stops only later Agent work/output | Portal, operations | never imply command cancellation |
| Lease expiry / reclaim | unchanged | not terminal | new claim generation | scheduler, operations | internal telemetry only |
| Stale claimant returns | unchanged | not terminal and no output authority | reject stale write | operations | no Portal frame |
| Terminal persistence temporarily fails | unchanged | persistence closure has not happened | retry terminal CAS | L2, operations | no best-effort duplicate event |
| Admission validation/CAS rejects input | no Turn | not a terminal case | caller receives rejection | API/MQ producer | preserve HTTP/MQ semantics |

## Consumer-driven field test

For every proposed terminal field, complete a **Field Necessity Record** before schema freeze.

### Mandatory field-necessity questions

1. **Who consumes it?** Name the runtime component, Portal behavior, operations query/alert, auditor, or compatibility adapter. “Might be useful” is not a consumer.
2. **What different decision or action does it drive?** State the branch, recovery action, display choice, SLO calculation, authorization, or investigation step that changes because of the field.
3. **Why can existing durable facts or trace data not answer it safely?** Identify the information gap and why deriving it would be ambiguous, expensive, unstable, or impossible.
4. **Does it cross a compatibility boundary?** State whether it is internal-only, persisted but private, exposed through REST/SSE/snapshot/replay, or shared across repositories, including migration/default behavior.
5. **Will its meaning survive domain and topology changes?** Demonstrate that Chemistry/Biology, graph reshaping, component renaming, and framework upgrades do not silently change the field's semantics.

### Record template

```text
Field:
Status: proposed | accepted | dropped | telemetry-only | compatibility-only

Q1 Named consumer:
Evidence:

Q2 Decision/action driven:
Evidence:

Q3 Why existing facts/trace are insufficient:
Evidence:

Q4 Compatibility exposure and migration:
Evidence:

Q5 Cross-domain/topology stability:
Evidence:

Decision:
Validation/test required:
Review owner/date:
```

### Summary table

| Candidate field | Named consumer | Decision/action it drives | Why existing durable data or trace cannot answer | Compatibility exposure | Keep/drop |
|---|---|---|---|---|---|
| `turn_cancelled` event kind | Portal lifecycle/chat projection; SSE replay | unlock, non-error cancellation finalization, interrupted-step convergence | completed/failed cause incorrect UI semantics; snapshot alone lacks ordered Turn correlation | additive persisted Session Event/SSE/replay | accepted |
| cancelled partial-output snapshot | none after durable-only retention decision | none | persisted completed segments already define replayable output; unfinished deltas are deliberately discarded | would add DB/event/SSE payload | dropped for v1 |
| Cancellation Actor Principal reference | authorized security/incident review; internal audit query/export | distinguish self-cancellation from peer intervention and attribute the winning request | Turn Initiator, mutable membership, and expiring trace data cannot identify the durable winning actor | persisted internal-only; not Portal-facing | accepted internally; record in `turn-cancellation-catalog.md` |
| `cancel_requested_at` | none | none | terminal commit timestamp is sufficient under immediate closure | would add private/event ambiguity | dropped for v1; record in `turn-cancellation-catalog.md` |
| cancellation source/free-text reason | none | none | terminal kind, authenticated actor, and telemetry are sufficient | request/event field deliberately absent | dropped for v1; record in `turn-cancellation-catalog.md` |
| terminal category | TBD | TBD | TBD | TBD | open |
| semantic reason code | TBD | TBD | TBD | TBD | open |
| response completeness | TBD | TBD | TBD | TBD | open |
| failure stage/component | none yet | none yet | currently derivable/ambiguous in telemetry | currently exposed in `turn_failed` | likely telemetry-only |
| diagnostic/trace reference | TBD | TBD | TBD | internal by default | open |

### Completed example: `failure_stage`

```text
Field: failure_stage
Status: telemetry-only internally; compatibility-only as legacy SSE error_stage

Q1 Named consumer:
- Portal: none; its local event type omits the field.
- retry/recovery: none; they use exception/current workflow facts.
- metrics/alerts: none currently.
- developer CLI: prints it for diagnostics.

Q2 Decision/action driven:
- No production workflow, UI, retry, recovery, or alert branch changes today.

Q3 Why existing facts/trace are insufficient:
- They are sufficient for current diagnostic use. Structured component/operation trace attributes are more accurate and can evolve without contract migration.

Q4 Compatibility exposure and migration:
- Existing turn_failed JSON contains error_stage and SSE/replay preserve it opaquely.
- Keep producing a best-effort compatibility value during the internal refactor; do not copy it into the new authoritative Turn terminal row.

Q5 Cross-domain/topology stability:
- Not stable. Current runtime_invoke/apply/append/emit labels describe implementation topology, and the live classifier does not reliably produce most declared values.

Decision:
- Drop from the new durable terminal contract.
- Keep structured stage/component only in telemetry.
- Preserve legacy error_stage through the compatibility mapper until a separate wire-removal review.

Validation/test required:
- Portal compatibility contract still receives the expected legacy field.
- terminal schema contains no required failure_stage.
- telemetry captures component/operation for diagnostics.

Review owner/date:
- Architecture grilling decision, 2026-07-15.
```

### Completed record: cancelled partial-output snapshot

```text
Field: partial text/reasoning/tool-call snapshot on cancellation
Status: dropped for v1

Q1 Named consumer:
- None after the confirmed Portal rule discards the unfinished emit-only fragment and retains only completed persisted segments.

Q2 Decision/action driven:
- No v1 branch requires the unfinished fragment. turn_cancelled drives non-error finalization; existing done/result events reconstruct durable content.

Q3 Why existing facts/trace are insufficient:
- Existing persisted text_done, reasoning_done, and tool results are sufficient for the selected durable-only UX.
- Emit-only fragments are not authoritative replay data; trace capture cannot safely become user-visible response content.

Q4 Compatibility exposure and migration:
- Adding it would require a new internal persistence path plus turn_cancelled/SSE/replay payload and Portal handling.
- V1 instead removes the unfinished fragment consistently, so no migration/default is needed.

Q5 Cross-domain/topology stability:
- A generic partial text field appears domain-neutral, but its flush boundary and meaning depend on model/stream/tool topology. It is not stable without a separately designed output-draft contract.

Decision:
- Do not add partial text, reasoning draft, tool-call draft, response snapshot, or output accumulator solely for cancellation in v1.
- Reconsider only through a demand gate with a named UX consumer, durability/SLO target, cross-process fencing, write-volume budget, and replay contract.

Validation/test required:
- Live/replay/refresh/multi-tab projections retain identical completed segments.
- Active emit-only fragments disappear on turn_cancelled.
- No partial-output field exists in the Turn row or event payload.

Review owner/date:
- Architecture grilling decision, 2026-07-15.
```

### Completed record: `turn_cancelled` event kind

```text
Field: turn_cancelled event kind
Status: accepted

Q1 Named consumer:
- Portal SSE client and dispatcher.
- Portal shared turnRunning interlock, assistant bubble finalization, and thinking-timeline convergence.
- Session history/reconnect replay for live/replay equivalence across tabs.

Q2 Decision/action driven:
- Clear the shared chat lock for the exact Turn.
- Finalize partial output as user-cancelled rather than completed or failed.
- Converge an open reasoning/tool node as interrupted without calling failure-only workflow behavior such as onAnalysisFailed().

Q3 Why existing facts/trace are insufficient:
- turn_failed creates a failed bubble and may mark an awaiting-analysis trial failed.
- turn_completed presents interrupted work as normal completion.
- snapshot collab.turn_running can restore the coarse lock after hydration but cannot finalize the correlated assistant Turn or preserve ordered live/replay semantics.
- trace data is not a Portal projection contract.

Q4 Compatibility exposure and migration:
- Additive persisted Session Event exposed through SSE, history, and replay to Portal.
- Current Portal drops unregistered named SSE kinds, so hidden Portal support must deploy before backend emission and Stop enablement.
- This is the explicitly approved cancellation cross-repo slice; it is not required by core Chemistry migration stages.
- No BIC-shared-types change is required under current Agent-event ownership.

Q5 Cross-domain/topology stability:
- Stable. It means an authorized user durably stopped one identified Agent Turn, independent of Chemistry/Biology, graph shape, model provider, or tool topology.

Decision:
- Add one distinct persisted turn_cancelled terminal event.
- Do not reuse turn_failed or turn_completed.
- Do not infer acceptance of any additional reason, actor, response-completeness, or diagnostic field.

Validation/test required:
- SSE named-event registration and RuntimeEvent exhaustiveness.
- Live, history, reconnect, snapshot, and multi-tab convergence.
- turnRunning clears and the matching assistant bubble finalizes as cancelled.
- no failure bubble and no onAnalysisFailed() invocation.
- rollout test/gate for mixed Portal versions.

Review owner/date:
- Architecture grilling decision, 2026-07-15.
```

## Schema-freeze gate

The terminal schema freezes only after:

1. every case above has an explicit closure owner and failure-injection test;
2. current `turn_completed` / `turn_failed` Portal, snapshot, and replay consumers are inventoried;
3. each persisted field passes the consumer-driven field test;
4. raw exception, topology, and internal framework details are excluded from stable contracts;
5. Core Chemistry compatibility mapping is agreed without coordinated Portal/shared-type changes, while the explicitly approved cancellation event follows its separately staged Portal rollout.

## Evidence

- `research/terminal-field-consumer-evidence.md`
