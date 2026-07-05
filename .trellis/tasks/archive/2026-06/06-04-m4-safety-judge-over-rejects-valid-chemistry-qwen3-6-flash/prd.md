# M4 — safety-judge over-rejects valid chemistry (qwen3.6-flash)

Status: planning

## Background

M4 is one of five mechanisms identified in earlier research on broken FE tests
and broken manual chat. Quoting that research summary verbatim:

> **M4 — Safety judge over-rejects valid chemistry.** When you type a message
> like "Draft a CC Spec for me" (CC = column chromatography, on-topic), the
> Qwen "is this message safe and on-topic?" judge says reject. The chemist
> sees "Request rejected" in chat. Affects: manual testing today.

The safety judge in question is the `user_admittance` node at
`app/runtime/graphs/nodes/user_admittance.py`. It runs in parallel with
`intent_detection` from START on every USER_MESSAGE turn and produces
structured output `{verdict: pass|reject, reason, user_facing_message}`.
The judge LLM is `qwen3.6-flash-2026-04-16`. The `pa/gpt-5-mini` baseline
admits the same messages that `qwen3.6-flash` rejects, so the issue is
judge accuracy, not the surrounding graph.

This task is intentionally split from the active M5 loader task. M5 is
fixing a different mechanism (loader / state hydration); M4 is fixing
the admittance judge. They share no files and should not be entangled in
one change set.

## Canonical Contract — Do Not Re-Litigate

This section is locked. Any future implementor reading this PRD: do not
re-architect the safety system. Fix the judge's accuracy, not the topology.

- `user_admittance` owns content-safety + capability-scope rejection. It is
  THE sole content-safety boundary at turn entry.
- `intent_detection` is a routing classifier (Execute vs Query), NOT a
  safety guard.
- `GuardrailMiddleware` gates ONLY the dangerous L4 submit
  (`submit_l4_execution`) on phase-state preconditions (params confirmed +
  validated), NOT content safety.
- Post-admit subgraphs (cc / re specialists, planner, query_agent) treat
  admitted messages as legitimate. They do NOT and MUST NOT perform a
  second content-safety check.
- This architecture is correct. Do not add redundant safety checks
  downstream. Do not remove `user_admittance` to "simplify." Fix the
  judge's accuracy, not the topology.

## Scope — Three Phases

### Phase 1 — Instrument (zero behavior change)

Add observability so the next decision is data-driven. Drake currently
cannot decide between prompt tuning / model swap / scope narrowing
without seeing real `(user_text, verdict, reason, user_facing_message)`
tuples in one place.

**What already exists** (verified by code reading 2026-06-04):

- `AdmittanceRejectedEvent` (`runtime_emitted.py:292-309`) already carries
  `reason` + `user_facing_message` to `session_events` for analytics.
- `TextDoneEvent` (`admittance_reject.py:32`) already carries the refusal
  text to the chemist via SSE.
- `NodeCompletedEvent.decision` (`user_admittance.py:117-121`) already
  carries `{admitted, verdict, reason}` to the runtime event stream.

**What is missing**: there is no single log line tying `user_text` (the
input) to `verdict.reason` + `verdict.user_facing_message` (the output)
for grep-based offline analysis. Phase 2 needs that tuple.

Concrete edits:

- In `user_admittance.py` at line ~113 (post-verdict, pre-emit), add a
  conditional `logger.info` that fires **only when** `verdict.verdict ==
  "reject"`. Use the **structured-kwargs** form:

  ```python
  if verdict.verdict == "reject":
      logger.info(
          "admittance_rejected",
          extra={
              "user_text": user_text,
              "reason": verdict.reason,
              "user_facing_message": verdict.user_facing_message,
          },
      )
  ```

  Rationale: `"admittance_rejected"` is the grep anchor for Phase 2;
  the `extra` dict surfaces cleanly when a JSON log formatter is added
  later, and the message stays human-readable in the meantime.
- Add `import logging` + `logger = logging.getLogger(__name__)` at the
  top of the module (the file does not currently import `logging`).

Do NOT extend `NodeCompletedEvent.decision` with `user_facing_message` —
the data is already in `AdmittanceRejectedEvent` for the reject case;
adding a third copy would be duplication. (Removed from earlier draft.)

Expected diff size: ~3-4 LOC total. No spec change (pure logging).
No event schema change. No Pydantic model change.

**PII boundary note**: `user_text` in `logger.info` is chemist chat
content. Acceptable for local dev (where Phase 2 collection happens).
If M4 ever ships to a prod-style log target, revisit: hash the text,
log a length-bucket, or skip the text entirely. Out of scope for this
task; flagged so the next reader doesn't roll Phase 1 to prod
unthinkingly.

### Phase 2 — Collect

Run normal dev for a few days. Grep agent-service logs for the
admittance log lines where `verdict=reject`. Goal: collect at least 5
real `(user_text, reason, user_facing_message)` tuples from live usage.
Drake's manual test today ("Draft a CC Spec for me") is sample #1.

### Phase 3 — Decide (one of)

Pick exactly one based on the collected data. Do NOT commit to an option
upfront. Document the chosen option and the reasoning back in this PRD
once the data is in hand.

- **3a. Tune prompt.** Edit `_ADMITTANCE_SYSTEM_PROMPT` at
  `user_admittance.py:36-52`. Soften "off-topic" criteria, add an
  explicit "default to PASS when in doubt; only REJECT on clear
  content-policy violations," and add Chinese-language chemistry
  examples (CC / RE / spec / 柱层析 / 重结晶 etc.). Free, low-risk,
  fastest.
- **3b. Swap judge model.** Use `qwen3.6-plus` or a different provider
  just for admittance. Higher cost, higher precision. Requires LLM
  client config change.
- **3c. Narrow judge scope.** Remove the "off-topic capacity" reject
  branch from the prompt entirely. Keep content-policy reject only.
  Let planner / query_agent gracefully decline off-topic instead.
  Narrower judge → fewer false positives, but slight risk of off-topic
  messages burning a planner LLM call.

## Out of Scope

- Removing `user_admittance` entirely (would create a real
  content-policy gap; contract is canonical).
- Touching `intent_detection` (it is a classifier, not a guard).
- Changing `GuardrailMiddleware` scope (it stays at the L4 submit
  boundary).
- Adding any second safety check inside cc / re / planner / query_agent
  subgraphs.
- Changing graph topology or fan-in semantics in `route_after_admit`.

## Acceptance Criteria

- [ ] Phase 1: `user_admittance.py` logs the
      `(user_text, reason, user_facing_message)` tuple via `logger.info`
      **only when** `verdict.verdict == "reject"`. Pass-case observability
      stays on the existing `NodeCompletedEvent.decision` emission
      (`{admitted, verdict, reason}` — already wired).
- [ ] Phase 2: At least 5 real `verdict=reject` samples captured from
      live dev usage with full payload.
- [ ] Phase 3: Decision (3a / 3b / 3c) recorded in this PRD with
      reasoning grounded in the collected data.
- [ ] Post-fix: "Draft a CC Spec for me" passes admit on
      `qwen3.6-flash`.
- [ ] Post-fix: "起草一个 CC Spec" passes admit on `qwen3.6-flash`.
- [ ] Existing E2E specs in `BIC-agent-portal/tests` still pass.

## Spec edits (Rule 10)

- `.trellis/spec/backend/L3/graphs.md §1.3` — review and, if needed,
  clarify the canonical contract: `user_admittance` is the sole
  content-safety boundary at turn entry; post-admit subgraphs trust
  admitted messages. May already be implicit; verify during impl and
  only edit if there is a gap.
