# Pre-test Quality Evidence Model

Generate a quality evidence matrix before executing tests. It describes what the
static Issue-to-Diff-to-test chain establishes and what remains unverified. It
does not assign high/medium/low, calculate an overall risk, or claim that a test
passed. The reader decides risk from the cited evidence and open questions.

## Inputs

Use only concrete evidence from:

- an explicitly supplied Issue or one unique linked/closing Issue from the
  auto-detected current PR;
- changed repositories, modules, files, declarations, routes, and change types;
- contract, state, persistence, and browser/user-journey boundaries;
- direct, safe indirect, possible, disabled, assertion-free, and missing tests,
  including Playwright/CDP evidence kept separate from backend/unit tests.

Do not use a path, label, filename, or keyword match by itself as a quality
conclusion. Do not choose among equally authoritative Issue candidates.

Keep provenance and topical similarity separate:

- `authoritative`: explicit Issue override, local Issue file, or one
  linked/closing Issue from the auto-detected current PR.
- `reference-hint`: commit/branch reference. It remains diagnostic context until
  the user explicitly supplies the Issue.
- `thematic-candidate`: ordinary open-Issue search match. It is background
  context even when it is the only similar candidate.
- `mentioned-reference`: bounded one-hop reference from a hydrated body. It does
  not inherit the parent candidate's authority.

Only an `authoritative` Issue enables requirement alignment.

## Affected-repository Issue analysis

Run Issue analysis only after the Diff identifies affected repositories and
modules. Scan open Issues for each affected repository. An explicit override is
authoritative. A unique current-PR linked/closing reference may resolve directly
and skip the broad scan only when exactly one affected GitHub repository exists.
With multiple affected repositories, scan every repository, then use one unique
current-PR Issue as an additive requirement overlay without filtering technical
scope. A Diff-commit closing reference or `issue-123` branch reference is a
protected search hint, not sufficient evidence for automatic selection.

When no authoritative link exists, use Issue titles and labels only to
shortlist. Match English, Chinese, and mixed-language module/object/path terms.
Require a module, object, path, or label signal for every ordinary candidate.
Repository membership alone records scan coverage and must not create a
candidate. Read at most 100 metadata records per affected repository, reduce
ordinary candidates to at most 10, and read the full body of every shortlisted
candidate. Use one GraphQL batch, bounded fallback lookups, and one shared
60-second GitHub deadline. Even one semantically similar ordinary candidate
remains thematic and leaves requirement alignment `not-enabled`.

Follow at most ten repository-contained Issue references from hydrated bodies
for one hop and show them as `mentioned-reference` context. Historical PR URLs
are background context only unless the analyzer auto-detects that PR from the
current checkout. Treat `scan-failed` and `partial-scan` as unavailable or
incomplete evidence, never proof that no open Issue exists.

## Evidence matrix

`assess-risk-matrix.sh` keeps its compatibility name but returns
`quality_evidence` with `decision_model: evidence-only`.

Each `quality_evidence_matrix` row contains:

- `dimension`: the inspected quality dimension;
- `finding`: the factual static conclusion;
- `issue_evidence`: authoritative requirement evidence when enabled;
- `diff_evidence`: exact changed repositories/files/objects/routes;
- `test_evidence`: exact related test, assertion, disabled state, or explicit
  absence;
- `open_evidence`: what still needs runtime or human verification.

The standard technical dimensions are impact breadth, contract/state boundary,
test evidence, browser/user-journey evidence, and change attribution.
Requirement-definition appears only when authoritative alignment is enabled.
Rows never contain a severity or priority. The assessment also returns a
deduplicated `open_evidence_items` list.

## Issue alignment

Requirement verification is a separate pass after structural/technical review.
Run it only when `requirement_alignment_enabled` and
`acceptance_items_eligible` are both true. A reference hint or thematic
candidate receives no acceptance-item comparison.

For every eligible acceptance item, report three independent axes:

- `scope`: `in-scope`, `adjacent`, `out-of-scope`, or `cannot-determine`.
- `implementation`: `static-evidence-found`, `static-evidence-missing`, or
  `cannot-verify`.
- `test_status`: `asserted`, `weak-or-disabled`, `missing`, `not-applicable`,
  or `cannot-verify`.

Every `static-evidence-found` result must cite an exact changed file, object,
route, or bounded journey. Every `in-scope` item must cite an exact related
test/assertion or explicitly state that no test was found. Keep adjacent and
out-of-scope items visible as Issue context, but do not place them in the
in-scope evidence rows. Never call an item satisfied, passed, complete, or
verified because tests were not executed.

## Scope divergence

After item review, report one of these evidence-bearing conditions:

- `narrow-issue-broad-diff`: concrete changed technical objects have no mapped
  acceptance item.
- `broad-issue-narrow-diff`: an `in-scope` acceptance item has
  `static-evidence-missing`.
- `bidirectional-divergence`: both conditions are present.
- `none-observed`: every attributable changed object maps to an eligible item
  and no in-scope item lacks static implementation evidence.
- `cannot-determine`: attribution is too incomplete to compare safely.

Absence of a match does not prove `out-of-scope`; that label requires explicit
Issue scope text or concrete unchanged-code evidence. Divergence never removes
technical objects, test candidates, or guidance.

## Test guidance groups

- `requirement-traced`: a concrete test needed for an eligible in-scope
  acceptance item.
- `technical-regression`: behavior-level add/strengthen guidance derived from
  the immutable technical scope, including behavior the Issue does not mention.
- `exploratory`: possible relations, partial journeys, or runtime behavior that
  static analysis cannot close.

The effective guidance is the union of all groups. A test may carry more than
one group label, but should be described once. No Issue outcome may remove
technical-regression guidance.

## Assessment status

Without an authoritative Issue, set `requirement_alignment` to `not-enabled`,
omit requirement rows, and mark the assessment
`complete-for-technical-pretest`. State explicitly that tests were not executed.
The current analyzer returns one workspace-level evidence assessment. Do not
infer business streams or allocate workspace evidence among guessed streams.
