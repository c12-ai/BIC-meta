#!/usr/bin/env python3
"""Evidence-only pre-test quality matrix for BIC Quality Briefs."""

from __future__ import annotations

import re
from typing import Any


PUBLIC_NON_SOURCE_MODULES = {"portal/tests", "agent/tests", "meta/docs", "meta/test-config"}


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


def changed_behavior_summary(module: dict[str, Any]) -> list[str]:
    """Describe concrete changed routes/objects without dumping every declaration."""
    descriptions: list[str] = []
    for symbol in module.get("changed_symbols", []):
        kind = str(symbol.get("kind") or "")
        if kind in {"file", "changed-file", "module-scope"}:
            continue
        if kind == "route" and symbol.get("route_path"):
            value = (
                f"{symbol.get('route_method', '')} {symbol.get('route_path', '')}"
            ).strip()
        else:
            value = str(symbol.get("name") or "")
        if value and value != "__all__" and value not in descriptions:
            descriptions.append(value)
    if descriptions:
        return descriptions[:6]
    paths = [
        str(item.get("path") or "")
        for item in module.get("changed_files", [])
        if item.get("path")
    ]
    return paths[:3]


def relation_evidence_summary(item: dict[str, Any]) -> str:
    cases = (
        item.get("relevant_test_cases")
        or item.get("behavior_test_cases")
        or item.get("contract_test_cases")
        or item.get("selected_test_cases")
        or item.get("test_names")
        or []
    )
    assertion = item.get("evidence_level") or item.get("assertion_status")
    suffix = f"；{assertion}" if assertion else ""
    if cases:
        return f"{item.get('path')}（{cases[0]}{suffix}）"
    return f"{item.get('path')}{suffix}"


def unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def build_brief_evidence_matrix(
    correspondence: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create object/behavior rows without borrowing evidence from a whole module."""

    def terms(value: str) -> set[str]:
        separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
        return {
            token for token in re.findall(r"[A-Za-z0-9]+", separated.lower())
            if len(token) > 2
            and token not in {
                "app", "src", "test", "tests", "unit", "service", "session",
                "state", "target", "result", "helper", "manager",
            }
        }

    def supports(
        relation: dict[str, Any],
        path: str,
        symbols: set[str],
    ) -> tuple[str | None, set[str]]:
        related = set(relation.get("related_symbols", []))
        object_linked = symbols & set(relation.get("assertion_linked_symbols", []))
        behavior_linked = symbols & set(relation.get("behavior_asserted_symbols", []))
        contract_linked = symbols & set(relation.get("contract_asserted_symbols", []))
        if object_linked:
            return "object-asserted", object_linked
        if behavior_linked:
            return "behavior-asserted", behavior_linked
        if contract_linked:
            return "contract-asserted", contract_linked
        if not symbols and path in relation.get("assertion_linked_files", []):
            return "object-asserted", set()
        if symbols & related:
            return None, symbols & related
        return None, set()

    def evidence_for(
        module: dict[str, Any],
        path: str,
        symbols: set[str],
    ) -> list[dict[str, Any]]:
        ranked: list[tuple[int, dict[str, Any]]] = []
        for relation in [
            *module.get("directly_related_tests", []),
            *module.get("indirectly_related_tests", []),
        ]:
            level, linked = supports(relation, path, symbols)
            if level is None:
                continue
            score = {
                "object-asserted": 300,
                "behavior-asserted": 220,
                "contract-asserted": 140,
            }[level]
            score += len(linked) * 10
            score += len(relation.get("behavior_test_cases", [])) * 8
            if path in relation.get("related_files", []):
                score += 20
            behavior_terms = set().union(*(terms(name) for name in symbols))
            cases = (
                relation.get("behavior_test_cases")
                or relation.get("contract_test_cases")
                or relation.get("selected_test_cases")
                or relation.get("test_names")
                or []
            )
            ranked_cases = sorted(
                (str(case) for case in cases),
                key=lambda case: (
                    -len(behavior_terms & terms(case)),
                    case,
                ),
            )
            best_case_overlap = (
                len(behavior_terms & terms(ranked_cases[0]))
                if ranked_cases else 0
            )
            score += best_case_overlap * 25
            ranked.append((
                score,
                {
                    **relation,
                    "evidence_level": level,
                    "relevant_test_cases": ranked_cases[:3],
                },
            ))
        ranked.sort(key=lambda item: (-item[0], str(item[1].get("path") or "")))
        if not ranked:
            return []
        best = ranked[0][0]
        return [
            item for score, item in ranked
            if score >= best - 15
        ][:2]

    rows: list[dict[str, Any]] = []
    for module in correspondence.get("modules", []):
        repo = str(module.get("repo") or "")
        module_scope = str(module.get("module_scope") or "")
        if module_scope in PUBLIC_NON_SOURCE_MODULES:
            continue
        symbols_by_path: dict[str, list[dict[str, Any]]] = {}
        for symbol in module.get("changed_symbols", []):
            if symbol.get("kind") in {"file", "changed-file", "module-scope"}:
                continue
            if symbol.get("name") == "__all__":
                continue
            symbols_by_path.setdefault(str(symbol.get("path") or ""), []).append(symbol)
        guidance_by_path = {
            str(item.get("path") or ""): item
            for item in module.get("test_guidance", [])
        }
        for path, path_symbols in symbols_by_path.items():
            guidance = guidance_by_path.get(path)
            requested_names = set(
                guidance.get("symbols", []) if guidance else []
            )
            groups: list[tuple[list[dict[str, Any]], dict[str, Any] | None]] = []
            if guidance:
                uncovered = [
                    symbol for symbol in path_symbols
                    if str(symbol.get("name") or "") in requested_names
                ]
                if uncovered:
                    groups.append((uncovered, guidance))
            covered = [
                symbol for symbol in path_symbols
                if str(symbol.get("name") or "") not in requested_names
            ]
            if covered:
                groups.append((covered, None))
            for group_symbols, group_guidance in groups:
                names = {
                    str(symbol.get("name") or "")
                    for symbol in group_symbols if symbol.get("name")
                }
                relations = evidence_for(module, path, names)
                existing = unique_strings([
                    relation_evidence_summary(item) for item in relations
                ])
                levels = unique_strings([
                    str(item.get("evidence_level") or "related-only")
                    for item in relations
                ])
                open_items = (
                    list(group_guidance.get("evidence_gaps", []))
                    if group_guidance
                    else ["no obvious static test gap was identified for this behavior"]
                )
                recommendations = (
                    [
                        (
                            f"{group_guidance.get('action')} "
                            f"{group_guidance.get('recommended_framework')} at "
                            f"{group_guidance.get('suggested_test_target')}"
                        )
                    ]
                    if group_guidance else ["none"]
                )
                behavior = [
                    str(symbol.get("name") or "")
                    for symbol in group_symbols if symbol.get("name")
                ]
                focus = (
                    str(group_guidance.get("target_behavior") or "")
                    if group_guidance
                    else " / ".join(behavior[:2])
                )
                rows.append({
                    "quality_focus": focus or f"{repo} / {module_scope}",
                    "changed_behavior": behavior,
                    "existing_test_evidence": (
                        existing
                        or ["no object- or behavior-linked active test evidence"]
                    ),
                    "evidence_strength": levels or ["none"],
                    "open_evidence": open_items,
                    "recommendation": recommendations,
                })

    browser_guidance = correspondence.get("browser_test_guidance", [])
    if browser_guidance:
        journey = correspondence.get("user_journey_graph", {})
        rows.append({
            "quality_focus": "browser user journey",
            "changed_behavior": [
                str(item.get("target_behavior") or "") for item in browser_guidance
            ],
            "existing_test_evidence": [
                test
                for item in browser_guidance
                for test in item.get("existing_tests", [])
            ] or ["no completed static browser path reaches this behavior"],
            "evidence_strength": ["static-browser-path"],
            "open_evidence": [
                (
                    f"{item.get('action')} {item.get('recommended_framework')} at "
                    f"{item.get('suggested_test_target')}；"
                    f"{'; '.join(item.get('evidence_gaps', []))}"
                )
                for item in browser_guidance
            ] + [
                (
                    f"static paths: {len(journey.get('paths', []))} completed, "
                    f"{len(journey.get('partial_paths', []))} partial; not executed"
                )
            ],
            "recommendation": [
                (
                    f"{item.get('action')} {item.get('recommended_framework')} at "
                    f"{item.get('suggested_test_target')}"
                )
                for item in browser_guidance
            ],
        })
    return rows[:20]


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
        "brief_evidence_matrix": build_brief_evidence_matrix(correspondence),
        "open_evidence_items": open_items,
        "requires_semantic_issue_alignment": alignment_enabled,
        "issue_acceptance_items": acceptance_items,
        "assessment_note": (
            "This is an evidence-only pre-test assessment. It reports known and missing "
            "evidence without assigning high/medium/low or an overall release-risk value."
        ),
    }
