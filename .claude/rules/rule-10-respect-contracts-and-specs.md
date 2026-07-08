# Rule 10 — Respect the contract doc and spec

Contracts between layers are the most important boundary in this codebase.
Every time you decide to change a contract between two layers — or between FE and BE — you must update the spec doc.

Applies to:
- Cross-layer contracts inside BIC-agent-service (e.g., L1 ↔ L2 ↔ L3 ↔ L4)
- FE ↔ BE contracts (BIC-agent-portal ↔ BIC-agent-service)
- Service-to-service contracts (BIC-agent-service ↔ BIC-lab-service / Nexus)
- Shared types in BIC-shared-types

Rules:
- Read the relevant spec under `.trellis/spec/` before changing any contract.
- If a code change alters a contract, update the spec in the same change set — not later.
- If spec and code disagree, surface the conflict (see Rule 5) and reconcile before proceeding.
- A contract change without a spec update is incomplete work (see Rule 9 — fail loud).
