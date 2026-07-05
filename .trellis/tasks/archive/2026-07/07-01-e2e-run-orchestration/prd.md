# E2E run orchestration and investigation

## Goal

Turn each BIC live E2E verification into a **self-documenting, self-investigating run**
under `.e2e-logs/run-YYYY-MM-DD-#N/`. Drake runs the suite ~twice a day (before lunch,
before leaving). Each run must, with minimal hand-holding:

1. materialize a run folder (`checklist.md`, `report.md`, `evidences/`) from templates,
2. capture continuous per-service evidence during the ~30-min run,
3. produce an analysis `report.md` (per-spec verdicts + root-cause labels), and
4. fan out one investigation subagent per finding that writes a **proposal** (cause,
   options, recommended fix, effort/risk) back into `report.md` for Drake to pick up.

This is orchestration + documentation, **not** a rewrite of the test bench. The existing
`bic-e2e-runner` skill (orchestrator) and agent (diagnostic brain) stay authoritative for
bring-up, running the suite, the reset/recovery playbook, and the 4-label taxonomy.

## Context (what already exists — do not reinvent)

- **Skill** `.claude/skills/bic-e2e-runner/SKILL.md` — Phases 0-5: preflight, start missing
  services, baseline session ids, run suite (`--workers=1`), parse, branch on result,
  cleanup. Owns the canonical **4-label taxonomy** (product bug / test bug / bench-state bug
  / external dependency) and the pass/fail output templates.
- **Agent** `.claude/agents/bic-e2e-runner.md` — reset/recovery playbook, TLC retry
  semantics, backend-truth-first diagnosis. Shares the same 4 labels.
- **Gold prior run** `.e2e-logs/run-2026-06-30-#1/evidences/` — proven evidence convention:
  numbered `NN-*.log` snapshots + `INDEX.md` (one line per file, PASS/FAIL/NA) +
  `SUMMARY.md` (per-spec results table + root-cause + recommended fixes). The new
  `report.md` is essentially a formalized `SUMMARY.md`.
- Both `.e2e-logs/*.template.md` files are **empty (0 bytes)** — must be authored.

## Cross-child contract — the run-folder layout (THE most important boundary)

All four children read/write this shared structure. It is a contract; changing it means
updating this PRD (Rule 10).

```
.e2e-logs/
  checklist.template.md          # base checklist (authored by child: templates)
  report.template.md             # base report   (authored by child: templates)
  run-YYYY-MM-DD-#N/             # one dir per run; #N auto-increments per calendar day
    checklist.md                 # copied from template; per-run diff-tasks APPENDED
                                 #   under their matching "## Section" as a new H2 block
    report.md                    # copied from template; filled post-run; investigation
                                 #   proposals appended per finding
    evidences/                   # continuous per-service logs + snapshots + screenshots
      agent-be.log  lab.log  portal.log   # continuous tails (child: monitors)
      NN-*.log                             # checkpoint snapshots (existing convention)
      INDEX.md  SUMMARY.md                 # kept from existing convention
```

Naming: `run-YYYY-MM-DD-#N` (matches existing `run-2025-07-01-#1`). `#N` = 1-based index
within the calendar day.

## Requirements

### R1 — Templates (child: e2e-templates)
- `checklist.template.md`: sectioned base with `- [ ]` items covering the standing verify
  points (preconditions, per-suite health, regression). Sections use `## H2`.
- Per-run diff-tasks (feature-specific checks for that run) append **under their matching
  section** as a nested `## H2` block — per Drake's spec.
- `report.template.md`: header (run id, command, timing, overall verdict), a per-spec
  results table with a **Root cause (label)** column, and a **Findings** area where each
  finding gets a slot for an investigation proposal.
- Both reverse-engineered from `run-2026-06-30-#1`'s `SUMMARY.md` / `INDEX.md`.

### R2 — Run-folder lifecycle (child: e2e-run-lifecycle)
- The runner skill gains a phase that, at run start, computes `run-YYYY-MM-DD-#N` (next
  free `#N` for today), creates the dir + `evidences/`, copies both templates in, and
  points all subsequent evidence writes at that folder.
- Post-run, generates `report.md` from the parsed suite result + evidence.

### R3 — Continuous monitor subagents (child: e2e-monitors)
- At run start, dispatch **3 Sonnet-4.6 subagents**, one per service (agent BE / lab /
  portal), each continuously capturing its service's output into `evidences/<svc>.log` for
  the run's duration, and flagging anomalies (wedge, FK races, 502s) as they appear.
- Main loop stays in control of overall progress and surfaces checklist attention points.
- **Design-phase open question:** subagents cannot truly stream for 30 min cheaply — the
  design must specify the actual mechanism (e.g. backgrounded `tail -F` writing the file +
  subagent doing periodic bounded reads + classification). Resolve in design.md; confirm
  with Drake before implementing.

### R4 — bic-e2e-investigate skill (child: e2e-investigate-skill)
- New **BIC-specific** skill at `.claude/skills/bic-e2e-investigate`.
- Input: a `report.md` with findings. For each finding, dispatch a subagent that researches
  root cause (code + internet best-practice search) and writes a **proposal** (cause /
  options / recommended fix / effort+risk) — appended into `report.md`. No code changes.
- Reuses the 4-label taxonomy; pairs with the existing runner skill+agent.
- Best-practice research on "automated failure investigation / triage" happens during this
  child's planning.

## Constraints

- **Do not** duplicate the runner skill's bring-up / reset / suite-run logic — extend it.
- **`--workers=1`** always (one live bench) — inherited, not re-litigated here.
- Monitors and investigators are **Sonnet 4.6** subagents (Drake's spec); main orchestration
  stays on the session model.
- Investigation writes proposals only — **never** edits product/test code (Rule 3).
- Keep the 4-label taxonomy identical across skill, agent, report, and investigator (Rule 5).

## Acceptance Criteria (parent — cross-child)

- [ ] A single "run the E2E suite" invocation materializes `run-YYYY-MM-DD-#N/` with
      `checklist.md` (from template + any diff-tasks), an `evidences/` folder receiving
      continuous per-service logs, and a post-run `report.md`.
- [ ] `report.md` has per-spec verdicts with root-cause labels AND, for every finding, an
      investigation proposal Drake can act on — without Drake re-deriving anything.
- [ ] The run-folder layout in this PRD is the single source of truth all four children
      conform to; no child invents its own paths.
- [ ] Existing `bic-e2e-runner` skill/agent behavior (bring-up, reset, suite run, cleanup,
      taxonomy) is preserved, not forked.

## Notes

- Children are independently verifiable: templates (author + render check), lifecycle
  (folder created correctly), monitors (evidence files populated), investigate skill
  (proposals generated). Ordering (templates → lifecycle → monitors → investigate) lives in
  each child's own prd/implement, not enforced by Trellis.
- Design + implement artifacts required per child before `task.py start` (complex work).
