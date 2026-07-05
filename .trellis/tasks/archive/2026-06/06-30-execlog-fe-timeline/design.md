# Design — FE: render execution timeline (Execution Log)

Render model locked: **separate collapsible `ExecutionLogPanel` fed by `step_events`**; existing
`ExperimentProgressPanel` (snapshot `steps`) untouched. History via Agent-proxy fetch on trial
focus + live SSE merge, dedup on `event_id`.

## Data shapes — two arrays, do NOT conflate

| | `steps` (existing) | `step_events` (new, this task) |
|---|---|---|
| meaning | per-step latest STATUS snapshot | chronological TRANSITION log |
| status vocab | pending/in_progress/completed | step_started/completed/failed/waiting |
| a step appears | once | possibly many times (started→completed) |
| has timestamp | no | yes (`occurred_at`) |
| stable id | no | yes (`event_id`) |
| rendered by | `ExperimentProgressPanel` (keep) | `ExecutionLogPanel` (new) |

## Part 1 — types (`src/types/events.ts`)

Add (mirroring backend `TaskStepEvent`):
```ts
export interface TaskStepEvent {
  event_id: string
  step_index: number
  skill_type: string
  status: string            // step_started | step_completed | step_failed | step_waiting
  occurred_at: string       // ISO datetime
  error_message?: string | null
}
```
Add to `TaskProgressEvent`: `step_events?: TaskStepEvent[]`. NO new `kind`. (CLAUDE.md: update
`events.ts` first, then propagate.)

## Part 2 — store merge (`src/stores/workspaceStore.ts`)

`TrialState` gains `executionLog: TaskStepEvent[]` (default `[]`). Extend `onTaskProgress`
(currently `:1174`) to merge `evt.step_events`:
```ts
// merge new events, dedup on event_id, keep chronological by occurred_at
const seen = new Set(existing.executionLog.map(e => e.event_id))
const merged = [...existing.executionLog]
for (const ev of evt.step_events ?? []) if (!seen.has(ev.event_id)) { merged.push(ev); seen.add(ev.event_id) }
merged.sort((a, b) => a.occurred_at.localeCompare(b.occurred_at) || a.step_index - b.step_index)
```
A `seedExecutionLog(trialId, events)` action for the history fetch uses the SAME merge (so
fetch-then-live and live-then-fetch converge identically — dedup on `event_id` makes it
order-independent). Mirror the existing `sameProgress()` redundant-render guard if needed.

## Part 3 — history fetch (`src/lib/agent-client.ts` + a query)

Mirror `fetchSessionSnapshot` (`:527`):
```ts
export async function fetchTrialStepEvents(sessionId: string, trialId: string): Promise<TaskStepEvent[]> {
  const res = await fetch(`${env.API_BASE_URL}/sessions/${sessionId}/trials/${trialId}/step-events`,
    { method: 'GET', headers: headers() })
  return jsonOrThrow<TaskStepEvent[]>(res)
}
```
A TanStack `trialStepEventsQueryOptions(sessionId, trialId)` in `session-queries.ts`. Call it on
trial focus / workspace open (where `activeTrialId` is known) and feed results to
`seedExecutionLog`. `enabled: !!trialId`. On success → `seedExecutionLog(trialId, data)`.

Hook point: the workspace component that knows `activeTrialId` (or a small effect in the
ExecutionLogPanel that `useQuery`s and seeds). Keep the fetch OUT of components subscribing to SSE
— the merge lives in the store (I-UI-1 respected: live events still flow dispatcher→store).

## Part 4 — component (`src/components/workspace/ExecutionLogPanel.tsx`)

- Reads `executionLog` for the active trial from `workspaceStore`.
- Collapsible (default collapsed? open? — minor; default OPEN when non-empty for visibility,
  collapsible to hide). Match the existing panel's card/typography tokens.
- Per row: `humanizeSkillType(skill_type)` (reuse `src/lib/skill-labels.ts`), the transition
  status, a formatted `occurred_at` (HH:MM:SS), `error_message` in the destructive box style if
  present. Reuse `statusTone()`/`ToneIcon` patterns from `ExperimentProgressPanel` where they fit
  the new status vocab (map step_started→running, step_completed→done, step_failed→error,
  step_waiting→waiting). `data-testid` for CDP/Playwright assertions.
- Mount it beside/below `ExperimentProgressPanel` in the workspace composition.

## Mock (target)
```
┌ Experiment Progress ───────────┐   (existing, unchanged)
│ ● Mount cartridges   · running │
│ ○ Start CC           · pending │
├ Execution Log            ▾ ────┤   (NEW — ExecutionLogPanel)
│ 12:01:03  Mount cartridges  started   │
│ 12:03:21  Mount cartridges  completed │
│ 12:03:22  Start CC          started   │
└────────────────────────────────┘
```

## No-regression
- `ExperimentProgressPanel`, `TaskProgressStep`, snapshot `steps` path: untouched.
- New field on `TaskProgressEvent` is optional → old replayed `session_events` rows (no
  `step_events`) dispatch fine (`step_events ?? []`).

## Spec (Rule 10)
- `events.ts` header comment cites the backend payload shape — add `step_events`.
- If `.trellis/spec/BIC-agent-portal/frontend` documents the event contract / store, note the new
  field + `executionLog` slice.

## Verification (portal Rule 1 — MANDATORY)
- CDP: navigate to a run, assert the ExecutionLogPanel DOM (rows in chronological order, count,
  no dup `event_id`, failed-step error visible), screenshot, **then delete screenshots** (clean tree).
- `pnpm check` + `pnpm typecheck` green. Existing Playwright specs still pass.
