# Chinese localization across BIC workflow

## Goal

Cross-repo zh/en localization for Portal UI, Agent Service LLM/user-facing display metadata, and Lab Service display-name data.

## Requirements

- Portal Chinese mode covers the workflow surfaces exercised in the TLC -> CC -> FP -> RE happy path: navigation/session chrome, form labels, parameter summaries, material preparation, rack/lab spatial labels, progress/result evidence, and confirmation surfaces.
- Agent Service carries `locale` from Portal requests and confirmation events into session context, planning/specialist prompts, narration, and deterministic display metadata without making business logic depend on translated strings.
- Lab Service exposes localized display names for material-preparation inventory/rack data while preserving stable material/location keys as the business contract.
- LLM-facing language rules keep chemist-facing prose in the selected UI language and preserve technical identifiers, reagent names, units, SMILES, IDs, protocol/tool names, and structured keys.
- Translation coverage includes a maintained zh/en key parity check and a short backend-facing note that Query Agent/business logic uses machine fields, not display text.
- Temporary E2E enablement fixes, guardrail exploration, generated docx files, and scratch outputs are out of scope for this translation PR set.

## Acceptance Criteria

- [x] Portal typecheck passes.
- [x] Portal i18n parity test passes.
- [x] Agent Service import hygiene test passes for the changed event/schema layer.
- [x] Lab Service staged diff passes whitespace validation.
- [x] Live Portal flow was exercised through the full workflow path for Chinese translation review, including LLM narration, forms, material preparation, CC/FP evidence, and RE transition surfaces.
- [x] Root Production PRD documents the cross-service language consistency requirement.
- [x] Guardrail and temporary E2E enablement changes remain unsubmitted for this PR set.

## Notes

- Child repo commits prepared:
  - `BIC-agent-service`: `5f5f36e Add backend locale support for Chinese UI`
  - `BIC-agent-portal`: `de64309 Complete Chinese localization coverage`
  - `BIC-lab-service`: `e7e7c80 Localize preparation display names`
- Root meta PRD / Trellis records are tracked separately in this meta repo.
