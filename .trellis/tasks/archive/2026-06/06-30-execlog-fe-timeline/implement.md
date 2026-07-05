# Implement — FE: Execution Log

Repo: `BIC-agent-portal`. `pnpm` tooling, Biome (single quotes, no semicolons, type-only imports,
`@/*`). Dev server `:5173`. **No code until `start` + review.** UI ⇒ CDP verify, not just typecheck.

## Ordered checklist

1. **Types** (`src/types/events.ts`): add `TaskStepEvent` interface (event_id, step_index,
   skill_type, status, occurred_at, error_message?). Add `step_events?: TaskStepEvent[]` to
   `TaskProgressEvent`. Update the header comment citing the backend shape. (Do types FIRST.)

2. **Store** (`src/stores/workspaceStore.ts`):
   - Add `executionLog: TaskStepEvent[]` to `TrialState` (default `[]`); init it where
     `TrialState` is created/hydrated (incl. `hydrateFromSnapshot` ~`:915` → `executionLog: []`).
   - Extend `onTaskProgress` (~`:1174`) to merge `evt.step_events` into the trial's `executionLog`:
     dedup on `event_id`, sort by `occurred_at` then `step_index`.
   - Add a `seedExecutionLog(trialId, events: TaskStepEvent[])` action using the SAME merge
     (order-independent via event_id dedup).
   - Add a selector to read a trial's `executionLog`.

3. **Fetch + query** (`src/lib/agent-client.ts`, `src/lib/session-queries.ts`):
   - `fetchTrialStepEvents(sessionId, trialId): Promise<TaskStepEvent[]>` mirroring
     `fetchSessionSnapshot` (`:527`).
   - `trialStepEventsQueryOptions(sessionId, trialId)` (`enabled: !!trialId`, `staleTime: 0`).

4. **Component** (`src/components/workspace/ExecutionLogPanel.tsx`):
   - `useQuery(trialStepEventsQueryOptions(sessionId, activeTrialId))`; on success →
     `seedExecutionLog`. Read merged `executionLog` from the store for render (so live SSE events
     show too).
   - Collapsible card matching `ExperimentProgressPanel` tokens. Per row: `humanizeSkillType`,
     transition status (map step_started→running / step_completed→done / step_failed→error /
     step_waiting→waiting for `statusTone`), `occurred_at` formatted HH:MM:SS, error box on
     `error_message`. `data-testid="execution-log-row"` + `data-event-id` for assertions.
   - Default OPEN when non-empty.

5. **Mount** it beside/below `ExperimentProgressPanel` in the workspace composition (find where
   that panel is rendered — `src/pages/chat/ChatPage.tsx` split or a workspace container).

6. **Spec (Rule 10)**: `events.ts` header + any `.trellis/spec/BIC-agent-portal/frontend` event/
   store doc — note `step_events` + the `executionLog` slice.

## Tests
- Playwright (live-backend) OR a store unit test: merge dedups on `event_id` and orders by
  `occurred_at`; seed-then-live and live-then-seed converge to the same log (Rule 7 — the
  order-independence invariant).
- A failed step (`step_failed`) renders the error + distinct style.

## Validation
```bash
pnpm check        # biome lint+format+organize — run before done
pnpm typecheck    # tsc -b --noEmit
pnpm exec playwright test   # existing specs must stay green (needs BE :8800 + portal :5173)
```

## CDP visual verification (portal Rule 1 — MANDATORY, then DELETE screenshots)
- Ensure portal `:5173` + agent BE `:8800` + lab up (tmux `bic-services`). Hide devtools
  (`VITE_HIDE_DEVTOOLS=1`).
- CDP: `navigate_page` to a session with a run; `evaluate_script` to assert ExecutionLogPanel rows
  are chronological, no duplicate `data-event-id`, count matches, failed-step error visible;
  `take_screenshot` and LOOK; then **delete every screenshot file** (clean tree).

## Risky points
- **Two arrays confusion** — render `executionLog` (step_events), NOT `progress.steps`. Do not
  touch `ExperimentProgressPanel`.
- **Merge correctness** — dedup MUST be on `event_id` (not index/status), else live+history double
  up. The seed/live convergence test guards this.
- **Time formatting** — `occurred_at` is ISO; format to local HH:MM:SS for display only.

## Done = all of:
- [x] `TaskStepEvent` + `step_events?` on `TaskProgressEvent` in `events.ts`.
- [x] Store `executionLog` slice + dedup(event_id)/sort(occurred_at) merge + `seedExecutionLog`.
      Bonus: `logChanged` guard added so log-only `task_progress` isn't swallowed by `sameProgress`.
- [x] `fetchTrialStepEvents` + `trialStepEventsQueryOptions`.
- [x] `ExecutionLogPanel` created + mounted in `MonitorPane` below `ExperimentProgressPanel`;
      existing panel git-confirmed UNTOUCHED.
- [x] Merge/order test (seed↔live convergence) + failed-step render — 4 vitest cases green.
- [x] `pnpm check` + `pnpm typecheck` green. (Full Playwright suite NOT run — needs live BE+portal.)
- [~] CDP visual verification: **DEFERRED** [Drake, 2026-06-30]. Synthetic injection blocked in
      this env (store not on `window`, no dispatcher hook, React DevTools backend not attached →
      `rendererCount:0`; the one live trial had no `step_events`, and the panel correctly renders
      empty with no data). Render is proven by the 4 unit tests, NOT by eye. Eyeball on the next
      real bench run that emits step_events (after the agent BE is restarted onto the new code).
- [x] Spec (Rule 10): `.trellis/spec/ui/L3/sse-contract.md` updated.

## Carried risk (fail-loud)
Visual confirmation outstanding. Also: the running agent BE process predates the step_events
backend code — a real end-to-end check requires restarting it (`kill :8800` owner, relaunch in
tmux pane 0.0) before step_events actually flow to the FE.