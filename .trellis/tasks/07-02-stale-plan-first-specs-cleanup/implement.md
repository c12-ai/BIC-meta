# Implement — objective-first spec migration

Repo: /Users/drakezhou/Development/BIC/BIC-agent-portal. Branch: `test/objective-first-specs`
off main @ db1fc3b2. Working tree has 5 dirty files under src/ + pnpm-lock — NOT ours, do not
touch, do not stage. Diff must stay inside `tests/`.
Read `research/migration-recipe.md` + `design.md` first. Reference implementation:
`tests/form-edit-sync-on-send.spec.ts`.

## Checklist (ordered) — state as of 2026-07-05
1. [x] `driveObjectiveFirstSession()` in tests/helpers.ts (6th export).
2. [x] cc-re-chained-flow migrated (by the interrupted implement agent — NOT yet re-reviewed
       by the main session; review before commit).
3. [x] honest-chain-guard (DOM-only TLC leg, no reload-recovery; bubble counts 1→2→3;
       forbidden-call grep clean).
4. [x] manual-live-demo (rts-phase gate REMOVED; G3 + fileChooser upload REMOVED — unreachable,
       see PRD DECISION section; resetLabState added; final bubble toHaveCount(2)).
5. [x] task-progress-stream (TLC leg first; ALL task_progress asserts scoped to CC trial_id;
       specialist-filtered events).
6. [ ] tlc-upload-chain T2/T3 — BLOCKED on Drake (PRD "DECISION NEEDED": TlcUploadControl
       unreachable under robot-TLC; manual-TLC variant vs delete). T1 untouched/valid.
7. [x] Static gates green 2026-07-05: tsc clean; biome lint tests/ = 5 pre-existing warnings
       (identical on main, zh-cc-form-render only); playwright --list parses on all 3 configs.
       (Repo lint is biome, not eslint.)
8. [x] git status: only tests/ files changed (5: helpers + 4 specs).

## NOT in this change set
- Running the live bench (needs services; separate step via bic-e2e-runner playbook).
- Committing (blocked on bench green — see design.md acceptance split).

## Run commands (for the later bench step)
- `VITE_HIDE_DEVTOOLS=1 pnpm exec playwright test <spec> --workers=1` (default config specs)
- cc-re-chained: `--config=playwright.cc-re-chained.config.ts`; manual-live-demo:
  `--config=playwright.live.config.ts`
- curl health checks need `--noproxy '*'` (local proxy masks localhost).
