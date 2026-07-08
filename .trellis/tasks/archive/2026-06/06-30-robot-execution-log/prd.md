# Detailed robot execution log (robot to FE)

## Goal

Give the chemist a **step-level execution timeline** for a trial: what the robot/lab
did, in order, with status transitions, timestamps, and error context — surfaced in
the portal workspace. Today the chemist only sees the *latest* task status and the
*current* step; the historical step-by-step trace never crosses the Lab→Agent
boundary even though LabService already records it.

## Source of truth (why this is "forward + surface", not "generate")

LabService **already records** fine-grained step events in its `EventLog` table
(`app/data/models/event.py`): `STEP_STARTED`, `STEP_COMPLETED`, `STEP_FAILED`,
`STEP_WAITING`, plus `TASK_*` events, each with `old_state` / `new_state` JSONB and a
timestamp. The detail is lost at the **Lab→Agent egress** (`TaskStatusMsgPayload`
ships only current status + a flat per-step status, no historical timeline).

Therefore: the robot needs **no new telemetry**. Scope is forwarding LabService's
existing step events across the boundary, persisting them durably on the Agent side,
and rendering them in the portal.

## Scope decisions (locked with Drake, 2026-06-30)

- **Reach**: all the way to FE — chemist-facing feature.
- **Granularity**: **step-level** only (1:1 with LabService `EventLog` STEP_* events).
  Action/sub-step micro-actions (move cartridge → insert column …) are **OUT** — the
  robot does not emit them today; that would be a separate, robot-blocked feature.
- **Entity state snapshots** (before/after equipment/material state) are **OUT of MVP**
  — revisit as a follow-up if chemists ask for it.

## Requirements

- R1. A trial's execution log is an **append-only, ordered timeline** of step events:
  each entry = `{ step_index, skill_type, status, timestamp, error_message? }`.
- R2. The timeline is **forwarded from LabService**, not reconstructed on the Agent side.
- R3. AgentService **persists** the timeline durably (queryable per trial), so it
  survives reconnect and is not just an ephemeral SSE replay artifact.
- R4. The portal renders the timeline per trial in the workspace, ordered, with clear
  status + time + error display, and updates live as new events arrive.
- R5. The contract change is **typed in BIC-shared-types** and consumed by all three
  repos; the relevant `.trellis/spec/` contract docs are updated in the same change set
  (Rule 10).
- R6. No regression to the existing `TaskProgressEvent` / latest-status path that other
  UI already depends on.

## Constraints

- C1. shared-types version bumps have historically broken `collect` (memory:
  v1.1.4a1 dropped a type → 29 collect errors). The contract task must bump
  **additively** and verify all three repos still import/collect.
- C2. Surgical changes (Rule 3) — do not refactor the existing status path; add the
  timeline alongside it.
- C3. Type-first (Rule 11) — Pydantic models on every boundary, no raw dicts.

## Architecture (locked with Drake, 2026-06-30 — supersedes any "Agent persists" wording)

**Live via SSE, history via Lab REST (Agent-proxied). The Agent stores NOTHING for the
timeline — LabService `EventLog` is the single store.**

- **Live**: `step_events` rides the existing `TaskProgressEvent` (SSE), no `trials` DB write.
- **History / reconnect**: FE calls the Agent `GET /api/trials/{trial_id}/step-events`; the
  Agent maps `trial_id → lab_task_id` and proxies to LabService
  `GET /tasks/{lab_task_id}/step-events`, which reads the `EventLog` STEP_* rows. No auth.
- **Portal architecture unchanged**: FE talks only to the Agent (no BFF, no direct FE→Lab).

This means **AC2's "durable on the Agent side" is wrong** — durability lives in LabService's
EventLog, surfaced via the Lab read endpoint. See revised cross-child AC below.

## Task map (children, in dependency order)

1. **06-30-execlog-shared-contract** — typed `TaskStepEvent` / `step_events` contract in
   BIC-shared-types, additive. ✅ DONE (`1.2.0a1`, 3-repo collect green). *(Blocks all.)*
2. **06-30-execlog-lab-publish** — LabService forwards the timeline over MQ from `EventLog`.
   ✅ DONE. *(Depends on 1.)*
3. **06-30-execlog-lab-readapi** — LabService `GET /tasks/{task_id}/step-events` read
   endpoint over `EventLog` STEP_* rows (the history source). *(Depends on 1.)*
4. **06-30-execlog-agent-passthrough** — (rescoped from "agent-persist"; the Agent does NOT
   persist) (a) add `step_events` to `TaskProgressEvent` for live SSE, no `trials` write;
   (b) Agent proxy `GET /api/trials/{trial_id}/step-events` → Lab readapi. *(Depends on 1,3.)*
5. **06-30-execlog-fe-timeline** — portal renders the per-trial timeline: live via the SSE
   `step_events` field + history via the Agent proxy endpoint. *(Depends on 1,3,4.)*

Ordering is documented here; this is not a dependency engine. Each child carries its
own testable acceptance criteria so it can be planned/implemented/checked independently
once its upstream contract exists.

## Cross-child acceptance criteria (parent owns integration)

> Status 2026-06-30: all 5 children code-complete + unit/contract-verified per child. The only
> outstanding item is a LIVE end-to-end run (AC1) + the FE visual check — both need the running
> agent BE restarted onto the new code, then a real bench run. Deferred with Drake.

- [~] AC1. End-to-end: a bench/scenario run produces a step-by-step timeline visible in
      the portal. **NOT yet run live** — each hop is verified in isolation (incl. a Lab-side
      REST==MQ shape-parity test), but a full robot→FE bench run is outstanding (needs agent BE
      restart). This is the one true integration gap.
- [x] AC2. Timeline history durable in **LabService EventLog**, re-fetched via the Agent proxy →
      Lab read endpoint (Agent persists nothing). Lab read endpoint + Agent proxy both built+tested.
- [x] AC3. A failed step shows `error_message` — STEP_FAILED now emitted (lab-publish), surfaced in
      MQ + REST + FE failed-step render test. (Live confirmation rides AC1.)
- [x] AC4. shared-types bump additive (`1.2.0a1`); all three repos collect/import green (verified).
- [ ] AC5. Every contract touched (shared-types, Lab→Agent MQ, Agent→FE SSE) has its
      `.trellis/spec/` doc updated in the same change set.
- [ ] AC6. Existing latest-status UI path is unchanged (no regression).

## Open questions (resolve during child planning)

- Q1. New MQ routing key for the timeline vs. enriching `TaskStatusMsgPayload`? (Lab task)
- Q2. New `trial_events` table vs. extending the `trials.result` JSONB? (Agent task)
- Q3. New dedicated SSE event kind vs. extending `TaskProgressEvent.steps`? (Agent+FE)
- Q4. Where in the workspace does the timeline live, and what does it look like? (FE task)

## Notes

- This parent is the requirement owner + integration reviewer; it normally won't be the
  implementation target. Start children, not the parent.
