# Executors reuse previous step's confirmed params

## Goal

When a multi-step plan chains executors (e.g. CC → RE), a later executor should
**reuse the confirmed parameters the previous executor already settled** instead
of starting blind. Concrete example: CC confirms `solvent_ratio = 2:1`; when RE's
`collecting_params` turn begins, RE's LLM should see that 2:1 and reuse it (unless
chemistry dictates otherwise).

The reuse decision is owned by the **LLM via prompt**, not a hard-coded data-merge
engine. This task surfaces the prior step's params into the next executor's
phase-scoped prompt and emphasizes the reuse rule there.

## What I already know (verified from code)

- **The data is already reachable.** The session loader hydrates ALL jobs' trials
  for the active plan into the frozen `ctx`
  (`app/session/orchestrator.py:535-545`). RE's `SpecialistState.ctx` IS that same
  ctx (`app/runtime/types/specialist.py:122`), so `ctx.trials[cc_job_id]` already
  holds CC's confirmed `params` (incl. `solvent_ratio`) at RE's first turn.
- **The prompt is blind to it.** `re_dynamic_prompt` composes the system prompt
  from `current_phase` only (`app/runtime/middleware/dynamic_prompts.py:309-313`);
  rehydrate only rebuilds messages (`app/runtime/graphs/specialists/rehydrate.py:40`);
  RE code only reads its OWN trial via `ctx.find_trial(state.task_id)`
  (`app/runtime/graphs/specialists/re.py:219`). No code injects sibling-step params.
- **The prompt already PROMISES this behavior with no data to back it:**
  - `dynamic_prompts.py:244-245` — "a chained CC run usually implies the volume +
    solvent system" (assumes CC context, injects nothing).
  - `dynamic_prompts.py:279-280` — exit (B) is for "standalone RE with no upstream
    CC context", but the prompt currently can't tell chained-vs-standalone apart.
- **Params live in `trials.params` JSONB**, shaped `{from_user, recommended,
  lab_logistics}` (`app/data/models.py:234`, `app/events/form_payloads.py`). The
  carry-relevant fields are in `from_user` (`solvent_ratio`, `solvents`,
  `volume_ml`).
- **No cross-step param inheritance exists today** — confirmed absent across
  `tools.py`, `context.py`, `reception_node.py`.

## Requirements

- [ ] When the **next executor's `collecting_params` turn** runs, its dynamic
      prompt includes the **previous step's confirmed `from_user` params** (the
      actual values, e.g. `solvent_ratio = [2, 1]`), read from `ctx`.
- [ ] The prompt **emphasizes the reuse rule**: reuse the prior step's shared
      params unless the chemistry of this executor dictates a different value.
- [ ] The injection is **phase-scoped to `collecting_params`** (the only phase
      where params are being decided). Other phases unchanged.
- [ ] When there is **no upstream step** (standalone RE), no prior-context block is
      injected, and the existing exit-(B) "standalone, don't silently default"
      behavior is preserved (`dynamic_prompts.py:279-280`).
- [ ] "Previous step" is resolved from the **plan ordering in `ctx`** (the job
      immediately before the current one in plan sequence), reading its **latest
      confirmed trial's `params`**.

## Acceptance Criteria

- [ ] **Verified precondition (DONE):** CC's confirmed params are reachable from
      RE's first turn via `ctx.trials[cc_job_id]` — confirmed by code trace.
- [ ] A CC→RE plan: after CC confirms `solvent_ratio=[2,1]`, RE's
      `collecting_params` system prompt string contains CC's `solvent_ratio=[2,1]`
      (assert on the composed prompt).
- [ ] A standalone RE plan (no prior step): RE's prompt contains NO prior-context
      block; exit-(B) language remains.
- [ ] Unit test asserts the prior-step resolver returns the correct prior job's
      latest-trial `from_user` params given a plan ordering, and `None` when the
      current step is first.
- [ ] The reuse rule wording is present in the `collecting_params` instructions.
- [ ] **Symmetric coverage:** `cc_dynamic_prompt` gets the same prior-step injection
      (shared resolver), proven by a test where a step precedes CC and CC's prompt
      surfaces that prior step's `from_user` params.

## Definition of Done

- Tests added (resolver unit test + prompt-composition assertion test).
- Lint / typecheck / CI green.
- If the L3 prompt/middleware contract is documented in `.trellis/spec/`, update it
  in the same change set (Rule 10).
- No behavior change to phases other than `collecting_params`.

## Technical Approach

**Symmetric injection into BOTH `re_dynamic_prompt` AND `cc_dynamic_prompt`**
(Drake confirmed: other plan orderings are possible/coming, so CC may have an
upstream step — e.g. TLC→CC). Chosen over the rehydrate SystemMessage approach
because it is always-fresh (recomputed each model request), phase-scoped, and lives
next to the existing prose hints at `dynamic_prompts.py:244,279`.

The prior-step resolver `_extract_prior_step_params` is shared by both prompts; the
injection block is identical. Factor it so CC and RE call the same helper.

Sketch (per the approved preview), applied identically to cc_ and re_:

```python
@dynamic_prompt
def re_dynamic_prompt(request: ModelRequest) -> str:
    phase = _resolve_phase(request)
    instructions = _RE_PHASE_INSTRUCTIONS.get(phase, ...)
    if phase == "collecting_params":
        prior = _extract_prior_step_params(request.state)  # reads ctx
        if prior:
            instructions += "\n\nPRIOR STEP CONTEXT:\n" + prior
            # + reuse rule emphasis
    return f"{_RE_HEADER}\n\n{instructions}"
```

`_extract_prior_step_params(state)`:
- Resolve current job from `state.task_id` / plan cursor.
- Find the immediately-preceding job in plan order from `ctx`.
- Return its latest trial's `params["from_user"]` rendered as a short text block,
  or `None` if no prior step or no confirmed params.

**Open design decisions (to resolve in design/implement phase):**
- **Override behavior** — left to the LLM (prompt-owned), per Drake. We do NOT
  hard-code prefill/hard-inherit/empty-only. The prompt says "reuse unless
  chemistry differs"; the model decides. Revisit only if testing shows the LLM
  reuses incorrectly.
- **Which fields to surface** — start with the whole `from_user` section (it's the
  chemist-intent section and is schema-shared in spirit). Narrow later if noise.
- **CC-as-downstream — DECIDED: mirror into `cc_dynamic_prompt` too.** Both prompts
  get the symmetric injection so CC reuses an upstream step's params when one exists.

## Decision (ADR-lite)

**Context**: A later executor (RE) starts blind to the prior executor's (CC)
confirmed params, even though the prompt already assumes "a chained CC run implies
volume + solvent system". The data is in `ctx` but never reaches the LLM.

**Decision**: Inject the prior step's confirmed `from_user` params into the next
executor's `collecting_params` dynamic prompt and emphasize a reuse rule there.
Keep the reuse judgment with the LLM rather than a deterministic carry-forward
merge.

**Consequences**:
- (+) Minimal, surgical — touches the prompt middleware, not the data/dispatch
  layers. Fulfills a promise the prompt already makes.
- (+) No rigid override rule to maintain; LLM adapts per chemistry.
- (−) Reuse correctness depends on prompt wording + model behavior; must be
  asserted by tests on a real CC→RE scenario.
- (−) Per-executor mirroring needed if more executor orderings appear.

## Out of Scope

- A deterministic field-mapping / carry-forward merge engine in `reception_node`
  or `tools.py`.
- Hard-inheriting / read-only-locking carried values (rejected: conflicts with the
  duo-panel principle — chemist must retain agency).
- Persisting carried params into the next trial's `trials.params` at dispatch time
  (we surface to the prompt only; persistence still happens via the chemist's
  normal confirm).
- Changing the params schemas or the unified-params form.
- Any FE change.

## Technical Notes

- Inject site: `app/runtime/middleware/dynamic_prompts.py:309-313`
  (`re_dynamic_prompt`); existing prose hints to align with at lines 244-245 and
  279-280; phase table `_RE_PHASE_INSTRUCTIONS` at 234-281.
- Data reachability: `app/session/orchestrator.py:535-545` (loads all plan jobs'
  trials); `app/runtime/types/specialist.py:122` (RE shares top-level ctx);
  `app/core/context.py:119-231` (`ctx.jobs`, `ctx.trials`, `ctx.latest_trial`,
  `ctx.find_trial`, `ctx.next_job`).
- Params model: `app/data/models.py:234` (`trials.params` JSONB);
  `app/events/form_payloads.py` (`CCParamsForm` ~124-141, `REParamsForm` ~195-212);
  `from_user` carry fields: `solvent_ratio`, `solvents`, `volume_ml`.
- Phase resolver: `_resolve_phase(request)` at `dynamic_prompts.py:288-297`.
- Rule 11 (type-first): render from typed snapshots / Pydantic forms, not raw dicts,
  where practical.
- Rule 10: check `.trellis/spec/backend/L3/` for any documented prompt/middleware
  contract before changing.

## Research References

- Verified via two `Explore` traces (executor invocation + param flow, and RE
  start-turn context contents). Key verdict: prior-step params are **reachable via
  ctx (A=YES)** but **absent from RE's current prompt (B=NO)**.
