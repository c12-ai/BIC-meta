# Design: Root meta repo for shared Production PRD

## Architecture

Use the current `BIC/` directory as the root meta repo. The meta repo owns shared documentation and workspace-level instructions only:

- `Production-PRD.md`
- root `README.md`
- root `AGENTS.md`
- root `CLAUDE.md`
- optional workspace bootstrap scripts
- Trellis workspace metadata, if Drake wants Trellis state synchronized through this repo

The child repos remain independent Git repositories:

- `BIC-agent-portal/`
- `BIC-agent-service/`
- `BIC-lab-service/`
- `BIC-shared-types/`
- optional supporting repos such as `mars_interface_mock/`, `tech_design/`, and `tlc-op-builder/`

Root Trellis artifacts follow the official Trellis tracking model:

- Track workflow and planning assets: `.trellis/workflow.md`, `.trellis/spec/`, `.trellis/tasks/`, and `.trellis/scripts/`.
- Track `.trellis/workspace/<developer>/` journals and indexes. Trellis treats workspace memory as part of the team-shared LLM wiki; teammates can read each other's progress.
- Do not track runtime/session pointer assets already listed in `.trellis/.gitignore`: `.trellis/.developer`, `.trellis/.current-task`, `.trellis/.runtime/`, `.trellis/.agents/`, `.trellis/.agent-log`, `.trellis/.session-id`, `.trellis/.plan-log`, `.trellis/.backup-*`, `*.tmp`, `*.pyc`, and caches.

## Recommended Git Model

Do not use Git submodules for the first version.

Instead:

- Root `.gitignore` ignores child repo directory contents.
- Root README documents the child repos and target clone commands.
- `make bootstrap` clones missing child repos into the expected sibling paths, using a script implementation if useful.

This keeps the root repo as a stable onboarding and documentation entry point without forcing every developer to learn submodule commands or pin child repo commits through the meta repo.

`make bootstrap` is an onboarding helper, not a package manager. It should be safe to run repeatedly: if a child repo directory already exists, it skips that repo; if it is missing, it runs the documented `git clone` command. It does not mutate child repo branches after clone unless explicitly designed to do so.

Bootstrap must support dry-run mode so validation can prove clone/skip decisions without network or filesystem mutation:

```bash
make bootstrap DRY_RUN=1
make bootstrap-backend DRY_RUN=1
```

Dry-run output should show which repos would be cloned and which existing repos would be skipped. The script must not run `git pull`, `git checkout`, `git reset`, or any other command that mutates an existing child repo.

Use Make targets rather than pseudo flags for targeted clones. `make bootstrap --backend` is not recommended because `--backend` is parsed as a Make option. Prefer explicit targets:

```bash
make bootstrap           # clone all missing child repos
make bootstrap-backend   # clone BIC-agent-service only
make bootstrap-portal    # clone BIC-agent-portal only
make bootstrap-lab       # clone BIC-lab-service only
make bootstrap-shared    # clone BIC-shared-types only; root-level clone only, no edits inside repo
```

## Production PRD Ownership

`Production-PRD.md` is the cross-repo product source of truth.

Service-local PRDs and technical specs remain valid when they describe service-specific implementation details. They should refer upward to the root Production PRD instead of trying to restate the product requirement.

PRD placement rule:

- Cross-end, cross-service, or overall business-logic PRDs live in the root meta repo.
- Agent behavior and Agent Copilot self-behavior PRDs live in the child repo that owns the agent behavior, currently `BIC-agent-service/docs/project-prd.md`.
- Child PRDs refine the root Production PRD; they do not replace it.
- Root PRDs should avoid backend-only implementation details unless those details are part of the cross-service product contract.

Example relationship:

- Root `Production-PRD.md`: product workflow, user-facing behavior, cross-service acceptance.
- `BIC-agent-service/docs/project-prd.md`: backend copilot behavior details and service-level contracts.
- `.trellis/spec/...`: executable engineering invariants and layer rules.

## Documentation Convergence

Root meta repo:

- `Production-PRD.md` is the canonical product requirements document.
- `Production-PRD.md` contains concrete business descriptions and business logic definitions, not PRD governance or workspace setup instructions.
- `README.md` explains the workspace model, clone order, `make bootstrap*` commands, and PRD update workflow.
- `CLAUDE.md` is the canonical AI instruction file and includes `Project-level Production PRD: @Production-PRD.md`.
- `AGENTS.md` should be a symlink to `CLAUDE.md`; before replacing the current root `AGENTS.md`, preserve any root-only Codex instructions by moving them into `CLAUDE.md`.

`BIC-agent-portal`:

- Keep implementation guidance in `CLAUDE.md`.
- Add `Project-level Production PRD: @../Production-PRD.md` near the top.
- Replace `AGENTS.md` with a symlink to `CLAUDE.md` after confirming no unique AGENTS-only content must be preserved.
- Do not duplicate the Production PRD in the repo.

`BIC-agent-service`:

- Keep `CLAUDE.md` as the canonical AI instruction file; `AGENTS.md -> CLAUDE.md` already exists and should be preserved.
- Keep `Project level PRD: @docs/project-prd.md` as the service-level/backend copilot PRD.
- Add `Project-level Production PRD: @../Production-PRD.md` above the service-local PRD reference, making the hierarchy explicit: root Production PRD for cross-repo product intent, service PRD for backend-specific behavior.
- Lightly tidy `docs/project-prd.md` only to clarify ownership if needed: it should state that it refines the root Production PRD for Agent Service behavior. Do not bulk-migrate or delete historical backend/copilot decisions from this file.

`BIC-lab-service`:

- Keep implementation guidance in `CLAUDE.md`.
- Add `Project-level Production PRD: @../Production-PRD.md` near the top.
- Replace `AGENTS.md` with a symlink to `CLAUDE.md` after confirming no unique AGENTS-only content must be preserved.
- Do not duplicate the Production PRD in the repo.

`BIC-shared-types`:

- Do not modify any files, symlinks, docs, metadata, or directory structure.
- It may be listed from root README/bootstrap as a referenced child repo only.

## PRD Skill

Create a root-level PRD Skill for creating, updating, relocating, splitting, merging, or reviewing PRD content.

Canonical location:

```text
BIC/.claude/skills/prd/SKILL.md
```

Expose the same skill to Codex under root `.agents/skills`, preferably as a symlink to the canonical skill if local tooling handles directory symlinks reliably:

```text
BIC/.agents/skills/prd -> ../../.claude/skills/prd
```

If directory symlinks prove brittle, duplicate only this skill folder and treat `.claude/skills/prd` as the canonical source.

Add SOP Index rows in root, `BIC-agent-portal`, `BIC-agent-service`, and `BIC-lab-service` canonical `CLAUDE.md` files. Because `AGENTS.md` will symlink to `CLAUDE.md`, Codex receives the same SOP routing. Do not add anything inside `BIC-shared-types`.

Root SOP Index row:

```md
| `prd` | Updating, creating, relocating, splitting, merging, or reviewing Production PRD / Project PRD content; deciding whether requirements belong at root or child-repo level | `@.claude/skills/prd/SKILL.md` |
```

Child repo SOP Index row:

```md
| `prd` | Updating, creating, relocating, splitting, merging, or reviewing Production PRD / Project PRD content; deciding whether requirements belong at root or child-repo level | `@../.claude/skills/prd/SKILL.md` |
```

The skill frontmatter description must include explicit trigger terms in English and Chinese:

- "PRD", "Production PRD", "Project PRD", "product requirements", "requirements doc"
- "update PRD", "create PRD", "move PRD", "split PRD", "merge PRD", "review PRD"
- "需求文档", "产品需求", "更新 PRD", "整理 PRD", "拆分 PRD", "迁移 PRD", "放在哪个 PRD"
- "跨端", "跨服务", "整体业务逻辑", "Agent 行为", "Agent Copilot", "Copilot behavior"

The skill body must define:

- How to understand PRDs in BIC: root Production PRDs contain business/product logic; PRD governance and update mechanics live in the skill.
- How to choose the correct PRD based on scope.
- How to preserve root vs child PRD hierarchy.
- Standard structure for root Production PRDs.
- Standard structure for child Project PRDs.
- Required clarification question when scope is ambiguous.
- Validation checklist before reporting done.

Standard root Production PRD structure:

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

Standard child Project PRD structure:

```md
# <Repo / Agent Capability> Project PRD

## Parent Product Context
Link to the root Production PRD, usually `@../Production-PRD.md`.

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

## AI Tool Instruction Sync

Claude Code reads `CLAUDE.md`; Codex reads `AGENTS.md`. The workspace standard is to keep one canonical instruction file per repo and expose it to both tools through a symlink.

Preferred pattern:

```text
CLAUDE.md   # canonical content
AGENTS.md  -> CLAUDE.md
```

This pattern is already present in `BIC-agent-service/AGENTS.md -> CLAUDE.md` and should be preserved. For root, `BIC-agent-portal`, `BIC-agent-service`, and `BIC-lab-service`, standardize on the same pattern unless a repo has a specific reason to keep separate tool instructions.

Do not modify `BIC-shared-types` at all. It is cross-team and has broader ownership, so this task may list or reference it from root-level docs/bootstrap only.

The shared Production PRD reference should live in the canonical `CLAUDE.md` content so both Claude Code and Codex receive the same product-context instruction through the symlink. Use the workspace's `@` reference style so AI tools treat the PRD as context to load:

```md
Project-level Production PRD: @../Production-PRD.md
```

From root-level `CLAUDE.md`, use:

```md
Project-level Production PRD: @Production-PRD.md
```

Child repo references should point upward to the root meta repo's PRD rather than duplicating PRD content locally.

## Update Flow

When a change affects product behavior:

1. Open a root meta repo PR that updates `Production-PRD.md`.
2. Open one or more child repo PRs that implement the change.
3. Link the PRD PR or commit from each implementation PR.

For small documentation-only PRD updates, only the root meta repo PR is required.

## Clone Flow

New developers clone the root meta repo first:

```bash
git clone git@github.com:<org>/<bic-meta-repo>.git BIC
cd BIC
```

Then they clone child repos using documented commands or `make bootstrap`.

## Risks and Tradeoffs

- Ignoring child dirs means root clone alone does not contain implementation code. Mitigation: README and bootstrap script make the second step explicit.
- Without submodules, the root meta repo does not pin exact child repo commits. This is acceptable if branch ownership remains in child repos.
- Tracking `.trellis/tasks` and `.trellis/workspace` means task planning artifacts and developer journals are shared through the root meta repo. This matches Trellis' default team coordination model.
- Git symlinks require developer environments that preserve symlinks. This is acceptable for the current workspace convention, but onboarding docs should call out that `AGENTS.md` is expected to point at `CLAUDE.md`.
- `BIC-shared-types` will not receive the root PRD AI-context reference from inside its repo. This is intentional to avoid cross-team repo churn.
- If exact workspace reproducibility becomes more important than simplicity, the design can later move to submodules or a manifest file.

## Rollback

If the meta repo model is rejected, remove root `.git/` and keep the child repos unchanged. Documentation edits can be reverted from the root meta repo branch without touching child repo histories.
