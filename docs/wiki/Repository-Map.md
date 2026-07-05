# Repository Map

The canonical entry point is `c12-ai/BIC-meta`. Developers should clone the meta repo first, then use its bootstrap commands to clone child repos.

## Repositories

| Repository | Purpose | Notes |
| --- | --- | --- |
| `c12-ai/BIC-meta` | Root meta repo | Owns Production PRD, workspace docs, bootstrap, and project-level AI instructions. |
| `c12-ai/BIC-agent-portal` | Frontend portal | Reads the root Production PRD and keeps portal-specific implementation details in repo-local docs. |
| `c12-ai/BIC-agent-service` | Agent backend | Owns Agent and Agent Copilot behavior details in its Project PRD. |
| `c12-ai/BIC-lab-service` | Lab service / Nexus | Owns lab status, orchestration, experiment task reporting, and robot/MQ integration. |
| `c12-ai/BIC-shared-types` | Cross-team contracts | Referenced as an external shared dependency. Do not modify from BIC-meta tasks unless explicitly coordinated. |

## Clone Order

1. Clone `BIC-meta`.
2. Run `make bootstrap` for all repos, or a targeted command such as `make bootstrap-backend`.
3. Work inside each child repo as an independent Git repository.

## Bootstrap Commands

| Command | Effect |
| --- | --- |
| `make bootstrap` | Clone all expected child repos if missing. |
| `make bootstrap-backend` | Clone `BIC-agent-service` only. |
| `make bootstrap-portal` | Clone `BIC-agent-portal` only. |
| `make bootstrap-lab` | Clone `BIC-lab-service` only. |
| `make bootstrap-shared` | Clone `BIC-shared-types` only. |
