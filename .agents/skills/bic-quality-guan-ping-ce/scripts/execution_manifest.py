#!/usr/bin/env python3
"""Build a non-executing hand-off contract for a separately authorized test phase."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def iter_relations(
    correspondence: dict[str, Any],
) -> Iterable[tuple[str, dict[str, Any], dict[str, Any]]]:
    relation_fields = (
        ("direct", "directly_related_tests"),
        ("indirect", "indirectly_related_tests"),
        ("possible", "possibly_related_tests"),
    )
    for module in correspondence.get("modules", []):
        module_ref = {"repo": module.get("repo"), "module_scope": module.get("module_scope")}
        for relation, field in relation_fields:
            for record in module.get(field, []):
                yield relation, record, module_ref


def command_for(record: dict[str, Any], inventory: dict[str, Any]) -> tuple[str | None, str]:
    path = str(record.get("path", ""))
    repo = str(record.get("repo", ""))
    framework = record.get("framework")
    local_path = path[len(repo) + 1:] if repo and path.startswith(f"{repo}/") else path
    if framework == "pytest":
        return f"uv run pytest {local_path}", "derived-file-command"
    if framework == "playwright":
        return f"pnpm exec playwright test {local_path}", "derived-file-command"
    for entry in inventory.get("tests", []):
        if entry.get("repo") == repo and path in entry.get("matching_discovered_assets", []):
            return entry.get("command_hint"), "configured-test-inventory"
    return None, "command-resolution-required"


def command_argv_for(record: dict[str, Any]) -> list[str] | None:
    path = str(record.get("path", ""))
    repo = str(record.get("repo", ""))
    local_path = path[len(repo) + 1:] if repo and path.startswith(f"{repo}/") else path
    if record.get("framework") == "pytest":
        return ["uv", "run", "pytest", local_path]
    if record.get("framework") == "playwright":
        return ["pnpm", "exec", "playwright", "test", local_path]
    return None


def prerequisites_for(framework: str | None) -> list[str]:
    if framework in {"playwright", "cdp"}:
        return [
            "healthy live BIC bench",
            "portal, agent service, lab service, Keycloak and configured infrastructure",
            "test-owned data state or separately authorized reset procedure",
        ]
    return []


def manifest_journey_paths(
    graph: dict[str, Any], field: str,
) -> list[dict[str, Any]]:
    nodes = {item.get("id"): item for item in graph.get("nodes", [])}
    edges = {item.get("id"): item for item in graph.get("edges", [])}
    records: list[dict[str, Any]] = []
    for path in graph.get(field, []):
        node_ids = list(path.get("nodes", []))
        edge_ids = list(path.get("edges", []))
        records.append({
            **path,
            "node_path": [nodes[node_id] for node_id in node_ids if node_id in nodes],
            "edge_path": [edges[edge_id] for edge_id in edge_ids if edge_id in edges],
            "execution_status": "not-run",
            "interpretation": (
                "Auditable static journey evidence only; this path does not clear an object-level test gap."
            ),
        })
    return records


def build_execution_manifest(
    context: dict[str, Any],
    correspondence: dict[str, Any],
    inventory: dict[str, Any],
) -> dict[str, Any]:
    """Describe what Phase 2 could run without running or mutating anything."""
    repositories = [
        {
            "repo": item.get("name"),
            "head": item.get("head"),
            "base_ref": item.get("base_ref"),
            "merge_base": item.get("merge_base"),
            "change_fingerprint": item.get("change_fingerprint"),
        }
        for item in context.get("repositories", [])
        if item.get("change_count")
    ]
    workspace_fingerprint = hashlib.sha256(
        json.dumps(repositories, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    journey_graph = correspondence.get("user_journey_graph", {})

    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    relation_rank = {"possible": 0, "indirect": 1, "direct": 2}
    journey_evidence: list[dict[str, Any]] = []
    for relation, record, module_ref in iter_relations(correspondence):
        key = (str(record.get("repo", "")), str(record.get("path", "")))
        command, source = command_for(record, inventory)
        command_argv = command_argv_for(record)
        browser = record.get("browser_evidence")
        candidate = {
            "repo": key[0],
            "path": key[1],
            "framework": record.get("framework"),
            "relation": relation,
            "required": relation in {"direct", "indirect"},
            "relation_reasons": record.get("relation_reasons", []),
            "related_files": record.get("related_files", []),
            "related_symbols": record.get("related_symbols", []),
            "assertion_linked_files": record.get("assertion_linked_files", []),
            "assertion_linked_symbols": record.get("assertion_linked_symbols", []),
            "selected_test_cases": record.get(
                "selected_test_cases", record.get("test_names", []),
            ),
            "command_hint": command,
            "command_argv": command_argv,
            "command_source": source,
            "command_ready": command_argv is not None,
            "working_directory": key[0],
            "environment_prerequisites": prerequisites_for(record.get("framework")),
            "state_mutation_requirement": "unknown-separate-authorization-required",
            "static_assertion_evidence": bool(record.get("has_active_test_with_assertion")),
            "browser_evidence": browser,
            "covers_changed_modules": [module_ref],
            "execution_status": "not-run",
        }
        previous = candidates.get(key)
        merge_fields = (
            "relation_reasons", "related_files", "related_symbols",
            "assertion_linked_files", "assertion_linked_symbols",
            "selected_test_cases", "covers_changed_modules",
        )
        if previous is None or relation_rank[relation] > relation_rank[previous["relation"]]:
            if previous is not None:
                for field in merge_fields:
                    candidate[field] = [
                        *previous[field],
                        *(item for item in candidate[field] if item not in previous[field]),
                    ]
            candidates[key] = candidate
        else:
            for field in merge_fields:
                previous[field].extend(
                    item for item in candidate[field] if item not in previous[field]
                )
        if browser:
            journey_evidence.append({
                "test_repo": key[0],
                "test_path": key[1],
                "relation": relation,
                "changed_module": module_ref,
                "scenarios": record.get(
                    "selected_test_cases", record.get("test_names", []),
                ),
                "browser_framework": browser.get("framework"),
                "browser_actions": browser.get("actions", []),
                "browser_observations": browser.get("observations", []),
                "browser_targets": browser.get("targets", []),
                "has_machine_check": bool(browser.get("has_machine_check")),
            })

    ordered = sorted(candidates.values(), key=lambda item: (not item["required"], item["repo"], item["path"]))
    return {
        "schema_version": 1,
        "phase": "phase-2-test-execution-handoff",
        "execution_status": "not-run",
        "analysis_complete": True,
        "workspace_change_fingerprint": workspace_fingerprint,
        "repositories": repositories,
        "required_candidates": [item for item in ordered if item["required"]],
        "optional_candidates": [item for item in ordered if not item["required"]],
        "affected_user_journey_evidence": sorted(
            journey_evidence,
            key=lambda item: (
                item["changed_module"].get("repo") or "",
                item["changed_module"].get("module_scope") or "",
                item["test_path"],
            ),
        ),
        "user_journey_graph_schema_version": journey_graph.get("schema_version"),
        "completed_user_journey_paths": manifest_journey_paths(journey_graph, "paths"),
        "partial_user_journey_paths": manifest_journey_paths(journey_graph, "partial_paths"),
        "coverage_layers": {
            "unit_or_service_tests": sorted({
                str(item["framework"])
                for item in ordered
                if item.get("framework") not in {"playwright", "cdp", None}
            }),
            "browser_tests": sorted({
                str(item["framework"])
                for item in ordered
                if item.get("framework") in {"playwright", "cdp"}
            }),
            "interpretation": "Browser evidence complements backend and unit evidence; neither layer alone establishes the end-to-end user journey.",
        },
        "pre_execution_gates": [
            "obtain explicit authorization to execute tests and start required services",
            "recompute and match workspace_change_fingerprint immediately before execution",
            "resolve every required command_hint and environment prerequisite",
            "obtain separate authorization before reset, seed, migration, cleanup, or other state mutation",
        ],
        "boundary_note": "This manifest is static guidance only. Phase 1 did not start services, execute tests, reset data, or mutate the workspace.",
    }
