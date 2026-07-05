# Documents and PRD

## Document Ownership

| Document Type | Location | Owner Scope |
| --- | --- | --- |
| Production PRD | `BIC-meta/Production-PRD.md` | Cross-repo business requirements and business logic. |
| Project PRD | Child repo docs, such as `BIC-agent-service/docs/project-prd.md` | Repo-specific behavior, implementation constraints, and specialized workflows. |
| SOP / AI Skill | `BIC-meta/.claude/skills/prd/SKILL.md` | Rules for updating, splitting, relocating, and validating PRDs. |
| Architecture notes | Repo-local docs or future wiki pages | Durable architecture context that is not a PRD requirement. |

## Placement Rules

- Cross-client, cross-service, or whole-business logic belongs in the root Production PRD.
- Agent behavior and Agent Copilot behavior belong in the Agent Service Project PRD.
- Shared contract changes in `BIC-shared-types` are cross-team and should be handled through that repo's normal review process.
- Do not duplicate PRD requirements across multiple repos. Link to the source of truth instead.

## PRD Update Flow

1. Identify whether the change is product-level or repo-specific.
2. Update the source-of-truth PRD.
3. Add links from repo-local AI docs when the repo must always load that PRD.
4. Validate that no conflicting duplicate requirements remain.
5. Commit the PRD and related doc references together.
