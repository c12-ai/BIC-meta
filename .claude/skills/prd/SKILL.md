---
name: prd
description: "Use when creating, updating, relocating, splitting, merging, or reviewing PRD content. Triggers include PRD, Production PRD, Project PRD, product requirements, requirements doc, update PRD, create PRD, move PRD, split PRD, merge PRD, review PRD, 需求文档, 产品需求, 更新 PRD, 整理 PRD, 拆分 PRD, 迁移 PRD, 放在哪个 PRD, 跨端, 跨服务, 整体业务逻辑, Agent 行为, Agent Copilot, and Copilot behavior."
---

# PRD

Use this skill whenever PRD content may need to be created, updated, moved, split, merged, or reviewed.

## How to Understand PRDs in BIC

BIC PRDs are product and behavior documents, not repo onboarding documents.

Root `Production-PRD.md` should contain concrete business descriptions and business logic definitions: users, scenarios, product requirements, workflow rules, cross-service behavior, and acceptance criteria.

PRD governance rules, placement rules, clone instructions, meta repo mechanics, and "how to update PRDs" guidance belong in this skill or workspace README, not in `Production-PRD.md`.

## Routing

Choose the PRD by ownership:

- Cross-end, cross-service, or overall business-logic requirements belong in the root `Production-PRD.md`.
- Agent behavior and Agent Copilot self-behavior belong in the owning child repo, currently `BIC-agent-service/docs/project-prd.md`.
- Child Project PRDs refine the root Production PRD; they do not replace it.
- Do not duplicate root Production PRD content into child repos.
- Do not modify `BIC-shared-types` for BIC-local PRD routing.

If the scope is ambiguous, ask one question before editing: "Does this requirement change cross-repo product behavior, or only the owning repo's agent/service behavior?"

## Placement Rules

- Cross-end, cross-service, or overall business-logic PRDs live in the root meta repo.
- Agent behavior and Agent Copilot behavior PRDs live in the child repo that owns the behavior.
- Child Project PRDs refine the root Production PRD; they do not replace it.
- Root PRDs should avoid backend-only implementation details unless those details are part of the cross-service product contract.
- The root Production PRD must not be used as a place to document Git, bootstrap, repo sync, or AI instruction mechanics.

## Update Flow

1. Identify the owning PRD using the routing rules.
2. Read the target PRD and any linked parent/child PRD.
3. Preserve existing decisions unless Drake explicitly asks to replace them.
4. Add or revise requirements in the correct section.
5. Add acceptance criteria that can be verified.
6. Update the change log with the date and short summary.
7. Verify no duplicate or conflicting PRD statement was introduced.

## Root Production PRD Structure

Use this structure for cross-end, cross-service, or overall business logic:

```md
# <Product / Workflow Name> Production PRD

## Status
Owner, review state, and last updated date.

## Scope
The cross-end, cross-service, or overall business logic covered by this PRD.

## Problem / Goal
The user or business problem and intended outcome.

## Users and Scenarios
Primary users, entry points, and common workflows.

## Product Requirements
Numbered requirements focused on externally visible behavior and cross-service contracts.

## Acceptance Criteria
Testable end-to-end criteria.

## Out of Scope
Explicit exclusions.

## Dependencies / Open Questions
Known upstream decisions, dependencies, and unresolved product questions.

## Related Project PRDs
Links to child repo PRDs that refine this root PRD.

## Change Log
Brief dated changes.
```

## Child Project PRD Structure

Use this structure for repo-owned Agent, service, UI, or lab behavior:

```md
# <Repo / Agent Capability> Project PRD

## Parent Product Context
Link to the root Production PRD. From a child repo instruction file this is usually `@../Production-PRD.md`; from a PRD under `docs/`, use the correct relative path such as `../../Production-PRD.md`.

## Scope
The repo-owned behavior this PRD refines.

## Behavior Contract
Agent, service, UI, or lab behavior rules owned by this repo.

## Inputs / Outputs
User inputs, system events, API/tool outputs, or artifacts relevant to the behavior.

## State and Flow
Important states, transitions, and ordering rules.

## Edge Cases and Authority
Missing information, missing authority, failure paths, human-vs-agent ownership.

## Acceptance Criteria
Repo-level criteria that prove the behavior.

## Tests / Evidence
Relevant tests, logs, fixtures, or manual verification paths.

## Out of Scope
What remains owned by root PRD or other repos.

## Change Log
Brief dated changes.
```

## Validation

Before reporting done:

- The updated requirement is in the correct PRD layer.
- Root Production PRD contains concrete business logic, not PRD governance or workspace setup instructions.
- Root and child PRDs link to each other where needed.
- Acceptance criteria are testable.
- No duplicate PRD content was copied across layers.
- `BIC-shared-types` was not changed for BIC-local PRD maintenance.
