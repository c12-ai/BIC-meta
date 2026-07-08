# BE log evidence — model-swap regression classification

- **Query**: classify which of M1 (schema drift) / M2 (terminal re-call loop) / M3 (reasoning chain capacity) / M4 (admittance false-rejection) fires per failing E2E spec + Drake's manual test
- **Scope**: internal (BE logs at `app/logs/app.log{,.1,.2}`, source files cited)
- **Date**: 2026-06-04
- **Logs used**:
  - `app.log` (15:14 → 17:45) — Drake's manual test session `191aae53-...`
  - `app.log.1` (14:32 → 15:20) — tail of v4 E2E run
  - `app.log.2` (... → 14:32) — head of v4 E2E run
  - `error.log` — read; no relevant errors on 2026-06-04 between reset windows

## Identification of the v4 E2E run window

- Two `POST /reset` to `app:8800` bracket the v4 run: **14:31:45** (start fence) and **15:12:20** (next-run start fence).
- All `HeadlessChrome/148.0.7778.96` sessions started AFTER 14:31:45 belong to v4.
- Test-to-session mapping (resolved from the user-message text seen in the admittance/intent LLM POSTs):

  | Session id (prefix) | First user message | Test spec |
  |---|---|---|
  | `e123fcc9-...` | `For RXN-001 purification: run a routine column chromatography to separate fractions, then concentrate the combined target fractions via rotary evaporation.` | **cc-re-chained-flow.spec.ts:124** (only spec sending this prompt) |
  | `8224885f-...` | `Run column chromatography on compound RXN-001.` | **persist-bubbles-hard-refresh.spec.ts:111** (test 2 — decision-resolved bubble — waits for `Reject ... re-plan`; the other 2 sessions with the same prompt below got the form fine) |
  | `08d07568-...` | `Run column chromatography on compound RXN-001.` | persist-bubbles test 1 (passes) OR task-progress-stream — see Cross-cutting |
  | `2fcdd0c3-...` | `Run column chromatography on compound RXN-001.` | the other of persist-bubbles test 1 / task-progress-stream |
  | (others) | (various) | passing specs |

  Only **08d07568** and **2fcdd0c3** survive into the spec-form phase (both reach plan_confirmed). One of them is `task-progress-stream.spec.ts:70` (which times out on `Sample amount`), and the other is the *passing* persist-bubbles test 1. Both show the same symptom (no `form_requested` for spec), so they are interchangeable for diagnosis — but the persist-bubbles test 1 line 39 passed in v4, so by elimination one of them is task-progress-stream and the other paused at plan-confirm WITHOUT entering cc (FE wait done as soon as Confirm Plan button appears). Diagnosis below treats both as the task-progress-stream witness.

## Manual test (Drake) — post-Confirm-Plan "Request rejected"

- **Session id**: `191aae53-2ec0-41b3-9915-9ecccf8e08bd`
- **User agent**: `Chrome/148` (NOT HeadlessChrome — real browser, not playwright)
- **Timeline of events around the rejection**:

  | Time | Event |
  |---|---|
  | 15:13:20.506 | `user_message_submitted` seq=1 (initial planner turn) |
  | 15:13:31.770 | `form_requested` seq=5 (plan form) |
  | 15:13:41.697 | `turn_completed` seq=7 (planner narrate) |
  | **15:20:27.680** | `plan_confirmed` seq=8 (Drake clicked Confirm Plan) |
  | 15:20:27.730 | `turn_started` seq=12 (cc dispatch turn 1) |
  | 15:20:40.598 | `text_done` seq=13 — cc specialist output TEXT, no spec form |
  | 15:20:40.617 | `task_created` seq=14 — cc plan step recorded |
  | 15:21:35.066 | `text_done` seq=15 + `turn_completed` seq=16 |
  | 15:21:35.087 → 15:23:51.913 | 4 more cc turns alternating `text_done` / `task_created`, never `form_requested` |
  | (idle 8 minutes) | Drake stares at chat, no spec form ever appears |
  | **15:31:27.849** | `user_message_submitted` seq=33 — Drake types `Draft a CC Spec for me` |
  | 15:31:27.912 | admittance judge LLM POST sent to `qwen3.6-flash-2026-04-16` with this text |
  | 15:31:29.360 | `admittance_rejected` seq=35 ← **the "Request rejected" the FE displayed** |
  | 15:40:39.559 | Drake follow-up `Why you rejected so ?` → also `admittance_rejected` at 15:40:40.691 |

- **Verdict**: **M4 — Qwen admittance-judge false-rejection** fired.
  - The judge LLM was given a system prompt that defines "Admit when on-topic for a chemistry-lab agent (synthesis, separation / purification, experiment status, lab-result analysis, chemistry questions)". The user said `Draft a CC Spec for me` — *CC = column chromatography*, the canonical chemistry purification operation in this codebase. This is unambiguously on-topic.
  - qwen3.6-flash-2026-04-16 returned `verdict='reject'` for it. Same model also rejected the follow-up `Why you rejected so ?` (a meta-question that pa/gpt-5-mini would likely admit, since complaining about a refusal is on-topic for the same conversation).
  - Confirmed Drake's manual-test root-cause hypothesis exactly (PRD §"Manual-test finding"). The reception code already ruled out plan-confirm-itself, GuardrailMiddleware, and SubmitGuardrail (PRD lines 122-134).
  - **Important secondary finding**: between 15:20:27 (plan_confirmed) and 15:31:27 (Drake's first follow-up message), the cc specialist ran 5 turns producing **only text + task_created** — never `form_requested`. The spec form NEVER rendered. Drake's `Draft a CC Spec for me` is **a USER WORKAROUND** to the missing spec form; M4 then made the workaround fail too. **This means M3 (or some other cc tool-skip mechanism) is ALSO live in Drake's manual test, not just M4.** Drake's chat would have failed even without M4 because the spec form never appeared post-plan-confirm.
- **Supporting log excerpts (line numbers in `app.log`)**:
  - L9139 `user_message_submitted` for `Draft a CC Spec for me`
  - L9157 admittance LLM POST body (system prompt + user text shown verbatim)
  - L9208 `admittance_rejected` event (seq=35)
  - L9209 `text_done` seq=36 (the user-facing rejection text — content NOT preserved in BE app.log; verdict reason / `user_facing_message` are emitted on the wire but not captured by loguru. To recover them, hit FE devtools or add a structured log line in `user_admittance.py:113-122` next time).

## E2E v4 run — cc-re-chained-flow.spec.ts (session `e123fcc9-...`)

- **Timeline (collated from app.log.2 and app.log.1)**:

  | Time | Event |
  |---|---|
  | 14:31:53.696 | `user_message_submitted` seq=1 (`For RXN-001 purification: ...`) |
  | 14:31:55.5xx | planner re-call loop visible — see Cross-cutting M2 evidence below |
  | 14:32:07.207 | `plan_proposed` seq=24 |
  | 14:32:07.212 | `form_requested` seq=25 (plan form) |
  | 14:32:07.716 | `plan_confirmed` seq=26 (FE auto-clicked Confirm Plan) |
  | **14:32:07.716 → 14:32:24.504** | cc react-agent turn 1: **0 tool_call_delta, 0 tool_result, lots of text_delta**, ending with `text_done` seq=49 + `turn_completed` seq=50 |
  | 14:32:24.520 | `turn_started` seq=51 (cc react-agent turn 2 — re-entered) |
  | 14:32:35.778 (log1) | `text_done` seq=65 — text only again |
  | 14:33:12.481 | `text_done` seq=86 + `turn_completed` seq=87 |
  | **never** | `form_requested` for spec / param |

- **Specialist tool-call sequence (post plan_confirm)**: NONE. Across both cc react turns, e123fcc9 emitted **1 tool_result total in the entire session** — and that single result was the planner's `request_plan_confirmation` at 14:31:59. After plan_confirm, the cc specialist produced **zero** `update_cc_spec`, `validate_cc_spec`, `recommend_cc_params`, or `request_spec_confirmation` calls. It just narrated text.

- **Verdict**: **M3 — Reasoning chain length capacity gap, extreme form (zero-tool-call)**.
  - The cc system prompt explicitly says (verbatim from the LLM POST at `app.log.1:2316`): *"Current phase: collecting_spec. 1. Call `update_cc_spec(fields=...)` ... 2. Call `validate_cc_spec()`. 3. Call `request_spec_confirmation()` (no args) exactly once and STOP."* qwen3.6-flash ignored step 1-3 entirely and went straight to free text.
  - Architecture context that makes this worse: `rehydrate_specialist_state` (`app/runtime/graphs/specialists/rehydrate.py:78-104`) gives cc react **only** `conversation_history + harness phase snapshot SystemMessage`. The cc react sees **no plan_confirmed signal, no echo of the user's original request, no carry-over from planner state** — just `current_phase: collecting_spec` + the system prompt. Across this conversational vacuum the model defaults to chat. (See raw cc-specialist messages list at `app.log.1:2316` parsed in research — only 2 `role:` entries, both `system`.)
  - **Why M3 not M1**: no `pydantic.ValidationError`, no `ToolErrorHandlingMiddleware` schema failure — there's literally no tool call to fail. The drafts are never populated because no `update_*` tool is ever called.
  - **Why M3 not M2**: M2 = same tool called 3+ times in a row. Here it's the opposite — *0* tool calls. The model just doesn't enter the tool ladder.

- **Supporting log excerpts** (in `app.log.1` unless noted):
  - `app.log.2:51823-51927` — plan_proposed → form_requested → plan_confirmed for e123fcc9
  - `app.log.1:2316` — first cc-specialist LLM POST after plan_confirm; full request body shows `messages` = [cc system prompt, phase snapshot] only, NO user history
  - `app.log.2:56832-56836` — turn 1 text_done + turn_completed + turn 2 turn_started, no form_requested
  - `app.log.1:9499-9504` — final text_done + turn_completed for e123fcc9

## E2E v4 run — persist-bubbles-hard-refresh.spec.ts:111 (session `8224885f-...`)

- **Timeline**:

  | Time | Event |
  |---|---|
  | 14:32:11.012 | `user_message_submitted` seq=32 (`Run column chromatography on compound RXN-001.`) |
  | 14:32:11.019 | `turn_started` seq=33 |
  | 14:32:16.958 | `tool_result` seq=41 (planner `request_plan_confirmation` #1) |
  | 14:32:52.081 | `tool_result` seq=77 (#2) |
  | 14:32:52.104 | `tool_result` seq=78 (#3) |
  | 14:32:52.110 | `tool_result` seq=79 (#4) |
  | 14:33:32.572 | `tool_result` seq=92 (#5) |
  | 14:33:54.162 | `tool_result` seq=97 (#6) |
  | 14:33:59.931 | `tool_result` seq=98 (#7) |
  | 14:34:02.989 | `plan_proposed` seq=99 |
  | 14:34:02.997 | `form_requested` seq=100 |
  | 14:34:08.794 | `turn_completed` seq=101 — planner-narrate finally finishes |

- **Verdict**: **M2 — Terminal-tool re-call loop in the planner**, *still alive after the parent task's mitigation*.
  - 7 successive `request_plan_confirmation` calls before the planner gave up looping and let `_post_react_route` route to `emit_form`. End-to-end from user message to plan_proposed: **111 seconds**. FE's `PLAN_PROPOSE_TIMEOUT_MS=90_000` (`persist-bubbles-hard-refresh.spec.ts:36`) fires at **14:33:41** — 21 seconds before plan_proposed actually emits. By the time the form lands, the FE assertion has already failed.
  - This contradicts a parent-task assumption recorded in `prd.md:154-165` H2 ("recursion_limit=25 cap is planner-only"). The cap is planner-only AND it's not enough — Qwen still loops up to ~7 times within the cap. The parent task's "thinking prefix + recursion_limit=25" mitigation reduces but doesn't eliminate planner M2 with qwen3.6-flash.
  - Direct evidence of the re-call loop is **visible in the planner's LLM-POST conversation history** (e.g. `app.log.2:52770` for a sibling session at 14:32:10 shows the chat history accumulating 3 `request_plan_confirmation` tool_calls in a row with `plan_confirmation_requested` ToolMessages in between — the exact pattern documented at `plan_subgraph.py:236-239`).

- **Supporting log excerpts**:
  - 7 `tool_result` events listed above span 14:32:16 → 14:33:59 (timing speaks for itself — see line numbers in command output)
  - `app.log.2:52770` — sibling-session planner LLM POST body with 3 prior request_plan_confirmation tool calls in `messages` (concrete proof of the misread-ack pattern)

## E2E v4 run — task-progress-stream.spec.ts:70 (sessions `08d07568-...` and/or `2fcdd0c3-...`)

Both sessions exhibit the same shape; treating them jointly. The FE-side cause of the timeout on `Sample amount` is identical regardless of which one is the task-progress-stream session and which is persist-bubbles test 1.

- **Timeline (sample: `08d07568-...`)**:

  | Time | Event |
  |---|---|
  | 14:32:09.239 | `user_message_submitted` seq=27 |
  | 14:32:12.347 | `tool_result` seq=34 (planner #1) |
  | 14:32:16.427 | `tool_result` seq=38 (planner #2) |
  | 14:32:25.472 | `plan_proposed` seq=53 |
  | 14:32:25.477 | `form_requested` seq=54 |
  | 14:32:25.836 | `plan_confirmed` seq=55 (FE auto-Confirm) |
  | **14:32:31.353** | `text_done` seq=59 + `turn_completed` seq=60 (cc turn 1 — text only) |
  | 14:32:31.364 | `turn_started` seq=61 (cc turn 2) |
  | 14:32:41.894 | `text_done` seq=68 (text only) |
  | 14:32:41.918 | `task_created` seq=69 (cc plan step record only) |
  | 14:33:51.517 | `text_done` seq=95 + `turn_completed` seq=96 |
  | **never** | `form_requested` for spec |

  Event-kind histogram for `08d07568` in log1 (post plan_confirm):
  ```
  form_requested:    1   (this was the plan form before confirm; nothing for spec)
  plan_confirmed:    1
  plan_proposed:     1
  task_created:      1
  text_delta:      105
  text_done:         3
  tool_call_delta:   0   ← no cc tool calls AT ALL
  tool_result:       0
  ```

  `2fcdd0c3` is the same pattern (105 text_delta, 0 tool_call_delta in cc phase, 3 text_done across 3 cc turns, never any `form_requested` for spec). See command output for the per-session histograms.

- **Verdict**: **M3 — Reasoning chain length capacity gap (zero-tool-call form)** in the cc specialist, identical to e123fcc9.
  - Same root cause: cc react sees only the system prompt + phase snapshot, no plan context, no user message echo (per `rehydrate_specialist_state`). qwen3.6-flash defaults to chat instead of the 5-step ladder.

- **Supporting log excerpts**:
  - `app.log.1:196-274` for the 08d07568 plan_proposed → plan_confirmed transition
  - `app.log.1:1391-14140` showing the sequence of post-plan_confirm text_done events with NO interleaved form_requested

## Cross-cutting observations

- **All three E2E specs hit the same family of mechanisms, but split across plan-phase and cc-phase**:
  - `persist-bubbles-hard-refresh.spec.ts:111` = **M2** (planner re-call loop, never gets to cc phase before timeout)
  - `cc-re-chained-flow.spec.ts:124` = **M3** (cc specialist post-plan_confirm produces ZERO tool calls)
  - `task-progress-stream.spec.ts:70` = **M3** (same)
- **Drake's manual symptom is M4 layered on top of M3**. After Confirm Plan he sat watching the cc specialist generate 5 turns of text-without-form for ~3.5 minutes, then typed a clarifying message that the M4 admittance judge then rejected. The PRD §"Manual-test finding" hypothesis was M4-only; the logs show M3 was already broken silently in the same session before M4 fired.
- **The cc specialist's input shape change is the load-bearing mechanism for M3**. Both pa/gpt-5-mini and qwen3.6-flash see the same cc system prompt; the question is whether the model follows a 3-step instruction ladder *without seeing any user message echoed in `messages`*. pa/gpt-5-mini does; qwen3.6-flash doesn't. This isolates the failure to **instruction-following over phase-snapshot-only context**, which is a tighter framing than the PRD's "function-call schema adherence".
- **The parent task's planner M2 mitigation (recursion_limit=25 + thinking prefix in `plan_subgraph.py:236-239`) is partially effective**: planners that loop 2-3 times still recover; planners that loop 7 times push past the FE timeout. Removing the cap entirely would only make this worse for `persist-bubbles:111`.
- **M1 ruled out across all witnesses**: no `pydantic.ValidationError` for `CCBeginSpec` / `CCUserParams` / `CCUserInput` anywhere in `error.log` or `app.log*` on 2026-06-04. There's an old ValidationError from 2026-05-30 in error.log but it's pre-swap and unrelated.
- **A possible 5th mechanism, not in the PRD: "specialist sees empty conversation_history"**. The cc react agent's `messages` list at call time contains only 2 `role: system` entries (cc system prompt + phase snapshot) — no `HumanMessage` carrying the original user request. If `ctx.conversation_history` is supposed to be non-empty here (per `rehydrate.py:35-75`), there may be a bug where it isn't being populated for FORM_CONFIRM(plan)-initiated cc dispatches. Worth verifying whether pa/gpt-5-mini was relying on something other than ctx.conversation_history to know what to do (e.g. an injected user-restate system message that has since been removed). This is **strictly orthogonal to model choice** and may be the actual fix surface.

## Caveats / Not found

- The admittance judge's `reason` and `user_facing_message` fields are emitted on the SSE wire but **not captured in `app.log`** (only `kind=admittance_rejected` with session_seq is logged). To recover them next time, add a `logger.info(...)` in `user_admittance.py:113-122` carrying the `verdict.reason` and `verdict.user_facing_message` strings. For this research the verdict is M4 by virtue of (a) user_text being unambiguously chemistry-on-topic and (b) the broadcaster firing `admittance_rejected`.
- I could not 100% disambiguate which of `08d07568` and `2fcdd0c3` is `task-progress-stream.spec.ts` vs `persist-bubbles-hard-refresh.spec.ts:39` (test 1, which passed). Both sessions exhibit the M3 cc-tool-skip symptom. If `persist-bubbles:39` is one of them, the test passed because that test only waits for the **plan-confirm** flow (`confirmPlanBtn`) which fires correctly at 14:32:25 — it never enters the cc phase, so the cc M3 failure is invisible to that test. The other session is the `task-progress-stream` failure.
- The session_seq for some events is `None` (e.g. `reasoning_delta`); these are streaming-only events that don't anchor the wire-level sequence, but they're useful as proxy progress signals.
- Reading the parsed `messages` list from a Python `_build_request` log line via shell regex is fragile (single quotes inside tool descriptions confuse the matcher). The "messages had only 2 system entries" claim was verified by counting `'role':` substrings outside tool descriptions, not by a full JSON parse. If anyone wants a clean parse, dump the request via `json.dumps` in `infrastructure/llm_client.py` and re-run.
