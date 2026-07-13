# Handover: Material Preparation redesign — implementation session

You are picking up three FULLY PLANNED, review-approved Trellis tasks. All
design decisions are FINAL (Drake, 2026-07-11, after four ruling iterations) —
implement them, do not re-litigate them. Planning artifacts are the authority;
this prompt is the map.

## Mission

Implement, in this order (each blocks the next's live verification):

1. `BIC-lab-service` → task `07-11-tube-relocate-endpoint`
   (atomic sample-tube location update; identity-preserving)
2. `BIC-agent-service` → task `07-11-material-reconcile-endpoint`
   (Validate Readiness = save draft → reconcile lab to draft → validate; one
   portal call; server-side pending-ID guard)
3. `BIC-agent-portal` → task `07-11-restore-item-card-staged-flow`
   (item-card UI restore; portal = UI-render-only, zero lab writes; may start
   against a mocked BE contract per its step 0)

Per task: `cd <repo>` → `python3 ./.trellis/scripts/task.py start <task>` →
dispatch `trellis-implement` subagents with `model: "sonnet"`, prompt starting
with `Active task: <path from task.py current>` on its own line (repo CLAUDE.md
protocol) → `trellis-check` subagent (also sonnet) → main session re-runs the
FULL gate chain itself (never trust a chain that short-circuited; re-run whole
chain after any fix) → raise the PR via the `raise-pr` skill (full local gate
green BEFORE push; poll CI with short non-blocking checks). Pause for Drake
between tasks.

## The final model (one paragraph)

The trial params draft (`trials.params` via `PUT .../params-draft`) is the
SINGLE staging area: staging a TLC tube appends a `pending:<box>-<cell>` entry
to `lab_logistics.sample_tubes`; reassign updates the SAME entry's cell
(identity kept); remove drops the entry; every change persists to the agent
(existing #46 path). Closing the panel keeps staged work (NO cancel/reset
machinery — Remove is the undo); reload restores. Validate Readiness is ONE
portal→agent call carrying current values: the agent pre-checks the trial
(404/409), saves the draft, reconciles Lab Service to it — removals (live
tubes stamped `properties.trial_id == current trial` and absent from draft),
moves (ONE atomic lab relocate call, tube ID preserved), creations
(`occupied:true` with `{purity, exp_id, exp_name, trial_id}`) — stop-at-first
with structured flush error, then calls lab's EXISTING
`POST /preparations/validate` and returns `{params, readiness, flush_error}`.
Confirm/dispatch refuses `pending:` IDs server-side
(`tlc_params_form_problems_from_values`, form_payloads.py:661).

## Read before coding (per task, in order)

Each task dir: `implement.jsonl` (context manifest) → `prd.md` → `design.md` →
`implement.md`. Cross-task desk-check with verified code anchors:
`BIC-agent-portal/.trellis/tasks/07-11-restore-item-card-staged-flow/research/desk-check-trace.md`.
Product authority: root `Production-PRD.md` rule 8 + 2026-07-11 change-log
entries (UNCOMMITTED working-tree edits — see warnings).

## Non-negotiables (settled rulings — do not reopen)

- Close KEEPS staged work (supersedes Wenlong #206 Option A rule 8(d) — he has
  been informed). No discard-on-close, no removal notes, no tombstones.
- Reassign is a MOVE via the lab relocate endpoint — never delete+recreate.
- No new lab VALIDATION endpoint: agent client method `validate_preparation`
  calls lab's existing `POST /preparations/validate`.
- Validate payload `params` = the agent's OWN dispatch composition (extract
  from `submit_l4_execution`, tools.py:635+) — do NOT port the portal's
  `buildLabTaskParams`; the FE task DELETES that mirror.
- Filled grid cells are inert (no green-select); item cards own all actions.
- No unique-constraint migration in the lab task (race parity with the
  existing cell PUT is deliberate).
- No silent retries on move conflicts / vanished records — loud stop.
- No cleanup of consumed/prior-round tubes (demo lifecycle; DB reset only).
- Lab model axis quirk: `cell_col` = row LETTER, `cell_row` = col NUMBER
  (tlc_inventory.py:26-27) — follow, don't "fix".
- Type integrity (#242) holds by construction (typed at Add); portal PR #72 is
  superseded — never merge it or build on its branch.

## Warnings

- FOUR repos carry uncommitted planning/PRD edits (meta, portal,
  agent-service, lab). The META repo's `Production-PRD.md` mixes THIS work
  with other sessions' edits (rule 13 developing-tank, rule 7 workbench) —
  NEVER commit the meta repo wholesale; Drake owns that commit. Task-repo PRD/
  spec edits ride their task PRs per rule 10 (BE task step 5 carries the final
  root-PRD + portal project PRD sync).
- The bench lab working tree is on MAIN (Drake switched 2026-07-11); the
  purity branch `feat/tlc_adapting` is NOT loaded. Live bench E2E of the BE
  move pass needs a bench lab containing the relocate endpoint.
- Subagent hygiene: never relay a subagent's "gap/missing" claim unverified —
  rg the chokepoint yourself before acting on it (session lesson,
  CLAUDE.local.md).
- All curl to localhost needs `--noproxy '*'`.
- Never run `task.py start` or begin implementing without Drake's explicit go
  for that task in the new session.

## Definition of done (per task)

Every acceptance criterion in its prd.md checked; check.jsonl invariants
verified; full repo gate green in ONE run; spec sync landed in the same change
set (rule 10); PR green per raise-pr SOP. FE task additionally: CDP visual
verification on the bench, screenshots deleted afterwards (portal rule-1).
