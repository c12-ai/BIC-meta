# Research — PPIO wire-level probe (deepseek-r1 + pa/gpt-5-mini)

- **Question**: Does PPIO emit `delta.reasoning_content` for reasoning-
  capable models? Does `pa/gpt-5-mini` (our current default) emit it?
- **Scope**: external provider behavior; proves the `ChatOpenAI` field-
  drop is wrapper-level, not provider-level
- **Date**: 2026-06-03
- **Probe artifacts**: `/tmp/ppio_wire_probe.py` (script — may be GC'd;
  results reproduced inline below)

---

## Setup

- Endpoint: `https://api.ppio.com/openai`
- Auth: PPIO `sk_...` key (the one we used to use; rotate when retired)
- Models probed: `pa/gpt-5-mini` (with various reasoning toggles) and
  `deepseek/deepseek-r1`
- Prompt: `"What is 17 * 23? Show your reasoning step by step."`
- Probe: raw httpx → POST `/chat/completions` with `stream=true`,
  iterate SSE frames, dump distinct `delta` keys + first reasoning-
  shaped chunk if any

## Results

| Probe | Request | Distinct delta keys | Reasoning surfaced? |
|---|---|---|---|
| A | `pa/gpt-5-mini` plain | `['content','role']` | **No** |
| B | `pa/gpt-5-mini` + `reasoning_effort:"medium"` | `['content','role']` | **No** — model explicitly refused: *"Sorry — I can't share my internal step-by-step chain-of-thought"* |
| C | `pa/gpt-5-mini` + `enable_thinking:true` | HTTP 400 `Unknown parameter` | rejected |
| D | `pa/gpt-5-mini` + `reasoning_effort:"high"` | `['content','role']` | **No** |
| E | `pa/gpt-5-mini` + `reasoning_split:true` | HTTP 400 `Unknown parameter` | rejected |
| F | `deepseek/deepseek-r1` plain | `['content','reasoning_content','role']` | **Yes** — `{"reasoning_content": "I"}`, `{"reasoning_content": " need to"}`, ... |

## Findings

1. **PPIO uses DeepSeek-style `delta.reasoning_content` convention** —
   directly confirmed by probe F. Matches PPIO's own docs at
   `https://ppio.com/docs/model/inference` and
   `https://ppio.com/docs/model/llm-interleaved-thinking`.
2. **`pa/gpt-5-mini` does not emit reasoning on the wire** regardless of
   any toggle. PPIO appears to run it as a non-reasoning proxy. This
   means even fixing the wrapper would not have surfaced reasoning
   under PPIO + our current model choice.
3. **`enable_thinking` / `reasoning_split` are unknown parameters on
   `pa/gpt-5-mini`** (HTTP 400). Confirms the model is not a hybrid in
   PPIO's setup.

## Implications for the decision

This probe is what justifies the dual change in the PRD:

- The provider swap (PPIO → DashScope) alone wouldn't have helped if we
  kept `ChatOpenAI`
- The wrapper swap (`ChatOpenAI` → `ChatDeepSeek`) alone wouldn't have
  helped on `pa/gpt-5-mini` because PPIO doesn't emit reasoning for
  that model
- We need both — and we also need a hybrid model on a provider that
  emits `reasoning_content`. DashScope `qwen-plus` is exactly that.

## Cross-reference

- See `qwen-wrapper-probe.md` (sibling file) for the post-swap
  verification on the chosen DashScope+ChatDeepSeek stack
- See `.trellis/tasks/archive/2026-06/06-03-tlc-image-s3-persistence/research/reasoning-event-investigation.md`
  for the original end-to-end gap analysis that surfaced this probe

## Reproducer (script frozen here)

```python
# /tmp/ppio_wire_probe.py
# Imports BIC settings to grab PPIO key + base URL, then runs probes
# A–F above. Dumps distinct delta keys per probe and the first
# reasoning-shaped chunk if any. Streams SSE via httpx (no langchain
# in the path).
#
# Invocation: cd BIC-agent-service && .venv/bin/python /tmp/ppio_wire_probe.py
# (full script body is in the project session transcript)
```
