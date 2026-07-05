# Required Params Drive Clarification, Never Silent Default

> **STATUS: CLOSED — SUPERSEDED (2026-06-24).** This task's core requirement
> (null `lab_logistics` at confirm → agent drives `request_clarification`) was
> **superseded by Drake's 2026-06-21 ruling**, now codified as spec contract
> **I-ST-F** in `.trellis/spec/backend/L3/specialist_tools.md:196`:
> *"Lab-logistics is dispatch-gated, never completeness-gated."*
>
> `sample_cartridge_location` (CC) and `flasks` / `collect_config` (RE) are now
> **deliberately ABSENT** from `cc_params_form_problems` / `re_params_form_problems`.
> A draft missing only lab-logistics is **complete** — the form opens, the chemist
> picks the value in the modal, and confirm is accepted (no 422). Enforcement is at
> **dispatch only**: `_submit_l4` raises a fail-loud `RuntimeError` naming the missing
> field (`tools.py:510-516` CC, `:527-536` RE), and lab-service material-readiness
> returns a `400` surfaced as a `missing_materials` `TurnFailedEvent`.
>
> The 06-21 ruling explains *why* the clarification approach was abandoned: it
> created a chicken-and-egg where the SAME field gated the form meant to collect it
> (clean-bench runs showed zero `form_requested(confirm_kind='params')` rows).
>
> **The code + a passing test (`test_validate_re_params_passes_when_lab_logistics_absent`,
> `test_submit_l4_execution_fails_loud_on_missing_lab_logistics`) already implement
> the dispatch-gated design.** No code change is required for this task.
>
> Current-code verification: `research/current-code-anchors.md` (2026-06-24). The
> body below describes the PRE-06-21 world (06-16) and is retained for history only.
>
> **One latent inconsistency was surfaced but NOT actioned here** (split if wanted):
> the RE collecting_params ladder (`dynamic_prompts.py:341-345`) still instructs a
> silent default `flasks=["volume_25ml"], collect_config=[1]`, and the literal
> `"volume_25ml"` does not match the `FlaskVolume` enum (only member `ML_500="500ml"`).
> Tolerated by the dispatch carve-out (dispatch would catch a bad value), but worth a
> follow-up cleanup.

## Goal

When a **required** params field cannot be filled by the agent (the LLM couldn't
derive it, or the user gave insufficient context — both legitimate; first-shot
success is never required), the agent must drive `request_clarification` naming
the missing field and asking the chemist for it. It must NOT silently confirm
with the field null, auto-default it, hard-code a stub value, or dead-end into a
`form_validation_failed` 422.

Concrete trigger: the **CC `sample_cartridge_location` (cartridge) gap** — and the
symmetric RE `flasks` / `collect_config` gap.

**This is a BE-only task** (the clarification behavior is prompt + validate-gate
logic). The symptom appeared at the FE (422 / un-clickable confirm) but the root
behavior is agent-side. **The chemist answers the clarification via chat reply**
(types the slot id → agent extracts it via `update_cc_lab_logistics` next turn) —
so no FE form control is needed (Drake 2026-06-16). `sample_cartridge_location`
will get a dedicated selector on a separate page later; until then chat-reply is
the answer surface and it works today.

**Note — other `from_user` fields already clarify correctly.** `solvent_ratio`,
`sample_quantity`, `solvents`, `product_rf` are already in the Exit-B required
list (`dynamic_prompts.py:193`) AND caught by `build_cc_param_request`, so a null
value already drives `request_clarification`. This task is *narrowly* about
wiring the `lab_logistics` fields (cartridge / RE flasks+collect_config) into the
SAME clarify path those `from_user` fields already enjoy.

## Background — origin (task 06-13, 2026-06-15)

This gap was discovered + fully investigated during the CC→RE E2E integration
(task 06-13). It surfaced as an LLM-abandon flake: when the agent skipped
`update_cc_lab_logistics`, `sample_cartridge_location` stayed null → the E2E
hit a dead-end and only passed via auto-re-run. Drake ruled the correct behavior
and deferred the fix to this dedicated task.

Drake's ruling (memory [[project_missing_param_clarify_not_default]]): a missing
required param is NOT a bug to default away — it's a legitimate "insufficient
input" state. The agent asks; it never silently defaults. Captured as spec
contract **I-ST-F** in `.trellis/spec/backend/L3/specialist_tools.md`.

## Root cause (already pinned — do not re-investigate)

1. **The value is 100% LLM-filled** via the `update_cc_lab_logistics` tool
   (`tools.py:617`) during `collecting_params`. No deterministic backstop.
2. **The prompt makes it soft.** `dynamic_prompts.py:149` says set the cartridge
   "when known" — optional-feeling, so the LLM fills `update_cc_from_user` then
   jumps to `request_params_confirmation`, skipping logistics.
3. **It's absent from the required-field clarification set.** The required-field
   list that drives `request_clarification` (`dynamic_prompts.py:188`) covers only
   `from_user` fields (sample_quantity, solvents, ...), NOT the `lab_logistics`
   cartridge.
4. **The FE control was orphaned.** Commit `c0b5314` ("consolidate params-form
   chrome") deleted BOTH the `#cc-cartridge` editable `<Select>` in
   `CcParamsForm.tsx` AND its presence-gate line
   (`if (d.sample_cartridge_location === '') return false`). *(Historical context:
   this drove the original full-loop framing. Per Drake 2026-06-16 the FE answer
   surface is now out of scope — the chemist answers by chat reply instead — so #4
   is NOT addressed in this task; it is deferred to the separate selector page.)*
5. **The BE strictly requires it** (correct): `form_payloads.py:271-272` →
   `service.py:323-326` raises `FormValidationError` → 422. `CreateCCTaskRequest.
   sample_cartridge_location` is non-optional, no default (`task_protocol/cc.py:20`,
   6-member `CCSampleCartridgeLocation` enum). The cartridge physically routes the
   sample — it CANNOT be silently defaulted (a default slot may be consumed →
   "No sample cartridge found" at the lab).

The clarification MECHANISM already exists and matches the intent: the
`request_clarification` tool (`tools.py:825`) + the HARD RULE that every
`collecting_params` turn ends in `request_params_confirmation` OR
`request_clarification` (`dynamic_prompts.py:182`) + "if validate reports missing
fields, ask the chemist via request_clarification for exactly those fields"
(`dynamic_prompts.py:157-158`). The gap is purely that cartridge/RE-logistics are
not WIRED into the required-fields set that triggers it.

## Scope: BE-only (agent asks; chemist answers via chat)

The fix is **entirely BE/agent-side** — the behavior Drake ruled on ("missing
required param → agent clarifies") is prompt + validate-gate logic. Once the agent
asks "which cartridge slot?", the chemist **answers by chat reply** — the agent
extracts the slot id via `update_cc_lab_logistics` on the next turn (full history
rehydrated per W3). No FE control is restored in this task; the duo-panel answer
surface for cartridge is deferred to the separate selector page (Drake 2026-06-16).

## Requirements

### A. BE / agent (THE FIX)
* **Gate the field into clarification.** Add `sample_cartridge_location` (CC) and
  `flasks` / `collect_config` (RE) to the prompt's **Exit-B required-field list**
  (`dynamic_prompts.py:193` for CC; RE twin), so a null value drives
  `request_clarification` (naming the missing field) instead of
  `request_params_confirmation`. The validate gate already flags these as missing
  (`form_payloads.py:278,292-295`) — likely no validate-code change, confirm only.
  The `collecting_params` LOOP-BREAKER HARD RULE already forces exit A or B — the
  field just needs to be named in the list the LLM reads.
* **Make the prompt treat them as REQUIRED, not "when known".** Remove the soft
  framing at `dynamic_prompts.py:153` so the LLM stops skipping logistics.
* This makes the bug functionally fixed: the agent stops dead-ending into a 422
  and starts asking the chemist for the missing slot. The chemist answers by chat
  reply; the agent extracts it via `update_cc_lab_logistics` next turn.

### B. Test
* Add a BE test: a null required `lab_logistics` field (CC cartridge; RE
  flasks/collect_config) at confirm time drives `request_clarification` naming the
  field, NOT a 422 and NOT a null confirm.
* Add a BE test covering the chat-reply recovery: after the clarification, a
  chemist message carrying the slot id is extracted via `update_cc_lab_logistics`
  and the next confirm passes validation.

### Out of this task (deferred)
* **FE cartridge selector + presence-gate** (orphaned by `c0b5314`) — deferred to
  the separate selector page. NOT restored here; chat-reply is the answer surface.
* The dead E2E chemist-edit fallback (`cc-re-chained-flow.spec.ts:365-373`) stays
  dead for now (no FE control to revive); not in scope.

## Acceptance Criteria (evolving)

* [ ] Agent: a null `sample_cartridge_location` at confirm time drives
      `request_clarification(question naming the field)`, NOT a null confirm / 422.
* [ ] Same for RE `flasks` / `collect_config`.
* [ ] Prompt no longer frames cartridge as "when known" — it is in the Exit-B
      required list alongside the `from_user` fields.
* [ ] Chat-reply recovery: a chemist message with the slot id is extracted via
      `update_cc_lab_logistics`; the subsequent confirm passes validation.
* [ ] I-ST-F contract satisfied; spec updated if behavior contract shifts (Rule 10).

## Out of Scope

* Silent defaults / stub cartridge values (explicitly rejected by Drake).
* Any FE change — the cartridge selector / presence-gate is deferred to the
  separate selector page (Drake 2026-06-16); chat-reply is the answer surface.
* Reviving the dead E2E chemist-edit fallback (no FE control to target yet).

## Technical Notes (key file:line — from the 06-13 investigation)

* Agent fill tool: `app/runtime/graphs/specialists/tools.py` (`update_cc_lab_logistics`,
  `request_clarification`). Line numbers drift — grep by name.
* Prompt (CC): `app/runtime/middleware/dynamic_prompts.py:153` (soft "when known"),
  `:157-158` (clarification rule), `:182` (LOOP-BREAKER HARD RULE), `:188-194`
  (Exit-B required-field list — cartridge missing here; `from_user` fields present).
  RE twin lives in the same file — find the RE phase-instruction block.
* Validate gate (already flags the field): `app/events/form_payloads.py:278` (CC
  cartridge), `:292-295` (RE flasks/collect_config). `solvent_ratio` is caught by
  `build_cc_param_request` (`:223`) — the pattern this task mirrors for logistics.
* BE 422 source (the dead-end being eliminated): raise at `app/session/service.py:323-326`.
* Contract type: `bic_shared_types task_protocol/cc.py:20`, `robot_protocol/enums.py:116-124`
  (CCSampleCartridgeLocation, 6 slots, seeded default bic_09B_l4_001).
* Spec contract: `.trellis/spec/backend/L3/specialist_tools.md` I-ST-F.
