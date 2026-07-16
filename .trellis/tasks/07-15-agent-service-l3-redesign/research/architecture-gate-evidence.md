# Architecture-gate evidence

Evidence baseline: BIC Agent Service live `main` at `12a84f3238a952f00eb95b24c1943f8303041350`.

## Existing tooling

- `pyproject.toml` installs and configures Ruff, mypy, and Pyright.
- Ruff is CI-gated and currently enables broad style, bug-risk, import sorting, and Bandit-derived rules, but there is no protected-package dependency contract or `TID` architecture configuration.
- Pyright is CI-gated but uses `typeCheckingMode = "basic"`.
- mypy is installed and configured but is not invoked by the visible Makefile, pre-commit hooks, or repository CI. Maintaining two type checkers without two active gates would create configuration drift.
- Pre-commit runs Ruff and Pyright but not Import Linter.
- Import Linter is neither installed nor configured.
- `tests/unit/test_import_hygiene.py` implements source-regex gates for only a small set of rules:
  - repositories must not import raw SQL helpers;
  - MQ and scheduler code must not import `SessionService`;
  - event modules must not import other application packages.
- The ordinary test workflow runs these regex checks as part of pytest. The reusable Python CI workflow runs the configured lint/type suite, but no explicit `lint-imports` step exists.
- The L3 Trellis mapping describes intended dependency contracts while explicitly recording that they are not connected to CI.
- A separate L1 spec currently claims Import Linter enforcement exists, so even the architecture documentation has drifted from the live gate state.

Primary files:

- `pyproject.toml`
- `.github/workflows/ci.yml`
- `.github/workflows/test.yml`
- `tests/unit/test_import_hygiene.py`
- `.trellis/spec/backend/L3/_apex_to_repo_mapping.md`
- `.trellis/spec/backend/L1/wiring-and-lifecycle.md`

## Demonstrated gaps

- `app/runtime/runtime.py` currently imports session implementations and receives `Persistence`.
- `app/runtime/graphs/factory.py` receives persistence/repository and raw Lab client capabilities.
- The Lab client protocol contains both read and state-changing operations, so allowing the protocol for Query Agent also grants command capability.
- A dependency graph check can reject a direct import but cannot by itself detect a raw client passed through a Composition Root, closure, `Any`, protocol with mixed effects, or generic service container.
- Type checking is not a security boundary if prohibited capabilities are present in an allowed protocol or erased to generic types.
- Dynamic MCP discovery currently delegates arbitrary server-provided tool names without a local effect-classification contract, so import rules cannot make a discovered tool safe.

## Required division of enforcement

| Mechanism | Target responsibility |
|---|---|
| Ruff/static lint | Universally banned imports and APIs, including framework-private contracts and explicitly forbidden infrastructure entry points |
| Import Linter | Authoritative direct and transitive package dependency graph, forbidden layer edges, Foundation/domain independence, and contract-only dependencies |
| Strict Pyright boundary typing | Narrow constructor/factory ports and rejection of `Any`, `object`, unchecked casts, and generic containers at protected boundaries |
| Pytest architecture tests | Constructor, factory, closure, decorator, tool, protocol, and actual Composition Root surfaces that expose raw persistence or command capability |
| Composition Root tests | Actual runtime object graph and dependency allowlist per component |
| Startup validation | Domain Pack manifest, tool effect class, Query provenance/capability metadata, contract-version compatibility, and default-deny registration |
| Transaction/integration tests | Behavioral proof that no external command occurs before commit or outside the executor, which static analysis cannot prove |

Every gate needs a negative fixture. Without a deliberately failing example, a renamed package, changed test discovery rule, or removed CI step can silently disable the intended protection.

Ruff remains fast hygiene rather than the layer-graph authority. Import Linter should run as a dedicated required CI job and local pre-commit hook. Pyright should become strict for Foundation, neutral contracts, and Domain Packs. A second type checker should be activated only for a demonstrated additional check; otherwise the dormant mypy configuration should not be represented as architectural protection.

## Target Import Linter contracts

The final module names depend on the package-layout plan, but the semantic contracts are fixed:

1. Foundation cannot import persistence, repositories, SQL/ORM modules, or concrete L2/session services.
2. Foundation cannot import external-command clients, MQ publishers, outbox executors, mutable storage adapters, or raw MCP transport.
3. Foundation cannot import Chemistry, Biology, or any concrete Domain Pack.
4. Domain Packs may import reviewed Foundation SPI and neutral Proposal/query contracts, but cannot import persistence, concrete L2, or concrete external clients.
5. Only the outbox executor adapter may import/resolve state-changing external-command clients.
6. L4 technical adapters remain leaf implementations and cannot reverse-import L1/L2/L3 policy.
7. L3 emits only Agent runtime output contracts; durable Turn-terminal ownership stays in L2.
8. One dedicated Composition Root is the reviewed cross-layer wiring exception; exceptions cannot spread through `main.py` or ordinary packages.

## Closing the raw-DI loophole

- Split the current mixed Lab protocol into capability-shaped query and command adapters; classification follows semantic effects, not HTTP methods.
- Do not mirror the entire raw Lab client in a nominally read-only port.
- Pass a curated, typed Foundation capability bundle rather than a service locator or client registry.
- Model-visible tools register through a typed descriptor with a mandatory effect class; bare dynamically discovered tools are rejected.
- Startup validation checks the loaded object graph and metadata rather than trusting structural `Protocol` compatibility alone.
- Architecture tests construct Foundation and Domain Packs with malicious or widened dependencies and prove composition fails.
