# Adopt root meta repo for shared Production PRD

## Goal

Convert the current `/Users/drakezhou/Development/BIC` workspace into a root meta repo that synchronizes shared project documentation across developers while preserving the existing child repositories as independent implementation repos.

The canonical Production PRD should live at the root workspace level and be discoverable from the child repos used by portal, agent service, lab service, and shared contracts.

## User Value

- Developers clone one workspace entry point before cloning or bootstrapping the child repos.
- Product requirements have one canonical source of truth instead of drifting across service repos.
- AI agents working from root or from a child repo can find the shared Production PRD consistently.
- Existing implementation repos keep their independent branch, PR, and release workflows.

## Confirmed Facts

- `/Users/drakezhou/Development/BIC` is currently not a Git repository.
- The workspace already has root-level `README.md`, `AGENTS.md`, `CLAUDE.md`, `.gitignore`, and `.trellis/`.
- Child directories including `BIC-agent-portal`, `BIC-agent-service`, `BIC-lab-service`, and `BIC-shared-types` are already independent Git repositories.
- Root `README.md` currently describes cloning child repos as siblings under one parent folder.
- `BIC-agent-service/AGENTS.md` already references a service-local PRD at `docs/project-prd.md`.
- `BIC-agent-service/docs/project-prd.md` contains backend/copilot-specific product behavior notes and should be preserved as a service-level PRD rather than treated as the cross-repo Production PRD.
- The requested direction is "方案 1：Root Meta Repo".

## Requirements

- Initialize or prepare the root workspace as a meta repo for shared documentation and workspace-level configuration.
- Add a canonical root Production PRD file at a stable path containing concrete business descriptions and business logic definitions.
- Establish PRD placement rules: cross-end or overall business-logic PRDs live in the root meta repo; Agent behavior and Agent Copilot self-behavior PRDs live in the relevant child repo.
- Add a root-level PRD Skill that captures the PRD hierarchy, update workflow, trigger conditions, and standard PRD structures.
- Move PRD-governance guidance out of `Production-PRD.md` and into the `prd` skill.
- Add the PRD Skill to the SOP Index in relevant repo AI instruction files so PRD work routes through the same workflow.
- Update root onboarding documentation so new developers clone the root meta repo first, then fetch child repos through documented commands.
- Manage child repos by root `.gitignore` plus documented clone/bootstrap flow; do not use Git submodules.
- Track Trellis workflow/spec/task/workspace artifacts in the root meta repo; ignore only Trellis runtime and personal pointer files per official Trellis guidance.
- Update child repo agent instructions so they point to the root Production PRD without duplicating its content.
- Keep `BIC-agent-service/docs/project-prd.md` as a service-level PRD, but clarify its relationship to the root Production PRD.
- Preserve the Claude Code / Codex instruction sync strategy by using `AGENTS.md` as a symlink to `CLAUDE.md` where this workspace standard applies.
- Do not modify any file, symlink, directory structure, or metadata inside `BIC-shared-types`; treat it only as a normal referenced child repo because it is cross-team and has broader ownership.
- Add `@../Production-PRD.md` style references from relevant child repo canonical AI instruction files so the shared product context is loaded by AI tools.
- Preserve child repos as independently managed Git repositories.
- Avoid backward-compatibility scaffolding that is not explicitly needed.
- Make the clone/update flow understandable to developers who have not used meta repos before.

## Acceptance Criteria

- [ ] Root workspace has a clear canonical Production PRD path.
- [ ] Root Production PRD contains concrete business description and business logic rather than PRD governance rules.
- [ ] Root workspace has a PRD Skill with explicit trigger conditions and standard root/child PRD structures.
- [ ] Root README explains the meta repo model and the expected clone order.
- [ ] Child repo agent docs reference the root Production PRD with `@../Production-PRD.md` where applicable.
- [ ] Root, portal, agent service, and lab service SOP Index tables reference the PRD Skill.
- [ ] Claude Code and Codex instructions stay synchronized through the agreed symlink pattern.
- [ ] Root Git tracking does not accidentally vendor full child repo contents.
- [ ] Root Git tracking includes `.trellis/spec/`, `.trellis/tasks/`, `.trellis/workspace/`, `.trellis/workflow.md`, and `.trellis/scripts/`.
- [ ] The planned workflow explains how to update PRD and implementation changes together when both are required.
- [ ] Verification proves root Git status does not stage child repo code unexpectedly.
- [ ] Verification proves child repo statuses are intentional and `BIC-shared-types` remains unchanged.
- [ ] Bootstrap verification proves all-target and targeted clone flows can dry-run and skip existing repos without mutating child repos.

## Out of Scope

- Moving implementation code between repos.
- Collapsing child repos into a monorepo.
- Migrating existing child repo branches or CI pipelines.
- Replacing service-local technical PRDs/specs unless explicitly requested.
- Migrating all `BIC-agent-service/docs/project-prd.md` content into the root Production PRD.
- Any changes inside `BIC-shared-types`.
- Publishing remote GitHub repositories; this task can prepare local files and instructions, but remote creation depends on repo access and naming decisions.

## Decisions

- Do not use Git submodules for child repos.
- Use root `.gitignore` to keep child repo contents out of the meta repo.
- Root meta repo should track `.trellis/workflow.md`, `.trellis/spec/`, `.trellis/tasks/`, `.trellis/workspace/`, and `.trellis/scripts/` artifacts. Ignore only runtime/pointer/temp files such as `.trellis/.developer`, `.trellis/.current-task`, `.trellis/.runtime/`, `.trellis/.agents/`, `.trellis/.agent-log`, `.trellis/.session-id`, `.trellis/.plan-log`, `.trellis/.backup-*`, `*.tmp`, `*.pyc`, and caches.
- Use README clone instructions, with `make bootstrap` as the one-command onboarding entry point and targeted Make targets for individual child repos.
- Keep the existing AI instruction synchronization approach: `AGENTS.md` should be a symlink to `CLAUDE.md` where both tools need the same repo-level instructions.
- `BIC-shared-types` is read/reference-only for this task; do not edit anything inside it.
- PRD placement rule: cross-end / overall business logic belongs in the root meta repo; Agent behavior / Agent Copilot behavior belongs in the child repo that owns that behavior.
- `Production-PRD.md` is for business/product content; PRD interpretation and maintenance rules belong in the `prd` skill.
- PRD Skill should live at root and be referenced from root, `BIC-agent-portal`, `BIC-agent-service`, and `BIC-lab-service` SOP Indexes; do not add anything inside `BIC-shared-types`.
