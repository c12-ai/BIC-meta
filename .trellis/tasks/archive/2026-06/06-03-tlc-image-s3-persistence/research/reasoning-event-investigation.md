# Research: ReasoningEvent emission across CC / RE / Plan agents

- **Query**: Do the CC, RE, and Plan subgraphs emit `ReasoningDeltaEvent`? Does the underlying LLM (PPIO `pa/gpt-5-mini`) actually emit reasoning blocks at all? If reasoning IS produced but not propagated, where is it dropped?
- **Scope**: mixed (internal code + external provider behavior + LangChain v1.3 reference)
- **Date**: 2026-06-03

---

## Section 1 — Per-agent findings

### Shared finding (applies to all three agents)

All three subgraphs route LLM token streaming through the **same outer translator**: `Runtime.invoke` consumes `astream(stream_mode=["messages","custom"], subgraphs=True)` and dispatches every `BaseMessage` on the `messages` channel through `iter_events_from_message` → `iter_text_events_from_chunk`. That helper IS already wired to emit `ReasoningDeltaEvent` when an `AIMessageChunk.content` list-of-blocks contains `{"type": "thinking"}` (Anthropic) or `{"type": "reasoning"}` (OpenAI Responses) blocks.

The agent graphs themselves are **agnostic** — they don't directly emit `ReasoningDeltaEvent`. The decision of "reasoning vs text" happens entirely inside the translator based on what the LLM wrapper hands back on the `messages` channel.

So the per-agent verdict is the SAME for all three: reasoning **would** surface if the wrapper produced reasoning blocks. The wrapper currently does NOT (see Section 2).

### CC subgraph — `app/runtime/graphs/specialists/cc.py`

- Subgraph builder: `build_cc_subgraph` (cc.py:321-508)
- React loop LLM call: `_react_agent_node` uses `create_agent(model=llm.chat_model, …)` then `agent.ainvoke(state, context=runtime.context)` (cc.py:419-446). Note: `agent.ainvoke` — NOT `astream` — but LangGraph's outer `astream(subgraphs=True)` captures the nested model's chunked emissions through the `messages` channel (verified by the inline comments at cc.py:385-417 referencing the `tests/fixtures/streaming/README.md` design_exp trace).
- Narrate LLM call: `_narrate_node` uses `await llm.chat_model.ainvoke([system_msg, *state.messages])` (cc.py:348-383). Same pattern — `ainvoke` but LangGraph's `messages` channel callback handler captures the inner `AIMessageChunk` stream.
- **No `reasoning=`, `thinking=`, `extra_body=`, or `reasoning_effort=` parameters anywhere in this file.** No call to `bind`/`with_config` that enables reasoning.
- Reasoning emission today: **none** (because the wrapper drops it — see Section 2).

### RE subgraph — `app/runtime/graphs/specialists/re.py`

Structurally a 1:1 mirror of CC (declared verbatim in the file docstring re.py:25-28).

- Subgraph builder: `build_re_subgraph` (re.py:284-391)
- React loop LLM call: `_react_agent_node` (re.py:331-353). Same `create_agent(model=llm.chat_model, …)` pattern.
- Narrate LLM call: `_narrate_node` (re.py:311-329). Same `llm.chat_model.ainvoke(...)` pattern.
- **No reasoning-specific config**, same as CC.
- Reasoning emission today: **none**, same reason as CC.

### Plan subgraph — `app/runtime/graphs/nodes/plan_subgraph.py`

- Subgraph builder: `build_plan_subgraph` (plan_subgraph.py:179-484)
- Propose LLM call: `_propose_node` uses `create_agent(model=llm.chat_model_structured, tools=[], response_format=PlannerOutput, …)` and ainvokes it with `config={"tags": [TAG_NOSTREAM]}` (plan_subgraph.py:199-262). **Reasoning would never surface here even if the model produced it** — the propose pass is deliberately tagged `TAG_NOSTREAM` and runs on the non-streaming sibling `chat_model_structured` (built with `streaming=False`) so the structured-output JSON does not leak to the chemist's stream. The outer translator at `runtime.py:190-193` ALSO substring-filters the namespace `propose:` from messages-channel emissions (`_NOSTREAM_NS_MARKERS`). So even Anthropic-style `thinking` blocks here would be dropped.
- Narrate LLM call: `_narrate_node` uses `await llm.chat_model.ainvoke([system_msg, *state.messages])` (plan_subgraph.py:407-462). Same `ainvoke`-on-streaming-model-via-LangGraph-callback pattern as CC/RE narrate.
- **No reasoning-specific config.**
- Reasoning emission today: **none** on propose path (by design — would also need to be allowed through `_NOSTREAM_NS_MARKERS` filter), **none** on narrate path (because the wrapper drops it).

---

## Section 2 — Model + provider

### Configuration (verified from `.env` and `app/core/config.py`)

| Setting | Value |
|---|---|
| `BASE_URL` | `https://api.ppio.com/openai` |
| Provider | PPIO (managed, OpenAI-wire-compatible) |
| `DEFAULT_MODEL` / `LIGHT_MODEL` | `pa/gpt-5-mini` (PPIO's GPT-5-mini proxy) |
| `HEAVY_MODEL` | `pa/gpt-5.2` (configured but `LLMClient` only constructs with `default_model`; the heavy model is unused — verified `llm_client.py:78-97` only passes `settings.default_model`) |
| Provider construction | `langchain_openai.ChatOpenAI(base_url=..., api_key=..., model=..., timeout=..., streaming=True)` (llm_client.py:78-84) |
| Reasoning-related kwargs | **None** — no `reasoning=`, `reasoning_effort=`, `extra_body=`, `model_kwargs={"reasoning_content": True}`, `use_responses_api=True` |

### Does `pa/gpt-5-mini` emit reasoning at all?

**At the wire level: maybe — but only via PPIO's DeepSeek-style `delta.reasoning_content` field, NOT via OpenAI-spec reasoning blocks.** PPIO's docs (https://ppio.com/docs/model/llm-interleaved-thinking, https://ppio.com/docs/model/inference) confirm:

1. PPIO uses the Chat Completions API (it does NOT support OpenAI's Responses API). Per their own docs in the OpenAI Agents SDK guide: "基于 PPIO 不支持 responses API，因此我们使用 chat completions API 作为示例".
2. Reasoning-capable PPIO models surface internal thinking as `delta.reasoning_content` (string field, sibling of `delta.content`) — this is the DeepSeek convention also used by Ollama / XAI / Groq, NOT the OpenAI Responses API shape.
3. Specifically for `pa/gpt-5-mini`: this is a PPIO-managed proxy for GPT-5-mini. Whether it returns `reasoning_content` by default depends on PPIO's server config — production wire logs (`app/logs/app.log.6:17611`) show only standard `messages` / `model` / `stream` fields on the request, no `reasoning_effort` or `enable_thinking` toggle, so reasoning is at best opt-out / default-off for this proxy.

### Does `langchain_openai.ChatOpenAI` propagate `reasoning_content` to LangGraph?

**No — this is the dropping point.** Two hard facts from the installed `langchain-openai` package:

1. The package docstring explicitly warns:
   > "`ChatOpenAI` targets official OpenAI API specifications only. Non-standard response fields added by third-party providers (e.g., `reasoning_content`, `reasoning_details`) are **not** extracted or preserved. If you are pointing `base_url` at a provider such as OpenRouter, vLLM, or DeepSeek, use the corresponding provider-specific LangChain package instead (e.g., `ChatDeepSeek`, `ChatOpenRouter`)."
   (`.venv/.../langchain_openai/chat_models/base.py:1-12`)

2. The chat-completions chunk converter `_convert_delta_to_message_chunk` (base.py:428-481) reads ONLY `id`, `role`, `content`, `function_call`, `tool_calls` from `delta`. It silently drops any non-standard field including `reasoning_content` / `reasoning_details`. The result `AIMessageChunk.content` is therefore the plain assistant text string, with no reasoning anywhere — neither in `content` nor in `additional_kwargs["reasoning_content"]` (the wrapper does not populate that key on PPIO chunks either).

3. The reasoning-aware streaming code path `_astream_responses` (base.py:1452-1516) is ONLY used when `_use_responses_api(...)` returns True, which requires `use_responses_api=True` or `output_version="responses/v1"` or one of the `gpt-5-pro` / `codex` model prefixes. PPIO does not support the Responses API, so this path is unreachable for our config.

### Net conclusion

- Even if `pa/gpt-5-mini` returns `delta.reasoning_content` on the wire, `ChatOpenAI` strips it before LangGraph sees it.
- The only model-family that would surface reasoning under the current code with no changes is Anthropic's Claude (extended thinking, `{"type": "thinking"}` blocks) via `langchain_anthropic.ChatAnthropic` with `thinking={"type": "enabled", "budget_tokens": ...}` — neither installed nor configured.

---

## Section 3 — Streaming pipeline

### What IS wired correctly

- `app/runtime/_emitter.py:iter_text_events_from_chunk` handles list-content blocks with `type ∈ {"thinking", "reasoning"}` and emits `ReasoningDeltaEvent(delta=...)` on the `custom` stream channel (_emitter.py:217-241).
- `app/runtime/_emitter.py:iter_events_from_message` dispatches AIMessage / AIMessageChunk through that helper (_emitter.py:272-280).
- `app/runtime/runtime.py:Runtime.invoke` consumes both `messages` and `custom` channels via `astream(subgraphs=True)`, filters the `propose:` / `intent_detection:` / `user_admittance:` structured-output namespaces, drops `rehydrated-` history replays, and yields every event including `ReasoningDeltaEvent` (runtime.py:139-216).
- `app/events/runtime_emitted.py:ReasoningDeltaEvent` exists, kind `"reasoning_delta"`, semantically emit-only per the D41 / I-E-E rule (runtime_emitted.py:71-83).
- FE is already listening: `BIC-agent-portal/src/types/events.ts:48` declares the event, `src/lib/sse-client.ts:37` registers the `reasoning_delta` handler, `src/lib/event-dispatcher.ts:106` dispatches it, `src/stores/chatStore.ts` (lines 28, 117-125, 279) coalesces reasoning fragments into a `thinkingTimeline`, `src/pages/chat/ThinkingSection.tsx` renders them.

### Two bugs (drops) in the pipeline downstream of the agents

**Bug A — `ChatOpenAI` wrapper strips PPIO `reasoning_content`** (Section 2). This is the upstream gap: even if we wanted to surface reasoning, the wrapper choice prevents it.

**Bug B — `Orchestrator._run_turn` does NOT bypass `ReasoningDeltaEvent` from persistence**, even though the spec marks it emit-only (`session_seq=None`, no apply, no append) per the I-E-E rule (`.trellis/spec/backend/L3/events.md`).

Current code (`app/session/orchestrator.py:307-313`):

```python
async for event in self._runtime.invoke(ctx, turn_input):
    if isinstance(event, TextDeltaEvent):
        # D41 exception: text_delta bypasses apply + append.
        await self._broadcaster.emit(session_id, event, session_seq=None)
        continue
    seq = await self.persist_event(event)
    await self._broadcaster.emit(session_id, event, session_seq=seq)
```

Only `TextDeltaEvent` is bypassed. A `ReasoningDeltaEvent` would fall through to `persist_event` → `tx.session_events.append(event)` and get a real BIGSERIAL `session_seq`. That is a **spec violation** (I-E-E lists `text_delta` + `reasoning_delta` + `node_completed` as the emit-only set) and would also corrupt the SSE `Last-Event-ID` semantics. Ticket-30's spec.md:73 explicitly anticipated this:
> "L2 post-processor handling for `ReasoningDeltaEvent` / `NodeCompletedEvent` — these are emit-only per D41 (no apply, no append, session_seq=None), mirroring the existing TextDeltaEvent exception. L2's persistence-triple dispatch must skip them so they are not mis-routed as malformed session_events inserts. That wiring lives in the L2 repo … and is out of scope for ticket-30; it is tracked as a follow-up ticket on the L2 side."

That follow-up was never wired. `NodeCompletedEvent` is also affected by the same gap (no carve-out in orchestrator either) — but that's a separate finding orthogonal to this investigation.

### SSE encoder is already correct

`app/api/routers/sse.py:107-117 _encode` honors `session_seq is None` by omitting the `id:` line, so once Bug B is fixed, `reasoning_delta` would correctly stream to the FE as an SSE frame with `event: reasoning_delta` and no `id:` line.

---

## Section 4 — LangChain v1.3 reference

### Canonical reasoning block shape (`langchain_core` 1.4 installed)

From `.venv/.../langchain_core/messages/content.py:456-492`:

```python
class ReasoningContentBlock(TypedDict):
    """Reasoning output from a LLM."""

    type: Literal["reasoning"]
    """Type of the content block. Used for discrimination."""

    id: NotRequired[str]
    reasoning: NotRequired[str]
    """Reasoning text. Either the thought summary or the raw reasoning text itself.
    Often parsed from `<think>` tags in the model's response."""

    index: NotRequired[int | str]
    extras: NotRequired[dict[str, Any]]
```

**Note**: the canonical v1 key is `reasoning` (NOT `text` and NOT `thinking`). Our emitter at `_emitter.py:234` reads `block.get("thinking") or block.get("text") or ""` — it covers Anthropic (`thinking` key) and old OpenAI o-series (`text` key) but NOT the canonical v1 `reasoning` key. Adding `block.get("reasoning")` to that fallback chain is a one-line fix.

### How DeepSeek-style `reasoning_content` is normalized to v1

`langchain_core/messages/base.py:24-44` defines `_extract_reasoning_from_additional_kwargs`:

```python
def _extract_reasoning_from_additional_kwargs(message):
    """Extract `reasoning_content` from `additional_kwargs`.
    Handles reasoning content stored in various formats:
    - `additional_kwargs["reasoning_content"]` (string) - Ollama, DeepSeek, XAI, Groq
    """
    additional_kwargs = getattr(message, "additional_kwargs", {})
    reasoning_content = additional_kwargs.get("reasoning_content")
    if reasoning_content is not None and isinstance(reasoning_content, str):
        return {"type": "reasoning", "reasoning": reasoning_content}
    return None
```

This helper is reached only via the `BaseMessage.content_blocks` property (base.py:199-260) — it is NOT applied automatically to `AIMessageChunk.content`. So even if some hypothetical wrapper put `reasoning_content` into `additional_kwargs`, our current outer translator (which reads `chunk.content` directly) would not see it. We would have to either:
- Switch to a provider package that emits typed reasoning blocks (e.g. `langchain_anthropic.ChatAnthropic` with extended thinking, or a hypothetical `ChatDeepSeek`-style PPIO wrapper), OR
- Add a custom subclass / preprocessor that maps PPIO `delta.reasoning_content` → `AIMessageChunk` `additional_kwargs["reasoning_content"]` → `content_blocks` view, and update the outer translator to walk `content_blocks` instead of raw `content`.

### Reasoning enablement patterns (per `langchain_openai.ChatOpenAI` docstring)

`.venv/.../langchain_openai/chat_models/base.py:2925-2956`:

```python
reasoning = {
    "effort": "medium",  # 'low', 'medium', or 'high'
    "summary": "auto",   # 'detailed', 'auto', or None
}
model = ChatOpenAI(
    model="...", reasoning=reasoning, output_version="responses/v1"
)
response = model.invoke("What is 3^3?")

for block in response.content:
    if block["type"] == "reasoning":
        for summary in block["summary"]:
            print(summary["text"])
```

This only works against the **Responses API**. PPIO does not support Responses API, so this lever is unavailable for the current provider.

`.venv/.../langchain_openai/chat_models/base.py:734-758`:

```python
reasoning_effort: str | None = None
"""Constrains effort on reasoning for reasoning models.
Reasoning models only, like OpenAI o1, o3, and o4-mini and gpt-5 series. ..."""

reasoning: dict[str, Any] | None = None
"""Reasoning parameters for reasoning models."""
```

These fields are forwarded to the OpenAI SDK in `_default_params`. PPIO accepts them as a passthrough but, per PPIO's own docs page, they map to PPIO's `enable_thinking` template kwarg only for compatible models (not guaranteed for the `pa/gpt-5-*` proxies).

---

## Section 5 — Gap analysis & recommendations

### Gap summary

| # | Gap | Severity | Where |
|---|---|---|---|
| 1 | `ChatOpenAI` (Chat Completions path) does not extract PPIO's `delta.reasoning_content` — silently drops it. | High (root cause of "no reasoning visible") | `app/infrastructure/llm_client.py` provider choice |
| 2 | Orchestrator does not bypass persistence for `ReasoningDeltaEvent` (and `NodeCompletedEvent`); current code would persist them with a real `session_seq`, violating the I-E-E rule. | Medium (bug-in-waiting; manifests only once reasoning starts flowing) | `app/session/orchestrator.py:307-313` |
| 3 | Outer translator's reasoning-block reader only knows the keys `"thinking"` and `"text"`, missing the canonical v1 `"reasoning"` key (`ReasoningContentBlock`). | Low (forward-compat; bites the day we switch to a provider that emits v1 shape). | `app/runtime/_emitter.py:231-241` |
| 4 | `HEAVY_MODEL=pa/gpt-5.2` is configured but never used — `LLMClient` only constructs with `default_model`. | Low (unrelated to reasoning; surfaced incidentally) | `app/infrastructure/llm_client.py:76-97` |

### Recommendations (for Drake to decide)

Three viable directions, each with a different surface area:

**Direction A — Switch provider to one that emits v1 reasoning blocks natively.**
- E.g. `langchain_anthropic.ChatAnthropic` with `thinking={"type": "enabled", "budget_tokens": 2048}`, or wait for an Anthropic-via-PPIO model.
- Pro: zero changes to the L3 translator beyond a one-line key-name expansion (Gap 3).
- Con: model swap is a product decision (cost / latency / output quality).

**Direction B — Keep `pa/gpt-5-mini` but write a thin PPIO subclass of `ChatOpenAI` that maps `delta.reasoning_content` → `additional_kwargs["reasoning_content"]` on each chunk, then update the outer translator to consult `.content_blocks` (which calls `_extract_reasoning_from_additional_kwargs` internally) instead of raw `.content`.**
- Pro: keeps the model.
- Con: maintenance burden (we own a subclass of a fast-moving wrapper); also requires sending `enable_thinking=true` (or PPIO-specific equivalent) via `extra_body=` to actually make PPIO emit the field.

**Direction C — Leave reasoning streaming unimplemented; fix only Gap 2 + Gap 3 + Gap 4 (cleanups).**
- Pro: minimal change; protects against future regressions.
- Con: chemists still see no thinking track even when the FE is fully wired for it.

### Ambiguities for Drake to confirm

1. **Which direction (A / B / C)?** If "we want the thinking section to light up next sprint", B is the fastest path; if "we'll switch to Claude for production reasoning", A is cleaner.
2. **Should propose-side reasoning be visible?** Plan's `propose:` namespace is currently filtered by `_NOSTREAM_NS_MARKERS`. If reasoning IS lit up, should it leak through that filter or stay suppressed (so only `narrate` reasoning is shown)?
3. **Does Gap 2 (orchestrator carve-out for `ReasoningDeltaEvent` / `NodeCompletedEvent`) need to be fixed even if we go Direction C?** Today the spec says emit-only; the runtime emits zero of these so the bug is latent. Worth fixing as a defensive change.

---

## Cross-reference notes (where in the spec each finding lives)

- I-E-E (emit-only event rule, including `reasoning_delta`): `.trellis/spec/backend/L3/events.md` widened rule (originally from `tickets/ticket-30/pr-diff.patch:363, 2119`).
- Translator contract: `.trellis/spec/backend/L3/runtime.md` §6 (referenced in `_emitter.py:194`).
- Ticket-30 spec.md:73 explicitly flagged the L2 follow-up gap for `ReasoningDeltaEvent` / `NodeCompletedEvent`.
- Streaming behavior contract for cc/re narrate: `tests/fixtures/streaming/README.md` (referenced in cc.py:357, 416).
