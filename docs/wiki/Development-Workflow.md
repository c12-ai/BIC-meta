# Development Workflow

## Default Workspace Flow

1. Clone `BIC-meta`.
2. Run the relevant bootstrap command.
3. Read root `CLAUDE.md` / `AGENTS.md`.
4. Read the repo-local `CLAUDE.md` / `AGENTS.md` for the child repo being modified.
5. Use the root Production PRD for cross-repo business logic.
6. Use repo-local Project PRDs for repo-specific behavior.

## AI Tool Synchronization

`AGENTS.md` is kept as a symbolic link to `CLAUDE.md` where practical. This keeps Claude Code and Codex aligned on the same repo instructions.

The root `prd` skill is stored at:

`BIC-meta/.claude/skills/prd/SKILL.md`

Codex accesses the same skill through:

`BIC-meta/.agents/skills/prd`

## Trellis

Trellis artifacts live under `.trellis/`. Track reusable workflow/spec/task artifacts that help the team reproduce the work. Do not track machine-local runtime state.
