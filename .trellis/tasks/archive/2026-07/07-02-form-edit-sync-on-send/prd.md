# Form-edit sync on send via SessionContext

## Goal

When the chemist manually edits the specialist params form (CC/RE/TLC) and then sends a chat
message WITHOUT confirming, the agent must (a) work from the chemist's edited values, not its own
stale draft, and (b) be explicitly aware that the chemist made those edits, so it responds to them
(the existing RE-RECOMMEND prompt rule fires).

Today the edits live only in React state: the agent is blind, and its reply's `task_params_set`
silently wipes the chemist's on-screen edits (`useParamsFormHandle.ts:40-47`, no `touched` guard).

## Requirements

- R1: On chat send, if the params form is dirty, the FE attaches the current draft
  (`{trial_id, params}` — the full unified `{from_user, recommended, lab_logistics}` blob) to the
  same `POST /sessions/{id}/messages` request. Lenient: no validation gate; draft truth, not confirm.
  The full blob is for persistence fidelity (leg 1); the prompt (leg 2) exposes only the
  chemist-editable sections — `from_user` + `lab_logistics`, never `recommended` (D2).
- R2: The BE persists the attached draft durably before the turn runs, so the existing
  `reception_node` re-seed (`trials.params` → `params_draft`) makes agent tools merge ON TOP of
  chemist values instead of a stale base.
- R3: The LLM is told, in the same turn's system prompt, that the chemist edited the form —
  surfaced via the existing SessionContext → dynamic-prompt pattern (Drake's constraint: reuse
  this pattern, no new channel).
- R4: The FE "agent proposal always overwrites" contract stays UNCHANGED. It becomes safe because
  the agent's next proposal is computed on top of the synced chemist draft. The successful sync is
  the point where the form clears `touched`.
- R5: Confirm (`/forms/confirm`) remains the only phase-advancing write. Draft sync must never
  advance phase or revert post-confirm state (respect the phase-conditional apply precedent,
  tasks 06-28/06-29).

## Non-goals

- Objective form (has its own REST draft flow — separate scope).
- Confirm-time diff awareness (option C) — not needed once drafts sync pre-turn.
- Apply-level "chemist wins even over deliberate agent change" pins (06-29 style) — heavy; the
  prompt-level RE-RECOMMEND rule + merged base is the MVP mechanism.
- Cross-tab form-state sync of unconfirmed edits.

## Acceptance Criteria

- [x] Chemist edits CC form field (e.g. sample quantity), sends "looks good, continue" without
  confirming → next agent turn's tools see the edited value in `params_draft`, and the system
  prompt contains a chemist-edits block for that turn. (Run 7 evidence, session events.)
- [x] The agent's turn HONORS the chemist's edited value: the ladder's final echo, the
  `form_requested` draft, and committed `trials.params` all carry the edit — never silently
  reverted. **Ship-bar ruling (Drake 2026-07-03): the COMMITTED value is the contract.** A
  transient first-write blip toward the objective value (self-corrected within the turn by the
  I-ST-G authority rule; run 7: 1.5→2.5→2.5 committed vs run 6's 1.5 committed) is accepted —
  the test edit deliberately contradicts the objective, which real flows rarely do. The blip is
  a cosmetic follow-up candidate, not an AC.
- [ ] A `lab_logistics`-only edit (e.g. CC cartridge location) appears in the prompt block as an
  informational bench fact (D2) and does not trigger a re-recommend by itself.
- [ ] Send with a clean (untouched) form → request carries no draft field; BE path unchanged.
- [ ] Draft sync on a trial past `collecting_params` does not revert confirmed
  `recommended`/`lab_logistics` state.
- [ ] Contract docs updated in the same change set (Rule 10): portal `backend-contract.md`
  (`/messages` row), BE `contracts.md` §3a, `L4/events.md` (UserMessageSubmittedEvent apply),
  `L4/domain-types.md` (SessionContext field). See research/spec-docs-to-update.md.
- [ ] BE tests: route DTO, event apply (phase guard), ctx loader, prompt block. FE: typecheck +
  `pnpm check` green; existing Playwright suite stays green.
