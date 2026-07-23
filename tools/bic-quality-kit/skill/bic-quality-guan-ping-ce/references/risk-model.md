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
Do not choose among equally authoritative Issue candidates. Enable requirement
alignment only when the user explicitly supplies an Issue or the auto-detected
current PR yields exactly one linked/closing Issue. Otherwise use technical-only
mode and preserve the independently derived technical risk.

Keep provenance and topical similarity separate:

- `authoritative`: explicit Issue override, local Issue file, or a linked/closing
  Issue from the auto-detected current PR.
- `reference-hint`: commit/branch reference. It remains diagnostic context until
  the user explicitly supplies the Issue on a later run.
- `thematic-candidate`: ordinary open-Issue search match. It is background
  context even when it is the only similar candidate.
- `mentioned-reference`: bounded one-hop reference from a hydrated body. It does
  not inherit the parent candidate's authority.

Only `authoritative` Issues may supply acceptance items to the risk matrix.
Never turn a reference hint or thematic candidate into the requirement source
because its vocabulary resembles the Diff.

## Affected-repository Issue analysis

Run Issue analysis only after the Diff identifies affected repositories and
modules. Scan open Issues for each affected repository. An explicit override is
authoritative. A unique current-PR linked/closing reference may resolve directly
and skip the broad scan only when exactly one affected GitHub repository exists.
With multiple affected repositories, scan every repository, then use one unique
current-PR Issue as an additive requirement overlay without filtering technical
scope. A Diff-commit closing reference or `issue-123` branch reference is a
protected search hint, not sufficient evidence for automatic selection.

When no authoritative link exists, use Issue titles and labels only to shortlist.
Match English, Chinese, and mixed-language module/object/path terms. Require a
module, object, path, or label signal for every ordinary candidate. Repository
membership alone records scan coverage and must not create a shortlist
candidate; report affected repositories without a semantic match as unmatched.
Do not fill the shortlist with unrelated candidates merely because budget remains. Read
at most 100 metadata records per affected repository, reduce ordinary candidates
to at most 10 after module and changed-object mapping, and read the full body of
every shortlisted candidate. Do not select a smaller body subset from metadata.
Use one GraphQL batch for multiple bodies, a bounded fallback for unresolved
candidates, and one shared 60-second deadline for the complete GitHub phase.
Require repository identity plus a concrete match between the Issue goal or
acceptance item and a changed module, file, or object when explaining thematic
context. Even if exactly one ordinary candidate meets that standard, keep it
thematic and leave workspace requirement alignment `not-enabled`. Follow at most ten
repository-contained Issue references from hydrated bodies for one hop; show
them as `mentioned-reference` context without inheriting authority. Historical
PR URLs are background context only: do not claim their Issue linkage as
workspace provenance unless the analyzer auto-detects that PR from the current
checkout. Keep requirement alignment disabled rather than substituting a thematic
Issue.

Treat `scan-failed` and `partial-scan` as unavailable or incomplete Issue
evidence, never as proof that no open Issue exists. Keep requirement alignment
`not-enabled` unless an authoritative reference resolves; do not discard
technical risk.

## Deterministic floor

`assess-risk-matrix.sh` emits rows for Issue clarity, impact breadth,
contract/state boundaries, test evidence, browser user-journey evidence, and
change attribution. A frontend or backend-route change without related browser
evidence raises the static verification floor; a possible, module-level,
disabled, manual-only, or non-object-linked browser scenario remains medium.
In technical-only mode, omit the `issue-clarity` row entirely. Treat the highest
deterministic row as the risk floor. Semantic review may raise but must not lower
it.

## Issue alignment rows

Requirement verification is a separate pass after structural/technical review.
Run it only when `requirement_alignment_enabled` is true for an authoritative
Issue. A reference hint or thematic candidate receives no acceptance-item
verdict and leaves requirement alignment `not-enabled`.

For every eligible acceptance item, report three independent axes:

- `scope`: `in-scope`, `adjacent`, `out-of-scope`, or `cannot-determine`.
- `implementation`: `static-evidence-found`, `static-evidence-missing`, or
  `cannot-verify`.
- `test_status`: `asserted`, `weak-or-disabled`, `missing`, `not-applicable`,
  or `cannot-verify`.

Every `static-evidence-found` verdict must cite an exact changed file, object,
route, or bounded journey. Every `in-scope` item must cite an exact related
test/assertion or explicitly state that no test was found. Do not batch multiple
acceptance items under one verdict. Keyword overlap alone is never sufficient.
Use `cannot-determine` or `cannot-verify` when evidence is incomplete.

Add one risk row per `in-scope` acceptance item. Keep adjacent and out-of-scope
items visible as Issue context, but do not let an umbrella Issue inflate the
risk matrix. Never call an item satisfied, passed, complete, or verified because
tests were not executed.

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

## Scope divergence

After item review, report one of these evidence-bearing conditions:

- `narrow-issue-broad-diff`: concrete changed technical objects have no mapped
  acceptance item. Preserve their technical regression guidance.
- `broad-issue-narrow-diff`: an `in-scope` acceptance item has
  `static-evidence-missing`.
- `bidirectional-divergence`: both conditions are present.
- `none-observed`: every attributable changed object maps to an eligible item
  and no in-scope item lacks static implementation evidence.
- `cannot-determine`: attribution is too incomplete to compare scope safely.

Absence of a match does not prove `out-of-scope`; that label requires explicit
Issue scope text or concrete unchanged-code evidence. Divergence may raise
requirement risk but never removes technical objects, candidates, or guidance.

## Test guidance groups

- `requirement-traced`: a concrete test to establish static evidence for an
  eligible in-scope acceptance item.
- `technical-regression`: existing add/strengthen guidance derived from the
  immutable technical scope, including behavior the Issue does not mention.
- `exploratory`: possible relations, partial journeys, or runtime behavior that
  static analysis cannot close.

The effective guidance is the union of all three groups. A test may carry more
than one group label, but count and describe the asset once. No Issue outcome may
remove or downgrade technical-regression guidance.

## Technical risk and requirement alignment

Use the highest deterministic technical row as `technical_risk` and the known
pre-test `overall_risk`. Issue alignment may raise this result later but cannot
lower it. If no Issue was authoritatively supplied or uniquely linked from the
current PR, set `requirement_alignment` to `not-enabled`, omit requirement rows,
and mark the assessment `complete-for-technical-pretest`. State explicitly that
tests were not executed. The current analyzer returns one workspace-level risk
assessment. Do not infer business streams or allocate workspace test counts and
risk rows among guessed streams.
