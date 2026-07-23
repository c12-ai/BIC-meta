#!/usr/bin/env python3
"""Read-only correspondence analysis between changed objects and tests."""

from __future__ import annotations

import ast
import json
import os
import posixpath
import re
from urllib.parse import urlsplit
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from content_safety import safe_repository_file
from symbol_extraction import extract_source_references, python_import_name


TOKEN_STOPWORDS = {
    "app", "src", "lib", "test", "tests", "unit", "integration", "index",
    "main", "service", "services", "component", "components", "py", "ts",
    "tsx", "js", "jsx", "pages", "api", "routers",
}
NON_SOURCE_TEST_MODULES = {"portal/tests", "agent/tests", "meta/docs", "meta/test-config"}
DOCUMENTATION_SUFFIXES = {".adoc", ".md", ".mdx", ".rst"}
DOCUMENTATION_DIRECTORIES = {"docs", "references"}
FILE_ONLY_GUIDANCE_KINDS = {"file", "changed-file"}
JOURNEY_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
JOURNEY_SCAN_EXCLUDES = {
    ".git", ".agents", ".claude", ".trellis", ".venv", "node_modules",
    "__pycache__", ".pytest_cache", ".pnpm-store", "artifacts", "dist", "build",
}
MAX_JOURNEY_EDGES = 2000
MAX_JOURNEY_PATHS = 40
MAX_JOURNEY_PATH_DEPTH = 7
MAX_JOURNEY_OUTPUT_NODES = MAX_JOURNEY_EDGES * 2 + MAX_JOURNEY_PATHS
MAX_GUIDANCE_EXISTING_TESTS = 5
MAX_PUBLIC_DIRECT_TESTS = 12
MAX_PUBLIC_INDIRECT_TESTS = 8
MAX_PUBLIC_POSSIBLE_GROUPS = 5
MAX_PUBLIC_POSSIBLE_PER_BEHAVIOR = 3
BEHAVIOR_STOPWORDS = TOKEN_STOPWORDS | {
    "behavior", "repository", "repo", "router", "route", "session", "state",
    "handler", "helper", "manager", "model", "context", "result", "target",
    "after", "before", "only", "this", "that", "the", "and", "with",
    "without", "while", "when", "then", "from", "into", "for", "its",
    "has", "have", "does", "each", "every", "same", "whole",
}
PUBLIC_GENERIC_BEHAVIOR_TOKENS = {
    "active", "build", "chat", "clear", "create", "delete", "event", "find",
    "get", "key", "load", "message", "none", "payload", "props", "remove",
    "set", "state", "store", "submit", "turn", "update", "use",
}


def guidance_applicability(path: str, module_scope: str) -> tuple[bool, str | None]:
    """Return whether a changed path should receive add/strengthen guidance."""
    if module_scope in NON_SOURCE_TEST_MODULES:
        return False, f"{module_scope} does not represent executable source behavior"
    parsed = Path(path)
    if parsed.suffix.lower() in DOCUMENTATION_SUFFIXES:
        return False, "documentation-only change"
    if {part.lower() for part in parsed.parts} & DOCUMENTATION_DIRECTORIES:
        return False, "documentation/reference path"
    return True, None


def guidance_profile(
    repo: str,
    module_scope: str,
    path: str,
    symbols: list[dict[str, Any]],
) -> tuple[str, str, list[str]]:
    """Choose a concrete test layer/framework without pretending it is universal."""
    kinds = {str(symbol.get("kind") or "") for symbol in symbols}
    lowered = path.lower()
    if "route" in kinds:
        return "backend-route", "pytest", []
    if "component" in kinds:
        return "frontend-component", "vitest", ["react-testing-library"]
    if kinds & {"api-client", "store-or-action", "hook"}:
        return "frontend-unit-integration", "vitest", ["react-testing-library"]
    if "/repositories/" in lowered or "database" in module_scope:
        return "repository", "pytest", []
    if any(token in lowered for token in ("/session/", "/service", "/runtime/", "/core/")):
        return "service-unit", "pytest", []
    if Path(path).suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}:
        return "frontend-unit", "vitest", []
    if Path(path).suffix.lower() == ".py" or repo.endswith("-service"):
        return "unit", "pytest", []
    return "executable-contract", "project-native", []


def public_test_method(layer: str, framework: str) -> str:
    """Return a stable, user-facing tool name without internal layer jargon."""
    if framework == "vitest" and layer == "frontend-component":
        return "Vitest + React Testing Library"
    return {
        "pytest": "pytest",
        "vitest": "Vitest",
        "playwright": "Playwright",
        "cdp": "CDP",
        "project-native": "项目原生测试命令",
    }.get(framework, framework)


def suggested_assertions(
    path: str,
    symbols: list[dict[str, Any]],
) -> list[str]:
    """Return behavior-facing assertions for one grouped recommendation."""
    kinds = {str(symbol.get("kind") or "") for symbol in symbols}
    lowered = path.lower()
    symbol_names = {
        str(symbol.get("name") or "")
        for symbol in symbols
        if symbol.get("name")
    }
    diff_tokens = {
        str(token).lower()
        for symbol in symbols
        for token in symbol.get("diff_tokens", [])
    }
    routes = [
        f"{symbol.get('route_method', '')} {symbol.get('route_path', '')}".strip()
        for symbol in symbols
        if symbol.get("kind") == "route" and symbol.get("route_path")
    ]
    if routes:
        if any(name.rsplit(".", 1)[-1] == "cancel_feedback" for name in symbol_names):
            return [
                f"assert {', '.join(routes)} returns 204 after successful cancellation",
                "assert service.cancel_feedback receives session_id, authenticated user_id, and target_event_id",
                "assert authentication, missing-session, and permission failures use the project's route error mapping",
            ]
        return [
            f"assert the request method/path and response contract for {', '.join(routes)}",
            "assert the intended state mutation or downstream call",
            "assert not-found, authorization, and downstream-failure behavior where applicable",
        ]
    if "component" in kinds:
        if {"assistant", "turn", "active"} <= diff_tokens:
            return [
                "assert sibling assistant bubbles from the same turn receive the same active state",
                "assert feedback controls stay hidden while that turn is active",
                "assert feedback controls become available for every persisted sibling after the turn settles",
            ]
        return [
            "assert the user-visible state after the changed interaction",
            "assert failure/disabled state instead of only rendering or clicking",
            "assert sibling state is not changed unintentionally",
        ]
    if kinds & {"api-client"}:
        return [
            "assert request method, path, payload, and response mapping",
            "assert empty/error responses are handled explicitly",
        ]
    if kinds & {"store-or-action", "hook"}:
        return [
            "assert the intended state transition",
            "assert rollback/error behavior and unaffected sibling state",
        ]
    if "/repositories/" in lowered:
        if any(name.endswith(".delete_for_target") for name in symbol_names):
            return [
                "assert only the row matching session_id, user_id, and target_event_id is deleted",
                "assert the deleted row is returned while other users and target events remain unchanged",
                "assert repeating the delete after the row is gone returns None",
            ]
        if any(name.endswith(".find_by_event_id") for name in symbol_names):
            return [
                "assert the matching session and event return a SessionEventRef with the complete payload",
                "assert the same event id in another session is not returned",
                "assert an unknown event id returns None",
            ]
        return [
            "assert the persisted/query result for the changed key",
            "assert missing-row behavior without affecting unrelated rows",
        ]
    if (
        "lifespan" in {name.rsplit(".", 1)[-1] for name in symbol_names}
        and {"provider", "setup", "shutdown", "tracing"} <= diff_tokens
    ):
        return [
            "assert startup stores the exact provider returned by setup_tracing on app.state",
            "assert shutdown_tracing receives that same provider during application shutdown",
            "assert app.state.tracer_provider is cleared after shutdown",
        ]
    if any(token in lowered for token in ("observability", "trace", "runtime")):
        return [
            "assert emitted metadata/attributes and lifecycle calls",
            "assert cleanup and failure behavior",
        ]
    return [
        "assert the changed return value or state transition",
        "assert the relevant failure or boundary case",
    ]


def guidance_behavior(
    path: str,
    symbols: list[dict[str, Any]],
) -> str:
    """Name the concrete changed behavior instead of repeating a container name."""
    symbol_names = sorted({
        str(symbol.get("name") or "")
        for symbol in symbols
        if symbol.get("name")
    })
    diff_tokens = {
        str(token).lower()
        for symbol in symbols
        for token in symbol.get("diff_tokens", [])
    }
    route = next((symbol for symbol in symbols if symbol.get("kind") == "route"), None)
    if route:
        return (
            f"{route.get('route_method', '')} {route.get('route_path', '')}".strip()
            or str(route.get("name") or "")
        )
    kinds = {str(symbol.get("kind") or "") for symbol in symbols}
    if "component" in kinds and {"assistant", "turn", "active"} <= diff_tokens:
        return "same-turn assistant bubbles share the authoritative active state"
    if (
        "lifespan" in {name.rsplit(".", 1)[-1] for name in symbol_names}
        and {"provider", "setup", "shutdown", "tracing"} <= diff_tokens
    ):
        return "lifespan stores and shuts down the same tracing provider"
    if any(name.endswith(".delete_for_target") for name in symbol_names):
        return "delete only the caller's feedback for the selected target event"
    if any(name.endswith(".find_by_event_id") for name in symbol_names):
        return "find a session event by id and return its complete payload"
    if len(symbol_names) == 1:
        return symbol_names[0]
    if symbol_names and len(symbol_names) <= 2:
        return " / ".join(symbol_names)
    return (
        f"{Path(path).stem.replace('_', ' ')}: "
        + ", ".join(symbol_names[:3])
        + (f" (+{len(symbol_names) - 3})" if len(symbol_names) > 3 else "")
    )


def identifier_tokens(value: str) -> set[str]:
    """Split paths, snake_case, camelCase, and qualified names into useful terms."""
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    tokens = set(re.findall(r"[A-Za-z0-9]+", separated.lower()))
    return {
        token for token in tokens
        if len(token) > 2 and token not in BEHAVIOR_STOPWORDS
    }


def behavior_tokens(path: str, symbols: Iterable[dict[str, Any]]) -> set[str]:
    tokens = identifier_tokens(Path(path).stem)
    for symbol in symbols:
        tokens.update(identifier_tokens(str(symbol.get("name") or "")))
        tokens.update(identifier_tokens(str(symbol.get("route_path") or "")))
    return tokens


def asserted_store_action_covers_container(
    symbol: dict[str, Any],
    symbols: Iterable[dict[str, Any]],
    asserted_symbol_names: set[str],
) -> bool:
    """Avoid a duplicate gap for a broad store factory around a covered action."""
    if (
        symbol.get("kind") != "hook"
        or not symbol.get("requires_diff_overlap")
    ):
        return False
    changed_tokens = set(symbol.get("diff_tokens", []))
    path = str(symbol.get("path") or "")
    for candidate in symbols:
        name = str(candidate.get("name") or "")
        if (
            candidate is symbol
            or candidate.get("kind") != "store-or-action"
            or str(candidate.get("path") or "") != path
            or name not in asserted_symbol_names
        ):
            continue
        action_name = name.rsplit(".", 1)[-1]
        action_tokens = identifier_tokens(action_name)
        if len(action_tokens) >= 2 and action_tokens <= changed_tokens:
            return True
    return False


def substantive_case_assertion(case: dict[str, Any]) -> bool:
    """Return whether a case asserts something more specific than ``assert True``."""
    return bool(
        not case.get("disabled")
        and case.get("assertions")
        and (
            case.get("assertion_linked_identifiers")
            or case.get("rendered_identifiers")
            or case.get("machine_checks")
        )
    )


def source_inspection_case(case: dict[str, Any]) -> bool:
    """Detect tests that inspect source syntax instead of executing the entrypoint."""
    identifiers = {
        str(value)
        for value in (
            *case.get("referenced_identifiers", []),
            *case.get("assertion_linked_identifiers", []),
        )
    }
    return bool(
        {"inspect.getsource", "ast.parse"} <= identifiers
        or "getsource" in identifiers
        and "parse" in identifiers
    )


def behavior_case_names(
    symbol: dict[str, Any],
    test_cases: Iterable[dict[str, Any]],
    *,
    reachable_from_import: bool,
    contract_only: bool = False,
) -> set[str]:
    """Find cases whose assertions describe the changed behavior.

    This is deliberately stricter than "the file imports the module and has an
    assertion".  The case must contain a substantive assertion and its name or
    asserted state must overlap the changed object's concrete behavior.
    """
    symbol_name = str(symbol.get("name") or "")
    identifier = symbol_identifier(symbol)
    target_tokens = behavior_tokens(str(symbol.get("path") or ""), [symbol])
    target_tokens.update(identifier_tokens(symbol_name))
    diff_tokens = set(symbol.get("diff_tokens", []))
    matched: set[str] = set()
    for case in test_cases:
        if not substantive_case_assertion(case):
            continue
        referenced = set(case.get("referenced_identifiers", []))
        asserted = set(case.get("assertion_linked_identifiers", []))
        asserted.update(case.get("rendered_identifiers", []))
        case_tokens = identifier_tokens(str(case.get("name") or ""))
        assertion_tokens = set().union(*(
            identifier_tokens(str(value)) for value in asserted
        )) if asserted else set()
        overlap = target_tokens & (case_tokens | assertion_tokens)
        diff_overlap = diff_tokens & (case_tokens | assertion_tokens)
        owner = (
            symbol_name.rsplit(".", 1)[0].rsplit(".", 1)[-1]
            if symbol.get("kind") == "field" and "." in symbol_name
            else None
        )
        owner_referenced = not owner or owner in referenced
        direct_reference = bool(
            identifier and identifier in referenced and owner_referenced
        )
        route_contract = (
            symbol.get("kind") == "route"
            and "router" in referenced
            and len(overlap) >= 2
        )
        if symbol.get("requires_diff_overlap"):
            reachable_match = (
                reachable_from_import
                and len(
                    diff_overlap - PUBLIC_GENERIC_BEHAVIOR_TOKENS
                ) >= 2
            )
        else:
            reachable_match = (
                reachable_from_import
                and len(overlap - PUBLIC_GENERIC_BEHAVIOR_TOKENS) >= 2
            )
        direct_match = (
            direct_reference
            and bool(overlap - PUBLIC_GENERIC_BEHAVIOR_TOKENS)
        )
        matched_case = (
            route_contract
            if contract_only
            else direct_match or reachable_match
        )
        if (
            matched_case
            and symbol.get("requires_diff_overlap")
            and not (diff_overlap - PUBLIC_GENERIC_BEHAVIOR_TOKENS)
        ):
            matched_case = False
        if matched_case:
            name = str(case.get("name") or "")
            if name:
                matched.add(name)
    return matched


def relation_relevance_score(
    relation: dict[str, Any],
    path: str,
    symbols: Iterable[dict[str, Any]],
) -> int:
    """Rank weak relations by concrete behavior overlap, not module proximity."""
    symbols_list = list(symbols)
    target_tokens = behavior_tokens(path, symbols_list)
    test_tokens = identifier_tokens(str(relation.get("path") or ""))
    for value in relation.get("test_names", []):
        test_tokens.update(identifier_tokens(str(value)))
    overlap = target_tokens & test_tokens
    score = len(overlap - PUBLIC_GENERIC_BEHAVIOR_TOKENS) * 18
    symbol_names = {
        str(symbol.get("name") or "")
        for symbol in symbols_list if symbol.get("name")
    }
    linked = symbol_names & set(relation.get("assertion_linked_symbols", []))
    if linked:
        score += 100
    reasons = " ".join(relation.get("relation_reasons", [])).lower()
    for symbol in symbols_list:
        identifier = symbol_identifier(symbol)
        if identifier and (
            f"references {identifier.lower()}" in reasons
            or f"reaches {identifier.lower()}" in reasons
        ):
            score += 45
    if relation.get("related_symbols"):
        score += 5
    if reasons and all(
        reason.startswith("configured module relation")
        for reason in relation.get("relation_reasons", [])
    ):
        score -= 30
    return score


def relevant_weak_relations(
    relations: Iterable[dict[str, Any]],
    path: str,
    symbols: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return only weak tests a human could reasonably strengthen for this behavior."""
    symbols_list = list(symbols)
    ranked = sorted(
        (
            (relation_relevance_score(relation, path, symbols_list), relation)
            for relation in relations
        ),
        key=lambda item: (-item[0], str(item[1].get("path") or "")),
    )
    return [relation for score, relation in ranked if score >= 18]


def suggested_test_target(
    repo: str,
    path: str,
    framework: str,
    existing_tests: list[str],
    *,
    symbols: Iterable[dict[str, Any]] = (),
    available_tests: Iterable[str] = (),
) -> str:
    """Propose one concrete place to add or strengthen the test."""
    local_path = repo_local(path, repo)
    source = Path(local_path)
    prefix = "" if repo == "BIC-meta" else f"{repo}/"
    symbol_list = list(symbols)
    available = sorted(set(available_tests))
    preferred: list[str] = []
    route = next(
        (symbol for symbol in symbol_list if symbol.get("kind") == "route"),
        None,
    )
    if route:
        route_parts = [
            part
            for part in str(route.get("route_path") or "").split("/")
            if part and not part.startswith("{")
        ]
        resource = (
            re.sub(r"[^a-z0-9]+", "_", route_parts[-1].lower()).strip("_")
            if route_parts else ""
        )
        route_target = (
            f"{prefix}tests/unit/test_route_{resource or source.stem}.py"
        )
        route_behavior_tests = [
            candidate
            for candidate in available
            if "/test_route_" in f"/{candidate}"
            and "contract" not in Path(candidate).stem.lower()
            and (
                not resource
                or resource in identifier_tokens(Path(candidate).stem)
            )
        ]
        if route_behavior_tests:
            return route_behavior_tests[0]
        return route_target
    if framework == "playwright":
        stem = re.sub(r"[^a-z0-9]+", "-", source.stem.lower()).strip("-")
        preferred.append(f"{prefix}tests/{stem or 'changed-behavior'}.spec.ts")
    if source.suffix.lower() in {".ts", ".tsx", ".js", ".jsx"}:
        preferred.append(
            f"{prefix}{source.with_name(source.stem + '.test' + source.suffix).as_posix()}"
        )
    if source.suffix.lower() == ".py":
        if "/repositories/" in f"/{local_path}":
            entity = source.stem.removesuffix("_repo")
            preferred.append(
                f"{prefix}tests/unit/test_persistence_repo_{entity}.py"
            )
        preferred.append(f"{prefix}tests/unit/test_{source.stem}.py")

    exact_available = [candidate for candidate in preferred if candidate in available]
    if exact_available:
        return exact_available[0]
    if (route or "/repositories/" in f"/{local_path}") and preferred:
        return preferred[0]

    ranked_existing = sorted(
        (
            (
                relation_relevance_score(
                    {
                        "path": candidate,
                        "test_names": [],
                        "relation_reasons": [],
                        "related_symbols": [],
                        "assertion_linked_symbols": [],
                    },
                    path,
                    symbol_list,
                ),
                candidate,
            )
            for candidate in set(existing_tests)
        ),
        key=lambda item: (
            -item[0],
            item[1],
        ),
    )
    relevant_existing = [
        candidate for score, candidate in ranked_existing if score >= 18
    ]
    if relevant_existing:
        return relevant_existing[0]
    if existing_tests:
        # Callers pass only relations that already cleared behavior relevance.
        # A generic fixture name must not force a duplicate test file when the
        # exact weak test is the file that should be strengthened.
        return sorted(set(existing_tests))[0]

    target_tokens = behavior_tokens(path, symbol_list)
    nearby = sorted(
        available,
        key=lambda candidate: (
            -len(target_tokens & identifier_tokens(candidate)),
            candidate,
        ),
    )
    if nearby and len(target_tokens & identifier_tokens(nearby[0])) >= 2:
        return nearby[0]
    if preferred:
        return preferred[0]
    return f"{prefix}{local_path}"


def browser_scenario_test_path(value: str) -> str | None:
    match = re.search(
        r"(?:^|:)([^:]+\.(?:spec|test)\.(?:js|jsx|ts|tsx))(?:[:]|$)",
        value,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def relation_weakness(relation: dict[str, Any]) -> str:
    """Describe a concrete test defect, not mere structural proximity."""
    if relation.get("disabled_tests"):
        return "the related test is skipped, disabled, todo, or xfailed"
    browser = relation.get("browser_evidence")
    if browser and not browser.get("has_machine_check"):
        return "the browser scenario has actions/observations but no target-linked machine check"
    if relation.get("assertions"):
        return "assertions exist but are not linked to the changed object's result or state"
    return "the related test has no active assertion"


def grouped_guidance(
    action: str,
    repo: str,
    module_scope: str,
    path: str,
    symbols: list[dict[str, Any]],
    weak_relations: list[dict[str, Any]],
    missing_relation_symbols: list[str],
    available_tests: Iterable[str] = (),
) -> dict[str, Any]:
    layer, framework, alternatives = guidance_profile(repo, module_scope, path, symbols)
    weak_relations = relevant_weak_relations(weak_relations, path, symbols)
    route = next((symbol for symbol in symbols if symbol.get("kind") == "route"), None)
    symbol_names = sorted({
        str(symbol.get("name") or "")
        for symbol in symbols if symbol.get("name")
    })
    behavior = guidance_behavior(path, symbols)
    all_existing_tests = sorted({
        str(relation.get("path"))
        for relation in weak_relations
        if relation.get("path")
    })
    evidence_gaps = sorted({
        relation_weakness(relation)
        for relation in weak_relations
    })
    if missing_relation_symbols:
        evidence_gaps.append(
            "no object-specific test relation was found for: "
            + ", ".join(sorted(set(missing_relation_symbols)))
        )
    available = set(available_tests)
    partial_evidence_targets = sorted({
        str(relation.get("path"))
        for relation in weak_relations
        if relation.get("path")
        and (
            relation.get("contract_asserted_symbols")
            or relation.get("evidence_level") == "contract-asserted"
        )
        and not route
    })
    target = (
        partial_evidence_targets[0]
        if partial_evidence_targets
        else suggested_test_target(
            repo,
            path,
            framework,
            all_existing_tests,
            symbols=symbols,
            available_tests=available,
        )
    )
    target_exists = target in available
    if action == "add":
        evidence_gaps = ["no active direct or safe-indirect test asserts this changed behavior"]
    effective_action = (
        "strengthen"
        if target_exists or target in all_existing_tests
        else "add"
    )
    if effective_action == "add":
        if route and any(
            relation.get("contract_asserted_symbols")
            or relation.get("evidence_level") == "contract-asserted"
            for relation in weak_relations
        ):
            evidence_gaps = [
                "the existing contract test covers method/path/status only; "
                "authenticated route delegation and error mapping are not asserted"
            ]
        else:
            evidence_gaps = [
                "no active direct or safe-indirect test asserts this changed behavior"
            ]
    elif target_exists and target not in all_existing_tests:
        all_existing_tests.append(target)
        all_existing_tests.sort()
        evidence_gaps = [
            "the existing test file has no active object- or behavior-linked assertion"
        ]
    return {
        "action": effective_action,
        "repo": repo,
        "module_scope": module_scope,
        "path": path,
        "symbols": symbol_names,
        "target_behavior": behavior,
        "test_layer": layer,
        "recommended_framework": framework,
        "public_test_method": public_test_method(layer, framework),
        "alternative_frameworks": alternatives,
        "existing_test_count": len(all_existing_tests),
        "existing_tests": all_existing_tests[:MAX_GUIDANCE_EXISTING_TESTS],
        "existing_test_overflow": max(
            0, len(all_existing_tests) - MAX_GUIDANCE_EXISTING_TESTS
        ),
        "evidence_gaps": evidence_gaps,
        "suggested_assertions": suggested_assertions(path, symbols),
        "suggested_test_target": target,
    }


def guidance_summary(item: dict[str, Any]) -> str:
    verb = "Add" if item["action"] == "add" else "Strengthen"
    symbols = ", ".join(item.get("symbols") or []) or item["target_behavior"]
    return (
        f"{verb} {item['public_test_method']} tests for "
        f"{item['target_behavior']} in {item['path']} covering: {symbols}."
    )


def browser_journey_guidance(
    changed_symbols: list[dict[str, Any]],
    journey_graph: dict[str, Any],
) -> list[dict[str, Any]]:
    """Recommend browser evidence separately from object-level unit guidance."""
    nodes_by_id = {
        str(node.get("id") or ""): node
        for node in journey_graph.get("nodes", [])
        if node.get("id")
    }
    completed_by_anchor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in journey_graph.get("paths", []):
        completed_by_anchor[str(path.get("anchor") or "")].append(path)
    partial_by_anchor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in journey_graph.get("partial_paths", []):
        partial_by_anchor[str(path.get("anchor") or "")].append(path)
    guidance: list[dict[str, Any]] = []
    for source in changed_symbols:
        for symbol in source.get("symbols", []):
            if symbol.get("kind") != "route" or not symbol.get("route_path"):
                continue
            anchor = (
                f"changed:{source.get('repo')}:{source.get('path')}:{symbol.get('name')}"
            )
            completed = completed_by_anchor.get(anchor, [])
            scenarios = sorted({
                str(path.get("scenario"))
                for path in completed
                if path.get("scenario")
            })
            scenario_nodes = sorted(
                (
                    nodes_by_id[scenario]
                    for scenario in scenarios
                    if scenario in nodes_by_id
                    and nodes_by_id[scenario].get("path")
                ),
                key=lambda node: (
                    str(node.get("repo") or ""),
                    str(node.get("path") or ""),
                ),
            )
            action = "strengthen" if completed else "add"
            method_path = (
                f"{symbol.get('route_method', '')} {symbol.get('route_path', '')}".strip()
            )
            protocol_terms = {
                token.lower()
                for token in re.findall(
                    r"[A-Za-z]+",
                    f"{symbol.get('name', '')} {symbol.get('route_path', '')}",
                )
            }
            alternatives = (
                ["cdp"]
                if protocol_terms & {"sse", "stream", "streaming", "websocket", "console"}
                else []
            )
            source_repo = str(source.get("repo") or "")
            target_repo = source_repo
            target_path: str | None = None
            if scenario_nodes:
                target_repo = str(scenario_nodes[0].get("repo") or source_repo)
                target_path = str(scenario_nodes[0].get("path") or "")
            else:
                frontend_layers = {
                    "api-client", "component", "frontend-module", "hook",
                    "page", "store",
                }
                frontend_nodes = [
                    nodes_by_id[node_id]
                    for path in partial_by_anchor.get(anchor, [])
                    for node_id in reversed(path.get("nodes", []))
                    if node_id in nodes_by_id
                    and nodes_by_id[node_id].get("repo")
                    and nodes_by_id[node_id].get("repo") != source_repo
                    and nodes_by_id[node_id].get("layer") in frontend_layers
                ]
                if frontend_nodes:
                    target_repo = str(frontend_nodes[0].get("repo") or source_repo)
            if not target_path:
                target_path = suggested_test_target(
                    target_repo,
                    str(source.get("path") or ""),
                    "playwright",
                    [],
                )
            guidance.append({
                "action": action,
                "repo": source.get("repo"),
                "test_repo": target_repo,
                "module_scope": "cross-stack-user-journey",
                "path": source.get("path"),
                "symbols": [symbol.get("name")],
                "target_behavior": f"end-to-end user behavior for {method_path}",
                "test_layer": "browser-user-journey",
                "recommended_framework": "playwright",
                "public_test_method": "Playwright",
                "alternative_frameworks": alternatives,
                "existing_tests": scenarios,
                "existing_test_count": len(scenarios),
                "existing_test_overflow": 0,
                "evidence_gaps": [
                    (
                        "a static browser path exists, but its machine check is not tied to "
                        "the changed route's user-visible outcome"
                    )
                    if completed else
                    "no completed static path reaches a browser scenario"
                ],
                "suggested_assertions": [
                    f"assert the browser issues {method_path} and consumes its result",
                    "assert the user-visible success state after the action",
                    "assert failure state and persistence after reload when applicable",
                ],
                "suggested_test_target": target_path,
            })
    return guidance


def useful_public_symbol(value: str) -> bool:
    name = value.rsplit(".", 1)[-1]
    return bool(
        value
        and name != "__all__"
        and not re.search(r"\.(?:json|ya?ml|md|rst|adoc)$", value, re.IGNORECASE)
    )


def public_test_tokens(relation: dict[str, Any]) -> set[str]:
    tokens = identifier_tokens(str(relation.get("path") or ""))
    for value in (
        *relation.get("test_names", []),
        *relation.get("selected_test_cases", []),
        *relation.get("behavior_test_cases", []),
        *relation.get("contract_test_cases", []),
    ):
        tokens.update(identifier_tokens(str(value)))
    return tokens


def explained_public_symbols(relation: dict[str, Any]) -> list[str]:
    """Keep only objects named by the chain or meaningfully matched by the test."""
    reasons = " ".join(relation.get("relation_reasons", [])).lower()
    test_tokens = public_test_tokens(relation)
    test_text = " ".join((
        str(relation.get("path") or ""),
        *[str(value) for value in relation.get("test_names", [])],
        *[str(value) for value in relation.get("selected_test_cases", [])],
        *[str(value) for value in relation.get("behavior_test_cases", [])],
        *[str(value) for value in relation.get("contract_test_cases", [])],
    )).lower()
    explained: list[str] = []
    for raw_symbol in relation.get("related_symbols", []):
        symbol = str(raw_symbol)
        if not useful_public_symbol(symbol):
            continue
        identifier = symbol.rsplit(".", 1)[-1]
        symbol_tokens = identifier_tokens(identifier)
        exact_reason = bool(identifier and identifier.lower() in reasons)
        overlap = symbol_tokens & test_tokens
        exact_case = bool(
            identifier
            and identifier.lower() in test_text
            and (
                identifier.lower() not in PUBLIC_GENERIC_BEHAVIOR_TOKENS
                or "." in symbol
            )
        )
        behavior_match = bool(
            exact_case
            or (overlap - PUBLIC_GENERIC_BEHAVIOR_TOKENS)
            or len(overlap) >= 2
        )
        if exact_reason or behavior_match:
            explained.append(symbol)
    return explained


def relevant_public_cases(
    relation: dict[str, Any],
    explained_symbols: Iterable[str],
    limit: int | None = 3,
) -> list[str]:
    symbols = [str(symbol) for symbol in explained_symbols]
    selected = list(
        relation.get("behavior_test_cases")
        or relation.get("contract_test_cases")
        or
        relation.get("selected_test_cases")
        or relation.get("test_names", [])
    )
    matched: list[str] = []
    for case in selected:
        case_text = str(case)
        case_tokens = identifier_tokens(case_text)
        if any(
            (
                (
                    symbol.rsplit(".", 1)[-1].lower() in case_text.lower()
                    and (
                        symbol.rsplit(".", 1)[-1].lower()
                        not in PUBLIC_GENERIC_BEHAVIOR_TOKENS
                        or "." in symbol
                    )
                )
                or bool(
                    (
                        identifier_tokens(symbol.rsplit(".", 1)[-1])
                        & case_tokens
                    ) - PUBLIC_GENERIC_BEHAVIOR_TOKENS
                )
                or len(
                    identifier_tokens(symbol.rsplit(".", 1)[-1])
                    & case_tokens
                ) >= 2
            )
            for symbol in symbols
        ):
            matched.append(case_text)
    if matched:
        return matched if limit is None else matched[:limit]
    return []


def test_or_document_path(path: str) -> bool:
    lowered = f"/{path.lower()}"
    return bool(
        "/tests/" in lowered
        or re.search(r"\.(?:test|spec)\.[^.]+$", lowered)
        or "/docs/" in lowered
        or "/.trellis/" in lowered
        or Path(path).suffix.lower() in DOCUMENTATION_SUFFIXES
    )


def relation_public_score(
    relation: dict[str, Any],
    relation_type: str,
    explained_symbols: Iterable[str],
) -> int:
    score = 0
    if relation.get("assertion_linked_symbols"):
        score += 100
    elif relation.get("assertion_linked_files"):
        score += 55
    elif relation.get("behavior_asserted_symbols"):
        score += 75
    elif relation.get("contract_asserted_symbols"):
        score += 35
    if relation.get("has_active_test_with_assertion"):
        score += 20
    useful_symbols = list(explained_symbols)
    score += min(len(useful_symbols), 3) * 12
    reasons = relation.get("relation_reasons", [])
    if any("references " in reason or "statically reaches " in reason for reason in reasons):
        score += 30
    if any("which imports the changed file via" in reason for reason in reasons):
        score += 10
    if reasons and all(reason.startswith("configured module relation") for reason in reasons):
        score -= 40
    if relation_type == "possible":
        target_tokens = set().union(*(
            identifier_tokens(str(path)) for path in relation.get("related_files", [])
        ))
        candidate_tokens = public_test_tokens(relation)
        score += len(target_tokens & candidate_tokens) * 18
        if relation.get("path") in relation.get("related_files", []):
            score -= 100
    return score


def relation_evidence_level(relation: dict[str, Any]) -> str:
    """Return the strongest evidence level, including legacy/manual fixtures."""
    if relation.get("assertion_linked_symbols"):
        return "object-asserted"
    if relation.get("behavior_asserted_symbols") or relation.get("behavior_asserted_files"):
        return "behavior-asserted"
    if relation.get("contract_asserted_symbols"):
        return "contract-asserted"
    return "related-only"


def public_behavior_label(relation: dict[str, Any]) -> str:
    useful_symbols = explained_public_symbols(relation)
    if useful_symbols:
        return ", ".join(useful_symbols[:3])
    related_files = [str(path) for path in relation.get("related_files", [])]
    if related_files:
        return Path(related_files[0]).stem
    return "unresolved changed behavior"


def public_relation_explanation(
    relation_type: str,
    target_behavior: str,
    relevant_cases: list[str],
    reasons: list[str],
) -> str:
    """Create one stable sentence for the human-facing test list."""
    case_note = (
        f"; matching case: {relevant_cases[0]}"
        if relevant_cases else ""
    )
    reason = reasons[0] if reasons else "a concrete changed-object relation"
    if relation_type == "direct":
        return f"Exercises {target_behavior}{case_note}."
    if relation_type == "indirect":
        return (
            f"Exercises {target_behavior} through {reason}{case_note}; "
            "the path passes through another source entry."
        )
    return (
        f"May relate to {target_behavior} because {reason}{case_note}; "
        "use it only as a search clue."
    )


def public_relation_record(
    relation: dict[str, Any],
    relation_type: str,
    explained_symbols: list[str] | None = None,
) -> dict[str, Any]:
    browser = relation.get("browser_evidence") or {}
    useful_symbols = (
        explained_public_symbols(relation)
        if explained_symbols is None else explained_symbols
    )
    relevant_cases = relevant_public_cases(relation, useful_symbols)
    target_behavior = (
        ", ".join(useful_symbols[:3])
        if useful_symbols else public_behavior_label(relation)
    )
    reasons = list(relation.get("relation_reasons", []))[:3]
    return {
        "relation_type": relation_type,
        "repo": relation.get("repo"),
        "path": relation.get("path"),
        "framework": relation.get("framework"),
        "target_behavior": target_behavior,
        "public_explanation": public_relation_explanation(
            relation_type,
            target_behavior,
            relevant_cases,
            reasons,
        ),
        "changed_objects": useful_symbols[:5],
        "why_related": reasons,
        "relevant_test_cases": relevant_cases,
        "browser_evidence": (
            {
                "framework": browser.get("framework"),
                "actions": list(browser.get("actions", []))[:5],
                "observations": list(browser.get("observations", []))[:5],
                "has_machine_check": bool(browser.get("has_machine_check")),
            }
            if browser else None
        ),
    }


def strict_relation_evidence(
    relation: dict[str, Any],
    relation_type: str,
) -> dict[str, Any] | None:
    """Return behavior-level evidence shared by the brief and execution scope."""
    if relation_type not in {"direct", "indirect"}:
        return None
    explained_symbols = explained_public_symbols(relation)
    score = relation_public_score(
        relation, relation_type, explained_symbols,
    )
    public_record = public_relation_record(
        relation, relation_type, explained_symbols,
    )
    record = {
        **public_record,
        "relevant_test_cases": relevant_public_cases(
            relation, explained_symbols, limit=None,
        ),
    }
    if (
        relation_type == "direct"
        and explained_symbols
        and bool(
            relation.get("behavior_asserted_symbols")
            or relation.get("contract_asserted_symbols")
        )
        and record["relevant_test_cases"]
        and score >= 20
    ):
        return {
            "score": score,
            "explained_symbols": explained_symbols,
            "record": record,
            "public_record": public_record,
            "selection_reason": (
                "active direct case asserts the changed behavior"
                if relation.get("behavior_asserted_symbols")
                else "active route contract case asserts the changed method/path/status"
            ),
        }
    if (
        relation_type == "indirect"
        and explained_symbols
        and bool(relation.get("behavior_asserted_symbols"))
        and record["relevant_test_cases"]
        and score >= 22
    ):
        return {
            "score": score,
            "explained_symbols": explained_symbols,
            "record": record,
            "public_record": public_record,
            "selection_reason": (
                "active indirect case asserts the changed behavior through an "
                "explainable import/reference chain"
            ),
        }
    return None


def dedupe_public_relations(
    items: Iterable[tuple[int, dict[str, Any]]],
    limit: int,
) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for _score, item in sorted(
        items,
        key=lambda pair: (
            -pair[0],
            str(pair[1].get("repo") or ""),
            str(pair[1].get("path") or ""),
        ),
    ):
        key = (
            str(item.get("repo") or ""),
            str(item.get("path") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        chosen.append(item)
        if len(chosen) >= limit:
            break
    return chosen


def build_public_test_summary(
    module_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a bounded, explainable view while preserving all raw relations."""
    direct_ranked: list[tuple[int, dict[str, Any]]] = []
    indirect_ranked: list[tuple[int, dict[str, Any]]] = []
    possible_by_behavior: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    raw_counts = {"direct": 0, "indirect": 0, "possible": 0}
    module_summaries: list[dict[str, Any]] = []

    for module in module_results:
        module_public: dict[str, Any] = {
            "repo": module.get("repo"),
            "module_scope": module.get("module_scope"),
            "direct": [],
            "indirect": [],
            "possible": [],
        }
        for relation_type, field in (
            ("direct", "directly_related_tests"),
            ("indirect", "indirectly_related_tests"),
            ("possible", "possibly_related_tests"),
        ):
            relations = module.get(field, [])
            raw_counts[relation_type] += len(relations)
            ranked: list[tuple[int, dict[str, Any]]] = []
            for relation in relations:
                strict = strict_relation_evidence(relation, relation_type)
                if strict is not None:
                    score = int(strict["score"])
                    record = strict["public_record"]
                    if relation_type == "direct":
                        direct_ranked.append((score, record))
                    else:
                        indirect_ranked.append((score, record))
                    ranked.append((score, record))
                    continue
                explained_symbols = explained_public_symbols(relation)
                score = relation_public_score(
                    relation, relation_type, explained_symbols,
                )
                record = public_relation_record(
                    relation, relation_type, explained_symbols,
                )
                if (
                    relation_type == "possible"
                    and not all(
                        test_or_document_path(str(path))
                        for path in relation.get("related_files", [])
                    )
                    and score >= 18
                ):
                    possible_by_behavior[record["target_behavior"]].append((score, record))
                    ranked.append((score, record))
            module_public[relation_type] = dedupe_public_relations(ranked, 3)
        module_summaries.append(module_public)

    direct = dedupe_public_relations(direct_ranked, MAX_PUBLIC_DIRECT_TESTS)
    indirect = dedupe_public_relations(indirect_ranked, MAX_PUBLIC_INDIRECT_TESTS)
    established_paths = {
        (str(item.get("repo") or ""), str(item.get("path") or ""))
        for item in [*direct, *indirect]
    }
    possible_groups = [
        {
            "target_behavior": behavior,
            "candidates": [
                item for item in dedupe_public_relations(
                    ranked, MAX_PUBLIC_POSSIBLE_PER_BEHAVIOR
                )
                if (
                    str(item.get("repo") or ""),
                    str(item.get("path") or ""),
                ) not in established_paths
            ],
        }
        for behavior, ranked in sorted(
            possible_by_behavior.items(),
            key=lambda item: (-max(score for score, _record in item[1]), item[0]),
        )[:MAX_PUBLIC_POSSIBLE_GROUPS]
    ]
    possible_groups = [
        group for group in possible_groups if group["candidates"]
    ]
    return {
        "selection_rule": (
            "Only bounded relations with concrete changed objects, explainable import/"
            "reference chains, or meaningful behavior terms are shown. Raw relations remain "
            "available for diagnostics and Phase 2 candidate construction."
        ),
        "raw_relation_counts": raw_counts,
        "displayed_relation_counts": {
            "direct": len(direct),
            "indirect": len(indirect),
            "possible": sum(len(group["candidates"]) for group in possible_groups),
        },
        "directly_related_tests": direct,
        "indirectly_related_tests": indirect,
        "possibly_related_test_groups": possible_groups,
        "modules": module_summaries,
    }


def repo_local(path: str, repo: str) -> str:
    return path[len(repo) + 1:] if repo != "BIC-meta" and path.startswith(f"{repo}/") else path


def without_extension(path: str) -> str:
    for extension in (".tsx", ".jsx", ".ts", ".js", ".py"):
        if path.endswith(extension):
            return path[:-len(extension)]
    return path


def semantic_tokens(value: str, repo: str | None = None) -> set[str]:
    tokens = set(re.findall(r"[A-Za-z0-9]+", value.lower()))
    excluded = set(TOKEN_STOPWORDS) | {"bic", "meta"}
    if repo:
        excluded.update(re.findall(r"[A-Za-z0-9]+", repo.lower()))
    return {token for token in tokens if len(token) > 2 and token not in excluded}


def basename_tokens(path: str, repo: str) -> set[str]:
    return semantic_tokens(Path(path).name, repo)


def python_module(path: str, repo: str) -> str:
    local = without_extension(repo_local(path, repo)).replace("/", ".")
    return local.removesuffix(".__init__")


def normalized_python_import(import_value: str, importing_path: str, repo: str) -> str:
    level = len(import_value) - len(import_value.lstrip("."))
    if not level:
        return import_value
    remainder = import_value[level:]
    package_parts = list(Path(repo_local(importing_path, repo)).parent.parts)
    parents_to_drop = max(level - 1, 0)
    if parents_to_drop:
        package_parts = package_parts[:-parents_to_drop]
    if remainder:
        package_parts.extend(part for part in remainder.split(".") if part)
    return ".".join(package_parts)


def javascript_import_path(import_value: str, test_path: str, repo: str) -> str:
    test_local = repo_local(test_path, repo)
    if import_value.startswith("."):
        value = posixpath.normpath(posixpath.join(posixpath.dirname(test_local), import_value))
    else:
        value = import_value.lstrip("@~/")
    return without_extension(value).removesuffix("/index")


def resolve_imported_source(
    workspace_root: Path, import_value: str, importing_path: str, repo: str,
) -> Path | None:
    repo_root = workspace_root if repo == "BIC-meta" else workspace_root / repo
    if importing_path.endswith(".py"):
        parts = normalized_python_import(import_value, importing_path, repo).split(".")
        importing_parent = repo_root / Path(repo_local(importing_path, repo)).parent
        if parts:
            sibling = importing_parent / parts[0]
            for candidate in (sibling.with_suffix(".py"), sibling / "__init__.py"):
                safe_candidate, _ = safe_repository_file(candidate, repo_root)
                if safe_candidate is not None:
                    return safe_candidate
        for size in range(len(parts), 0, -1):
            base = repo_root.joinpath(*parts[:size])
            for candidate in (base.with_suffix(".py"), base / "__init__.py"):
                safe_candidate, _ = safe_repository_file(candidate, repo_root)
                if safe_candidate is not None:
                    return safe_candidate
        return None

    imported = javascript_import_path(import_value, importing_path, repo)
    bases = [repo_root / imported]
    if not imported.startswith(("src/", "app/")):
        bases.extend([repo_root / "src" / imported, repo_root / "app" / imported])
    extensions = (".ts", ".tsx", ".js", ".jsx")
    for base in bases:
        for extension in extensions:
            candidate = base.with_suffix(extension)
            safe_candidate, _ = safe_repository_file(candidate, repo_root)
            if safe_candidate is not None:
                return safe_candidate
            index = base / f"index{extension}"
            safe_index, _ = safe_repository_file(index, repo_root)
            if safe_index is not None:
                return safe_index
    return None


def workspace_path(path: Path, workspace_root: Path) -> str:
    return path.resolve().relative_to(workspace_root.resolve()).as_posix()


def local_target_path(workspace_root: Path, target: str, repo: str) -> Path | None:
    repo_root = (workspace_root if repo == "BIC-meta" else workspace_root / repo).resolve()
    candidate = Path(target).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    safe_candidate, _ = safe_repository_file(candidate, repo_root)
    return safe_candidate


def target_matches(
    workspace_root: Path,
    target: str,
    changed_path: str,
    repo: str,
) -> bool:
    resolved = local_target_path(workspace_root, target, repo)
    if resolved is None:
        return False
    repo_root = workspace_root if repo == "BIC-meta" else workspace_root / repo
    changed, _ = safe_repository_file(workspace_root / changed_path, repo_root)
    return changed is not None and resolved == changed


def ast_dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = ast_dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def command_branch_roots(tree: ast.Module, command: str) -> set[str]:
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    main = functions.get("main")
    if main is None:
        return set()

    def compared_command(node: ast.AST) -> str | None:
        if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
            return None
        if not isinstance(node.ops[0], ast.Eq):
            return None
        left = ast_dotted_name(node.left)
        right = node.comparators[0]
        if left.endswith("args.command") and isinstance(right, ast.Constant) and isinstance(right.value, str):
            return right.value
        return None

    def called_functions(statements: list[ast.stmt]) -> set[str]:
        return {
            call.func.id
            for statement in statements
            for call in ast.walk(statement)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
        }

    def select_branch(node: ast.If) -> set[str]:
        candidate = compared_command(node.test)
        if candidate == command:
            return called_functions(node.body)
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            return select_branch(node.orelse[0])
        return called_functions(node.orelse)

    for statement in main.body:
        if isinstance(statement, ast.If) and compared_command(statement.test) is not None:
            return {"main", *select_branch(statement)}
    return set()


def python_reachable_symbols(
    path: Path,
    roots: Iterable[str],
    argv: Iterable[str] = (),
    *,
    repository_root: Path,
) -> set[str]:
    """Return statically reachable local symbols without importing the file."""
    safe_path, _ = safe_repository_file(path, repository_root)
    if safe_path is None or safe_path.suffix != ".py":
        return set()
    try:
        tree = ast.parse(safe_path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return set(roots)

    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    constants: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            constants.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            constants.add(node.target.id)
    known_symbols = set(functions) | classes | constants
    requested = set(roots)
    arguments = list(argv)
    selected_command_roots: set[str] = set()
    if arguments and arguments[0] not in {"-c", "-m"}:
        selected_command_roots = command_branch_roots(tree, arguments[0])
        requested.update(selected_command_roots)

    reachable: set[str] = set()
    pending = [name for name in requested if name in known_symbols]
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        function = functions.get(name)
        if function is None:
            continue
        if name == "main" and selected_command_roots:
            continue
        referenced = {
            call.func.id
            for call in ast.walk(function)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id in (set(functions) | classes)
        }
        referenced.update(
            node.id for node in ast.walk(function)
            if isinstance(node, ast.Name) and node.id in constants
        )
        pending.extend(referenced - reachable)
    return reachable


def python_reachable_references(
    path: Path,
    roots: Iterable[str],
    argv: Iterable[str] = (),
    *,
    repository_root: Path,
) -> dict[str, list[str]]:
    """Return imports actually referenced by statically reachable functions."""
    safe_path, _ = safe_repository_file(path, repository_root)
    if safe_path is None or safe_path.suffix != ".py":
        return {"imports": [], "identifiers": []}
    try:
        tree = ast.parse(safe_path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return {"imports": [], "identifiers": []}

    reachable = python_reachable_symbols(
        safe_path, roots, argv, repository_root=repository_root,
    )
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    arguments = list(argv)
    selected_command_roots = (
        command_branch_roots(tree, arguments[0])
        if arguments and arguments[0] not in {"-c", "-m"}
        else set()
    )
    selected_nodes = [
        functions[name]
        for name in reachable
        if name in functions and not (selected_command_roots and name == "main")
    ]
    if not selected_nodes and not selected_command_roots:
        return {"imports": [], "identifiers": []}

    identifiers: set[str] = set(selected_command_roots)
    imported_bindings: dict[str, str] = {}

    def inspect(nodes: Iterable[ast.AST]) -> None:
        for parent in nodes:
            for node in ast.walk(parent):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_bindings[alias.asname or alias.name.split(".", 1)[0]] = alias.name
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported = python_import_name(node, alias)
                        if imported:
                            imported_bindings[alias.asname or alias.name] = imported
                elif isinstance(node, ast.Name):
                    identifiers.add(node.id)
                elif isinstance(node, ast.Attribute):
                    identifiers.add(node.attr)

    inspect(
        statement
        for statement in tree.body
        if isinstance(statement, (ast.Import, ast.ImportFrom))
    )
    inspect(selected_nodes)
    selected_imports = {
        imported for binding, imported in imported_bindings.items()
        if binding in identifiers
    }
    return {
        "imports": sorted(selected_imports),
        "identifiers": sorted(identifiers),
    }


def import_matches(import_value: str, test_path: str, changed_path: str, repo: str) -> bool:
    changed_local = without_extension(repo_local(changed_path, repo)).removesuffix("/index")
    if changed_path.endswith(".py"):
        module = python_module(changed_path, repo)
        imported = normalized_python_import(import_value, test_path, repo)
        return imported == module or imported.startswith(f"{module}.")
    imported = javascript_import_path(import_value, test_path, repo)
    if imported == changed_local:
        return True
    # Common aliases such as @/stores/chatStore may omit the source root.
    imported_parts = imported.split("/")
    changed_parts = changed_local.split("/")
    return len(imported_parts) >= 2 and changed_parts[-len(imported_parts):] == imported_parts


def symbol_identifier(symbol: dict[str, Any]) -> str | None:
    name = symbol["name"].rsplit(".", 1)[-1]
    return name if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name) else None


def symbol_owner_identifier(symbol: dict[str, Any]) -> str | None:
    """Return the declaring type for a qualified field/member when available."""
    name = str(symbol.get("name") or "")
    if "." not in name:
        return None
    owner = name.rsplit(".", 1)[0].rsplit(".", 1)[-1]
    return owner if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", owner) else None


def declaration_reachable_changed_symbols(
    path: Path,
    symbols: Iterable[dict[str, Any]],
    roots: Iterable[str],
    *,
    repository_root: Path,
) -> set[str]:
    """Expand tested declaration roots through references inside the same file.

    The changed-object mapper already provides declaration line ranges. Reusing
    those ranges keeps this traversal language-neutral and bounded: only other
    changed declarations referenced from a proven root can be added.
    """
    symbol_list = list(symbols)
    by_identifier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for symbol in symbol_list:
        identifier = symbol_identifier(symbol)
        if identifier:
            by_identifier[identifier].append(symbol)

    safe_path, _ = safe_repository_file(path, repository_root)
    reachable: set[str] = set()
    if safe_path is None:
        return reachable
    try:
        content = safe_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return reachable

    if safe_path.suffix == ".py":
        try:
            tree = ast.parse(content)
        except SyntaxError:
            tree = None
        if tree is not None:
            declarations: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = defaultdict(list)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    declarations[node.name].append(node)
            pending = [
                str(root) for root in roots
                if str(root) in declarations or str(root) in by_identifier
            ]
            seen_identifiers: set[str] = set()
            while pending:
                identifier = pending.pop()
                if identifier in seen_identifiers:
                    continue
                seen_identifiers.add(identifier)
                reachable.update(
                    str(symbol["name"])
                    for symbol in by_identifier.get(identifier, [])
                )
                referenced: set[str] = set()
                for declaration in declarations.get(identifier, []):
                    for node in ast.walk(declaration):
                        if isinstance(node, ast.Name):
                            referenced.add(node.id)
                        elif isinstance(node, ast.Attribute):
                            referenced.add(node.attr)
                pending.extend(sorted(
                    (
                        referenced
                        & (set(declarations) | set(by_identifier))
                    ) - seen_identifiers
                ))
            return reachable

    lines = content.splitlines()
    pending = [str(root) for root in roots if str(root) in by_identifier]
    seen_identifiers: set[str] = set()
    while pending:
        identifier = pending.pop()
        if identifier in seen_identifiers:
            continue
        seen_identifiers.add(identifier)
        for symbol in by_identifier[identifier]:
            reachable.add(str(symbol["name"]))
            start = symbol.get("start_line")
            end = symbol.get("end_line")
            if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
                continue
            declaration_text = "\n".join(lines[start - 1:min(end, len(lines))])
            referenced = set(re.findall(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b", declaration_text))
            pending.extend(sorted((referenced & set(by_identifier)) - seen_identifiers))
    return reachable


def module_ref(key: tuple[str, str]) -> dict[str, str]:
    return {"repo": key[0], "module_scope": key[1]}


def configured_targets(entry: dict[str, Any]) -> set[tuple[str, str]]:
    own = entry.get("relates_modules", entry.get("covers_modules", []))
    targets = {(entry["repo"], module) for module in own}
    cross = entry.get("relates_repository_modules", entry.get("covers_repository_modules", []))
    targets.update(
        (target["repo"], target["module_scope"])
        for target in cross if target.get("repo") and target.get("module_scope")
    )
    return targets


def configured_objects(entry: dict[str, Any], key: tuple[str, str]) -> set[str]:
    own_targets = {(entry["repo"], module) for module in entry.get("relates_modules", entry.get("covers_modules", []))}
    objects = set(entry.get("relates_objects", [])) if key in own_targets else set()
    cross = entry.get("relates_repository_modules", entry.get("covers_repository_modules", []))
    for target in cross:
        if (target.get("repo"), target.get("module_scope")) == key:
            objects.update(target.get("objects", []))
    return objects


def assertion_linked_import_evidence(
    import_value: str,
    test_cases: Iterable[dict[str, Any]],
) -> tuple[set[str], set[str]]:
    """Return cases and imported roots whose values reach an assertion."""
    imported = import_value.lstrip(".")
    imported_leaf = imported.rsplit(".", 1)[-1]
    case_names: set[str] = set()
    roots: set[str] = set()
    for case in test_cases:
        if case.get("disabled"):
            continue
        for raw_identifier in case.get("assertion_linked_identifiers", []):
            identifier = str(raw_identifier).lstrip(".")
            root: str | None = None
            if identifier == imported_leaf or imported.endswith(f".{identifier}"):
                root = identifier.rsplit(".", 1)[-1]
            elif identifier == imported:
                root = imported_leaf
            elif identifier.startswith(f"{imported}."):
                root = identifier[len(imported) + 1:].split(".", 1)[0]
            if root:
                case_names.add(str(case.get("name", "")))
                roots.add(root)
    case_names.discard("")
    return case_names, roots


def normalized_target_path(value: str) -> str:
    parsed = urlsplit(value)
    path = parsed.path or value.split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/"):
        path = f"/{path}"
    return path.rstrip("/") or "/"


def browser_target_http_method(target: dict[str, Any]) -> str:
    """Normalize a browser operation to the HTTP method it can evidence."""
    method = str(target.get("method") or "").upper()
    if target.get("receiver") == "page" and method == "GOTO":
        return "GET"
    return method


def relation_record(
    asset: dict[str, Any], reasons: list[str], related_files: Iterable[str],
    related_symbols: Iterable[str], relation_proves_object_path: bool = False,
    related_case_names: Iterable[str] | None = None,
    assertion_linked_symbols: Iterable[str] | None = None,
    assertion_linked_files: Iterable[str] | None = None,
    behavior_asserted_symbols: Iterable[str] | None = None,
    behavior_asserted_files: Iterable[str] | None = None,
    behavior_case_names: Iterable[str] | None = None,
    contract_asserted_symbols: Iterable[str] | None = None,
    contract_case_names: Iterable[str] | None = None,
    related_browser_target_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    facts = asset.get("test_facts", {})
    test_names = facts.get("test_names", [])
    scenario_names = facts.get("scenario_names", test_names)
    disabled = facts.get("disabled_tests", [])
    related_identifiers = {
        name.rsplit(".", 1)[-1]
        for name in related_symbols
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name.rsplit(".", 1)[-1])
    }
    test_cases = facts.get("test_cases", [])
    case_names = None if related_case_names is None else set(related_case_names)
    selected_test_cases = (
        list(test_names)
        if case_names is None
        else [name for name in scenario_names if name in case_names]
    )
    if case_names is not None:
        has_active_assertion = any(
            case.get("name") in case_names
            and not case.get("disabled")
            and bool(case.get("assertions"))
            for case in test_cases
        )
    elif relation_proves_object_path:
        has_active_assertion = bool(facts.get("has_active_test_with_assertion"))
    elif related_identifiers and test_cases:
        has_active_assertion = any(
            not case.get("disabled")
            and bool(case.get("assertions"))
            and bool(
                related_identifiers
                & set(
                    case.get(
                        "assertion_linked_identifiers",
                        case.get("referenced_identifiers", []),
                    )
                )
            )
            for case in test_cases
        )
    else:
        has_active_assertion = False
    related_files_set = set(related_files)
    related_symbols_set = set(related_symbols)
    linked_symbols = (
        set(related_symbols_set) if assertion_linked_symbols is None
        else set(assertion_linked_symbols)
    )
    linked_files = (
        set(related_files_set) if assertion_linked_files is None
        else set(assertion_linked_files)
    )
    behavior_symbols = set(behavior_asserted_symbols or [])
    behavior_files = set(behavior_asserted_files or [])
    behavior_cases = set(behavior_case_names or [])
    contract_symbols = set(contract_asserted_symbols or [])
    contract_cases = set(contract_case_names or [])
    if not has_active_assertion:
        linked_symbols.clear()
        linked_files.clear()
    browser_evidence = None
    if facts.get("browser_framework"):
        browser_cases = [
            case for case in test_cases
            if case_names is None or case.get("name") in case_names
        ]
        target_ids = None if related_browser_target_ids is None else set(related_browser_target_ids)
        selected_targets = [
            target
            for case in browser_cases
            for target in case.get("browser_targets", [])
            if target_ids is None or target.get("id") in target_ids
        ]
        selected_checks = [
            check
            for case in browser_cases
            if not case.get("disabled")
            for check in case.get("machine_checks", [])
            if target_ids is None or bool(set(check.get("target_ids", [])) & target_ids)
        ]
        browser_evidence = {
            "framework": facts.get("browser_framework"),
            "actions": sorted({
                action for case in browser_cases for action in case.get("browser_actions", [])
            }),
            "observations": sorted({
                observation
                for case in browser_cases
                for observation in case.get("browser_observations", [])
            }),
            "targets": selected_targets,
            "machine_checks": selected_checks,
            "uses_cdp": bool(facts.get("uses_cdp")),
            "has_machine_check": bool(selected_checks),
        }
        if target_ids is not None:
            has_active_assertion = bool(browser_evidence["has_machine_check"])
            if not has_active_assertion:
                linked_symbols.clear()
                linked_files.clear()
    return {
        "repo": asset["repo"], "path": asset["path"], "framework": asset.get("framework"),
        "relation_reasons": sorted(set(reasons)),
        "related_files": sorted(related_files_set),
        "related_symbols": sorted(related_symbols_set),
        "assertion_linked_files": sorted(linked_files),
        "assertion_linked_symbols": sorted(linked_symbols),
        "behavior_asserted_files": sorted(behavior_files),
        "behavior_asserted_symbols": sorted(behavior_symbols),
        "behavior_test_cases": sorted(behavior_cases),
        "contract_asserted_symbols": sorted(contract_symbols),
        "contract_test_cases": sorted(contract_cases),
        "evidence_level": (
            "object-asserted"
            if linked_symbols
            else "behavior-asserted"
            if behavior_symbols or behavior_files
            else "contract-asserted"
            if contract_symbols
            else "object-asserted"
            if linked_files and not related_symbols_set
            else "related-only"
        ),
        "imports": facts.get("imports", []),
        "test_names": test_names,
        "scenario_names": scenario_names,
        "selected_test_cases": selected_test_cases,
        "assertions": facts.get("assertions", []),
        "disabled_tests": disabled,
        "has_active_test_with_assertion": has_active_assertion,
        "browser_evidence": browser_evidence,
    }


def journey_source_layer(path: str, symbols: Iterable[dict[str, Any]] = ()) -> str:
    """Classify only stable frontend layers; keep other files as traversal nodes."""
    symbol_kinds = {str(item.get("kind") or "") for item in symbols}
    lowered = f"/{path.lower()}"
    stem = Path(path).stem.lower()
    if "api-client" in symbol_kinds or any(token in lowered for token in ("/api/", "/client/", "/clients/")):
        return "api-client"
    if "hook" in symbol_kinds or "/hooks/" in lowered or re.match(r"use[A-Z]", Path(path).stem):
        return "hook"
    if "store-or-action" in symbol_kinds or any(token in lowered for token in ("/store/", "/stores/")):
        return "store"
    if "/pages/" in lowered or "/routes/" in lowered or stem.endswith("page"):
        return "page"
    if "component" in symbol_kinds or "/components/" in lowered:
        return "component"
    return "frontend-module"


def repository_roots_for_journeys(
    workspace_root: Path,
    scope: dict[str, Any],
    changed_symbols: list[dict[str, Any]],
    discovered_assets: list[dict[str, Any]],
) -> dict[str, Path]:
    names = {
        str(item.get("repo"))
        for item in [*scope.get("changed_files", []), *changed_symbols, *discovered_assets]
        if item.get("repo")
    }
    roots: dict[str, Path] = {}
    for name in sorted(names):
        root = workspace_root if name == "BIC-meta" else workspace_root / name
        if root.is_dir():
            roots[name] = root.resolve()
    return roots


def package_aliases(repo_roots: dict[str, Path]) -> dict[str, tuple[str, Path, dict[str, Any]]]:
    aliases: dict[str, tuple[str, Path, dict[str, Any]]] = {}
    for repo, root in repo_roots.items():
        package_file, _ = safe_repository_file(root / "package.json", root)
        if package_file is None:
            continue
        try:
            payload = json.loads(package_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = payload.get("name")
        if isinstance(name, str) and name.strip():
            aliases[name.strip()] = (repo, root, payload)
    return aliases


def resolve_package_source(
    import_value: str,
    aliases: dict[str, tuple[str, Path, dict[str, Any]]],
) -> tuple[str, Path] | None:
    matches = [name for name in aliases if import_value == name or import_value.startswith(f"{name}/")]
    if not matches:
        return None
    package_name = max(matches, key=len)
    repo, root, package = aliases[package_name]
    suffix = import_value[len(package_name):].lstrip("/")
    candidates: list[Path] = []
    if suffix:
        candidates.extend([root / suffix, root / "src" / suffix])
    for field in ("types", "module", "main"):
        value = package.get(field)
        if isinstance(value, str):
            candidates.append(root / value)
    candidates.extend([root / "src/index", root / "index"])
    for candidate in candidates:
        for path in (
            candidate,
            *(candidate.with_suffix(extension) for extension in JOURNEY_SOURCE_SUFFIXES),
            *(candidate / f"index{extension}" for extension in JOURNEY_SOURCE_SUFFIXES),
        ):
            safe_path, _ = safe_repository_file(path, root)
            if safe_path is not None:
                return repo, safe_path
    return None


def route_literal_evidence(content: str, method: str, route_path: str) -> str | None:
    method = method.upper()
    # Scan each JavaScript literal form independently. A combined alternation
    # can start at an apostrophe in a comment (or at a closing quote) and then
    # swallow a later template literal. Ordinary JS quotes cannot cross a raw
    # newline; template literals can.
    string_matches = [
        match
        for pattern in (
            re.compile(r"`(?:\\.|[^`\\])*`", re.DOTALL),
            re.compile(r"'(?:\\.|[^'\\\r\n])*'"),
            re.compile(r'"(?:\\.|[^"\\\r\n])*"'),
        )
        for match in pattern.finditer(content)
    ]
    for match in sorted(string_matches, key=lambda item: item.start()):
        candidate = match.group(0)[1:-1]
        if not route_templates_match(candidate, route_path):
            continue
        prefix = content[max(0, match.start() - 120):match.start()]
        suffix = content[match.end():min(len(content), match.end() + 1200)]
        if re.search(rf"\.\s*{re.escape(method.lower())}\s*\(\s*$", prefix, re.IGNORECASE):
            return f"{method} route template {candidate} in API-client call"
        if (
            re.search(r"\bfetch\s*\(\s*$", prefix, re.IGNORECASE)
            and re.search(
                rf"\bmethod\s*:\s*(['\"]){re.escape(method)}\1",
                suffix,
                re.IGNORECASE,
            )
        ):
            return f"fetch route template {candidate} with method {method}"
    return None


def route_template_segments(value: str) -> tuple[str, ...]:
    """Normalize backend and JS-template route variables to wildcard segments."""
    raw = value.strip().strip("'\"`")
    raw = re.sub(r"^\$\{[^}]+\}", "", raw)
    parsed = urlsplit(raw)
    path = parsed.path or raw.split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/"):
        path = f"/{path}"
    segments: list[str] = []
    for segment in path.split("/"):
        if not segment:
            continue
        if re.search(r"\{[^}]+\}|\$\{[^}]+\}", segment):
            segments.append("*")
        else:
            segments.append(segment.lower())
    return tuple(segments)


def route_templates_match(candidate: str, route_path: str) -> bool:
    """Match a full frontend URL template against a backend router path."""
    candidate_segments = route_template_segments(candidate)
    route_segments = route_template_segments(route_path)
    if not candidate_segments or not route_segments or len(candidate_segments) < len(route_segments):
        return False
    candidate_suffix = candidate_segments[-len(route_segments):]
    return all(
        left == right or left == "*" or right == "*"
        for left, right in zip(candidate_suffix, route_segments)
    )


def frontend_route_literal_evidence(content: str, source_path: str, route_path: str) -> str | None:
    quoted_path = rf"(['\"]){re.escape(route_path)}\1"
    if re.search(rf"<Route\b[^>]*\bpath\s*=\s*{quoted_path}", content, re.IGNORECASE):
        return f"JSX Route path literal {route_path} in {source_path}"
    if re.search(r"(?:^|/)(?:routes?|router)(?:/|\.|$)", source_path, re.IGNORECASE) and re.search(
        rf"(?:^|[{{,])\s*path\s*:\s*{quoted_path}", content, re.IGNORECASE | re.MULTILINE,
    ):
        return f"route-config path literal {route_path} in {source_path}"
    return None


def javascript_imported_bindings(content: str) -> dict[str, set[str]]:
    """Return statically imported bindings keyed by module specifier."""
    bindings: dict[str, set[str]] = defaultdict(set)
    import_re = re.compile(
        r"\bimport\s+(?P<clause>(?:type\s+)?(?:"
        r"\{[^}]*\}|\*\s+as\s+[A-Za-z_$][\w$]*|"
        r"[A-Za-z_$][\w$]*(?:\s*,\s*(?:\{[^}]*\}|\*\s+as\s+[A-Za-z_$][\w$]*))?"
        r"))\s+from\s*['\"](?P<path>[^'\"]+)['\"]",
        re.DOTALL,
    )
    for match in import_re.finditer(content):
        clause = re.sub(r"^type\s+", "", match.group("clause").strip())
        path = match.group("path")
        named = re.search(r"\{(?P<items>[^}]*)\}", clause, re.DOTALL)
        if named:
            for item in named.group("items").split(","):
                imported = re.sub(r"^type\s+", "", item.strip()).split(" as ", 1)[0].strip()
                if re.fullmatch(r"[A-Za-z_$][\w$]*", imported):
                    bindings[path].add(imported)
        if re.search(r"\*\s+as\s+[A-Za-z_$][\w$]*", clause):
            bindings[path].add("*")
        prefix = clause.split(",", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", prefix) and named is None:
            bindings[path].add("*")
    return bindings


JOURNEY_FEATURE_STOPWORDS = {
    "session", "sessions", "target", "event", "events", "request", "response",
    "page", "opens", "open", "real", "with", "from", "into", "user", "users",
}


def journey_feature_tokens(value: str) -> set[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value).replace("_", "-")
    return semantic_tokens(expanded) - JOURNEY_FEATURE_STOPWORDS


def build_user_journey_graph(
    workspace_root: Path,
    scope: dict[str, Any],
    changed_symbols: list[dict[str, Any]],
    discovered_assets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build bounded, auditable static paths from changed boundaries to browsers."""
    repo_roots = repository_roots_for_journeys(
        workspace_root, scope, changed_symbols, discovered_assets,
    )
    aliases = package_aliases(repo_roots)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    source_nodes: dict[Path, str] = {}
    source_contents: dict[Path, str] = {}
    source_imports: dict[Path, list[str]] = {}
    source_import_bindings: dict[Path, dict[str, set[str]]] = {}
    scan_counts: dict[str, int] = {}
    warnings: list[str] = []

    def add_node(node: dict[str, Any]) -> str:
        nodes.setdefault(str(node["id"]), node)
        return str(node["id"])

    def add_edge(
        source: str, target: str, relation: str, evidence: str,
        *, machine_check: bool = False,
    ) -> None:
        if len(edges) >= MAX_JOURNEY_EDGES:
            if "journey edge limit reached" not in warnings:
                warnings.append("journey edge limit reached")
            return
        key = (source, target, relation, evidence)
        edges.setdefault(key, {
            "id": f"edge-{len(edges) + 1}",
            "from": source,
            "to": target,
            "relation": relation,
            "evidence": evidence,
            "machine_check": machine_check,
        })

    changed_by_path = {item["path"]: item for item in changed_symbols}
    browser_repos = {
        str(asset.get("repo")) for asset in discovered_assets
        if asset.get("test_facts", {}).get("browser_framework")
    }
    frontend_repos = browser_repos | {
        str(item.get("repo")) for item in changed_symbols
        if Path(str(item.get("path", ""))).suffix.lower() in JOURNEY_SOURCE_SUFFIXES
    }
    for repo in sorted(frontend_repos):
        root = repo_roots.get(repo)
        if root is None:
            continue
        count = 0
        skipped_count = 0
        for current_root, dirs, files in os.walk(root):
            current = Path(current_root)
            dirs[:] = sorted(
                name for name in dirs
                if name not in JOURNEY_SCAN_EXCLUDES and not (current / name).is_symlink()
            )
            for filename in sorted(files):
                path = current / filename
                if path.suffix.lower() not in JOURNEY_SOURCE_SUFFIXES:
                    continue
                local_parts = {part.lower() for part in path.relative_to(root).parts}
                if local_parts & {"test", "tests", "__tests__", "e2e"} or re.search(
                    r"\.(?:test|spec)\.[^.]+$", filename, re.IGNORECASE,
                ):
                    continue
                safe_path, _ = safe_repository_file(path, root)
                if safe_path is None:
                    skipped_count += 1
                    continue
                try:
                    content = safe_path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    skipped_count += 1
                    continue
                count += 1
                output_path = workspace_path(safe_path, workspace_root)
                changed = changed_by_path.get(output_path, {})
                node_id = add_node({
                    "id": f"source:{repo}:{output_path}",
                    "repo": repo,
                    "path": output_path,
                    "layer": journey_source_layer(output_path, changed.get("symbols", [])),
                    "symbols": sorted({
                        str(symbol.get("name")) for symbol in changed.get("symbols", [])
                        if symbol.get("name")
                    }),
                })
                source_nodes[safe_path] = node_id
                source_contents[safe_path] = content
                source_imports[safe_path] = re.findall(
                    r"(?:import\s+(?:type\s+)?(?:[^;]*?\s+from\s+)?|require\s*\()"
                    r"['\"]([^'\"]+)['\"]",
                    content,
                )
                source_import_bindings[safe_path] = javascript_imported_bindings(content)
        scan_counts[repo] = count
        if skipped_count:
            warnings.append(f"{repo} skipped {skipped_count} unsafe or unreadable journey source files")

    anchor_ids: list[str] = []
    shared_anchors: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    route_anchors: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    anchor_feature_tokens: dict[str, set[str]] = {}
    for changed in changed_symbols:
        repo = str(changed.get("repo"))
        path = str(changed.get("path"))
        shared_repo = "shared" in repo.lower() and "type" in repo.lower()
        shared_path = bool(re.search(r"(?:^|/)(?:types?|contracts?)(?:/|$)", path, re.IGNORECASE))
        for symbol in changed.get("symbols", []):
            layer = None
            if symbol.get("kind") == "route" and symbol.get("route_path"):
                layer = "backend-route"
            elif shared_repo or (shared_path and symbol.get("kind") in {"type", "class", "event-or-constant"}):
                layer = "shared-contract"
            if layer is None:
                continue
            node_id = add_node({
                "id": f"changed:{repo}:{path}:{symbol.get('name')}",
                "repo": repo,
                "path": path,
                "layer": layer,
                "symbols": [symbol.get("name")],
                "route_method": symbol.get("route_method"),
                "route_path": symbol.get("route_path"),
            })
            anchor_ids.append(node_id)
            anchor_feature_tokens[node_id] = journey_feature_tokens(
                " ".join(str(value or "") for value in (
                    symbol.get("name"), symbol.get("route_path"), path,
                ))
            )
            target = (node_id, changed, symbol)
            (route_anchors if layer == "backend-route" else shared_anchors).append(target)

    for importer, imports in source_imports.items():
        importer_node = source_nodes[importer]
        importer_repo = str(nodes[importer_node]["repo"])
        importer_path = str(nodes[importer_node]["path"])
        for import_value in imports:
            resolved = resolve_package_source(import_value, aliases)
            if resolved is None:
                local = resolve_imported_source(
                    workspace_root, import_value, importer_path, importer_repo,
                )
                resolved = (importer_repo, local) if local is not None else None
            if resolved is None or resolved[1] not in source_nodes:
                continue
            imported_node = source_nodes[resolved[1]]
            if imported_node == importer_node:
                continue
            imported_symbols = {
                identifier
                for name in nodes[imported_node].get("symbols", [])
                if (identifier := symbol_identifier({"name": name}))
            }
            if nodes[imported_node]["layer"] == "api-client" and imported_symbols:
                bindings = source_import_bindings.get(importer, {}).get(import_value, set())
                if "*" not in bindings and not (bindings & imported_symbols):
                    continue
            add_edge(
                imported_node, importer_node, "reverse-import",
                f"{importer_path} imports {import_value} from {workspace_path(resolved[1], workspace_root)}",
            )

    for anchor_id, _changed, symbol in route_anchors:
        method = str(symbol.get("route_method") or "GET").upper()
        route_path = str(symbol.get("route_path"))
        for source_path, content in source_contents.items():
            source_node = source_nodes[source_path]
            if nodes[source_node]["layer"] != "api-client":
                continue
            evidence = route_literal_evidence(content, method, route_path)
            if evidence:
                add_edge(anchor_id, source_node, "route-client-literal", evidence)

    for anchor_id, changed, symbol in shared_anchors:
        changed_repo = str(changed.get("repo"))
        package_names = {
            name for name, (repo, _root, _package) in aliases.items() if repo == changed_repo
        }
        identifier = symbol_identifier(symbol)
        if not package_names or not identifier:
            continue
        for source_path, imports in source_imports.items():
            matched = sorted({
                value for value in imports
                if any(value == name or value.startswith(f"{name}/") for name in package_names)
                and re.search(rf"\b{re.escape(identifier)}\b", source_contents[source_path])
            })
            if matched:
                add_edge(
                    anchor_id, source_nodes[source_path], "shared-contract-package-import",
                    f"{nodes[source_nodes[source_path]]['path']} imports {identifier} via {', '.join(matched)}",
                )

    scenario_feature_tokens: dict[str, set[str]] = {}
    for asset in discovered_assets:
        facts = asset.get("test_facts", {})
        if not facts.get("browser_framework") or asset.get("asset_kind") not in {"test-file", "browser-scenario"}:
            continue
        for case_index, case in enumerate(facts.get("test_cases", []), start=1):
            case_name = str(case.get("name") or f"scenario-{case_index}")
            case_key = re.sub(r"[^A-Za-z0-9]+", "-", case_name).strip("-").lower() or "scenario"
            case_active = not bool(case.get("disabled"))
            case_checks = list(case.get("machine_checks", [])) if case_active else []
            scenario_id = add_node({
                "id": (
                    f"scenario:{asset.get('repo')}:{asset.get('path')}:"
                    f"{case_index}:{case_key}"
                ),
                "repo": asset.get("repo"),
                "path": asset.get("path"),
                "layer": "browser-scenario",
                "symbols": [case_name],
                "scenario_name": case_name,
                "scenario_index": case_index,
                "framework": facts.get("browser_framework"),
                "disabled": bool(case.get("disabled")),
            })
            scenario_feature_tokens[scenario_id] = journey_feature_tokens(
                " ".join([
                    case_name,
                    *map(str, case.get("assertions", [])),
                    *(
                        str(check.get("expression") or "")
                        for check in case.get("machine_checks", [])
                    ),
                ])
            )
            for import_value in facts.get("imports", []):
                resolved = resolve_package_source(import_value, aliases)
                if resolved is None:
                    local = resolve_imported_source(
                        workspace_root, import_value, str(asset.get("path")), str(asset.get("repo")),
                    )
                    resolved = (str(asset.get("repo")), local) if local is not None else None
                if resolved is None or resolved[1] not in source_nodes:
                    continue
                add_edge(
                    source_nodes[resolved[1]], scenario_id, "browser-scenario-import",
                    f"{asset.get('path')} case {case_name!r} imports {import_value} from {workspace_path(resolved[1], workspace_root)}",
                    machine_check=any(
                        check.get("kind") == "dom-assertion" for check in case_checks
                    ),
                )
            for anchor_id, _changed, symbol in route_anchors:
                method = str(symbol.get("route_method") or "").upper()
                route_path = normalized_target_path(str(symbol.get("route_path") or ""))
                for target in case.get("browser_targets", []):
                    target_method = browser_target_http_method(target)
                    if normalized_target_path(str(target.get("target") or "")) != route_path:
                        continue
                    if method and target_method != method:
                        continue
                    add_edge(
                        anchor_id, scenario_id, "browser-route-target",
                        f"{asset.get('path')} case {case_name!r} targets {target_method} {symbol.get('route_path')}",
                        machine_check=bool(case_active and target.get("machine_check_linked")),
                    )
            for target in case.get("browser_targets", []):
                if target.get("receiver") != "page":
                    continue
                target_path = normalized_target_path(str(target.get("target") or ""))
                for source_path, content in source_contents.items():
                    source_node = source_nodes[source_path]
                    evidence = frontend_route_literal_evidence(
                        content, str(nodes[source_node]["path"]), target_path,
                    )
                    if evidence:
                        add_edge(
                            source_node, scenario_id, "frontend-route-browser-target",
                            f"{evidence}; {asset.get('path')} case {case_name!r} navigates to {target_path}",
                            machine_check=bool(case_active and target.get("machine_check_linked")),
                        )

    adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges.values():
        adjacency[edge["from"]].append(edge)
    paths: list[dict[str, Any]] = []
    partial_paths: list[dict[str, Any]] = []
    for anchor_id in anchor_ids:
        pending: list[tuple[str, list[str], list[str]]] = [(anchor_id, [anchor_id], [])]
        terminal_branches: dict[str, tuple[list[str], list[str], str]] = {}
        while pending and len(paths) < MAX_JOURNEY_PATHS:
            current, node_path, edge_path = pending.pop(0)
            if len(edge_path) >= MAX_JOURNEY_PATH_DEPTH:
                terminal_branches.setdefault(
                    current, (node_path, edge_path, "path-depth-limit"),
                )
                continue
            outgoing = []
            for edge in sorted(adjacency.get(current, []), key=lambda item: item["id"]):
                if edge["to"] in node_path:
                    continue
                if (
                    edge["relation"] == "frontend-route-browser-target"
                    and not (
                        anchor_feature_tokens.get(anchor_id, set())
                        & scenario_feature_tokens.get(edge["to"], set())
                    )
                ):
                    continue
                outgoing.append(edge)
            if not outgoing:
                terminal_branches.setdefault(
                    current,
                    (
                        node_path,
                        edge_path,
                        "no-static-bridge" if current == anchor_id else "terminal-without-browser-scenario",
                    ),
                )
            for edge in outgoing:
                target = edge["to"]
                next_nodes = [*node_path, target]
                next_edges = [*edge_path, edge["id"]]
                if nodes[target]["layer"] == "browser-scenario":
                    paths.append({
                        "id": f"journey-{len(paths) + 1}",
                        "anchor": anchor_id,
                        "scenario": target,
                        "nodes": next_nodes,
                        "edges": next_edges,
                        "machine_check": bool(edge.get("machine_check")),
                        "relation": (
                            "machine-checked-static-path"
                            if edge.get("machine_check")
                            else "possible-static-path"
                        ),
                        "clears_object_gap": False,
                    })
                else:
                    pending.append((target, next_nodes, next_edges))
        completed_node_ids = {
            node_id
            for path in paths if path.get("anchor") == anchor_id
            for node_id in path.get("nodes", [])[1:-1]
        }
        for terminal, (node_path, edge_path, reason) in terminal_branches.items():
            if terminal in completed_node_ids or len(partial_paths) >= MAX_JOURNEY_PATHS:
                continue
            partial_paths.append({
                "id": f"partial-journey-{len(partial_paths) + 1}",
                "anchor": anchor_id,
                "terminal": terminal,
                "nodes": node_path,
                "edges": edge_path,
                "relation": "partial-static-path",
                "reason": reason,
                "clears_object_gap": False,
            })
        if len(paths) >= MAX_JOURNEY_PATHS:
            warnings.append("journey path limit reached")
            break

    return {
        "schema_version": 1,
        "limits": {
            "max_edges": MAX_JOURNEY_EDGES,
            "max_paths": MAX_JOURNEY_PATHS,
            "max_path_depth": MAX_JOURNEY_PATH_DEPTH,
            "max_output_nodes": MAX_JOURNEY_OUTPUT_NODES,
        },
        "scan_counts": scan_counts,
        # Source scanning can inspect more files than the Agent-facing graph
        # should expose. Only nodes participating in an auditable edge/path are
        # serialized; the edge/path limits therefore impose this explicit cap.
        "nodes": sorted(
            (
                node for node_id, node in nodes.items()
                if node_id in {
                    node_id
                    for edge in edges.values()
                    for node_id in (edge["from"], edge["to"])
                } | {
                    node_id
                    for path in [*paths, *partial_paths]
                    for node_id in path.get("nodes", [])
                }
            ),
            key=lambda item: item["id"],
        ),
        "edges": sorted(edges.values(), key=lambda item: int(item["id"].split("-")[-1])),
        "paths": paths,
        "partial_paths": partial_paths,
        "warnings": warnings,
        "semantics": "Static paths are auditable relation evidence only; they never clear an object-level test gap or prove runtime wiring.",
    }


def analyze_test_relations(
    workspace_root: Path, scope: dict[str, Any], changed_symbols: list[dict[str, Any]],
    discovered_assets: list[dict[str, Any]], inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    symbols_by_path = {item["path"]: item for item in changed_symbols}
    module_files: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in scope["file_mappings"]:
        module = item["mapping"].get("module_scope")
        if module:
            module_files[(item["repo"], module)].append(item)

    test_assets = [
        asset for asset in discovered_assets
        if asset.get("asset_kind") in {"test-file", "browser-scenario"}
    ]
    inventory_by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in inventory:
        for path in entry.get("matching_discovered_assets", []):
            inventory_by_asset[path].append(entry)
    source_reference_cache: dict[Path, dict[str, list[str]]] = {}
    reachable_symbol_cache: dict[tuple[Path, Path, tuple[str, ...], tuple[str, ...]], set[str]] = {}
    changed_declaration_cache: dict[
        tuple[Path, Path, tuple[str, ...], tuple[tuple[str, int | None, int | None], ...]],
        set[str],
    ] = {}
    changed_file_by_path = {
        str(item.get("path") or ""): item
        for item in scope.get("changed_files", [])
    }
    source_lines_cache: dict[str, list[str]] = {}

    def enrich_symbol_diff(
        repo: str,
        repo_root: Path,
        path: str,
        symbol: dict[str, Any],
    ) -> dict[str, Any]:
        """Attach changed-line terms for large container attribution."""
        changed_file = changed_file_by_path.get(path, {})
        start = symbol.get("new_start_line") or symbol.get("start_line")
        end = symbol.get("new_end_line") or symbol.get("end_line")
        if not isinstance(start, int) or not isinstance(end, int):
            return symbol
        if path not in source_lines_cache:
            source_path, _ = safe_repository_file(
                workspace_root / path,
                repo_root,
            )
            source_lines_cache[path] = (
                source_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ).splitlines()
                if source_path is not None
                else []
            )
        lines = source_lines_cache[path]
        changed_lines: set[int] = set()
        for hunk in changed_file.get("diff_hunks", []):
            hunk_start = hunk.get("new_start")
            hunk_end = hunk.get("new_end")
            if not isinstance(hunk_start, int) or not isinstance(hunk_end, int):
                continue
            if hunk_end < hunk_start:
                continue
            for line_number in range(max(start, hunk_start), min(end, hunk_end) + 1):
                changed_lines.add(line_number)
        tokens: set[str] = set()
        for line_number in changed_lines:
            if 1 <= line_number <= len(lines):
                tokens.update(identifier_tokens(lines[line_number - 1]))
        span = max(1, end - start + 1)
        return {
            **symbol,
            "diff_tokens": sorted(tokens),
            "requires_diff_overlap": bool(
                span >= 80
                and changed_lines
                and len(changed_lines) <= max(8, span // 5)
            ),
        }

    def reachable_symbols(
        path: Path,
        roots: Iterable[str],
        argv: Iterable[str] = (),
        *,
        repository_root: Path,
    ) -> set[str]:
        key = (path, repository_root, tuple(sorted(set(roots))), tuple(argv))
        if key not in reachable_symbol_cache:
            reachable_symbol_cache[key] = python_reachable_symbols(
                path, key[2], key[3], repository_root=repository_root,
            )
        return reachable_symbol_cache[key]

    def reachable_changed_declarations(
        path: Path,
        symbols: Iterable[dict[str, Any]],
        roots: Iterable[str],
        *,
        repository_root: Path,
    ) -> set[str]:
        symbol_list = list(symbols)
        symbol_key = tuple(sorted(
            (
                str(symbol.get("name") or ""),
                symbol.get("start_line") if isinstance(symbol.get("start_line"), int) else None,
                symbol.get("end_line") if isinstance(symbol.get("end_line"), int) else None,
            )
            for symbol in symbol_list
        ))
        key = (path, repository_root, tuple(sorted(set(roots))), symbol_key)
        if key not in changed_declaration_cache:
            changed_declaration_cache[key] = declaration_reachable_changed_symbols(
                path, symbol_list, key[2], repository_root=repository_root,
            )
        return changed_declaration_cache[key]

    module_results: list[dict[str, Any]] = []
    for key in sorted(module_files):
        repo, module = key
        repo_root = workspace_root if repo == "BIC-meta" else workspace_root / repo
        changed = module_files[key]
        module_symbol_items = [
            {
                **symbols_by_path[item["path"]],
                "symbols": [
                    enrich_symbol_diff(
                        repo,
                        repo_root,
                        item["path"],
                        symbol,
                    )
                    for symbol in symbols_by_path[item["path"]]["symbols"]
                ],
            }
            for item in changed if item["path"] in symbols_by_path
        ]
        flattened_symbols = [
            {**symbol, "path": item["path"], "change_types": item.get("change_types", [])}
            for item in module_symbol_items for symbol in item["symbols"]
        ]
        direct: list[dict[str, Any]] = []
        indirect: list[dict[str, Any]] = []
        possible: list[dict[str, Any]] = []

        for asset in test_assets:
            facts = asset.get("test_facts", {})
            imports = facts.get("imports", [])
            identifiers = set(facts.get("referenced_identifiers", []))
            has_assertion_linkage_facts = any(
                "assertion_linked_identifiers" in case
                for case in facts.get("test_cases", [])
            )
            target_calls = [
                {**target, "case_name": case.get("name")}
                for case in facts.get("test_cases", [])
                for target in case.get("target_calls", [])
            ]
            related_files: set[str] = set()
            related_symbols: set[str] = set()
            reasons: list[str] = []
            direct_assertion_cases: set[str] = set()
            direct_assertion_files: set[str] = set()
            direct_assertion_symbols: set[str] = set()
            direct_behavior_cases: set[str] = set()
            direct_behavior_files: set[str] = set()
            direct_behavior_symbols: set[str] = set()
            direct_contract_cases: set[str] = set()
            direct_contract_symbols: set[str] = set()
            configured_entries = [
                entry for entry in inventory_by_asset[asset["path"]]
                if key in configured_targets(entry)
            ]
            configured = [entry["id"] for entry in configured_entries]
            if asset["repo"] == repo:
                for source in module_symbol_items:
                    matching_imports = [value for value in imports if import_matches(value, asset["path"], source["path"], repo)]
                    if matching_imports:
                        related_files.add(source["path"])
                        reasons.append(f"imports changed file via {', '.join(matching_imports)}")
                        source_linked_cases: set[str] = set()
                        for matching_import in matching_imports:
                            linked_cases, _ = assertion_linked_import_evidence(
                                matching_import, facts.get("test_cases", []),
                            )
                            direct_assertion_cases.update(linked_cases)
                            source_linked_cases.update(linked_cases)
                        source_identifiers = {
                            identifier for symbol in source["symbols"]
                            if (identifier := symbol_identifier(symbol))
                        }
                        if source_identifiers and asset.get("framework") != "pytest":
                            source_linked_cases.update(
                                str(case.get("name"))
                                for case in facts.get("test_cases", [])
                                if not case.get("disabled")
                                and source_identifiers
                                & set(case.get("assertion_linked_identifiers", []))
                            )
                            source_linked_cases.discard("")
                            direct_assertion_cases.update(source_linked_cases)
                        linked_identifiers = {
                            identifier
                            for case in facts.get("test_cases", [])
                            if case.get("name") in source_linked_cases
                            for identifier in (
                                *case.get("assertion_linked_identifiers", []),
                                *case.get("rendered_identifiers", []),
                            )
                        }
                        if source_linked_cases:
                            direct_assertion_files.add(source["path"])
                        source_path, _ = safe_repository_file(
                            workspace_root / source["path"], repo_root,
                        )
                        source_root_identifiers = source_identifiers & identifiers
                        linked_root_identifiers = source_identifiers & linked_identifiers
                        rendered_asserted_cases = {
                            str(case.get("name"))
                            for case in facts.get("test_cases", [])
                            if not case.get("disabled")
                            and substantive_case_assertion(case)
                            and source_identifiers
                            & set(case.get("rendered_identifiers", []))
                            and source_identifiers
                            & set(case.get("assertion_linked_identifiers", []))
                        }
                        rendered_asserted_cases.discard("")
                        reachable_names = (
                            reachable_changed_declarations(
                                source_path, source["symbols"], identifiers,
                                repository_root=repo_root,
                            )
                            if source_path is not None
                            else set()
                        )
                        assertion_reachable_names = (
                            reachable_changed_declarations(
                                source_path, source["symbols"], linked_root_identifiers,
                                repository_root=repo_root,
                            )
                            if source_path is not None
                            else set()
                        )
                        for symbol in source["symbols"]:
                            identifier = symbol_identifier(symbol)
                            owner_identifier = symbol_owner_identifier(symbol)
                            owner_is_referenced = (
                                symbol.get("kind") != "field"
                                or bool(
                                    owner_identifier
                                    and owner_identifier in identifiers
                                )
                            )
                            symbol_is_reachable = bool(
                                owner_is_referenced
                                and identifier
                                and (
                                    identifier in source_root_identifiers
                                    or str(symbol["name"]) in reachable_names
                                )
                            )
                            behavior_cases = behavior_case_names(
                                {**symbol, "path": source["path"]},
                                facts.get("test_cases", []),
                                reachable_from_import=symbol_is_reachable,
                            )
                            if (
                                symbol.get("kind") == "component"
                                and symbol_is_reachable
                                and str(symbol["name"]) in assertion_reachable_names
                            ):
                                behavior_cases.update(rendered_asserted_cases)
                            contract_cases = (
                                behavior_case_names(
                                    {**symbol, "path": source["path"]},
                                    facts.get("test_cases", []),
                                    reachable_from_import=False,
                                    contract_only=True,
                                )
                                if symbol.get("kind") == "route"
                                else set()
                            )
                            if symbol_is_reachable or behavior_cases or contract_cases:
                                related_symbols.add(symbol["name"])
                                if identifier and identifier in source_root_identifiers:
                                    reasons.append(f"references {identifier} from the imported changed file")
                                elif identifier and symbol_is_reachable:
                                    reasons.append(
                                        f"reaches {identifier} from a referenced declaration in the imported changed file"
                                    )
                                if (
                                    identifier
                                    and (
                                        (
                                            identifier in linked_root_identifiers
                                            and (
                                                symbol.get("kind") != "field"
                                                or bool(
                                                    owner_identifier
                                                    and owner_identifier
                                                    in linked_identifiers
                                                )
                                            )
                                        )
                                        or (
                                            str(symbol["name"])
                                            in assertion_reachable_names
                                            and bool(behavior_cases)
                                        )
                                    )
                                    and (
                                        not symbol.get("requires_diff_overlap")
                                        or behavior_cases
                                    )
                                ):
                                    direct_assertion_symbols.add(symbol["name"])
                                if behavior_cases:
                                    direct_behavior_symbols.add(symbol["name"])
                                    direct_behavior_files.add(source["path"])
                                    direct_behavior_cases.update(behavior_cases)
                                if contract_cases:
                                    direct_contract_symbols.add(symbol["name"])
                                    direct_contract_cases.update(contract_cases)

                    matching_targets = [
                        target for target in target_calls
                        if target_matches(workspace_root, target.get("path", ""), source["path"], repo)
                    ]
                    if not matching_targets:
                        continue
                    related_files.add(source["path"])
                    for target in matching_targets:
                        source_kind = target.get("source", "local target")
                        reasons.append(f"reaches changed file through {source_kind}")
                        if target.get("case_name") and target.get("assertion_linked"):
                            direct_assertion_cases.add(target["case_name"])
                            direct_assertion_files.add(source["path"])
                        target_path = local_target_path(
                            workspace_root, target.get("path", ""), repo,
                        )
                        target_symbols = set(target.get("symbols", []))
                        if target_path is not None:
                            target_symbols.update(reachable_symbols(
                                target_path,
                                target_symbols,
                                target.get("argv", []),
                                repository_root=repo_root,
                            ))
                        for symbol in source["symbols"]:
                            identifier = symbol_identifier(symbol)
                            if identifier and identifier in target_symbols:
                                related_symbols.add(symbol["name"])
                                reasons.append(f"statically reaches {identifier} from the resolved local target")
                                if target.get("assertion_linked"):
                                    direct_assertion_symbols.add(symbol["name"])
            if related_files:
                direct.append(relation_record(
                    asset,
                    reasons,
                    related_files,
                    related_symbols,
                    related_case_names=(
                        direct_assertion_cases if has_assertion_linkage_facts else None
                    ),
                    assertion_linked_symbols=(
                        direct_assertion_symbols if has_assertion_linkage_facts else None
                    ),
                    assertion_linked_files=(
                        direct_assertion_files if has_assertion_linkage_facts else None
                    ),
                    behavior_asserted_symbols=direct_behavior_symbols,
                    behavior_asserted_files=direct_behavior_files,
                    behavior_case_names=direct_behavior_cases,
                    contract_asserted_symbols=direct_contract_symbols,
                    contract_case_names=direct_contract_cases,
                ))

            asset_has_indirect_relation = False
            if asset["repo"] == repo:
                one_hop_files: set[str] = set()
                one_hop_symbols: set[str] = set()
                one_hop_reasons: list[str] = []
                one_hop_cases: set[str] = set()
                one_hop_assertion_files: set[str] = set()
                one_hop_assertion_symbols: set[str] = set()
                one_hop_behavior_files: set[str] = set()
                one_hop_behavior_symbols: set[str] = set()
                one_hop_behavior_cases: set[str] = set()
                entrypoints: list[
                    tuple[Path, str, str | None, dict[str, Any] | None, set[str], set[str]]
                ] = []
                for test_import in imports:
                    entry_path = resolve_imported_source(
                        workspace_root, test_import, asset["path"], repo,
                    )
                    if not entry_path:
                        continue
                    linked_cases, linked_roots = assertion_linked_import_evidence(
                        test_import, facts.get("test_cases", []),
                    )
                    entrypoints.append((
                        entry_path, f"imports {test_import}", None, None,
                        linked_cases, linked_roots,
                    ))
                for target in target_calls:
                    entry_path = local_target_path(workspace_root, target.get("path", ""), repo)
                    if entry_path is None:
                        continue
                    entrypoints.append((
                        entry_path,
                        target.get("source", "local target"),
                        target.get("case_name"),
                        target,
                        ({target["case_name"]} if target.get("case_name") and target.get("assertion_linked") else set()),
                        set(target.get("symbols", [])),
                    ))

                seen_entrypoints: set[tuple[Path, str | None]] = set()
                for entry_path, entry_reason, case_name, target, linked_cases, linked_roots in entrypoints:
                    safe_entry_path, _ = safe_repository_file(entry_path, repo_root)
                    if safe_entry_path is None:
                        continue
                    entry_path = safe_entry_path
                    entry_key = (entry_path, case_name)
                    if entry_key in seen_entrypoints:
                        continue
                    seen_entrypoints.add(entry_key)
                    entry_workspace_path = workspace_path(entry_path, workspace_root)
                    if target and (target.get("symbols") or target.get("argv")):
                        references = python_reachable_references(
                            entry_path,
                            target.get("symbols", []),
                            target.get("argv", []),
                            repository_root=repo_root,
                        )
                    elif linked_roots:
                        references = python_reachable_references(
                            entry_path,
                            linked_roots,
                            repository_root=repo_root,
                        )
                    else:
                        if entry_path not in source_reference_cache:
                            source_reference_cache[entry_path] = extract_source_references(entry_path)
                        references = source_reference_cache[entry_path]
                    for source in module_symbol_items:
                        source_path, _ = safe_repository_file(
                            workspace_root / source["path"], repo_root,
                        )
                        if source_path is None:
                            continue
                        matching_source_imports = [
                            value for value in references["imports"]
                            if (
                                resolve_imported_source(workspace_root, value, entry_workspace_path, repo)
                                == source_path
                                or import_matches(value, entry_workspace_path, source["path"], repo)
                            )
                        ]
                        if not matching_source_imports:
                            continue
                        one_hop_files.add(source["path"])
                        one_hop_reasons.append(
                            f"{entry_reason} reaches {entry_workspace_path}, which imports the changed file via "
                            f"{', '.join(matching_source_imports)}"
                        )
                        one_hop_cases.update(linked_cases)
                        entry_identifiers = set(references["identifiers"])
                        linked_test_cases = [
                            case
                            for case in facts.get("test_cases", [])
                            if case.get("name") in linked_cases
                        ]
                        source_roots: set[str] = set()
                        source_related_symbols: set[str] = set()
                        source_behavior_symbols: set[str] = set()
                        source_behavior_cases: set[str] = set()
                        for symbol in source["symbols"]:
                            identifier = symbol_identifier(symbol)
                            owner_identifier = symbol_owner_identifier(symbol)
                            owner_is_referenced = (
                                symbol.get("kind") != "field"
                                or bool(
                                    owner_identifier
                                    and owner_identifier in entry_identifiers
                                )
                            )
                            if (
                                owner_is_referenced
                                and identifier
                                and identifier in entry_identifiers
                            ):
                                one_hop_symbols.add(symbol["name"])
                                source_related_symbols.add(symbol["name"])
                                source_roots.add(identifier)
                        expanded_symbols = reachable_symbols(
                            source_path, source_roots, repository_root=repo_root,
                        )
                        for symbol in source["symbols"]:
                            identifier = symbol_identifier(symbol)
                            if identifier and identifier in expanded_symbols:
                                one_hop_symbols.add(symbol["name"])
                                source_related_symbols.add(symbol["name"])
                            behavior_cases = behavior_case_names(
                                {**symbol, "path": source["path"]},
                                linked_test_cases,
                                reachable_from_import=bool(
                                    identifier
                                    and identifier in expanded_symbols
                                ),
                            )
                            if (
                                not behavior_cases
                                and identifier
                                and identifier in expanded_symbols
                                and linked_test_cases
                                and not any(
                                    source_inspection_case(case)
                                    for case in linked_test_cases
                                )
                            ):
                                behavior_cases = {
                                    str(case.get("name") or "")
                                    for case in linked_test_cases
                                    if substantive_case_assertion(case)
                                }
                                behavior_cases.discard("")
                            if behavior_cases:
                                one_hop_behavior_files.add(source["path"])
                                one_hop_behavior_symbols.add(symbol["name"])
                                one_hop_behavior_cases.update(behavior_cases)
                                source_behavior_symbols.add(symbol["name"])
                                source_behavior_cases.update(behavior_cases)
                        if source_behavior_cases:
                            one_hop_assertion_files.add(source["path"])
                            one_hop_assertion_symbols.update(
                                source_related_symbols & source_behavior_symbols
                            )
                if one_hop_files:
                    asset_has_indirect_relation = True
                    indirect.append(relation_record(
                        asset, one_hop_reasons, one_hop_files, one_hop_symbols,
                        relation_proves_object_path=True,
                        related_case_names=(
                            one_hop_cases if has_assertion_linkage_facts else None
                        ),
                        assertion_linked_symbols=(
                            one_hop_assertion_symbols if has_assertion_linkage_facts else None
                        ),
                        assertion_linked_files=(
                            one_hop_assertion_files if has_assertion_linkage_facts else None
                        ),
                        behavior_asserted_symbols=one_hop_behavior_symbols,
                        behavior_asserted_files=one_hop_behavior_files,
                        behavior_case_names=one_hop_behavior_cases,
                    ))

            if configured and not related_files and not asset_has_indirect_relation:
                asset_has_indirect_relation = True
                indirect.append(relation_record(
                    asset, [f"configured module relation {entry_id}" for entry_id in configured],
                    [item["path"] for item in changed],
                    set().union(*(configured_objects(entry, key) for entry in configured_entries)),
                    relation_proves_object_path=True,
                ))

            browser_route_files: set[str] = set()
            browser_route_symbols: set[str] = set()
            browser_route_reasons: list[str] = []
            browser_route_cases: set[str] = set()
            browser_route_target_ids: set[str] = set()
            if not related_files and not asset_has_indirect_relation and facts.get("browser_framework"):
                for source in module_symbol_items:
                    for symbol in source.get("symbols", []):
                        route_path = symbol.get("route_path")
                        route_method = str(symbol.get("route_method") or "").upper()
                        if symbol.get("kind") != "route" or not route_path:
                            continue
                        for target in facts.get("browser_targets", []):
                            if normalized_target_path(str(target.get("target") or "")) != normalized_target_path(str(route_path)):
                                continue
                            target_method = browser_target_http_method(target)
                            if route_method and target_method != route_method:
                                continue
                            browser_route_files.add(source["path"])
                            browser_route_symbols.add(symbol["name"])
                            if target.get("case_name"):
                                browser_route_cases.add(str(target["case_name"]))
                            if target.get("id"):
                                browser_route_target_ids.add(str(target["id"]))
                            browser_route_reasons.append(
                                f"browser scenario targets {target_method} {route_path}; route identity matches but runtime wiring is unexecuted"
                            )
            if browser_route_files:
                possible.append(relation_record(
                    asset,
                    browser_route_reasons,
                    browser_route_files,
                    browser_route_symbols,
                    related_case_names=browser_route_cases,
                    related_browser_target_ids=browser_route_target_ids,
                ))

            if related_files or asset_has_indirect_relation or browser_route_files or asset["repo"] != repo:
                continue

            file_affinity = set().union(*(basename_tokens(item["path"], repo) for item in changed)) & basename_tokens(asset["path"], repo)
            module_affinity = semantic_tokens(module, repo) & semantic_tokens(asset["path"], repo)
            scenario_text = " ".join(facts.get("scenario_names", facts.get("test_names", [])))
            scenario_affinity = semantic_tokens(module, repo) & semantic_tokens(scenario_text, repo)
            possible_reasons = []
            if file_affinity:
                possible_reasons.append(f"shares filename terms: {', '.join(sorted(file_affinity))}")
            if module_affinity:
                possible_reasons.append(f"test path mentions module terms: {', '.join(sorted(module_affinity))}")
            if scenario_affinity:
                possible_reasons.append(f"test scenario mentions module terms: {', '.join(sorted(scenario_affinity))}")
            if possible_reasons:
                possible.append(relation_record(
                    asset,
                    possible_reasons,
                    [
                        item["path"] for item in changed
                        if basename_tokens(item["path"], repo) & basename_tokens(asset["path"], repo)
                    ],
                    [],
                ))

        guidance_groups: dict[str, dict[str, Any]] = {}
        diagnostic_test_guidance: list[dict[str, Any]] = []
        no_gaps: list[str] = []
        non_testable_changes: dict[str, str] = {}
        asserted_symbol_names = {
            str(name)
            for relation in [*direct, *indirect]
            for name in [
                *(
                    relation.get("assertion_linked_symbols", [])
                    if relation.get("has_active_test_with_assertion")
                    else []
                ),
                *relation.get("behavior_asserted_symbols", []),
            ]
        }
        for symbol in flattened_symbols:
            applicable, exclusion_reason = guidance_applicability(symbol["path"], module)
            if not applicable:
                non_testable_changes.setdefault(symbol["path"], exclusion_reason or "not applicable")
                continue
            name = symbol["name"]
            direct_for_object = [
                relation for relation in direct
                if name in relation["related_symbols"]
                or (
                    symbol["kind"] in {"file", "changed-file", "module-scope"}
                    and symbol["path"] in relation["related_files"]
                )
            ]
            indirect_for_object = [
                relation for relation in indirect
                if name in relation["related_symbols"]
            ]
            active_direct = any(
                (
                    relation["has_active_test_with_assertion"]
                    and (
                    name in relation["assertion_linked_symbols"]
                    or (
                        symbol["kind"] in {"file", "changed-file", "module-scope"}
                        and symbol["path"] in relation["assertion_linked_files"]
                    )
                    )
                )
                or name in relation.get("behavior_asserted_symbols", [])
                for relation in direct_for_object
            )
            active_indirect = any(
                (
                    relation["has_active_test_with_assertion"]
                    and name in relation["assertion_linked_symbols"]
                )
                or name in relation.get("behavior_asserted_symbols", [])
                for relation in indirect_for_object
            )
            if "added" in symbol.get("change_types", []):
                observation = "declared in an added file"
            elif symbol["kind"] == "module-scope":
                observation = "changed outside a declaration"
            else:
                observation = "selected by a changed diff hunk"
            subject = f"{symbol['kind']} {name} in {symbol['path']} ({observation})"
            if active_direct or active_indirect:
                no_gaps.append(f"No obvious static gap for {subject}: an active object-related test contains an assertion.")
                continue
            if asserted_store_action_covers_container(
                symbol,
                flattened_symbols,
                asserted_symbol_names,
            ):
                no_gaps.append(
                    f"No standalone static gap for {subject}: the changed store "
                    "action inside this broad container has object-level evidence."
                )
                continue
            if symbol["kind"] in FILE_ONLY_GUIDANCE_KINDS or name == "__all__":
                diagnostic_test_guidance.append({
                    "path": symbol["path"],
                    "symbol": name,
                    "reason": (
                        "file-level attribution is diagnostic-only"
                        if symbol["kind"] in FILE_ONLY_GUIDANCE_KINDS
                        else "export-list changes do not receive standalone test guidance"
                    ),
                })
                continue
            weak_relations = [
                relation
                for relation in [*direct_for_object, *indirect_for_object]
                if not (
                    (
                        relation.get("has_active_test_with_assertion")
                        and (
                        name in relation.get("assertion_linked_symbols", [])
                        or (
                            symbol["kind"] in {
                                "file", "changed-file", "module-scope"
                            }
                            and symbol["path"]
                            in relation.get("assertion_linked_files", [])
                        )
                        )
                    )
                    or name in relation.get("behavior_asserted_symbols", [])
                )
            ]
            group = guidance_groups.setdefault(
                symbol["path"],
                {
                    "action": "add",
                    "path": symbol["path"],
                    "symbols": [],
                    "weak_relations": [],
                    "missing_relation_symbols": [],
                },
            )
            group["symbols"].append(symbol)
            group["weak_relations"].extend(weak_relations)
            if weak_relations:
                group["action"] = "strengthen"
            else:
                group["missing_relation_symbols"].append(name)

        test_guidance = [
            grouped_guidance(
                group["action"],
                repo,
                module,
                group["path"],
                group["symbols"],
                group["weak_relations"],
                group["missing_relation_symbols"],
                [
                    str(asset.get("path"))
                    for asset in test_assets
                    if asset.get("path")
                ],
            )
            for _key, group in sorted(guidance_groups.items())
        ]
        add_tests = [
            guidance_summary(item)
            for item in test_guidance
            if item["action"] == "add"
        ]
        strengthen_tests = [
            guidance_summary(item)
            for item in test_guidance
            if item["action"] == "strengthen"
        ]

        module_results.append({
            **module_ref(key),
            "changed_files": [
                {"path": item["path"], "change_types": next(
                    (changed_file.get("change_types", []) for changed_file in scope["changed_files"] if changed_file["path"] == item["path"]),
                    [],
                )}
                for item in changed
            ],
            "changed_symbols": flattened_symbols,
            "symbol_scope_note": "Supported source files use ast-outline Diff-hunk declarations; legitimate module-level changes remain module-scope objects.",
            "directly_related_tests": direct,
            "indirectly_related_tests": indirect,
            "possibly_related_tests": possible,
            "add_tests": add_tests,
            "strengthen_tests": strengthen_tests,
            "test_guidance": test_guidance,
            "diagnostic_test_guidance": diagnostic_test_guidance,
            "no_obvious_test_gaps": no_gaps,
            "non_testable_changes": [
                {"path": path, "reason": reason}
                for path, reason in sorted(non_testable_changes.items())
            ],
        })

    journey_graph = build_user_journey_graph(
        workspace_root, scope, changed_symbols, discovered_assets,
    )
    browser_guidance = browser_journey_guidance(changed_symbols, journey_graph)
    all_guidance = [
        item
        for module in module_results
        for item in module.get("test_guidance", [])
    ] + browser_guidance
    return {
        "modules": module_results,
        "public_summary": build_public_test_summary(module_results),
        "user_journey_graph": journey_graph,
        "test_guidance": all_guidance,
        "browser_test_guidance": browser_guidance,
        "analysis_note": "Static correspondence only. Tests were not executed, and assertions do not prove passing behavior or complete coverage.",
    }
