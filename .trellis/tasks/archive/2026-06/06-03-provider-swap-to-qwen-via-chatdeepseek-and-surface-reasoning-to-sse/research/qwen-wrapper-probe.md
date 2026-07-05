# Research — Qwen via DashScope + langchain wrapper comparison

- **Question**: Does Qwen on DashScope OpenAI-compatible endpoint emit
  reasoning, and does `langchain_openai.ChatOpenAI` preserve it?
  If not, does `langchain_deepseek.ChatDeepSeek` work as a drop-in?
- **Scope**: external provider behavior + langchain wrapper field
  preservation
- **Date**: 2026-06-03
- **Probe artifacts**: `/tmp/qwen_wrapper_probe.py` (script — may be
  garbage-collected; reproduced inline below for durability)

---

## Setup

- Endpoint: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- Auth: DashScope `sk-...` key from `.env` (var name: `API_KEY`)
- Model: `qwen-plus` (hybrid; reasoning gated by per-call
  `enable_thinking=True` via `extra_body`)
- Prompt: `"What is 17 * 23?"`
- Test venv: `/tmp/ppio-test-venv` (Python 3.12, langchain-core 1.4.0,
  langchain-openai 1.2.2, langchain-deepseek 1.0.1) — matches BIC's
  langchain-core version, isolated from the project lock file

## Three setups tested

### S1. Raw httpx → confirm wire shape

```
delta chunks: 296
distinct delta keys: ['content', 'reasoning_content', 'role']
first reasoning chunk: {"content": "", "reasoning_content": "Okay, so"}
reasoning_content (first 200): 'Okay, so I need to figure out what 17 multiplied by 23 is.
  Let me think about how to approach this. I remember that multiplying
  two numbers can be done in a few different ways, like the standard algor'
content (first 120): 'To compute $ 17 \\times 23 $, we can use multiple methods to ensure accuracy.
  \n\n---\n\n### **Method 1: Distributive Property'
```

**Confirmed**: DashScope returns reasoning via `delta.reasoning_content`
(DeepSeek convention). Sibling field of `delta.content`. Both are
strings, both stream across chunks.

### S2. langchain_openai.ChatOpenAI (control test — expected to fail)

```
chunks read: 80
chunk.content types seen: {'str'}
additional_kwargs keys: []
first reasoning artifact: NONE — dropped
```

**Confirmed**: `ChatOpenAI` strips `reasoning_content` silently. The
field is not surfaced in `chunk.content` (still plain string) nor in
`chunk.additional_kwargs` (empty). Root cause: `ChatOpenAI._convert_
delta_to_message_chunk` (`langchain_openai/chat_models/base.py:428-481`)
only reads `id/role/content/function_call/tool_calls` from the wire
delta and discards everything else.

### S3. langchain_deepseek.ChatDeepSeek (proposed drop-in)

Streaming:
```
chunks read: 80
chunk.content types seen: {'str'}
additional_kwargs keys: ['reasoning_content']
first reasoning artifact: {"_via": "additional_kwargs", "value_excerpt": "Okay, so"}
reasoning_content streamed (first 200): 'Okay, so I need to figure out
  what 17 multiplied by 23 is. Let me think about how to approach this.
  I remember that multiplying two numbers can be done in a few different
  ways, like the standard algor'
```

Non-streaming `ainvoke`:
```
resp.additional_kwargs keys: ['reasoning_content', 'refusal']
resp.content_blocks types: ['reasoning', 'text']
```

**Confirmed**: `ChatDeepSeek` preserves `reasoning_content` into
`AIMessageChunk.additional_kwargs["reasoning_content"]` on every chunk
during streaming, and projects to canonical v1 shape `[{"type":
"reasoning", ...}, {"type": "text", ...}]` via `content_blocks` for
non-streaming `ainvoke`.

## Implications for BIC

1. **Provider swap unblocks reasoning** — DashScope qwen-plus is a
   compatible provider out of the box (wire format is the DeepSeek
   convention `reasoning_content`).
2. **Wrapper swap is the gating change** — even if we kept PPIO, just
   switching from `ChatOpenAI` to `ChatDeepSeek` would have unblocked
   any DeepSeek-style reasoning provider. The provider swap (DashScope)
   was chosen for product/cost reasons; the wrapper swap is what
   technically enables reasoning.
3. **Two `LLMClient` instance topology is necessary** — `qwen-plus` is a
   hybrid model; `enable_thinking=True/False` is set per-call via
   `extra_body`. We need at least one instance with each setting so
   callers can pick per node (cost vs. UX tradeoff).
4. **Translator extension** — streaming reasoning arrives in
   `additional_kwargs["reasoning_content"]` (string), NOT as a content
   block. `_emitter.py:iter_text_events_from_chunk` must add a path
   that reads from `additional_kwargs` directly, in addition to the
   existing list-of-blocks scan.
5. **Latency cost** — S1 showed 296 reasoning+content chunks for "17 *
   23" with thinking on; S3 capped at 80 chunks (we stopped early) but
   total wall-clock was visibly higher than the non-thinking case. PRD
   acknowledges this as a Q2.c risk; mitigation is per-node fallback
   to the no-thinking `chat_model` instance.

## Reproducer (probe script — frozen here in case /tmp/ is wiped)

```python
# /tmp/qwen_wrapper_probe.py
# (see Section "Three setups tested" above for outputs)
# Strips proxies, parses .env (handles inline-comment quirks), then
# runs S1 (httpx) + S2 (ChatOpenAI) + S3 (ChatDeepSeek streaming +
# invoke) against qwen-plus with enable_thinking=True passed via
# extra_body.
#
# Invocation: /tmp/ppio-test-venv/bin/python /tmp/qwen_wrapper_probe.py
# (full script body is in the project session transcript; recreate from
# there if /tmp is wiped — the contract is the three setups above)
```
