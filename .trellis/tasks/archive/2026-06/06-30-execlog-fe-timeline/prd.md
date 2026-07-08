# FE: render execution timeline

Parent: `06-30-robot-execution-log`. Depends on `06-30-execlog-shared-contract` (wire
shape) and `06-30-execlog-agent-persist` (Agent emits/serves the timeline).

## Goal

Render a **per-trial step-level execution timeline** in the portal workspace: ordered,
timestamped, status-coded, error-aware, and live-updating as new events arrive — so the
chemist can see what the robot/lab did and where it is now.

## Context (real code)

- Wire types live in `src/types/events.ts`: `TaskProgressStep` (snapshot:
  `step_index, skill_type, status, error_message?` — **no timestamp**) and
  `TaskProgressEvent` (`kind: 'task_progress'`, `steps[]`).
- Event flow invariant **I-UI-1**: SSE → `src/lib/sse-client.ts` → `src/lib/event-dispatcher.ts`
  → zustand stores → components. No component subscribes to SSE directly. New event kinds
  register in `KINDS` (sse-client.ts) + a `dispatchEvent` case.
- Existing workspace progress UI: `src/components/workspace/ExperimentProgressPanel.tsx`
  (current step/status). `workspaceStore` is a singleton (one foregrounded trial).
- This is the surface that resolves parent **Q4** (where the timeline lives + how it looks).

## Render model (locked with Drake, 2026-06-30)

The FE ALREADY renders a step-STATUS list (`ExperimentProgressPanel` + `TimelineRow`, fed by the
snapshot `steps`). The new `step_events` is a DIFFERENT thing — a chronological TRANSITION log
(started/completed/failed/waiting, timestamped, a step can appear twice). Decision:
- **Keep the existing progress panel untouched** (it answers "where are we").
- **Add a SEPARATE collapsible "Execution Log" view** fed by `step_events` (the literal
  "more detailed robot execution log" ask).
- **History source**: fetch from the Agent proxy `GET /sessions/{id}/trials/{trial_id}/step-events`
  on trial focus (TanStack Query, Lab EventLog = authoritative), then **merge live SSE
  `step_events` deduped on `event_id`**.

## Requirements

- R1. Add a `TaskStepEvent` interface to `src/types/events.ts` (`event_id, step_index, skill_type,
  status, occurred_at, error_message`) and add `step_events?: TaskStepEvent[]` to
  `TaskProgressEvent`. NO new SSE kind — `task_progress` already exists + is registered in `KINDS`.
- R2. Add an `agent-client` fetch + TanStack Query hook for
  `GET /sessions/{session_id}/trials/{trial_id}/step-events` → `TaskStepEvent[]`; call it on trial
  focus / workspace open to seed the Execution Log history (parent AC2).
- R3. Live: the dispatcher's existing `task_progress` case feeds the workspace store; extend the
  store's `onTaskProgress` to merge `evt.step_events` into a per-trial `executionLog`, **deduped
  on `event_id`**, kept chronologically ordered by `occurred_at`. (I-UI-1: no direct SSE in
  components.)
- R4. New component (e.g. `ExecutionLogPanel`) renders the merged `executionLog`: per transition,
  humanized skill_type (reuse `humanizeSkillType` in `src/lib/skill-labels.ts`), status, a
  formatted `occurred_at` time, error_message on failure. Collapsible.
- R5. Sit it BESIDE/below `ExperimentProgressPanel` in the workspace. No change to that panel.
- R6. Don't regress the existing snapshot-`steps` progress UI (parent R6).

## Constraints

- C1. Match portal conventions: TS strict, Biome (single quotes, no semicolons), type-only
  imports, `@/*` alias; run `pnpm check` before done.
- C2. Event handling **only** through dispatcher→store (I-UI-1); register new kinds in `KINDS`.
- C3. **Visual verification required** (portal Rule 1): verify via Chrome DevTools MCP —
  navigate, assert DOM (order, count, no dupes), screenshot, then **delete screenshots**.

## Acceptance Criteria

- [ ] AC1. Workspace shows an ordered, timestamped step timeline for the active trial.
- [ ] AC2. Reload the portal mid/post-run → full timeline re-renders from persisted history.
- [ ] AC3. Live: a new step event appears in correct order without manual refresh.
- [ ] AC4. A failed step is visually distinct and shows its error message.
- [ ] AC5. Existing progress panel / latest-status UI unaffected (no regression).
- [ ] AC6. `src/types/events.ts` matches the backend wire shape; new kind registered in
      `KINDS` + a `dispatchEvent` case; `pnpm check` + `pnpm typecheck` green.
- [ ] AC7. CDP visual verification done and screenshots deleted (clean tree).
- [ ] AC8. `.trellis/spec/` FE event/contract doc updated if the wire shape changed (Rule 10).

## Resolved (was open)

- **Placement**: dedicated collapsible `ExecutionLogPanel` BESIDE `ExperimentProgressPanel`,
  fed by `step_events` — existing panel untouched. [Drake, 2026-06-30]
- **History source**: Agent proxy fetch on trial focus + live SSE merge, dedup on `event_id`.
  [Drake, 2026-06-30]
- **Skill labels**: `humanizeSkillType` already exists (`src/lib/skill-labels.ts`, 13+ entries) —
  reuse it; no new map.
- **No new SSE kind**: `task_progress` already carries the field + is registered in `KINDS`.

## Notes

- Complex task: design.md + implement.md before `start`. UI ⇒ CDP verification, not just typecheck.
