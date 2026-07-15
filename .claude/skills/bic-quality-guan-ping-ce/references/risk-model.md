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
- direct, safe indirect, possible, disabled, assertion-free, and missing tests.

Do not use a path, label, filename, or keyword match by itself to assign risk.
Do not choose among equally authoritative Issue candidates; keep the overall result
`unassessed` until the association is strongly linked or uniquely supported by
semantic Diff/module evidence.

## Affected-repository Issue analysis

Run Issue analysis only after the Diff identifies affected repositories and
modules. Scan open Issues for each affected repository. An explicit override is
authoritative. A unique current-PR linked/closing reference may resolve directly
and skip the broad scan only when exactly one affected GitHub repository exists.
With multiple affected repositories, scan every repository and keep that
current-PR Issue as a repository-local candidate; it cannot resolve workspace
Issue alignment by itself. A Diff-commit closing reference or `issue-123` branch
reference is a protected search hint, not sufficient evidence for automatic
selection.

When no authoritative link exists, use Issue titles and labels only to shortlist.
Match English, Chinese, and mixed-language module/object/path terms. Require a
module, object, path, or label signal for ordinary candidates, while allowing at
most one no-signal fallback per affected repository. Do not fill the shortlist
with unrelated candidates merely because budget remains. Read
at most 100 metadata records per affected repository, reduce ordinary candidates
to at most 10 after module and changed-object mapping, and read the full body of
every shortlisted candidate. Do not select a smaller body subset from metadata.
Use one GraphQL batch for multiple bodies, a bounded fallback for unresolved
candidates, and one shared 60-second deadline for the complete GitHub phase.
Require repository identity plus a concrete match between the Issue goal or
acceptance item and a changed module, file, or object. If exactly one candidate
meets that standard, use it for final Issue alignment. If none or several remain,
show the candidates and keep the overall result `unassessed`.

Treat `scan-failed` and `partial-scan` as unavailable or incomplete Issue
evidence, never as proof that no open Issue exists. Keep overall risk
`unassessed` unless a separately preserved authoritative reference resolves and aligns.

## Deterministic floor

`assess-risk-matrix.sh` emits rows for Issue clarity, impact breadth,
contract/state boundaries, test evidence, and change attribution. Treat the
highest deterministic row as the risk floor. Semantic review may raise but must
not lower it.

## Issue alignment rows

Add one row per Issue acceptance item:

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

## Overall risk

Use the highest row after Issue alignment. If no Issue was authoritatively linked or
uniquely selected by semantic affected-repository analysis, overall risk is
`unassessed`, even when deterministic Diff/test rows are available. State
explicitly that tests were not executed. The current analyzer returns one
workspace-level risk assessment. Do not infer business streams or allocate
workspace test counts and risk rows among guessed streams.
