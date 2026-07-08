# Research: current-code anchors for "required lab_logistics param → clarify, not silent-default / 422"

- **Query**: Pin EXACT current-code anchors (file:line + quote) for a BE-only task in `BIC-agent-service`. PRD is stale (06-16); code refactored since (branch `feat/shared-types-v1-1-6a1-cc-re-migration`). Verify everything vs CURRENT code on disk.
- **Scope**: internal (BE), plus pinned shared-types package + spec
- **Date**: 2026-06-24
- **Branch**: `feat/shared-types-v1-1-6a1-cc-re-migration`
- **shared-types pin**: `bic-shared-types==1.1.6a1` (uv.lock rev `v1.1.6a1`, git commit `51c70c49…`), checkout on disk: `/Users/drakezhou/.cache/uv/git-v0/checkouts/e89807eb86353b73/51c70c4/bic_shared_types/`

> NOTE on task dir: the active task resolved by `task.py current` is
> `06-15-required-params-drive-clarification-not-silent-default` (state: stale,
> session-fallback). The dir name in the dispatch prompt
> (`06-15-clarify-missing-lab-logistics`) does NOT exist; I wrote here under the
> resolved task. Flagging so the parent can confirm the intended task dir.

> **MAJOR PRD DRIFT (overarching):** the PRD repeatedly cites `app/events/form_payloads.py` for the CC/RE *validate gate* and `build_cc_param_request`. Those lines now hold TLC code or pure builders. The **actual validate functions are tools in `app/runtime/graphs/specialists/tools.py`**, the form-completeness helpers live in `form_payloads.py` but at different line numbers, and the **missing-lab-logistics detection lives in the DISPATCH path (`_submit_l4`), not in the validate/confirm path at all** — by deliberate design (Drake's 2026-06-21 "dispatch-gated, never completeness-gated" ruling). This reshapes the whole task: lab_logistics is intentionally absent from the completeness gate, so it never trips the 422 path; it raises a fail-loud `RuntimeError` at submit instead. See items 1–3.

---

## Findings (by the 8 numbered items)

### 1. CC validate gate (+ missing-`sample_cartridge_location` detection + `build_cc_param_request`)

PRD claimed `form_payloads.py:278` validate + `build_cc_param_request` ~`:223`. **WRONG** — those lines now hold TLC code. Current anchors:

- **(a) CC validate tool** — `app/runtime/graphs/specialists/tools.py:1081-1089`
  ```python
  def validate_cc_params(
      state: Annotated[SpecialistState, InjectedState],
      tool_call_id: Annotated[str, InjectedToolCallId],
  ) -> Command:
      ...
      return _validate_params_tool_result(state, tool_call_id, cc_params_form_problems_from_values)
  ```
  Backing completeness helper: `app/events/form_payloads.py:478 def cc_params_form_problems(form: CCParamsForm)` and the raw-dict wrapper `app/events/form_payloads.py:519 def cc_params_form_problems_from_values(values)`.

- **(b) `sample_cartridge_location` missing-ness detection** — NOT in the validate gate. By design it is **dispatch-gated** (`form_payloads.py:485-491` comment: *"Lab-logistics (`sample_cartridge_location`) is deliberately NOT a completeness requirement … enforced only at DISPATCH time"*). The actual missing check is in `_submit_l4`:
  - `app/runtime/graphs/specialists/tools.py:510-512`
    ```python
    cartridge = cc_form.lab_logistics.sample_cartridge_location
    if cartridge is None:
        cc_problems.append("lab_logistics.sample_cartridge_location: missing")
    ```
  - raises at `tools.py:513-516`: `raise RuntimeError(f"submit_l4_execution: params not dispatchable: ...")`

- **(c) `build_cc_param_request` equivalent** — `app/events/form_payloads.py:422 def build_cc_param_request(from_user: CCFromUserFields) -> CCParamRequest`. (This is the recommend gate, NOT a "CC param request" for dispatch. The dispatch request is `CreateCCTaskRequest(...)` built inline at `tools.py:517-521`.)

### 2. RE validate gate (+ missing-`flasks`/`collect_config` detection + `build_re_param_request`)

PRD claimed `form_payloads.py:292-295`. **WRONG**. Current anchors mirror CC:

- **(a) RE validate tool** — `app/runtime/graphs/specialists/tools.py:1935 def validate_re_params(...)`. Backing helper: `app/events/form_payloads.py:503 def re_params_form_problems(form: REParamsForm)`; raw-dict wrapper `form_payloads.py:534 def re_params_form_problems_from_values(values)`.

- **(b) `flasks`/`collect_config` missing detection** — again dispatch-gated, in `_submit_l4`:
  - `app/runtime/graphs/specialists/tools.py:527-532`
    ```python
    flasks = re_form.lab_logistics.flasks
    collect_config = re_form.lab_logistics.collect_config
    if flasks is None:
        re_problems.append("lab_logistics.flasks: missing")
    if collect_config is None:
        re_problems.append("lab_logistics.collect_config: missing")
    ```
  - raises at `tools.py:533-536` (same `RuntimeError`). Dispatch request built at `tools.py:537-542` `CreateRETaskRequest(..., flasks=flasks, collect_config=collect_config)`.

- **(c) `build_re_param_request`** — `app/events/form_payloads.py:441 def build_re_param_request(from_user: REFromUserFields) -> REStandaloneParamRequest`.

### 3. The 422 source (`FormValidationError`)

PRD claimed `app/session/service.py:323-326`. **CLOSE but off** — the doc-comment is near there; the actual `raise` sites are :329 / :344 / :349.

- **Exception type def** — `app/core/exceptions.py:524 class FormValidationError(ApplicationError)` (ctor takes `problems: list[str]`, exposes `self.problems`).
- **Raised (params confirm gate)** — `app/session/service.py` inside `_validate_params_confirm` (declared ~:307):
  - `:329` raise when specialist kind unresolvable
  - `:344` raise on unsupported kind
  - `:349` `raise FormValidationError(problems)` — the real completeness 422 (`problems` from `cc_/re_/tlc_params_form_problems_from_values` at :337-347)
- **422 mapping** — `app/core/exception_handlers.py:274-281`
  ```python
  @app.exception_handler(FormValidationError)
  async def form_validation_error_handler(request, exc):
      return JSONResponse(status_code=422,
          content={"error_code": "form_validation_failed", "details": exc.problems})
  ```
- **KEY**: because lab_logistics is excluded from `*_params_form_problems` (item 1b/2b), a draft missing ONLY lab_logistics is "complete" → confirm is accepted (no 422). The 422 path is therefore NOT where a missing cartridge/flask is caught today. The dead-end the task wants to prevent is the dispatch-time `RuntimeError` (tools.py:513-516 / 533-536) + lab-service material-readiness 400 — NOT this 422.

### 4. `request_clarification` tool

PRD claimed `tools.py:825`. **WRONG line**. There are THREE identical defs (one per factory: CC, RE, objective):

- CC factory — `app/runtime/graphs/specialists/tools.py:1092`
- (third occurrence) `:1379`
- RE factory — `:1722` (and another at `:1954`)

Signature (CC, representative):
```python
@tool
def request_clarification(question: str) -> str:
    """Call this when a required from_user field is genuinely unknown and
    not extractable from chat — ask the chemist for it instead of guessing."""
    return f"clarification requested: {question}"
```
Phase-agnostic, no emit, does not exit phase. Spec authority: `specialist_tools.md` §2 Table A row (line 47) + I-ST-F.

### 5. `update_cc_params` / RE update tools

PRD referenced an old `update_cc_lab_logistics`. **CONFIRMED GONE.** Current:

- **CC** — `app/runtime/graphs/specialists/tools.py:891 def update_cc_params(fields: CCParamsUpdate, ...)`. ONE merged tool; `CCParamsUpdate` has optional `from_user` + `lab_logistics` members. Cartridge written via `update_cc_params(fields={lab_logistics: {sample_cartridge_location: ...}})` (docstring :903 *"fields.lab_logistics: sample_cartridge_location. Never sent to Mind."*).
- **RE — TWO tools (baseline pair, NOT merged):**
  - `app/runtime/graphs/specialists/tools.py:1815 def update_re_from_user(fields: REFromUserFields, ...)` (volume_ml / solvents / solvent_ratio)
  - `app/runtime/graphs/specialists/tools.py:1843 def update_re_lab_logistics(fields: RELabLogistics, ...)` (flasks / collect_config) — docstring :1849-1859.
  - So the RE write tool name is **`update_re_lab_logistics`** (the name the prompt mentioned IS current for RE; only the CC `update_cc_lab_logistics` was removed in favor of `update_cc_params`).

### 6. Contract types (shared-types v1.1.6a1)

PRD claimed `task_protocol/cc.py:20` + `robot_protocol/enums.py:116-124`. Path partly drifted (`task_protocol` → `experiment_task/http`), enum line CONFIRMED.

- **CC dispatch request** — `experiment_task/http/cc.py:17 class CreateCCTaskRequest(CreateTaskRequestBase)`; field at **`:22`**:
  ```python
  sample_cartridge_location: CCSampleCartridgeLocation = Field(description="样品柱在备料区的位置")
  ```
  → **non-optional, NO default.** Constructing the request with it absent raises pydantic `ValidationError`. (This is why `_submit_l4` must null-check first and raise its own fail-loud RuntimeError before reaching here.)
- **CC enum** — `robot_protocol/enums.py:116 class CCSampleCartridgeLocation(StrEnum)` (6 members `BIC_09B_L4_001..006`, lines 119-124). Matches PRD's `:116-124`.
  - ⚠️ a SEPARATE robot-skill model DOES default it: `robot_protocol/skills/cc.py:82 sample_cartridge_location: CCSampleCartridgeLocation = CCSampleCartridgeLocation.BIC_09B_L4_002`. That is the robot SkillCommand, NOT the Apex `CreateCCTaskRequest` — do not confuse the two; the dispatch contract (`CreateCCTaskRequest`) has NO default.
- **RE dispatch request** — `experiment_task/http/re.py:17 class CreateRETaskRequest(CreateTaskRequestBase)`; fields at `:23` `flasks: list[FlaskVolume]` and `:26` `collect_config: list[int]` → **both non-optional, NO default.**
- **RE enum** — `robot_protocol/enums.py:138 class FlaskVolume(StrEnum)` — single member `ML_500 = "500ml"` (:141). (NB: the RE update-tool docstring at tools.py:1856 says `"500ml"`; some L3 prompt text says `volume_25ml` — that's an L3 prompt/ladder string, not the enum.)

### 7. Spec contract I-ST-F

PRD claimed `.trellis/spec/backend/L3/specialist_tools.md`. **CONFIRMED — path exists.** I-ST-F is at `.trellis/spec/backend/L3/specialist_tools.md:196`. Verbatim head:

> **I-ST-F** **Missing-required-param → clarify, never default** (task 06-13, Drake's ruling 2026-06-15). A required params field that the agent could not fill … MUST drive the agent to `request_clarification` naming the missing field … It MUST NOT: silently `request_params_confirmation` with the field null, auto-default the value, hard-code a stub value, or dead-end into a `form_validation_failed` 422 …

Key clause for THIS task (same line, later): *"**Lab-logistics is dispatch-gated, never completeness-gated (Drake's ruling 2026-06-21).** `sample_cartridge_location` (CC) and `flasks`/`collect_config` (RE) … are deliberately ABSENT from `cc_params_form_problems` / `re_params_form_problems`, so a draft missing only lab-logistics is **complete** — the form opens, the chemist picks the value in the modal, and confirm is accepted (no 422). Enforcement is at dispatch only: `_submit_l4` raises a fail-loud `RuntimeError` naming the missing field (Rule 9), and lab-service material-readiness returns a `400` …"*

> ⚠️ TENSION TO SURFACE: I-ST-F's general rule says required missing params MUST drive `request_clarification` (never dead-end), but its lab-logistics clause says lab-logistics is dispatch-gated and *intentionally* absent from the completeness gate (so it relies on the modal + dispatch RuntimeError, NOT clarification). The task ("agent must drive request_clarification for null lab_logistics at confirm time") therefore CONFLICTS with the current spec's lab-logistics carve-out. This is a spec/intent decision the parent must reconcile (Rule 5 + Rule 10) before implementing — do not silently pick one.

### 8. Existing tests to mirror

All under `tests/unit/test_specialists_tools.py` (BE unit). Most relevant:

- `:904 def test_validate_cc_params_fails_when_recommended_missing` — validate-gate failure-naming pattern.
- `:929 def test_validate_re_params_passes_when_lab_logistics_absent` — **directly encodes the current "lab-logistics is NOT completeness-gated" behavior**; any change to clarify-on-missing-lab-logistics must update/replace this test.
- `:957 def test_validate_re_params_passes_on_complete_draft`
- `:1146 async def test_submit_l4_execution_fails_loud_on_missing_recommended`
- `:1172 async def test_submit_l4_execution_fails_loud_on_missing_lab_logistics` — asserts `pytest.raises(RuntimeError, match="lab_logistics")` + `lab.submit_task.assert_not_awaited()`. This is the current dead-end behavior the task wants to replace with clarification.
- `:290 def test_request_params_confirmation_lenient_about_missing_recommended` + `:366 def test_re_request_params_confirmation_refuses_on_missing_draft` — confirm-tool refusal/lenience patterns.
- `:452 def test_update_cc_params_merges_lab_logistics_section_and_emits_full_draft` + `:522 def test_update_re_from_user_and_lab_logistics_write_state` — write-tool patterns.
- `request_clarification` itself has **NO dedicated behavior test** today — only registry-presence assertions (`:591`, `:601`, `:614`, `:646`, `:678`). New tests would be net-new here.
- 422 / `FormValidationError` confirm-path tests live in `tests/unit/test_session_service_submit_form_confirm_persist.py` and `..._race.py` (mirror these for any confirm-path change).

## Caveats / Not Found

- Active task dir is `06-15-required-params-drive-clarification-not-silent-default`, not the `06-15-clarify-missing-lab-logistics` named in the prompt. Confirm intended dir.
- The pre-pinned CC prompt anchors were re-verified against current `dynamic_prompts.py`: CC ladder "when known" at `:174` and `:180`; exit-B clarify list at `:213-216` names only from_user fields (sample_quantity, solvents, solvent_ratio, product_rf) — `sample_cartridge_location` is absent. Matches the dispatch info.
- I did NOT re-verify the RE-prompt ladder lines (:341-345 / :373-374) — pre-pinned by the dispatcher and out of scope per instructions.
- shared-types is a git checkout in the uv cache (read-only); `experiment_task/http/cc.py` and `re.py` are the dispatch contracts, `robot_protocol/skills/*.py` are the robot SkillCommands (different defaults — see item 6 warning).
