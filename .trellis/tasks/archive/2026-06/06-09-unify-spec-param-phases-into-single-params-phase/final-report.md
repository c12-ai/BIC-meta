# Task 06-09 — Unify spec+param phases into a single params phase — Final Report

Date: 2026-06-12 · Branches: `BIC-agent-service@feat/experiments-plans-jobs-trials-overhaul`, `BIC-agent-portal@feat/unified-params-form`

## What shipped

**Hard cutover** from the 2-phase specialist flow (`collecting_spec` → `collecting_params`) to ONE
`collecting_params` phase with a unified 3-section form per specialist (CC/RE):
`{from_user, recommended, lab_logistics}`. `submitting` renamed `rts`. No backward compatibility.

### Backend (BIC-agent-service)
- `form_payloads.py` rewritten: `CCParamsForm`/`REParamsForm` (lenient drafts), strict gates via
  `build_cc_param_request`/`build_re_param_request` + `*_params_form_problems` — ONE validation
  pipeline shared by the recommend gate, the validate tool, the L2 confirm gate (422
  `form_validation_failed`), and the dispatch guardrail.
- New tool ladder per specialist: `update_*_from_user` / `update_*_lab_logistics` /
  `recognize_tlc_plate` (CC) / `recommend_*_params` (CC recommend stubbed per Drake; RE real HTTP) /
  `validate_*_params` / `request_params_confirmation`. Every draft mutation emits
  `TaskParamsSetEvent` (FE live-form write-through).
- `ConfirmKind = {plan, params, result_review}`; phase advance table:
  `(collecting_params, params) → rts`, `(conducting, result_review) → done`.
- DB: migration `c7e41f0a9b21` (drop `trials.spec`/`param`, add `trials.params JSONB`,
  default phase `collecting_params`). Shared-types pin moved to tag `v1.1.2a1` (Drake; upstream
  branch deleted).
- **Deterministic backstops for 7 live-observed LLM "abandon shapes"** (the LangGraph router is the
  product's safety net, prompts are best-effort):
  1–3. complete-draft → `emit_form` promotion after any ladder tool; 4. `auto_analyze` node for
  terminal trials in `conducting`; 5. promotion regardless of last tool;
  6. zero-tool prose turns — shared `_NO_PROSE_ONLY_RULE` prompt block (graph nudge rejected by
  Drake; test-side one-shot user nudge instead); 7. **phase-gated router branches** — a
  hallucinated call to an UNBOUND tool yields a LangChain error ToolMessage with no refusal
  marker; ungated it emitted a params form mid-`conducting`, stomping the review pane.
- `submit_l4_execution` made **idempotent per trial** (asyncio lock + first-success cache): the LLM
  emitted 4 parallel submit calls → 4 lab tasks (the lab ignores `idempotency_key` — **flagged to
  the lab team**), trial bound to a "Robot is busy" duplicate.
- `_merge_params_draft` section-merge reducer (parallel same-step tool writes), state/reception/
  guardrail/prompt updates, fast-path `merge_params_from_user_keys` (TLC recognize writes nested
  under `from_user`).
- All `.trellis/spec/backend` docs updated in the same change sets (Rule 10).

### Frontend (BIC-agent-portal)
- `ParameterDesignPanel` + new `CcParamsForm`/`ReParamsForm`/`form-chrome`/`useParamsFormHandle`:
  one editable form per specialist, "From you" (with Required badges, incl. lab logistics) +
  "Recommended" sub-sections; duo-panel preserved (chemist can hand-fill anything, incl.
  `recommended`).
- Store/event plumbing: `task_params_set` dispatch, `params`/`paramsConfirmed`/
  `paramsValidationErrors`, 422 renders as form-level errors, submit payload
  `{from_user, recommended, lab_logistics}`.

## Verification

- **BE unit suite: 643 passed** (incl. new regression tests: submit parallel-dup → 1 POST;
  shape-7 router gates; reducer merge semantics). ruff/format/pyright/alembic clean;
  `scenario_mind_failure` script passes.
- **FE**: tsc + Biome clean.
- **Chained CC→RE live E2E (`cc-re-chained-flow.spec.ts`): PASSED 3× including the final 4.9-min
  run** — plan(cc,re) → confirm → CC params form → confirm → dispatch → robot completes → review
  accept → RE auto-dispatch → params (1 min/1 mbar override) → confirm → dispatch → robot completes
  → review accept → assertions (2 task_created cc+re, ≥2 params forms, 2 review captions). All of
  Drake's check criteria exercised, including hand-edited fields (RE pressure override + CC
  cartridge-slot chemist-fill) and post-edit re-recommend.
- **Suite ledger (latest run of each spec): 12/14 green.**
  - `task-progress-stream`: green after the shared bench reset.
  - **`tlc-upload-chain` T2/T3: RED — external blocker.** ChemEngine at `52.83.119.132:8002`
    returns `400 {"detail":"VISION_SERVICE_URL 未配置"}` — the deployment lost its vision-service
    config. Not fixable from these repos; needs the ChemEngine operator. Probe to reproduce:
    `POST /api/tlc/tlc_plate_rawjudge`.

## Test-infra hardening (why E2E is now stable)

- `tests/helpers.ts`: `resetLabState()` (admin reset-to-test-data → cartridge
  `sample_40g_001@bic_09B_l4_001:unused` → ALL devices idle → runtime-table wipe → **block until
  robot idle, fail-loud**) used by every lab-dispatching spec; `waitForParamsForm()` (one-shot
  duo-panel nudge for shape 6, injectable count source).
- Every long wait has a persisted-`session_events` fallback + reload recovery — the page's
  EventSource drops randomly and missed events are unrecoverable until `05-27-sse-replay` ships.
- Final assertions read backend truth (reload-immune); stale "Analysis completed." phantom caption
  replaced with the real "Confirmed result review." signal.

## Follow-ups (out of scope, surfaced loudly)

1. **ChemEngine `VISION_SERVICE_URL`** — unblocks TLC T2/T3.
2. **Lab service ignores `idempotency_key`** on task creation.
3. **SSE `Last-Event-ID` replay** (`05-27-sse-replay`) — removes the whole stall-fallback class.
4. `manual-live-demo.spec.ts` updated but not re-executed (separate live config).

## Commits (this closing stretch)

BE: `61082fa` shape-6 prompts · `901ae2e` submit dedup · `b8970ec` simplify · `3abf8ff` shape-7
router gates. FE: `23d5abd`→`3231e35` (9 commits: bench reset, backend-truth waits, nudge, caption
fix, helper consolidation).
