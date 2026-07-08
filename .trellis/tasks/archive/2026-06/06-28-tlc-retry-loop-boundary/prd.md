# TLC Rf-retry loop: prep-once / per-round develop / cleanup-on-success

## Goal

Make the TLC specialist run a **real iterative separation**: develop a plate, photograph
it, recognize the product Rf, and — if the Rf is outside the chemist's target window —
re-develop with a **new solvent ratio**, looping until the Rf lands in-window (or a cap is
hit), then clean up. The retry loop must model the **physical envelope correctly**: one-time
material prep at the start, per-round tank-prep + spotting + develop + photo + recognition,
and cleanup **once, only on a successful (in-window) result**.

This redesign also dissolves a live E2E bug (TLC retry drops `sample_tubes` → dispatch
fails) by sending the fixed sample tubes **once at prep** instead of on every round.

## User value

A chemist gets a TLC analysis that actually converges on a usable separation (the way the
bench process works), instead of a single fixed-ratio shot or a retry that crashes.

## Confirmed facts (from research — do not re-litigate)

Research: `research/lab-service-tlc-loop.md`, `research/agent-service-tlc-retry.md`.

**Corrected physical model (CONFIRMED against lab code):**
- **PREP once at start** = material fetch from the supply shelf (`_pickup_materials`,
  `planner.py:532`, gated `if is_first`). Round-1 only. ✅
- **Per-round (every round):** aspirate + prepare developing tank with a **new solvent
  ratio** (`_prepare_solvents`, `planner.py:598`, unconditional per round) → sip + spot dot
  on silica plate (`_spot_plate`, `planner.py:636`) → immerse + aim camera (`_immerse_and_aim`,
  `planner.py:687`) → **develop/observe (RGB+UV)** + **take photo**. ✅ for tank/spot/immerse.
- **CLEANUP once at end** = dispose plate (`end_tlc`, `planner.py:374`).
- Only the **recommended solvent ratio** changes per round (e.g. 2:1→3:1); `sample_tubes`
  and `target_window` are FIXED, sent once at prep.
- Loop exit = **deterministic auto-recognition** of in-window Rf (no manual chemist confirm).

**Gaps that make the model non-functional today:**
- Lab runs **ONE round per dispatched task** (`TASK_STEPS` = fixed `START_TLC`→`END_TLC`,
  `task.py:127`; `plan_from_request` hard-codes `round_index=1`, `service.py:231`).
- The planner **has a latent multi-round skeleton** (`plan_run` loops rounds, prep round-1-only,
  dispose round≥2-only, fresh tank per round, `planner.py:393`) — never fed >1 round.
- `observe_view` / `observe_uv` / `take_photo` are **defined but never called** (dead code,
  `planner.py:326-372`) — **no photo op is dispatched**.
- Terminal MQ payload `TaskStatusMsgPayload` carries **no image URL** — no "photo ready,
  decide next ratio" inter-round handover (`task_service.py:411`).
- `END_TLC` runs on START-skill success (HTTP 200), **NOT** gated on Rf-in-window
  (`task_service.py:220-271`).
- `CreateTLCTaskRequest` has **no Rf-goal / target-window field** (`shared-types tlc.py:24`).
- Agent has **no prep-once / cleanup-on-success notion** — every retry re-POSTs a COMPLETE
  `CreateTLCTaskRequest`, so the lab re-runs the whole program (incl. prep + cleanup) each
  attempt (`tools.py:562`, `tlc.py:684`).
- `recommend_tlc_mixcase` is **STUBBED and ignores trial history** (`mind_client.py:215`) —
  the request type already carries `trials` observed-Rf history; only the impl is canned.

**The live bug (to be dissolved, not separately patched):** a post-confirm `collecting_params`
LLM turn emits a whole-blob `TaskParamsSetEvent` that overwrites the confirmed
`lab_logistics.sample_tubes` with empty (LLM is told "lab_logistics: empty for TLC",
`dynamic_prompts.py:256`); the retry re-seeds from that clobbered row → `_submit_l4`
"select 2–4 sample tubes (got 0)" (root-cause chain in agent-service research §Root Cause).

## Decisions already made (by Drake)

1. **Scope = full round-based redesign** (not a stop-gap bug fix).
2. **The param-clobber bug is dissolved by the redesign** — tubes sent once at prep; no
   separate fix; the TLC retry E2E stays red until the redesign lands (accepted).
3. **Real history-aware `recommend_tlc_mixcase` IS in scope** — each round's ratio must adapt
   to the prior round's observed Rf (replace the stub with a live/working recommendation).

## Requirements

- **R1 — Agent owns the loop.** The agent drives rounds via a finer-grained Agent↔Lab command
  surface (`tlc_prep` → `tlc_run_round(ratio)` × N → `tlc_cleanup`); the lab does not loop.
- **R2 — Correct envelope.** Prep (material fetch) runs **exactly once** at the start; tank-prep +
  spot + develop + photo run **per round**; cleanup runs **exactly once**, **only after an
  in-window (successful) result**.
- **R3 — Round dispatch is incremental.** A `tlc_run_round` does NOT re-run prep or cleanup.
- **R4 — Agent-side decision loop.** After each round the agent reads the plate photo URL off the
  MQ `TaskStatusMsgPayload`, calls `recognize_tlc_plate`, and runs the deterministic in-window
  check; out-of-window → fetch a NEW ratio + run another round; in-window → cleanup. Caps at
  `TLC_MAX_ATTEMPTS`.
- **R5 — Fixed vs. per-round params.** `sample_tubes` + `target_window` are sent ONCE at prep and
  fixed across rounds; only the recommended **solvent ratio** changes per round. (This dissolves
  the `sample_tubes`-drop bug — tubes are never re-validated per round.)
- **R6 — Adaptive recommendation (L4 stub).** `recommend_tlc_mixcase` reads `trials` observed-Rf
  history and returns an adjusted ratio. Stays an L4 stub (no live HTTP).
- **R7 — Mock-in-L4-only.** No mocks / test-special-casing above L4. All fakery (scripted
  recognition Rf, history-aware ratio) lives in `mind_client` L4 stubs; going live = edit only L4.
- **R8 — Photo URL on MQ.** `TaskStatusMsgPayload` carries the round's captured-image S3 URL.
- **R9 — Contracts + specs (Rule 10).** Every changed cross-layer surface updates its spec doc in
  the same change set: the new TLC round commands / `CreateTLCTaskRequest`, `TaskStatusMsgPayload`,
  shared-types, and the affected `.trellis/spec/**` in both repos.

## Acceptance criteria

- [ ] **AC1 — Round-based retry E2E (rewrite `tlc-retry-flow.spec.ts`).** Drives the chemist UI;
  asserts the round-based truth: prep once (tubes sent once) → **≥2** `run-round` dispatches with a
  **different solvent ratio** between round 1 and round 2 → recognition OUT then IN → **one**
  `tlc_cleanup`, AFTER success only → **one** `result_review(SUCCESS)` → accept → **no**
  `turn_failed`. Count-agnostic (≥1 retry), shape-true.
- [ ] **AC2 — Prep-once / cleanup-once proven.** A test/assertion proves prep ran exactly once and
  cleanup ran exactly once AND only on success (the envelope, not just "it advanced").
- [ ] **AC3 — Ratio actually adapts.** An assertion that the round-2 dispatch carries a DIFFERENT
  solvent ratio than round 1 (proves the L4 history-aware recommendation is wired through, not a
  constant).
- [ ] **AC4 — Contract + spec docs updated.** Every changed cross-layer surface has its spec doc
  updated in the same change set (Rule 10) — verified.
- [ ] **AC5 — BE suites green both repos.** `BIC-agent-service` pytest + `BIC-lab-service` pytest
  both pass (per-round planner path, L4 history-aware stub, MQ payload change).

## Out of scope

- Live ChemEngine/Mind HTTP routes (`recommend_tlc_mixcase`, `recognize_tlc_plate`,
  `tlc_plate_rawjudge`) — they stay L4 stubs; wiring live routes is a separate task gated on the
  external team.
- A general fix for the whole-blob `TaskParamsSetEvent` clobber as a standalone bug (the redesign
  dissolves it for TLC by sending tubes once at prep). The CC `sample_cartridge_location` clobber
  RISK is noted but not fixed here — flag as a follow-up.
- Activating the lab's latent `plan_run` multi-round program (rejected in Q-A in favor of the
  agent-owned per-round command surface).
- **Orphan/abandoned-session handling** (agent gives up after PREP/a failed round, leaving a
  prepped plate). MVP relies on bench reset; documented follow-up. The thin `tlc_session` store
  leans on single-TLC-in-flight (`service.py:272`), so a stuck plate is cleared by the next reset.
- A full durable TLC-session aggregate (lifecycle/round-history/concurrency beyond one robot) —
  shared-types models no plate identity to drive it (`research/sharedtypes-tlc-ops.md`); thin
  `task_id → {plate_slot, tank_slot, box_slots}` mapping only.

## Open questions (block planning)

(none remaining — A/B/C/D resolved above)

- ~~Q-A. Loop-owner mechanism~~ → **RESOLVED: Agent owns the loop** via a finer-grained
  per-round Agent↔Lab command surface: `tlc_prep` (once; sends the FIXED sample_tubes +
  fetches materials) → `tlc_run_round(ratio)` (repeatable; tank-prep + spot + develop + photo;
  returns the plate photo) → `tlc_cleanup` (once; on in-window success). The agent runs
  recognition + the deterministic Rf decision between rounds (keep `_evaluate_route` /
  `recognize_tlc_plate` / mixcase recommender agent-side). Rationale: keeps the deterministic
  decision where it already works; avoids inventing a stateful pause/resume MQ protocol; makes
  prep-once / cleanup-once EXPLICIT. Cost: more MQ round-trips (acceptable — spec assumes
  single-in-flight TLC dispatch).
- ~~Q-B. The photo handover~~ → **RESOLVED: the captured-image S3 URL rides on the existing
  MQ `TaskStatusMsgPayload`** (Lab→Agent `agent.exchange` / `{task_id}.task.status`). Confirmed
  facts: (1) the robot uploads the plate photo to S3/MinIO itself and returns only the URL
  (`CapturedImage.url`); the lab persists it in `skill_results.captured_images` — no binary on
  the wire. (2) Lab→Agent task progress ALREADY flows over MQ on every step transition
  (`mq_producer.py:148`, `task_service.py:227/256`), confirmed by `docs/dataflow.md` Lane 1. The
  ONLY gap: `TaskStatusMsgPayload` carries `task_id`/`status`/`steps[]` but NO image URL
  (`task_service.py:411-433`). Fix: add the round's captured-image URL to `TaskStatusMsgPayload`
  so the agent reads it off the message it already consumes → `recognize_tlc_plate(url)`. Keeps
  one Lab→Agent channel; no extra REST round-trip.
- ~~Q-C. MVP depth for "real" `recommend_tlc_mixcase`~~ → **RESOLVED: keep the mock in L4 ONLY.**
  Boundary discipline for the whole task: the L3 TLC retry loop + deterministic Rf decision are
  built PRODUCTION-REAL — no mocks, no test-special-casing above L4. ALL fakery lives inside the
  L4 `mind_client` stub methods. Going live later = editing ONLY `mind_client.py`.
  - `recommend_tlc_mixcase` (L4 stub) becomes **history-aware**: reads `request.trials`
    observed-Rf and returns an ADJUSTED ratio (Rf below window → more polar; above → less polar).
    Real adaptation, but stays a stub (no live HTTP — the `/api/tlc/tlc_mixcase_protocol` route is
    not confirmed deployed by the external ChemEngine/Mind team; only CC/RE `recommend_param` is
    live). Research note: `recognize_tlc_plate`, `parse_experiment_materials`,
    `confirm_experiment_goal` are ALSO L4 stubs pending external routes — consistent with this rule.
  - `recognize_tlc_plate` (L4 stub) stays scripted per round/attempt index: round 1 → 0.25 (OUT),
    round 2 → 0.51 (IN) — drives deterministic retry→success in the E2E without a real vision service.
  - The two L4 stubs are **INDEPENDENT** (recognition keys off round index; mixcase adapts ratio
    from observed-Rf history) — NOT causally linked. The loop's correctness does not depend on a
    fake causal ratio→Rf model.
- Q-D. Acceptance-criteria shape + which E2E proves it.
