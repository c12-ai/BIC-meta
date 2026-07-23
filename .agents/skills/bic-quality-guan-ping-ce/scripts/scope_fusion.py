#!/usr/bin/env python3
"""Immutable technical-scope indexes and additive requirement-scope fusion."""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

from content_safety import REDACTED_PATH, is_sensitive_path


RELATION_FIELDS = (
    ("direct", "directly_related_tests"),
    ("indirect", "indirectly_related_tests"),
    ("possible", "possibly_related_tests"),
)
RECOMMENDATION_FIELDS = (
    ("add", "add_tests"),
    ("strengthen", "strengthen_tests"),
    ("no-obvious-gap", "no_obvious_test_gaps"),
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _object_identity(repo: str, module: str, symbol: dict[str, Any]) -> str:
    qualified = symbol.get("qualified_name") or symbol.get("symbol") or symbol.get("name")
    return ":".join(
        str(value or "-")
        for value in (repo, module, symbol.get("path"), symbol.get("kind"), qualified)
    )


def _relation_identity(
    repo: str,
    module: str,
    strength: str,
    relation: dict[str, Any],
) -> str:
    cases = relation.get("related_case_names") or []
    return ":".join(
        (
            repo,
            module,
            strength,
            str(relation.get("path") or "-"),
            _digest("\0".join(sorted(str(case) for case in cases))),
        )
    )


def _recommendation_identity(
    repo: str,
    module: str,
    category: str,
    recommendation: str,
) -> str:
    return ":".join((repo, module, category, _digest(recommendation)))


def _journey_identity(path: dict[str, Any]) -> str:
    if path.get("id"):
        return str(path["id"])
    nodes = "\0".join(str(node) for node in path.get("nodes", []))
    edges = "\0".join(str(edge) for edge in path.get("edges", []))
    return f"journey:{_digest(nodes + chr(1) + edges)}"


def build_technical_scope(
    context: dict[str, Any],
    scope: dict[str, Any],
    correspondence: dict[str, Any],
) -> dict[str, Any]:
    """Build a bounded identity index before any requirement scope is fused."""
    object_ids: list[str] = []
    route_ids: list[str] = []
    test_candidate_ids: list[str] = []
    recommendation_ids: list[str] = []

    for module in correspondence.get("modules", []):
        repo = str(module.get("repo") or "-")
        module_scope = str(module.get("module_scope") or "-")
        for symbol in module.get("changed_symbols", []):
            identity = _object_identity(repo, module_scope, symbol)
            object_ids.append(identity)
            if symbol.get("kind") == "route":
                route_ids.append(identity)
        for strength, field in RELATION_FIELDS:
            test_candidate_ids.extend(
                _relation_identity(repo, module_scope, strength, relation)
                for relation in module.get(field, [])
            )
        for category, field in RECOMMENDATION_FIELDS:
            recommendation_ids.extend(
                _recommendation_identity(repo, module_scope, category, str(item))
                for item in module.get(field, [])
            )

    journey_graph = correspondence.get("user_journey_graph", {})
    journey_ids = [
        _journey_identity(path)
        for path in [
            *journey_graph.get("paths", []),
            *journey_graph.get("partial_paths", []),
        ]
    ]
    changed_file_ids = []
    for item in context.get("changed_files", []):
        path = str(item.get("path") or "-")
        safe_path = REDACTED_PATH if is_sensitive_path(path) else path
        changed_file_ids.append(f"{item.get('repo', '-')}:{safe_path}")
    result = {
        "schema_version": 1,
        "derivation": "diff-ast-static-test-evidence",
        "issue_independent": True,
        "repositories": sorted(set(scope.get("affected_repositories", []))),
        "changed_file_ids": sorted(set(changed_file_ids)),
        "changed_object_ids": sorted(set(object_ids)),
        "changed_route_ids": sorted(set(route_ids)),
        "journey_path_ids": sorted(set(journey_ids)),
        "test_candidate_ids": sorted(set(test_candidate_ids)),
        "test_recommendation_ids": sorted(set(recommendation_ids)),
    }
    result["counts"] = {
        key: len(result[key])
        for key in (
            "repositories",
            "changed_file_ids",
            "changed_object_ids",
            "changed_route_ids",
            "journey_path_ids",
            "test_candidate_ids",
            "test_recommendation_ids",
        )
    }
    return result


def build_requirement_scope(issue: dict[str, Any]) -> dict[str, Any]:
    """Index requirement provenance without turning it into a technical filter."""
    alignment_enabled = bool(issue.get("requirement_alignment_enabled", False))
    acceptance_items = issue.get("acceptance_items", []) if alignment_enabled else []
    return {
        "schema_version": 1,
        "alignment_enabled": alignment_enabled,
        "alignment_mode": issue.get("requirement_alignment_mode", "technical-only"),
        "alignment_origin": issue.get("requirement_alignment_origin"),
        "alignment_reason": issue.get("requirement_alignment_reason", "no-authoritative-issue"),
        "association_status": issue.get("association_status") or issue.get("association") or "unresolved",
        "resolved": bool(issue.get("resolved")) if alignment_enabled else False,
        "acceptance_items_eligible": alignment_enabled,
        "issue_reference": issue.get("reference") if alignment_enabled else None,
        "acceptance_item_ids": [
            f"acceptance:{_digest(str(item.get('text') or ''))}"
            for item in acceptance_items
            if item.get("text")
        ],
        "semantics": "Requirement context may add attention and tests, but cannot remove or downgrade technical scope.",
    }


def initialize_scope_fusion(
    technical_scope: dict[str, Any],
    requirement_scope: dict[str, Any],
    requirement_test_candidate_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Create the additive union and expose a machine-checkable monotonicity invariant."""
    technical_ids = set(technical_scope.get("test_candidate_ids", []))
    requirement_ids = {str(item) for item in requirement_test_candidate_ids}
    effective_ids = technical_ids | requirement_ids
    removed_ids = sorted(technical_ids - effective_ids)
    return {
        "schema_version": 1,
        "strategy": "union",
        "technical_test_candidate_ids": sorted(technical_ids),
        "requirement_test_candidate_ids": sorted(requirement_ids),
        "effective_test_candidate_ids": sorted(effective_ids),
        "invariants": {
            "issue_cannot_reduce_technical_scope": not removed_ids,
            "removed_technical_test_candidate_ids": removed_ids,
            "technical_candidate_count": len(technical_ids),
            "effective_candidate_count": len(effective_ids),
        },
        "requirement_association_status": requirement_scope.get("association_status", "unresolved"),
    }
