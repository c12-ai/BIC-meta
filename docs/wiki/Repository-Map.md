# Repository Map

The canonical entry point is `c12-ai/BIC-meta`. Developers clone the meta repo first, then clone each child repo next to it.

## Repositories

| Repository | Purpose | Notes |
| --- | --- | --- |
| `c12-ai/BIC-meta` | Root meta repo | Owns Production PRD, workspace docs, orchestrator scripts, and project-level AI instructions. |
| `c12-ai/BIC-agent-portal` | Frontend portal | Reads the root Production PRD and keeps portal-specific implementation details in repo-local docs. |
| `c12-ai/BIC-agent-service` | Agent backend | Owns Agent and Agent Copilot behavior details in its Project PRD. |
| `c12-ai/BIC-lab-service` | Lab service / Nexus | Owns lab status, orchestration, experiment task reporting, and robot/MQ integration. |
| `c12-ai/BIC-shared-types` | Cross-team contracts | Referenced as an external shared dependency. Do not modify from BIC-meta tasks unless explicitly coordinated. |

## Clone Order

1. Clone `BIC-meta` (this repo), `cd` into it.
2. Clone each child repo next to it (`git clone git@github.com:c12-ai/<repo>.git`):
   `BIC-agent-service`, `BIC-agent-portal`, `BIC-lab-service`, `BIC-shared-types`,
   `mars_interface_mock`.
3. Work inside each child repo as an independent Git repository.

`make up STAGE=local` red-cards any missing repo with the clone command. See the root
`README.md` "Scripts" + "Local Startup" sections for the full orchestrator surface.
