#!/usr/bin/env python3
"""Evidence-based pre-test risk signals for BIC Quality Briefs."""

from __future__ import annotations

from typing import Any


RANK = {"low": 1, "medium": 2, "high": 3}


def row(
    dimension: str,
    level: str,
    reason: str,
    issue_evidence: list[str] | None = None,
    diff_evidence: list[str] | None = None,
    test_evidence: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "risk_level": level,
        "issue_evidence": issue_evidence or [],
        "diff_evidence": diff_evidence or [],
        "test_evidence": test_evidence or [],
        "reason": reason,
    }


def module_names(scope: dict[str, Any]) -> set[str]:
    return {
        module["module_scope"]
        for modules in scope.get("modules_by_repository", {}).values()
        for module in modules
        if module.get("module_scope")
    }


def assess_pretest_risk(
    context: dict[str, Any],
    scope: dict[str, Any],
    correspondence: dict[str, Any],
    issue: dict[str, Any],
    model: dict[str, Any],
) -> dict[str, Any]:
    modules = module_names(scope)
    affected_repositories = scope.get("affected_repositories", [])
    module_results = correspondence.get("modules", [])
    add_tests = [item for module in module_results for item in module.get("add_tests", [])]
    strengthen_tests = [item for module in module_results for item in module.get("strengthen_tests", [])]
    no_gaps = [item for module in module_results for item in module.get("no_obvious_test_gaps", [])]
    possible_tests = [item for module in module_results for item in module.get("possibly_related_tests", [])]
    file_level = [
        symbol for module in module_results for symbol in module.get("changed_symbols", [])
        if symbol.get("kind") == "changed-file"
    ]

    issue_evidence = []
    if issue.get("title"):
        item_label = "PR" if issue.get("item_type") == "pull-request" else "Issue"
        issue_evidence.append(f"{item_label}: {issue['title']}")
    issue_evidence.extend(item["text"] for item in issue.get("acceptance_items", []))
    issue_summary = issue_evidence[:1]

    rows: list[dict[str, Any]] = []
    if not issue.get("resolved"):
        rows.append(row(
            "issue-clarity", "unassessed",
            "No resolved Issue context is available; Issue-to-Diff alignment cannot be judged.",
        ))
    elif not issue.get("acceptance_items"):
        rows.append(row(
            "issue-clarity", "medium",
            "The Issue is available but has no explicit acceptance checklist or acceptance section.",
            issue_evidence=issue_evidence,
        ))
    else:
        rows.append(row(
            "issue-clarity", "low",
            "The Issue provides explicit acceptance items for semantic comparison with the Diff.",
            issue_evidence=issue_evidence,
        ))

    cross_repo = bool(scope.get("direct_cross_repository"))
    if cross_repo and add_tests:
        breadth_level = "high"
        breadth_reason = "Multiple repositories change directly and at least one changed object has no active related assertion."
    elif cross_repo or len(modules) > 1:
        breadth_level = "medium"
        breadth_reason = "The Diff spans multiple repositories or functional modules."
    else:
        breadth_level = "low"
        breadth_reason = "The Diff is limited to one repository and one functional module."
    rows.append(row(
        "impact-breadth", breadth_level, breadth_reason,
        issue_evidence=issue_summary,
        diff_evidence=[
            f"repositories: {', '.join(affected_repositories) or 'none'}",
            f"modules: {', '.join(sorted(modules)) or 'none'}",
        ],
        test_evidence=[f"missing object-level tests: {len(add_tests)}"],
    ))

    sensitive_modules = set(model.get("sensitive_modules", [])) & modules
    if sensitive_modules and add_tests:
        boundary_level = "high"
        boundary_reason = "A contract/stateful boundary changes without complete object-level test evidence."
    elif sensitive_modules:
        boundary_level = "medium"
        boundary_reason = "A contract or stateful boundary changes; static tests exist but runtime behavior is not verified."
    else:
        boundary_level = "low"
        boundary_reason = "No configured contract or stateful boundary module is affected."
    rows.append(row(
        "contract-and-state-boundary", boundary_level, boundary_reason,
        issue_evidence=issue_summary,
        diff_evidence=[f"sensitive modules: {', '.join(sorted(sensitive_modules)) or 'none'}"],
        test_evidence=[f"missing object-level tests: {len(add_tests)}"],
    ))

    if add_tests:
        test_level = "high"
        test_reason = "At least one changed object has no active direct or safe indirect test with an assertion."
    elif strengthen_tests or possible_tests:
        test_level = "medium"
        test_reason = "Related tests exist, but some evidence is weak, disabled, assertion-free, or only a possible candidate."
    else:
        test_level = "low"
        test_reason = "No obvious static test gap was found for the analyzed changed objects."
    rows.append(row(
        "test-evidence", test_level, test_reason,
        issue_evidence=issue_summary,
        test_evidence=[
            f"add: {len(add_tests)}",
            f"strengthen: {len(strengthen_tests)}",
            f"no obvious gap: {len(no_gaps)}",
            f"possible candidates: {len(possible_tests)}",
        ],
    ))

    attribution_level = "medium" if file_level else "low"
    rows.append(row(
        "change-attribution", attribution_level,
        "Some modified/renamed/deleted files only have file-level attribution; semantic review must locate the exact changed behavior."
        if file_level else
        "Changed declarations were extracted at object level for the analyzed source files.",
        issue_evidence=issue_summary,
        diff_evidence=[f"file-level changed objects: {len(file_level)}"],
    ))

    ranked = [item["risk_level"] for item in rows if item["risk_level"] in RANK]
    risk_floor = max(ranked, key=RANK.get) if ranked else "low"
    overall = risk_floor if issue.get("resolved") else "unassessed"
    return {
        "assessment_stage": "pre-test",
        "overall_risk": overall,
        "risk_floor": risk_floor,
        "risk_matrix": rows,
        "requires_semantic_issue_alignment": bool(issue.get("resolved")),
        "issue_acceptance_items": issue.get("acceptance_items", []),
        "assessment_note": (
            "This is a pre-test risk assessment. Compare every Issue acceptance item semantically "
            "with Diff and test evidence; that review may raise, but must not lower, the risk floor."
        ),
    }
