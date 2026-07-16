# Source inventory

Evidence gathered on 2026-07-15 for the Agent Service L3 redesign. This file records source scope and freshness; it does not approve the proposed architecture.

## Product and architecture sources

- Root product contract: `Production-PRD.md` in BIC-meta.
- Original technical design: `/Users/wenlongwang/Work/BIC/tech_design/narrative/`, especially `31_architecture.md`, `32_layer_L1.md`, `33_layer_L2.md`, `34_layer_L3.md`, `35_layer_L4.md`, and `diagrams/`.
- Feishu guide: `[中文] Agent Foundation 重构 · 自顶向下导读`, document token `Vm6RdmhZCoBvTCx3VlucX3UFnbg`.
- Full Feishu proposal: `[中文] Agent Foundation 重构：需求与架构提案`, document token `WsbLdCfkToIqj4xvmx7caBxWnrc`.
- The full proposal says its baseline is Agent Service `main @ 643d2bc`; live `origin/main` was `12a84f3` during this review.

## Pull requests

- [Agent Service PR #94](https://github.com/c12-ai/BIC-agent-service/pull/94): open, conflicting, review required, head `4d86c17`.
- [Agent Service PR #136](https://github.com/c12-ai/BIC-agent-service/pull/136): open, conflicting, review required, head `4e77442`.
- [Agent Service PR #150](https://github.com/c12-ai/BIC-agent-service/pull/150): open draft, docs-only, review required, head `8614569`.
- PR #150's current head is newer than the `4a9a951` revision named by the Feishu guide.

## Issue scope

The primary meta umbrella issues are [#131](https://github.com/c12-ai/BIC-meta/issues/131), [#128](https://github.com/c12-ai/BIC-meta/issues/128), and [#33](https://github.com/c12-ai/BIC-meta/issues/33). Supporting issues are summarized in `meta-structural-issues.md`.

## Evidence boundary

- PR facts were checked against live GitHub metadata and the three PR heads.
- Original-design findings describe the historical design documents, not necessarily live code.
- Meta issue findings describe the facts and baselines recorded by each issue; not every historical issue assertion was independently reproduced against live Agent Service main.
- Feishu documents are proposals and review artifacts, not approved implementation authority.
