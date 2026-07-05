# Implementation Plan

## Preconditions

- Drake confirmed child repos should be ignored/bootstrap-managed, not tracked as Git submodules.
- Drake provides or approves the remote repository name for the root meta repo, if remote setup is in scope.

## Steps

1. Create or update root `Production-PRD.md`.
   - Keep it focused on concrete business descriptions and business logic definitions.
   - Do not put PRD governance, clone flow, or workspace setup mechanics in this file.
2. Update root `.gitignore` so child repo directories are not accidentally committed as embedded repositories.
   - Ensure `.trellis/workflow.md`, `.trellis/spec/`, `.trellis/tasks/`, `.trellis/workspace/`, and `.trellis/scripts/` remain trackable.
   - Ensure Trellis runtime/pointer/temp files remain ignored via `.trellis/.gitignore`.
3. Update root `README.md` to explain:
   - root meta repo purpose
   - clone root first
   - clone/bootstrap child repos second with `make bootstrap`
   - how to update Production PRD alongside implementation PRs
4. Standardize AI instruction sync for touched repos:
   - `CLAUDE.md` contains canonical instructions.
   - `AGENTS.md` is a symlink to `CLAUDE.md`.
   - Preserve existing symlinks, including `BIC-agent-service/AGENTS.md -> CLAUDE.md`.
   - Do not touch `BIC-shared-types`.
5. Converge repo docs:
   - Root `CLAUDE.md`: add `Project-level Production PRD: @Production-PRD.md` and preserve any root `AGENTS.md`-only instructions before converting `AGENTS.md` to a symlink.
   - `BIC-agent-portal/CLAUDE.md`: add `Project-level Production PRD: @../Production-PRD.md`; convert `AGENTS.md` to a symlink after preserving any unique content if present.
   - `BIC-agent-service/CLAUDE.md`: add `Project-level Production PRD: @../Production-PRD.md` above the existing `Project level PRD: @docs/project-prd.md`; keep `AGENTS.md -> CLAUDE.md`.
   - `BIC-agent-service/docs/project-prd.md`: keep as service-level PRD and, if edited, add a short ownership note that it refines the root Production PRD for backend/copilot behavior.
   - `BIC-lab-service/CLAUDE.md`: add `Project-level Production PRD: @../Production-PRD.md`; convert `AGENTS.md` to a symlink after preserving any unique content if present.
   - `BIC-shared-types`: no changes.
6. Add root PRD Skill:
   - Create `.claude/skills/prd/SKILL.md`.
   - Expose the same skill under `.agents/skills/prd`, preferably by symlink to the canonical root skill.
   - Encode PRD placement rules: cross-end / overall business logic at root; Agent behavior / Agent Copilot behavior in child repo PRDs.
   - Encode how to understand PRDs in BIC: `Production-PRD.md` contains business/product logic, while PRD governance and maintenance rules live in the skill.
   - Encode standard structures for root Production PRDs and child Project PRDs.
   - Encode explicit trigger keywords and phrases in English and Chinese.
   - Add SOP Index rows to root, `BIC-agent-portal`, `BIC-agent-service`, and `BIC-lab-service`; do not touch `BIC-shared-types`.
7. Add root `Makefile` bootstrap targets to clone missing child repos, delegating to `scripts/bootstrap.sh` if that keeps the Makefile readable:
   - `make bootstrap` clones all missing child repos.
   - `make bootstrap-backend` clones `BIC-agent-service` only.
   - `make bootstrap-portal` clones `BIC-agent-portal` only.
   - `make bootstrap-lab` clones `BIC-lab-service` only.
   - `make bootstrap-shared` clones `BIC-shared-types` only without modifying anything inside it.
   - `DRY_RUN=1` prints clone/skip decisions without cloning or mutating existing repos.
8. Initialize root Git repo if not already initialized.
9. Verify root Git status only includes intended meta files and does not stage child repo contents.

## Validation

```bash
git status --short
git -C BIC-agent-portal status --short
git -C BIC-agent-service status --short
git -C BIC-lab-service status --short
git -C BIC-shared-types status --short
git check-ignore -v BIC-agent-portal BIC-agent-service BIC-lab-service BIC-shared-types
if git check-ignore -q .trellis/workspace; then echo ".trellis/workspace must be tracked"; exit 1; fi
git check-ignore -v .trellis/.developer .trellis/.current-task .trellis/.runtime .trellis/.agents
find . -maxdepth 2 -name AGENTS.md -print
find . -maxdepth 2 \( -name AGENTS.md -o -name CLAUDE.md \) -exec ls -la {} \;
test -f .claude/skills/prd/SKILL.md
test -e .agents/skills/prd
rg -n "prd|Production PRD|Project PRD|更新 PRD|整理 PRD|Agent Copilot" .claude/skills/prd/SKILL.md CLAUDE.md BIC-agent-portal/CLAUDE.md BIC-agent-service/CLAUDE.md BIC-lab-service/CLAUDE.md
```

```bash
make -n bootstrap
make -n bootstrap-backend
make bootstrap DRY_RUN=1
make bootstrap-backend DRY_RUN=1
bash -n scripts/bootstrap.sh
```

## Review Gates

- Root Git status must not show child repo implementation files as staged or untracked meta repo content.
- Child repo Git statuses must show only intentional doc/symlink changes in touched repos.
- `BIC-shared-types` Git status must remain unchanged.
- `.trellis/workspace/` must remain trackable by root Git, matching official Trellis team-sharing guidance.
- Trellis runtime/pointer/temp files must remain ignored by root Git.
- Bootstrap dry-run must prove existing repo skip behavior and targeted clone behavior without mutating child repos.
- Child repo references must point to the root PRD by relative path and must not duplicate the PRD text.
- Child repo PRD references must use `@../Production-PRD.md` in canonical AI instruction files.
- `Production-PRD.md` must describe BIC business logic and must not be a PRD-governance document.
- `AGENTS.md` / `CLAUDE.md` synchronization must be intentional and visible in `ls -la`.
- PRD Skill must define trigger conditions and standard structures for root Production PRDs and child Project PRDs.
- SOP Index entries must point to the PRD Skill from root and relevant child repos.
- No files under `BIC-shared-types/` may be modified.
- README must be clear enough for a developer unfamiliar with meta repos.
