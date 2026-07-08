# Implement — Objective backstop (BE)

Child of `06-30-objective-stall-fix`. Read `design.md` first.

## Pre-dev

- [ ] `BIC-agent-service:trellis-before-dev` for the backend package — load
  `graphs.md`, `events.md`, `http-routes.md`.
- [ ] Read the CC pattern being mirrored end-to-end (shared authority
  `../06-30-objective-stall-fix/research/cc-consistency-pattern.md` §(a)):
  `cc.py:230-233` (complete-draft promotion) + `cc.py:281-288` (`None` allowed).
- [ ] Confirm `objective_params_form_problems_from_values` (`form_payloads.py:626`)
  is the completeness predicate — already exists, do NOT author a new one.
- R2 verb resolved: use `atomic_resolve` per `contracts.md §3c-user-initiated`
  (no open question — see design.md).

## Step 1 — R1 complete-draft promotion (the load-bearing fix)

- [ ] `objective.py`: import `objective_params_form_problems_from_values` from
  `form_payloads`.
- [ ] `objective.py:_post_route` (146-171): add the complete-draft branch (see
  design). Keep the existing terminal-tool branch first; add the
  `not last_tool_refused and no problems → emit_form` branch before `narrate`.
- [ ] `objective.py:_emit_form_node` (227-291): add the one-line `None`-allowed
  comment mirroring `cc.py:271-277`. No body change.
- [ ] Update the `_post_route` docstring (158-167): the "NO auto_* backstop"
  paragraph is now partly false — document that complete-draft promotion exists
  (06-30), auto_parse/auto_goal still absent.

### Validate Step 1
- [ ] Unit test: drive `_post_route` with a complete `objective_draft` +
  `last_tool_name=None`, `last_tool_refused=False` → `"emit_form"` (AC1).
- [ ] Unit test: incomplete draft → `"narrate"` (AC2).
- [ ] `pytest` the objective subgraph test module green.

## Step 2 — R2 REST confirm resolves the dangling decision

- [ ] `fast_path_handlers.py:handle_objective_confirm` (663-751): query the
  session's pending objective decision server-side; `atomic_resolve` (or the
  verb resolved in pre-dev) it inside the same tx as the stage advance.
- [ ] `service.py:confirm_objective` (627-673): thread the resolution (no
  client-supplied decision_id).
- [ ] No-op safety: when no pending objective decision exists, stage still
  advances (idempotent).

### Validate Step 2
- [ ] Scenario script (`scripts/`): mint objective decision → direct
  `POST /objective/confirm` → snapshot has no pending objective +
  `stage=workflow_design` (AC3).

## Step 3 — R3 prompt hardening

- [ ] `dynamic_prompts.py:393-453`: add the "drive objective ladder first, don't
  narrate a plan" rule to `_OBJECTIVE_HEADER`.

## Step 4 — Spec updates (Rule 10, same change set)

- [ ] `graphs.md` §1.5a — document the complete-draft promotion.
- [ ] `events.md` — objective row: REST confirm resolves the decision.

## Step 5 — Full-scope check

- [ ] `BIC-agent-service:trellis-check`.
- [ ] Re-run `tlc-retry-flow.spec.ts` (live) — objective leg reaches a form
  without the chemistry nudge (AC4). Use `bic-e2e-runner` if a full bench reset
  is needed.
- [ ] Confirm no `experiments.status` writes were introduced (parent out-of-scope).

## Rollback points

- Step 1 is independently revertible (pure routing add).
- Step 2 is independently revertible (handler-local).
- If R1 over-fires in live traces, gate it behind a feature check rather than
  reverting — but default is ship.

## Validation commands

```bash
cd BIC-agent-service
pytest tests/ -k objective            # subgraph unit tests
python scripts/<objective-confirm-scenario>.py   # AC3
curl -X POST http://localhost:8800/reset | jq    # bench reset before E2E
```
