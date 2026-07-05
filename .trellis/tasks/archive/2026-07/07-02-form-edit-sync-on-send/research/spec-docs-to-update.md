# Research: Spec docs a contract change must update (Rule 10)

- **Query**: Which `.trellis/spec/` docs cover SessionContext, prompt assembly, forms/decisions contract, and event contracts — and which must be updated by this task's contract changes.
- **Scope**: internal (spec tree)
- **Date**: 2026-07-02

**Summary**: The real spec authority lives in the per-repo trees; the root `.trellis/spec/BIC-agent-service` and `.trellis/spec/BIC-agent-portal` are **symlinks** into `BIC-agent-service/.trellis/spec` and `BIC-agent-portal/.trellis/spec` (verified `ls -la`; spec edits are committed in the sub-repos). `.trellis/spec/tech_design/{backend,frontend}/index.md` are unfilled templates ("To fill") — NOT contract authority; do not treat them as needing updates. The FE↔BE contract of record is `BIC-agent-portal`'s `backend-contract.md` plus BE `contracts.md`.

## Spec map (what covers what)

### BIC-agent-service (`.trellis/spec/BIC-agent-service/backend/` → symlink to repo)

| Doc | Covers (relevant sections) | Must update if... |
|---|---|---|
| `contracts.md` | §3a `POST /messages` flow + `SubmitUserMessageResponse` (`:125-159`); §3c forms/confirm CAS + duo-panel user-initiated confirm; §4 `TurnInput` trigger matrix (`:326`) | `/messages` body or `TurnInput`/payload changes; any new draft-sync REST contract |
| `L1/http-routes.md` | Route table (`:21` messages, `:26` objective/draft); idempotency rules (`:267,276`) | New/changed route or request model |
| `L2/facade.md` | `submit_user_message` flow (`:39-133`) | Service facade signature/flow changes |
| `L2/fast-path-handlers.md` | HITL fast-path transactions (objective draft handler home) | New fast-path draft handler |
| `L2/orchestrator.md` | `SessionContext` loader contract (`:255-298`, incl. `decode_history` projection) | New SessionContext field / loader query |
| `L4/domain-types.md` | `SessionContext` field roster (`:155-185+`); `turn_schemas.py` | New ctx field; new TurnInput payload field |
| `L4/events.md` | Event roster + apply semantics: `TaskParamsSetEvent` phase-conditional apply (`:161`), `ExperimentObjectiveDrafted` (`:162`), `FormConfirmedEvent` (`:163`), `UserMessageSubmittedEvent` (`:178-187`) | New event kind; changed payload or apply semantics |
| `L3/state.md` | `GraphState`/`SpecialistState` rosters + seeding order (`:241-246`); `SpecialistDispatchInputs` (`:147`) | New state/bundle field |
| `L3/events.md` | Emit-site roster (`:82-86`, `:243-248`) | New emitter or changed emit rules |
| `L3/graphs.md` | §2.1 dynamic-prompt ownership | New prompt block contract (e.g. chemist-draft block) |
| `L3/specialist_tools.md` | Tool ladder + §2a scalar-only prose channel | Tool/merge behavior changes |

### BIC-agent-portal (`.trellis/spec/BIC-agent-portal/` → symlink to repo)

| Doc | Covers | Must update if... |
|---|---|---|
| `backend-contract.md` | THE FE↔BE contract table: `/messages` row (`:51`), event-kind roster (`:343-345`), `task_params_set` semantics incl. "replace-merge into the live form" (`:392`) | `/messages` body change; `task_params_set` FE-side handling policy change; any new endpoint/event |
| `frontend/*.md` | Template stubs ("To fill") — component/hook/state/type-safety guidelines | Only if real content exists to add; not contract docs |
| `ui/` + `frontend/index.md` | Design tokens / chat spec | Unlikely for this task |

### Not authority

- `.trellis/spec/tech_design/backend/index.md` + `.trellis/spec/tech_design/frontend/index.md` — generic unfilled templates ("Status: To fill"); no project content. No update obligation.
- `.trellis/spec/guides/` — cross-layer thinking guides; read-only for this task.

## Rule-10 checklist for the likely change set

1. Draft rides `/messages` (or a new sibling endpoint) → `contracts.md` §3a/§4 + `L1/http-routes.md` + `L2/facade.md` + `backend-contract.md:51`.
2. New `SessionContext` field → `L4/domain-types.md` + `L2/orchestrator.md` loader section.
3. New prompt block → `L3/graphs.md` §2.1 (+ `L3/state.md` if state fields added).
4. `task_params_set` FE overwrite policy change → `backend-contract.md:392` wording ("replace-merge") + the product-contract comment in `useParamsFormHandle.ts:40-47` (keep code comment and spec in the same change set).
5. New event kind or changed apply → `L4/events.md` + `L3/events.md` + FE `src/types/events.ts` + `KINDS` in `sse-client.ts` (portal CLAUDE.md convention).

## Caveats

- Code docstrings cite spec paths as `.trellis/spec/backend/...` — that resolves inside BIC-agent-service's own `.trellis/spec/`; same files as the root symlink view.
