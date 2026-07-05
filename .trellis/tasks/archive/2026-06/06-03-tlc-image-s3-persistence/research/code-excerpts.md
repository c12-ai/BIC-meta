# Code excerpts — ReasoningEvent investigation

All file paths absolute; line numbers from current HEAD as of 2026-06-03.

## 1. LLM client construction

`/Users/drakezhou/Development/BIC/BIC-agent-service/app/infrastructure/llm_client.py:68-97`

```python
def __init__(
    self,
    base_url: str,
    api_key: str,
    model: str,
    timeout_sec: float = 60.0,
    provider: Literal["ppio", "vllm"] = "ppio",
) -> None:
    self._model = model
    self._provider = provider
    self.chat_model = ChatOpenAI(
        base_url=base_url,
        api_key=api_key,  # type: ignore[arg-type]  # ChatOpenAI accepts plain str
        model=model,
        timeout=timeout_sec,
        streaming=True,
    )
    # Non-streaming sibling used for ``with_structured_output`` calls ...
    self.chat_model_structured = ChatOpenAI(
        base_url=base_url,
        api_key=api_key,  # type: ignore[arg-type]  # ChatOpenAI accepts plain str
        model=model,
        timeout=timeout_sec,
        streaming=False,
    )
```

Note: no `reasoning=`, `reasoning_effort=`, `use_responses_api=`, `output_version=`, `model_kwargs=`, or `extra_body=`.

## 2. Configured model

`/Users/drakezhou/Development/BIC/BIC-agent-service/.env:1-5`

```
BASE_URL="https://api.ppio.com/openai"
API_KEY="sk_..."  # PPIO
DEFAULT_MODEL="pa/gpt-5-mini"
LIGHT_MODEL="pa/gpt-5-mini"
HEAVY_MODEL="pa/gpt-5.2"
```

`/Users/drakezhou/Development/BIC/BIC-agent-service/app/core/lifespan.py:86-92`

```python
llm_commercial: LLMClient | None = None
if settings.base_url and settings.api_key:
    llm_commercial = LLMClient(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.default_model,   # <-- only default_model is used; LIGHT_MODEL / HEAVY_MODEL never wired
        provider="ppio",
    )
```

## 3. CC react + narrate LLM calls

`/Users/drakezhou/Development/BIC/BIC-agent-service/app/runtime/graphs/specialists/cc.py:348-383` (narrate)

```python
async def _narrate_node(state: SpecialistState, runtime: Runtime[RuntimeContext]) -> dict:
    """Second LLM pass: produce narration via direct chat-model invoke. ..."""
    system_msg = SystemMessage(content=_build_narrate_prompt(state))
    response = await llm.chat_model.ainvoke([system_msg, *state.messages])
    text = response.content if isinstance(response.content, str) else ""
    if text.strip():
        emit_event(runtime, TextDoneEvent, text=text)
    else:
        logger.warning("cc.narrate: empty narration ...")
    return {"messages": [response]}
```

`/Users/drakezhou/Development/BIC/BIC-agent-service/app/runtime/graphs/specialists/cc.py:419-446` (react)

```python
agent = create_agent(
    model=llm.chat_model,
    tools=phase_tool_index.get(state.current_phase, full_catalogue),
    state_schema=SpecialistState,  # type: ignore[arg-type]
    context_schema=RuntimeContext,
    middleware=[  # type: ignore[list-item]
        cc_dynamic_prompt,
        LLMErrorHandlingMiddleware(),
        GuardrailMiddleware(),
        LoopDetectionMiddleware(),
        ToolErrorHandlingMiddleware(),
        AfterToolMiddleware(),
    ],
)
result = await agent.ainvoke(state, context=runtime.context)  # type: ignore[arg-type]
```

(RE subgraph mirrors this 1:1 at `re.py:311-329, 331-353`.)

## 4. Plan subgraph LLM calls

`/Users/drakezhou/Development/BIC/BIC-agent-service/app/runtime/graphs/nodes/plan_subgraph.py:229-251` (propose, structured output, TAG_NOSTREAM)

```python
agent = create_agent(
    model=llm.chat_model_structured,
    tools=[],
    response_format=PlannerOutput,
    state_schema=GraphState,  # type: ignore[arg-type]
    context_schema=RuntimeContext,
    middleware=[LLMErrorHandlingMiddleware()],  # type: ignore[list-item]
)
result = await agent.ainvoke(
    {
        "messages": [
            {"role": "system", "content": _PLAN_PROPOSE_SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    },
    context=runtime.context,
    config={"tags": [TAG_NOSTREAM]},
)
```

`/Users/drakezhou/Development/BIC/BIC-agent-service/app/runtime/graphs/nodes/plan_subgraph.py:407-444` (narrate)

```python
async def _narrate_node(state, runtime) -> dict | Command:
    """Second LLM pass: produce chemist-facing narration via direct invoke. ..."""
    system_msg = SystemMessage(content=_pick_narrate_prompt(state))
    try:
        response = await llm.chat_model.ainvoke([system_msg, *state.messages])
        text = response.content if isinstance(response.content, str) else ""
        if text.strip():
            emit_event(runtime, TextDoneEvent, text=text)
        else:
            logger.warning("plan.narrate: empty narration ...")
    except Exception as exc:  # noqa: BLE001 -- best-effort (PRD AC5)
        logger.warning("plan.narrate: LLM failure ...", exc)
    ...
```

## 5. Outer-translator reasoning emission

`/Users/drakezhou/Development/BIC/BIC-agent-service/app/runtime/_emitter.py:208-241`

```python
if isinstance(content, str):
    if content:
        yield TextDeltaEvent(
            session_id=session_id,
            turn_id=turn_id,
            in_turn_seq=seq_allocator.next_seq(),
            delta=content,
        )
    return
if isinstance(content, list):
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text = block.get("text") or ""
            if text:
                yield TextDeltaEvent(...)
        elif btype in ("thinking", "reasoning"):
            # Anthropic uses ``thinking`` key; o-series uses ``text``.
            # Accept either to stay provider-agnostic.
            think = block.get("thinking") or block.get("text") or ""
            if think:
                yield ReasoningDeltaEvent(
                    session_id=session_id,
                    turn_id=turn_id,
                    in_turn_seq=seq_allocator.next_seq(),
                    delta=think,
                )
```

**Gap**: canonical LangChain v1 `ReasoningContentBlock` stores the text in `block["reasoning"]`, not `block["thinking"]` or `block["text"]`. To future-proof, this should fall through to `block.get("reasoning")` as well.

## 6. Outer-runtime astream dispatch

`/Users/drakezhou/Development/BIC/BIC-agent-service/app/runtime/runtime.py:139-216`

(See research/reasoning-event-investigation.md Section 3 — it already routes the `messages` channel through `iter_events_from_message`, so once a `ReasoningDeltaEvent` is yielded from the translator it lands on the outer runtime's stream correctly.)

## 7. Orchestrator persistence-bypass gap (Bug B)

`/Users/drakezhou/Development/BIC/BIC-agent-service/app/session/orchestrator.py:307-313`

```python
async for event in self._runtime.invoke(ctx, turn_input):
    if isinstance(event, TextDeltaEvent):
        # D41 exception: text_delta bypasses apply + append.
        await self._broadcaster.emit(session_id, event, session_seq=None)
        continue
    seq = await self.persist_event(event)
    await self._broadcaster.emit(session_id, event, session_seq=seq)
```

Should be (per I-E-E rule):

```python
if isinstance(event, TextDeltaEvent | ReasoningDeltaEvent | NodeCompletedEvent):
    await self._broadcaster.emit(session_id, event, session_seq=None)
    continue
```

## 8. langchain-openai chunk converter drops reasoning_content

`/Users/drakezhou/Development/BIC/BIC-agent-service/.venv/lib/python3.12/site-packages/langchain_openai/chat_models/base.py:1-12` (module docstring)

```
"""OpenAI chat wrapper.

!!! warning "API scope"

    `ChatOpenAI` targets official OpenAI API specifications only. Non-standard
    response fields added by third-party providers (e.g., `reasoning_content`,
    `reasoning_details`) are **not** extracted or preserved. If you are pointing
    `base_url` at a provider such as OpenRouter, vLLM, or DeepSeek, use the
    corresponding provider-specific LangChain package instead (e.g.,
    `ChatDeepSeek`, `ChatOpenRouter`).
"""
```

`/Users/drakezhou/Development/BIC/BIC-agent-service/.venv/lib/python3.12/site-packages/langchain_openai/chat_models/base.py:428-464`

```python
def _convert_delta_to_message_chunk(_dict, default_class):
    """Convert to a LangChain message chunk."""
    id_ = _dict.get("id")
    role = cast(str, _dict.get("role"))
    content = cast(str, _dict.get("content") or "")
    additional_kwargs: dict = {}
    if _dict.get("function_call"):
        ...
    tool_call_chunks = []
    if raw_tool_calls := _dict.get("tool_calls"):
        ...
    # NB: NO read of `reasoning_content` or `reasoning_details`.
    if role == "assistant" or default_class == AIMessageChunk:
        return AIMessageChunk(
            content=content,
            additional_kwargs=additional_kwargs,
            id=id_,
            tool_call_chunks=tool_call_chunks,  # type: ignore[arg-type]
        )
    ...
```

## 9. Canonical v1 ReasoningContentBlock shape

`/Users/drakezhou/Development/BIC/BIC-agent-service/.venv/lib/python3.12/site-packages/langchain_core/messages/content.py:456-492`

```python
class ReasoningContentBlock(TypedDict):
    type: Literal["reasoning"]
    id: NotRequired[str]
    reasoning: NotRequired[str]   # <-- canonical key name
    index: NotRequired[int | str]
    extras: NotRequired[dict[str, Any]]
```

## 10. langchain_core fallback for DeepSeek-style reasoning_content

`/Users/drakezhou/Development/BIC/BIC-agent-service/.venv/lib/python3.12/site-packages/langchain_core/messages/base.py:24-44`

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

Only reached via `BaseMessage.content_blocks` (base.py:199-260); NOT applied automatically to `AIMessageChunk.content`.

## 11. FE wiring (proof FE is ready to render reasoning)

- Event type declaration: `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/types/events.ts:48`
- SSE handler registration: `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/lib/sse-client.ts:37`
- Dispatcher: `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/lib/event-dispatcher.ts:106`
- Store coalescing: `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/stores/chatStore.ts:28, 117-125, 279`
- Render: `/Users/drakezhou/Development/BIC/BIC-agent-portal/src/pages/chat/ThinkingSection.tsx:28-29`
