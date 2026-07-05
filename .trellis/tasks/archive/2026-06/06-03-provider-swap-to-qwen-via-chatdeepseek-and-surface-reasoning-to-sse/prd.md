# Provider swap to Qwen via ChatDeepSeek and surface reasoning to SSE

## Goal

Swap the LLM provider and wrapper so reasoning content reaches chemists
end-to-end. Today `ChatOpenAI` strips `delta.reasoning_content` from
every chunk before LangGraph can emit a `ReasoningDeltaEvent`, so the
FE's already-wired `ThinkingSection` never receives content. Move to
DashScope (Aliyun) Qwen models accessed via
`langchain_deepseek.ChatDeepSeek`, which preserves `reasoning_content`
in `AIMessageChunk.additional_kwargs`. Extend the L3 translator and
orchestrator carve-outs so reasoning flows from LLM → SSE → FE for
every cc/re/plan agent path (narrate + react). Rip out all PPIO-era
code in the same change.

## REVISION 2026-06-03 (post-Phase-A)

Phase A wire validation surfaced a DashScope-server-side
incompatibility: `with_structured_output(...)` sets `tool_choice` to
force a function call, and DashScope rejects that with
`enable_thinking=True`:

```
400 InternalError.Algo.InvalidParameter: The tool_choice parameter does
not support being set to required or object in thinking mode
```

In parallel, Drake redesigned `plan_subgraph` to mirror cc/re — the
old `_propose_node` (structured-JSON output) is GONE. Plan now uses
`react_agent` + `narrate`, both on `chat_model.ainvoke(...)`. This
makes the structured-output incompatibility moot for cc/re/plan.

`chat_model_structured` IS still used by `user_admittance` and
`intent_detection` (fast-path classifiers) — but those nodes don't
want thinking anyway (latency-sensitive gates, TAG_NOSTREAM-tagged).
So `chat_model_structured` stays as-is: thinking off, structured-output
preserved.

The PRD's two-instance topology (`chat_model` + `chat_model_reasoning`)
collapses to ONE instance: `chat_model` with `enable_thinking=True`
always on, used by cc/re/plan. R5 (loosen `_NOSTREAM_NS_MARKERS`) is
also dropped — there's no `propose:` namespace anymore.

## What I already know

Verified earlier in this session (research/reasoning-event-investigation.md
from the archived task is the authoritative source — see Research
References):

- `langchain_openai.ChatOpenAI._convert_delta_to_message_chunk` only
  reads `id/role/content/function_call/tool_calls` — silently drops
  any non-OpenAI-spec field including `reasoning_content`. Module
  docstring at `langchain_openai/chat_models/base.py:1-12` calls this
  out explicitly and tells third-party-provider users to switch to
  provider-specific wrappers.
- Wire-confirmed: `ChatDeepSeek` pointed at DashScope OpenAI-compatible
  endpoint preserves Qwen `delta.reasoning_content` into
  `AIMessageChunk.additional_kwargs["reasoning_content"]` (streaming)
  and projects to `content_blocks` with canonical v1 shape
  `[{"type": "reasoning", ...}, {"type": "text", ...}]` (non-streaming).
- `qwen-plus` is a hybrid model: reasoning toggles per-call via
  `extra_body={"enable_thinking": True}`. Wire probe showed ~3× wall-
  clock cost vs non-thinking mode for the same prompt.
- FE side already wired end-to-end: `events.ts`, `sse-client.ts`,
  `event-dispatcher.ts`, `chatStore.ts`, `ThinkingSection.tsx` — zero
  FE work needed once reasoning reaches the runtime.
- Latent bug in `app/session/orchestrator.py:307-313`: only
  `TextDeltaEvent` bypasses persistence. `ReasoningDeltaEvent` and
  `NodeCompletedEvent` would fall through to `persist_event` →
  malformed `session_events` rows (I-E-E rule violation per
  `.trellis/spec/backend/L3/events.md`). Currently latent because no
  reasoning flows today; will fire as soon as this PR lands unless
  fixed in the same change.
- `_emitter.py:231-241` reads `block.get("thinking") or block.get("text")`
  — misses canonical v1 `block["reasoning"]` key (forward-compat gap).
- `plan_subgraph._propose_node` is muted today by `TAG_NOSTREAM` +
  `propose:` substring filter in `runtime.py:190-193` for the structured
  JSON output. The propose-time *reasoning* should pass through this
  filter even though the JSON tokens still must not.

## Locked decisions (from brainstorm session, 2026-06-03)

| # | Decision |
|---|---|
| Q1 | Scope: minimum + reasoning end-to-end + spec doc updates + latent `NodeCompletedEvent` carve-out fix |
| Q2 | Reasoning visibility: ALL paths in cc/re/plan — narrate + react. Original Q2.c said "+propose" but the propose node has since been retired from plan_subgraph (see REVISION block above); `user_admittance` / `intent_detection` stay structured-only (no reasoning by design). |
| Q3 | Model topology (REVISED): ONE `chat_model` instance, `qwen-plus` + `enable_thinking=True`, used by every cc/re/plan node. `chat_model_structured` unchanged (thinking off, for admittance/intent only). |
| Q4 | Acceptance: chemist sends a planning request → SSE stream contains `reasoning_delta` events → FE `ThinkingSection.tsx` renders content → narrate text follows |
| Q5 | Cleanup: rip all PPIO-era code (`pa/gpt-5-*` model IDs, PPIO base URL references, any `ChatOpenAI` imports) in this PR — no follow-up cleanup task |
| Q6 | Sequencing: single atomic PR (scaffold + emitter + orchestrator + node wiring + PPIO purge + specs all together). AC depends on the whole stack working together. |

### Q2.c risk acknowledged

Including the react loop means cc/re/plan will emit many short
reasoning bursts as tools fire — may feel chaotic in the FE thinking
panel. After revision, there's NO per-node opt-out instance — every
cc/re/plan call has thinking on. Fallback path if chemist feedback
hates it: a follow-up task adds back a `chat_model_fast` (no thinking)
instance and rewires the react paths to it. Not in scope here.

## Assumptions (to validate during implement)

- DashScope `qwen-plus` accepts the same OpenAI-style request shape we
  send today (messages array, tools schema, response_format for
  structured output). No request-format adapter needed.
- DashScope structured-output path supports the same
  `response_format=<PydanticModel>` pattern langchain uses, via
  `ChatDeepSeek.with_structured_output`. Needs wire validation before
  the `chat_model_structured` instance is wired.
- `qwen-plus` tool-calling semantics match OpenAI tool-calling shape
  closely enough that `create_agent(...)` in cc/re react loops works
  without changes. Needs wire validation.
- DashScope `qwen-max` is the right choice for `HEAVY_MODEL`. Drake
  picked this in `.env.example`; confirm during integration testing
  that nothing in our code actually reads `HEAVY_MODEL` today (per
  research finding "HEAVY_MODEL is configured but never used").

## Requirements

### Code changes

- R1 (REVISED). Replace `ChatOpenAI` with `ChatDeepSeek` in
  `app/infrastructure/llm_client.py`. Construct TWO instances (down
  from three in the original PRD):
  - `chat_model` — `qwen-plus`, `streaming=True`,
    `extra_body={"enable_thinking": True}` (thinking ON, used by every
    cc/re/plan node)
  - `chat_model_structured` — `qwen-plus`, `streaming=False`, NO
    `enable_thinking` (used only by `user_admittance` and
    `intent_detection`; `.with_structured_output(...)` is applied at
    the call sites; A1 wire-failure proves we can't combine
    `with_structured_output` + `enable_thinking` against DashScope)
- R2. Add `langchain-deepseek` to `pyproject.toml` deps. Remove
  `langchain-openai` if no other code path depends on it (verify with
  grep). Note: install already done by Phase A; removal still pending.
- R3 (REVISED). Wire all cc/re/plan nodes to `chat_model`. No node
  rewiring beyond what's already there — every cc/re/plan node ALREADY
  calls `llm.chat_model` post-redesign. The change is invisible at the
  node level: turning `enable_thinking=True` on the single
  `chat_model` instance gives every node reasoning, automatically.
  Verify by grep that:
  - `plan_subgraph.py` `_react_agent_node` and `_narrate_node` →
    `llm.chat_model`
  - `cc.py` `_react_agent_node` and `_narrate_node` → `llm.chat_model`
  - `re.py` `_react_agent_node` and `_narrate_node` → `llm.chat_model`
  - `user_admittance.py` and `intent_detection.py` → `llm.chat_model_structured`
    (UNCHANGED — these stay structured-only)
- R4. Extend `_emitter.py:iter_text_events_from_chunk`:
  - Add a path that reads `chunk.additional_kwargs["reasoning_content"]`
    (string) and emits `ReasoningDeltaEvent(delta=...)` — the streaming
    hot path
  - Add `block.get("reasoning")` to the existing block-fallback chain at
    `_emitter.py:234` (forward-compat for canonical v1 shape)
- ~~R5~~ (DROPPED). The `_NOSTREAM_NS_MARKERS` filter does NOT need
  loosening. After the plan_subgraph redesign there's no `propose:`
  namespace and no structured-output streaming on cc/re/plan paths;
  the existing filter (for `user_admittance:` and `intent_detection:`
  namespaces) stays untouched and correct.
- R6 (REVISED — widened to all 5 emit-only kinds). Orchestrator carve-
  out fix in `app/session/orchestrator.py:307-313`: change the
  isinstance check from `(TextDeltaEvent,)` to the full I-E-E
  emit-only set. Per
  `.trellis/spec/BIC-agent-service/backend/L3/events.md` that set is:
  - `TextDeltaEvent` (already carved out)
  - `ReasoningDeltaEvent` (must add for this PR's primary goal)
  - `NodeCompletedEvent` (must add — latent bug)
  - `NodeStartedEvent` (must add — latent bug)
  - `ToolCallDeltaEvent` (must add — latent bug)
  All five emit with `session_seq=None`, skip `persist_event`. Aligns
  the orchestrator with the spec's full I-E-E rule, not just the
  three originally flagged.
- R7. Rip all PPIO-era code:
  - Remove `pa/gpt-5-mini` / `pa/gpt-5.2` references everywhere
  - Remove `api.ppio.com` URL references
  - Remove `langchain_openai.ChatOpenAI` imports
  - `.env.example` and `.env` already done
  - Update `app/core/config.py` if model defaults are hard-coded anywhere
  - Update `app/core/lifespan.py`: `provider="ppio"` literal → `"dashscope"`
  - Update `app/main.py` doc string PPIO mention
  - Update `app/runtime/middleware/llm_error_handling.py` docstring PPIO mention

### Spec changes (Rule 10 — contract changes require spec updates)

- R8. Update `.trellis/spec/backend/L3/runtime.md` §6 (translator
  contract) to document the new `additional_kwargs["reasoning_content"]`
  source path alongside the existing block-shape path.
- R9. Update `.trellis/spec/backend/L3/events.md` I-E-E rule section to
  confirm `NodeCompletedEvent` membership and document the orchestrator
  carve-out invariant.
- R10. Add a new spec section (location TBD during implement —
  candidates: `.trellis/spec/backend/L4/llm_client.md` or
  `.trellis/spec/backend/L4/providers.md`) capturing:
  - Why DashScope+ChatDeepSeek (the `ChatOpenAI` field-drop defect we
    discovered) — so the next person doesn't try to "simplify" by
    reverting
  - The two-instance topology and which nodes use which
  - `enable_thinking` toggle semantics

## Acceptance Criteria

- [ ] **AC1 (primary E2E)**: Chemist sends a planning request via the
  chat surface → SSE stream contains at least one `reasoning_delta`
  event → FE `ThinkingSection.tsx` renders content above the message
  bubble → narrate text follows in the bubble. Validated by:
  - **New** Playwright spec at
    `BIC-agent-portal/tests/reasoning-streaming.spec.ts` (NOT folded
    into an existing spec) that asserts `event: reasoning_delta` frames
    arrive before the first narrate text token. Naming the file after
    the contract makes it discoverable for future contract changes.
  - Manual smoke run captured in research/manual-smoke-trace.md
- [ ] **AC2 (per-path reasoning — REVISED)**: For each of
  `plan_subgraph.react_agent`, `plan_subgraph.narrate`,
  `cc._react_agent`, `cc._narrate`, `re._react_agent`, `re._narrate` —
  a wire-level capture shows `reasoning_delta` events emitted from
  that node namespace. (Original PRD listed `plan_subgraph.propose`;
  that node no longer exists after the redesign.)
- [ ] **AC3 (no JSON leak — REVISED)**: `user_admittance` and
  `intent_detection` (which still use `chat_model_structured.with_
  structured_output(...)`) continue to emit ZERO SSE frames to the
  chemist (structured JSON stays muted by `streaming=False` +
  `TAG_NOSTREAM` + the existing `_NOSTREAM_NS_MARKERS` filter).
  Validated by inspecting an SSE capture during a hello/intent gate
  turn — no `text_delta` and no `reasoning_delta` from
  `user_admittance:` or `intent_detection:` namespaces.
- [ ] **AC4 (orchestrator carve-out — WIDENED)**: Unit test asserts
  that all 5 emit-only event kinds — `TextDeltaEvent`,
  `ReasoningDeltaEvent`, `NodeCompletedEvent`, `NodeStartedEvent`,
  `ToolCallDeltaEvent` — flowing through `Orchestrator._run_turn` do
  NOT call `persist_event` and emit with `session_seq=None`. One
  table-driven parametrize covers all five. Mirrors and supersedes the
  existing single-case `TextDeltaEvent` test.
- [ ] **AC5 (PPIO purge)**: `rg -i "ppio|pa/gpt-5|api\.ppio" app/` returns
  nothing. `rg "ChatOpenAI|langchain_openai" app/` returns nothing.
- [ ] **AC6 (spec parity)**: Specs R8/R9/R10 land in the same PR. Code
  reviewer can read the spec and predict the code behavior.

## Definition of Done

- All existing BE unit + scenario tests pass (no regression from the
  provider swap)
- Existing FE Playwright suite passes (`/Users/drakezhou/Development/BIC/BIC-agent-portal/tests/`)
- New AC1 Playwright test added and passes
- New AC4 unit test added and passes
- `mypy app/` and `ruff check app/` green
- Spec docs R8/R9/R10 updated in the same commit

## Out of Scope

- Migration tooling for old PPIO session data (none expected; sessions
  are model-agnostic)
- FE changes to `ThinkingSection.tsx` styling/behavior (already wired)
- Cost/latency optimization beyond using `chat_model` (no thinking) on
  cc/re react-loop tool decisions if Q2.c noise becomes a problem —
  that fallback is a separate task if needed
- Adding a `HEAVY_MODEL` code path. Research showed it's configured but
  unused; leaving as-is for a future task that actually needs heavy.
- Adding tests for DashScope provider availability/health checks
- Per-user model selection / model routing

## Technical Approach

### Architecture (post-PR)

```
.env: BASE_URL, API_KEY (DashScope), DEFAULT_MODEL=qwen-plus, ...
      │
      ▼
LLMClient (app/infrastructure/llm_client.py)
  ├── chat_model              ChatDeepSeek(qwen-plus, streaming)
  ├── chat_model_reasoning    ChatDeepSeek(qwen-plus, streaming,
  │                                        extra_body={enable_thinking: True})
  └── chat_model_structured   ChatDeepSeek(qwen-plus, non-streaming,
                                           with_structured_output(...))
      │
      ▼
Subgraphs (cc / re / plan)
  All narrate/propose/react nodes → chat_model_reasoning
      │
      ▼ AIMessageChunk(additional_kwargs={"reasoning_content": "..."})
      │
runtime.py outer translator (astream stream_mode=["messages","custom"])
  ├── _NOSTREAM_NS_MARKERS — propose:JSON-text suppressed; propose:reasoning passes
  └── _emitter.iter_text_events_from_chunk
      ├── chunk.additional_kwargs["reasoning_content"] → ReasoningDeltaEvent
      ├── chunk.content blocks {"type":"reasoning"|"thinking"|"text"} → ReasoningDeltaEvent
      └── chunk.content plain text → TextDeltaEvent
      │
      ▼
Orchestrator._run_turn (app/session/orchestrator.py)
  EMIT_ONLY = (TextDelta, ReasoningDelta, NodeCompleted)
  if isinstance(event, EMIT_ONLY): emit(session_seq=None); continue
  else: seq = persist(); emit(session_seq=seq)
      │
      ▼ SSE encoder (sse.py:107-117)
      omits `id:` line for session_seq=None
      │
      ▼ FE (already wired)
      events.ts → sse-client.ts → event-dispatcher.ts → chatStore.ts
        → ThinkingSection.tsx (reasoning_delta coalesced into thinkingTimeline)
        → message bubble (text_delta)
```

### Critical implementation order

The dependency chain matters — getting order wrong wedges intermediate
states:

1. Add `langchain-deepseek` dep + verify it imports
2. Build `LLMClient` two-instance topology behind a feature flag OR in
   a single atomic commit — DO NOT half-swap (one node on
   `chat_model_reasoning`, others on `chat_model`) because the FE will
   see a broken thinking section on some turns but not others
3. Extend `_emitter` to handle `additional_kwargs["reasoning_content"]`
   — this MUST land before any node calls `chat_model_reasoning`,
   otherwise reasoning silently disappears at the translator
4. Fix orchestrator carve-out (R6) — MUST land before the first
   `ReasoningDeltaEvent` flows, otherwise we get malformed
   `session_events` rows that may persist after the PR
5. Loosen `_NOSTREAM_NS_MARKERS` (R5) — only after propose reasoning is
   verifiably working in dev; risk of accidentally unmuting JSON
6. Rip PPIO code (R7) — last, after E2E validation passes

### Validation harness

The existing `scripts/run_demo_e2e.py` and Playwright suite should both
go green. Beyond that, this PR adds:

- A scenario script that captures raw SSE frames for a planning turn and
  asserts the `reasoning_delta` events arrive in the expected order
- A unit test for the new orchestrator carve-out

## Decision (ADR-lite)

**Context**: Today's `pa/gpt-5-mini` via PPIO + `ChatOpenAI` cannot
surface reasoning. Wire probes proved (a) PPIO's `pa/gpt-5-mini` does
not emit reasoning at all regardless of `reasoning_effort`, and (b)
even when a reasoning-capable model is used (e.g., `deepseek/deepseek-r1`
via PPIO), `ChatOpenAI` strips `delta.reasoning_content` before
LangGraph sees it. FE has been wired for `reasoning_delta` for some
time but receives nothing.

**Decision**: Move to DashScope (Aliyun) Qwen models accessed via
`langchain_deepseek.ChatDeepSeek`. `qwen-plus` is the default (hybrid;
per-call `enable_thinking` toggle). Two streaming `LLMClient`
instances: one with thinking on (`chat_model_reasoning`), one without
(`chat_model`) — kept around so we can fall back per-node if noise from
react-loop reasoning is too high. All cc/re/plan nodes initially use
`chat_model_reasoning` to validate Q2.c (all paths emit reasoning).
Translator + orchestrator + namespace filter extended in the same PR
so reasoning flows end-to-end and no malformed event rows can be
persisted.

**Consequences**:
- Latency ↑ on every LLM call (Qwen thinking ≈ 3× wall-clock for the
  same prompt). Mitigation: fall back to `chat_model` per node if
  chemist feedback dings react-loop noise.
- DashScope provider lock-in (was PPIO lock-in before). Mitigation:
  config-only swap if we ever move again.
- Removes our `HEAVY_MODEL` future option implicitly (it was always
  unused). Re-enabling in a future task requires re-introducing a code
  path; trivially done.
- One spec gap closed: `NodeCompletedEvent` carve-out has been a
  latent bug since I-E-E was widened in ticket-30; the fix lands here
  even though only `ReasoningDeltaEvent` is functionally needed.

## Open Questions

(None — all six brainstorm questions resolved. PRD frozen 2026-06-03.)

## Research References

- `.trellis/tasks/archive/2026-06/06-03-tlc-image-s3-persistence/research/reasoning-event-investigation.md`
  — full per-agent / model / pipeline / LangChain v1.3 / gap analysis
  from the original investigation that led to this task
- `.trellis/tasks/archive/2026-06/06-03-tlc-image-s3-persistence/research/code-excerpts.md`
  — verbatim code excerpts (file:line refs) for every claim in the
  investigation
- `research/qwen-wrapper-probe.md` — DashScope qwen-plus wire probe +
  ChatOpenAI vs ChatDeepSeek wrapper comparison (S1/S2/S3)
- `research/ppio-deepseek-r1-probe.md` — PPIO probes A–F: proves
  `pa/gpt-5-mini` emits no reasoning, `deepseek/deepseek-r1` does, and
  PPIO uses the `delta.reasoning_content` convention

## Technical Notes

- `BIC-agent-service/.env.example` already updated with the new LLM block
- `BIC-agent-service/.env` already has `API_KEY` = DashScope key (Drake
  rotated/swapped; if the key in the chat transcript hasn't been rotated
  yet, rotate before starting implement)
- DashScope OpenAI-compatible endpoint:
  `https://dashscope.aliyuncs.com/compatible-mode/v1`
- DashScope deep-thinking docs:
  `https://help.aliyun.com/zh/model-studio/deep-thinking`
- LangChain v1.4 canonical reasoning content block shape lives in
  `langchain_core/messages/content.py:456-492`
  (`ReasoningContentBlock` TypedDict)
- DeepSeek-style `reasoning_content` normalization helper is at
  `langchain_core/messages/base.py:24-44`
  (`_extract_reasoning_from_additional_kwargs`)
