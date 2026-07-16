# Current model-selection and provenance evidence

## Scope

This note records the current Agent Service model-selection and provenance behavior relevant to the target Foundation contract. Evidence is from `BIC-agent-service` `main` at commit `12a84f3238a9`; current code is migration evidence, not the target contract.

## Selection is startup precedence, not capability matching

`app/core/lifespan.py:86-123` may construct two optional clients:

- DashScope from `base_url`, `api_key`, and `default_model`;
- vLLM from `vllm_base_url`, optional API key, and `vllm_default_model`.

Application composition then selects `app.state.llm_commercial or app.state.llm_local` once at `app/main.py:68-108` and injects that one client into the global Runtime. This is fixed provider precedence: when both are configured, DashScope wins. There is no component capability declaration, allowlisted selection policy, per-Turn resolution, or runtime compatibility check.

`app/core/config.py:67-85` stores a concrete default model and context-window/budget configuration, but those values do not form a versioned provider-neutral capability contract. If no provider is configured, the service remains live in degraded mode while Turn-submitting endpoints are unavailable; there is no compatible-model failover after Runtime composition.

The LLM retry middleware retries the same selected model and raises after exhaustion (`app/runtime/middleware/llm_error_handling.py:41-143`). A failed commercial invocation does not switch to the configured local model. Some narration/query paths can fall back to deterministic text, but that is semantic degradation rather than provider/model failover.

## One client fans out to all current model call sites

`LLMClient` constructs streaming and structured-output handles over the same concrete model at `app/infrastructure/llm_client.py:200-272`. The handles hard-code important behavior such as streaming mode, `max_tokens=4096`, and `enable_thinking=False`.

The single client is passed through `Runtime` into the graph factory and then into Objective, Plan, Query, CC, RE, TLC, FP, admission, intent, ReAct, and narration paths. Current code distinguishes call mechanics but has no graph-level Model Capability Level declaration or governed level-to-model mapping.

## Current provenance is incomplete and mostly telemetry

- `app/infrastructure/token_counter.py:73-116` extracts provider usage and optionally logs prompt/completion token counts; it does not persist provider/model/config identity.
- `app/runtime/middleware/llm_error_handling.py:71-135` reads a model name for retry logs only.
- `app/infrastructure/llm_client.py:5-9,223-224,284-291` stores a provider label but does not attach it to the durable Turn record; despite the module documentation, its later explicit use is an error message during close.
- `app/runtime/runtime.py:111-127` creates Turn span attributes containing Agent, Session, Turn, user, and feedback context but no selected provider/model.
- `app/runtime/runtime.py:201-226` persists the Turn root-span identifier and feedback-context snapshot. `app/data/models.py:119-137` has no model-provenance fields.
- automatic LLM instrumentation may retain model detail in Phoenix spans, but that telemetry is not the authoritative compact Turn-correlated audit record and may have different retention.

Current entity, Session Event, snapshot, and shared wire schemas also do not expose model selection. That external absence should remain compatible; the target provenance record is internal.

## Target implication

The redesign should replace process-global provider precedence with exactly two v1 Model Capability Levels: `light` and `complex`. Each hosted Agent graph declares one of them, Foundation maps that level to an approved concrete model, and every actual call emits Model Invocation Provenance correlated to its Turn and graph. Domain Packs cannot add levels. This supports several graph invocations or calls without pretending the whole Turn used one model. A compact internal record and full telemetry remain correlatable, secrets/raw prompts stay excluded by default, and exact model lifecycle pinning remains separately demand-gated.
