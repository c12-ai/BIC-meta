# FE tube selector silently drops clicks at 4-cap

## Goal

The tube selector must never SILENTLY ignore a chemist's click. At the 4-tube cap, a further
click currently no-ops with no feedback — so pre-filled (even garbage) tubes can't be
corrected, and the chemist has no signal why.

## Evidence (bench run 5b, 2026-07-02, task 07-02)

`BIC-agent-portal/src/components/workspace/forms/TubeSelectorGrid.tsx:59` —
`if (tubes.length >= 4) return tubes` in `toggleTubeSelection`: at the cap, selecting a NEW
cell returns the list unchanged (deselecting an existing cell still works). In run 5b the
agent had pre-filled 4 (hallucinated) tubes, so the spec's A1/A2 declarations were no-ops and
the garbage `box_01 A1-A4` selection dispatched. The silent drop is what let it through
unnoticed. Interacts with [[07-02-tlc-sample-tubes-hallucination]] (the fabrication) — but the
silent-drop is an independent UX defect worth fixing on its own.

## Decision (Drake, 2026-07-02): REPLACE OLDEST

At the cap, a click on a NEW cell deselects the OLDEST selection and adds the new one
(rolling FIFO). Never a silent no-op. Deselecting an existing selected cell still just
removes it (unchanged).

## Requirements

- R1: `toggleTubeSelection` at 4 selections + a NEW cell → drop the first (oldest) entry,
  append the new one (keep insertion order so "oldest" is well-defined). Replace the
  `if (tubes.length >= 4) return tubes` no-op at `TubeSelectorGrid.tsx:59`.
- R2: The valid range 2–4 (`hasRequiredManualSelection`) invariant is preserved — replace-
  oldest keeps the count at 4, never exceeds.
- R3: Unit coverage for `toggleTubeSelection`: at-cap new-cell click replaces oldest;
  deselect still removes; below-cap add still appends.

## Acceptance Criteria

- [x] At 4 selected, clicking a 5th distinct cell yields 4 tubes with the oldest gone and
  the new one present.
- [x] Deselecting a selected cell at cap removes it (returns 3).
- [x] `pnpm typecheck` + `pnpm check` — gated at PR #2 merge; not re-run locally on 07-03
  (working tree dirty with unrelated in-flight files).

## Verification (2026-07-03, sonnet research-agent pass)

RESOLVED — on BIC-agent-portal main via PR #2 squash `1c713d81` (pre-squash `d37ab5c`).
R1/R2: `TubeSelectorGrid.tsx:61` now `const kept = tubes.length >= 4 ? tubes.slice(1) : tubes`
(rolling FIFO, count stays 4); deselect path unchanged. Confirmed in main's COMMITTED file
(`git show main:...TubeSelectorGrid.tsx`). R3: `TubeSelectorGrid.test.ts` covers below-cap
append, deselect, at-cap FIFO replace (asserts oldest gone, order kept), at-cap deselect.
