# BIC Workspace Discovery

BIC is a multi-repository workspace rooted at `BIC-meta`. The table below is
orientation only; it is not the analyzer's repository registry. The analyzer
always discovers the root and immediate independent child Git repositories via
`git rev-parse --show-toplevel`, including worktrees and future repositories.

| Area | Path | Role |
|---|---|---|
| Meta | `BIC-meta` | Workspace, PRD, Trellis, cross-repo governance |
| Portal | `BIC-agent-portal` | React/Vite frontend, local port 5173 |
| Agent Service | `BIC-agent-service` | FastAPI/LangGraph backend, local port 8800 |
| Lab Service | `BIC-lab-service` | Nexus/LIMS/Robot/MQ/MCP service, local port 8192 |
| Shared Types | `BIC-shared-types` | Cross-team shared object types and contracts |
| Robot Mock | `mars_interface_mock` | Robot MQ mock |

This phase is read-only. Do not start services, reset data, or execute tests while using this skill.
New repositories appear immediately under their discovered directory name.
Their unmatched source files receive structural modules when possible and stay
visible as `unmapped` otherwise. Configuration is only needed to assign a known
BIC business module or explicit module-to-test relationship.
