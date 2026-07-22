# Pre-test Risk Model

Generate the Risk Matrix before executing tests. It describes how much
verification uncertainty remains in the Issue-to-Diff-to-test chain; it is not
post-test residual risk and cannot claim that a test passed.

## Inputs

Use only concrete evidence from:

- the selected or explicitly overridden Issue title, body, labels, and
  acceptance items, plus open-Issue candidates scanned from affected
  repositories and their ambiguity warnings;
- changed repositories, modules, files, objects, and change types;
- contract/stateful module boundaries;
- direct, safe indirect, possible, disabled, assertion-free, and missing tests,
  including Playwright/CDP browser evidence kept separate from backend/unit tests.

Do not use a path, label, filename, or keyword match by itself to assign risk.
Do not choose among equally authoritative Issue candidates. Keep requirement
alignment `unassessed` until the association is authoritative or a
provenance-bearing reference hint is explicitly justified as strong-related;
preserve the independently derived technical risk.

Keep provenance and topical similarity separate:

- `authoritative`: explicit Issue override, local Issue file, or a linked/closing
  Issue from the auto-detected current PR.
- `reference-hint`: commit/branch reference. It may become `strong-related` only
  after its preserved provenance and full body both match concrete Diff objects.
- `thematic-candidate`: ordinary open-Issue search match. It is background
  context even when it is the only similar candidate.
- `mentioned-reference`: bounded one-hop reference from a hydrated body. It does
  not inherit the parent candidate's authority.

Only `authoritative` and explicitly justified `strong-related` Issues may supply
acceptance items to the risk matrix. Never turn a thematic candidate into the
requirement source because its vocabulary resembles the Diff.

## Affected-repository Issue analysis

Run Issue analysis only after the Diff identifies affected repositories and
modules. Scan open Issues for each affected repository. When the current PR or
local Diff commits provide timestamps, use a padded activity window to scan a
bounded closed-Issue slice as well. The combined metadata budget remains 100
per repository. An explicit override is
authoritative. A unique current-PR linked/closing reference may resolve directly
and skip the broad scan only when exactly one affected GitHub repository exists.
With multiple affected repositories, scan every repository and keep that
current-PR Issue as a repository-local candidate; it cannot resolve workspace
Issue alignment by itself. A Diff-commit closing reference or `issue-123` branch
reference is a protected search hint, not sufficient evidence for automatic
selection.

When no authoritative link exists, use Issue titles and labels only to shortlist.
Match English, Chinese, and mixed-language module/object/path terms. Activity
window proximity may recall a closed candidate but never changes its thematic
association. Require a
module, object, path, or label signal for ordinary candidates, while allowing at
most one no-signal fallback per affected repository. Do not fill the shortlist
with unrelated candidates merely because budget remains. Read
at most 100 metadata records per affected repository, reduce ordinary candidates
to at most 10 after module and changed-object mapping, and read the full body of
every shortlisted candidate. Do not select a smaller body subset from metadata.
Use one GraphQL batch for multiple bodies, a bounded fallback for unresolved
candidates, and one shared 60-second deadline for the complete GitHub phase.
For only the top three candidates, read at most twenty timeline events and five
comments each; truncate comment bodies, mark them as untrusted data, and report
whether timeline evidence corroborates the auto-detected current PR without
granting authority.
Require repository identity plus a concrete match between the Issue goal or
acceptance item and a changed module, file, or object when explaining thematic
context. Even if exactly one ordinary candidate meets that standard, keep it
thematic and leave workspace Issue alignment `unassessed`. Follow at most ten
repository-contained Issue references from hydrated bodies for one hop; show
them as `mentioned-reference` context without inheriting authority. Historical
PR URLs are background context only: do not claim their Issue linkage as
workspace provenance unless the analyzer auto-detects that PR from the current
checkout. Keep Issue alignment unassessed rather than substituting a thematic
Issue.

Treat `scan-failed` and `partial-scan` as unavailable or incomplete Issue
evidence, never as proof that no open Issue exists. Keep requirement alignment
`unassessed` unless a separately preserved authoritative reference resolves and
aligns; do not discard technical risk.

## Deterministic floor

`assess-risk-matrix.sh` emits rows for Issue clarity, impact breadth,
contract/state boundaries, test evidence, browser user-journey evidence, and
change attribution. A frontend or backend-route change without related browser
evidence raises the static verification floor; a possible, module-level,
disabled, manual-only, or non-object-linked browser scenario remains medium.
Treat the highest deterministic row as the risk floor. Semantic review may raise but must
not lower it.

## Issue alignment rows

First classify every eligible acceptance item as `in-scope`, `adjacent`, or
`unchanged/out-of-scope` by comparing it with concrete changed objects. Add one
row per `in-scope` acceptance item. Keep adjacent and unchanged/out-of-scope
items visible as Issue context, but do not let an umbrella Issue inflate the
risk matrix.

For each in-scope row:

- `high`: no concrete Diff evidence implements the item, or a required
  cross-repository consumer/contract/test is missing.
- `medium`: Diff evidence exists but test evidence is missing, disabled,
  assertion-free, only possible, or too broad to verify the acceptance item.
- `low`: concrete Diff objects implement the item and an active direct/safe
  indirect test contains a relevant assertion.
- `unassessed`: the Issue is unavailable, ambiguous, or the changed behavior
  cannot be attributed precisely enough to compare.

Every row must cite Issue, Diff, and test evidence. Keyword overlap is a search
hint only. Do not lower risk because an Issue checkbox is already checked.

## Technical risk and requirement alignment

Use the highest deterministic technical row as `technical_risk` and the known
pre-test `overall_risk`. Issue alignment may raise this result later but cannot
lower it. If no Issue was authoritatively linked or explicitly promoted from a
provenance-bearing reference hint to `strong-related`, set
`requirement_alignment` to `unassessed` and assessment completeness to partial.
State explicitly that tests were not executed. The current analyzer returns one
workspace-level risk assessment. Do not infer business streams or allocate
workspace test counts and risk rows among guessed streams.
