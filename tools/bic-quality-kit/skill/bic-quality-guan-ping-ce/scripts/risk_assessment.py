#!/usr/bin/env python3
"""Evidence-only pre-test quality matrix for BIC Quality Briefs."""

from __future__ import annotations

from typing import Any


def evidence_row(
    dimension: str,
    finding: str,
    issue_evidence: list[str] | None = None,
    diff_evidence: list[str] | None = None,
    test_evidence: list[str] | None = None,
    open_evidence: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "finding": finding,
        "issue_evidence": issue_evidence or [],
        "diff_evidence": diff_evidence or [],
        "test_evidence": test_evidence or [],
        "open_evidence": open_evidence or [],
    }


def module_names(scope: dict[str, Any]) -> set[str]:
    return {
        module["module_scope"]
        for modules in scope.get("modules_by_repository", {}).values()
        for module in modules
        if module.get("module_scope")
    }


def assess_pretest_evidence(
    context: dict[str, Any],
    scope: dict[str, Any],
    correspondence: dict[str, Any],
    issue: dict[str, Any],
    model: dict[str, Any],
) -> dict[str, Any]:
    """Describe known and missing evidence without assigning release-risk levels."""
    alignment_enabled = bool(issue.get("requirement_alignment_enabled", False))
    acceptance_eligible = bool(
        alignment_enabled and issue.get("acceptance_items_eligible", False)
    )
    acceptance_items = issue.get("acceptance_items", []) if acceptance_eligible else []
    modules = module_names(scope)
    affected_repositories = scope.get("affected_repositories", [])
    module_results = correspondence.get("modules", [])
    guidance = correspondence.get("test_guidance", [])
    add_guidance = [item for item in guidance if item.get("action") == "add"]
    strengthen_guidance = [
        item for item in guidance if item.get("action") == "strengthen"
    ]
    no_gaps = [
        item
        for module in module_results
        for item in module.get("no_obvious_test_gaps", [])
    ]
    possible_tests = [
        item
        for module in module_results
        for item in module.get("possibly_related_tests", [])
    ]
    file_level = [
        symbol
        for module in module_results
        for symbol in module.get("changed_symbols", [])
        if symbol.get("kind") == "changed-file"
    ]
    changed_routes = [
        symbol
        for module in module_results
        for symbol in module.get("changed_symbols", [])
        if symbol.get("kind") == "route"
    ]
    browser_relations: list[tuple[str, dict[str, Any]]] = []
    for module in module_results:
        for relation_type, field in (
            ("direct", "directly_related_tests"),
            ("indirect", "indirectly_related_tests"),
            ("possible", "possibly_related_tests"),
        ):
            browser_relations.extend(
                (relation_type, relation)
                for relation in module.get(field, [])
                if relation.get("browser_evidence")
            )

    issue_evidence: list[str] = []
    if issue.get("title"):
        item_label = "PR" if issue.get("item_type") == "pull-request" else "Issue"
        issue_evidence.append(f"{item_label}: {issue['title']}")
    issue_evidence.extend(item["text"] for item in acceptance_items)
    issue_summary = issue_evidence[:1]

    rows: list[dict[str, Any]] = []
    if alignment_enabled:
        rows.append(evidence_row(
            "requirement-definition",
            (
                "The authoritative Issue provides explicit acceptance items for comparison."
                if acceptance_items else
                "The authoritative Issue is available but has no explicit acceptance items."
            ),
            issue_evidence=issue_evidence,
            open_evidence=(
                [] if acceptance_items
                else ["acceptance behavior must be derived or clarified before requirement comparison"]
            ),
        ))

    cross_repo = bool(scope.get("direct_cross_repository"))
    rows.append(evidence_row(
        "impact-breadth",
        (
            "The Diff spans multiple repositories or functional modules."
            if cross_repo or len(modules) > 1 else
            "The Diff is limited to one repository and one functional module."
        ),
        issue_evidence=issue_summary,
        diff_evidence=[
            f"repositories: {', '.join(affected_repositories) or 'none'}",
            f"modules: {', '.join(sorted(modules)) or 'none'}",
        ],
        test_evidence=[
            f"actionable add guidance: {len(add_guidance)}",
            f"actionable strengthen guidance: {len(strengthen_guidance)}",
        ],
        open_evidence=(
            ["cross-repository runtime behavior has not been executed"]
            if cross_repo else []
        ),
    ))

    sensitive_modules = set(model.get("sensitive_modules", [])) & modules
    boundary_guidance = [
        item for item in guidance
        if item.get("module_scope") in sensitive_modules
        or item.get("test_layer") in {"backend-route", "repository"}
    ]
    rows.append(evidence_row(
        "contract-and-state-boundary",
        (
            "Configured contract or stateful boundaries are affected."
            if sensitive_modules else
            "No configured contract or stateful boundary module is affected."
        ),
        issue_evidence=issue_summary,
        diff_evidence=[
            f"sensitive modules: {', '.join(sorted(sensitive_modules)) or 'none'}",
        ],
        test_evidence=[
            f"boundary guidance items: {len(boundary_guidance)}",
        ],
        open_evidence=[
            f"{item.get('recommended_framework')} {item.get('test_layer')}: "
            f"{item.get('target_behavior')}"
            for item in boundary_guidance
        ],
    ))

    rows.append(evidence_row(
        "test-evidence",
        "Static test correspondence and actionable test guidance were collected.",
        issue_evidence=issue_summary,
        test_evidence=[
            f"add: {len(add_guidance)}",
            f"strengthen: {len(strengthen_guidance)}",
            f"no obvious gap: {len(no_gaps)}",
            f"possible candidates: {len(possible_tests)}",
        ],
        open_evidence=[
            f"{item.get('action')} {item.get('recommended_framework')} "
            f"{item.get('test_layer')}: {item.get('target_behavior')}"
            for item in guidance
        ],
    ))

    journey_graph = correspondence.get("user_journey_graph", {})
    completed_paths = journey_graph.get("paths", [])
    partial_paths = journey_graph.get("partial_paths", [])
    checked_browser = [
        relation
        for _relation_type, relation in browser_relations
        if relation.get("browser_evidence", {}).get("has_machine_check")
    ]
    strong_browser = [
        relation
        for relation_type, relation in browser_relations
        if relation_type in {"direct", "indirect"}
        and relation.get("browser_evidence", {}).get("has_machine_check")
        and relation.get("related_symbols")
    ]
    browser_relevant = any(module.startswith("portal/") for module in modules) or bool(changed_routes)
    browser_guidance = correspondence.get("browser_test_guidance", [])
    rows.append(evidence_row(
        "browser-user-journey-evidence",
        (
            "Frontend or backend-route changes make browser evidence relevant."
            if browser_relevant else
            "No frontend module or backend route makes browser evidence a required layer."
        ),
        issue_evidence=issue_summary,
        diff_evidence=[
            f"backend routes changed: {len(changed_routes)}",
            f"completed static paths: {len(completed_paths)}",
            f"partial static paths: {len(partial_paths)}",
        ],
        test_evidence=[
            f"browser relations: {len(browser_relations)}",
            f"machine-checked browser candidates: {len(checked_browser)}",
            f"object-related machine checks: {len(strong_browser)}",
        ],
        open_evidence=[
            f"{item.get('action')} {item.get('recommended_framework')}: "
            f"{item.get('target_behavior')}"
            for item in browser_guidance
        ],
    ))

    rows.append(evidence_row(
        "change-attribution",
        (
            "Some changes remain file-level and cannot support object-specific conclusions."
            if file_level else
            "Changed declarations were extracted at object level for the analyzed source files."
        ),
        issue_evidence=issue_summary,
        diff_evidence=[f"file-level changed objects: {len(file_level)}"],
        open_evidence=(
            ["file-level changes are retained as diagnostics and receive no standalone test guidance"]
            if file_level else []
        ),
    ))

    if not alignment_enabled:
        requirement_alignment = "not-enabled"
    elif acceptance_items:
        requirement_alignment = "pending-review"
    else:
        requirement_alignment = "insufficient-definition"
    requirement_scope_status = "available" if alignment_enabled else "not-enabled"
    open_items: list[str] = []
    for item in rows:
        for evidence in item.get("open_evidence", []):
            if evidence not in open_items:
                open_items.append(evidence)
    return {
        "assessment_stage": "pre-test",
        "decision_model": "evidence-only",
        "requirement_alignment": requirement_alignment,
        "assessment_completeness": {
            "overall": (
                "complete-for-pretest"
                if alignment_enabled
                else "complete-for-technical-pretest"
            ),
            "technical_scope": "assessed",
            "requirement_scope": requirement_scope_status,
            "test_execution": "not-run",
        },
        "quality_evidence_matrix": rows,
        "open_evidence_items": open_items,
        "requires_semantic_issue_alignment": alignment_enabled,
        "issue_acceptance_items": acceptance_items,
        "assessment_note": (
            "This is an evidence-only pre-test assessment. It reports known and missing "
            "evidence without assigning high/medium/low or an overall release-risk value."
        ),
    }
