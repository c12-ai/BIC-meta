# Implement — Shared-types: step-event contract

Repo: `BIC-shared-types`. All commands `uv run`. **No code until `task.py start` + Drake review.**

## Pre-flight

- [x] Version bump level confirmed: `1.1.9a1 → 1.2.0a1` (minor). [Drake, 2026-06-30]
- [ ] Re-read `AGENTS.md` "Auto-do after editing types" + the gate command list.

## Ordered checklist

1. **Add the model + field** in `bic_shared_types/experiment_task/mq/task_status.py`:
   - `from datetime import datetime`.
   - New `TaskStepEvent(BaseModel)` with fields per design.md (event_id, step_index,
     skill_type, status, occurred_at, error_message).
   - Add `step_events: list[TaskStepEvent] = []` to `TaskStatusMsgPayload` (after `steps`).
   - Add `"TaskStepEvent"` to `__all__`.
   - Docstrings consistent with the existing file tone.

2. **Regenerate derived artifacts** (per AGENTS.md — even though MQ payloads aren't in the
   JSON-schema REGISTRY, run the exports so the gate's `--check` is satisfied / proves no drift):
   - `uv run python scripts/export_json_schema.py`   (expect: no change, MQ not registered)
   - `uv run python scripts/export_ts_enums.py`        (expect: no change, no enum touched)
   - `uv run python scripts/validate_examples.py`      (expect: pass, no example references it)

3. **Version bump** → `1.2.0a1`:
   - Edit `version` in `pyproject.toml` (`1.1.9a1` → `1.2.0a1`).
   - `uv lock` in this repo.
   - Update `CHANGELOG.md` (additive: new `TaskStepEvent`, new `step_events` field).
   - Update `docs/contract-inventory.md` only if it inventories MQ payloads (check first;
     it may be HTTP-only like the schema registry).

4. **Spec update (Rule 10)** — document the contract in `.trellis/spec/` (shared-types backend
   + agent-service MQ-ingress reference): `step_events`, `TaskStepEvent`, the 4 `status` string
   values, and the "full-timeline-each-message + dedup-on-event_id" expectation.

## Validation (the AGENTS.md gate — all must pass)

```bash
uv run ruff check bic_shared_types/ scripts/ tests/
uv run ruff format --check bic_shared_types/ scripts/ tests/
uv run python scripts/validate_contracts.py
uv run python scripts/export_json_schema.py --check
uv run python scripts/validate_examples.py
uv run python scripts/export_ts_enums.py --check
uv run pytest
uv run pyright
```

## 3-repo consume check (must do before reporting done — the real risk)

```bash
# point each consumer at the new local version (path/editable or re-pin), then:
cd ../BIC-lab-service   && uv run pytest --collect-only -q   # green, no collect errors
cd ../BIC-agent-service && uv run pytest --collect-only -q   # green, no collect errors
```
If either regresses on collect → STOP, do not bump/publish, surface to Drake (this is exactly
the v1.1.4a1 failure mode).

## Risky points / rollback

- **Riskiest**: the version bump + consumer re-pin. Rollback = revert `version` + `uv.lock`,
  consumers re-pin to `1.1.9a1`. The model addition itself is pure-additive and safe to keep.
- If `export_json_schema.py --check` unexpectedly goes red, it means MQ payloads ARE somehow
  in a generated artifact — investigate before forcing; do not hand-edit generated files.

## Propagation reality (discovered at implement time)

Consumers pin shared-types by **git branch** `feat/tlc-objectlocation-on-a2`, NOT by version
number (`BIC-{lab,agent}-service/pyproject.toml [tool.uv.sources]`). So the version bump alone
does not reach them. Drake authorized: **commit on the branch + push + re-sync consumers**.
- Two commits: `4b3bc9f` (contract) + `99763dc` (version bump) — pushed to the branch.
- Re-sync each consumer: `uv lock --upgrade-package bic-shared-types` (forces new branch commit;
  `uv` caches git deps by commit). This also updated each consumer's `uv.lock`.

## Rule 10 (spec) — deferred to agent-persist child, ON PURPOSE

This child only *defines* the type in shared-types. The authoritative contract record here is the
shared-types **CHANGELOG + contract-inventory** (done). The Agent-side spec
`.trellis/spec/BIC-agent-service/backend/L2/event-ingress.md` describes how `handle_task_status`
*consumes* the payload — but consumption of `step_events` doesn't change until
`06-30-execlog-agent-persist`. Updating it now would document non-existent behavior. → that spec
edit lands WITH the agent-persist child.

## Done = all of:

- [x] Gate (8 commands) green. [sub-agent verified]
- [x] Both consumer repos `--collect-only` green. [agent 933 / lab 333, 0 collect errors]
- [x] Version bumped → 1.2.0a1 + `uv lock` + CHANGELOG + contract-inventory.
- [x] Contract committed (`4b3bc9f`) + version bump committed (`99763dc`) + pushed.
- [x] `step_events` defaults `[]`; existing `steps`/`TaskStatusStepPayload` untouched.
- [x] Rule 10: shared-types CHANGELOG/inventory updated; agent-spec edit deferred to persist child (see above).
