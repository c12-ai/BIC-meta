#!/usr/bin/env python3
"""Build a behavior-scoped handoff contract for authorized test execution."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from test_relations import strict_relation_evidence


RELATION_FIELDS = (
    ("direct", "directly_related_tests"),
    ("indirect", "indirectly_related_tests"),
    ("possible", "possibly_related_tests"),
)
TIER_RANK = {"not-runnable": 0, "recommended": 1, "must-run": 2}
RELATION_RANK = {"possible": 0, "indirect": 1, "direct": 2, "changed-test": 3}


def iter_relations(
    correspondence: dict[str, Any],
) -> Iterable[tuple[str, dict[str, Any], dict[str, Any]]]:
    for module in correspondence.get("modules", []):
        module_ref = {
            "repo": module.get("repo"),
            "module_scope": module.get("module_scope"),
        }
        for relation, field in RELATION_FIELDS:
            for record in module.get(field, []):
                yield relation, record, module_ref


def repository_records(context: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "repo": item.get("name"),
            "relative_path": item.get("relative_path", item.get("name")),
            "head": item.get("head"),
            "base_ref": item.get("base_ref"),
            "merge_base": item.get("merge_base"),
            "change_fingerprint": item.get("change_fingerprint"),
        }
        for item in context.get("repositories", [])
        if item.get("change_count")
    ]


def workspace_fingerprint(repositories: list[dict[str, Any]]) -> str:
    """Hash the repository-local fingerprints consumed by the assessment."""
    normalized = [
        {
            "repo": item.get("repo", item.get("name")),
            "relative_path": item.get("relative_path"),
            "head": item.get("head"),
            "base_ref": item.get("base_ref"),
            "merge_base": item.get("merge_base"),
            "change_fingerprint": item.get("change_fingerprint"),
        }
        for item in repositories
    ]
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def repo_local_path(path: str, repo: str) -> str:
    return path[len(repo) + 1:] if repo and path.startswith(f"{repo}/") else path


def exact_name_pattern(case_name: str) -> str:
    return f"^{re.escape(case_name)}$"


def inventory_assets(inventory: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(item.get("repo") or ""), str(item.get("path") or "")): item
        for item in inventory.get("discovered_assets", [])
        if item.get("path")
    }


def case_facts(
    asset: dict[str, Any] | None,
    case_name: str,
) -> dict[str, Any] | None:
    if not asset:
        return None
    return next(
        (
            case
            for case in asset.get("test_facts", {}).get("test_cases", [])
            if str(case.get("name") or "") == case_name
        ),
        None,
    )


def configured_cdp_argv(
    repo: str,
    inventory: dict[str, Any],
) -> tuple[list[str] | None, str]:
    """Resolve CDP only from a real repository-owned package script."""
    for asset in inventory.get("discovered_assets", []):
        if asset.get("repo") != repo or asset.get("asset_kind") != "test-command":
            continue
        haystack = " ".join(
            str(asset.get(field) or "")
            for field in ("id", "reason", "command_hint")
        ).lower()
        if "cdp" not in haystack:
            continue
        hint = str(asset.get("command_hint") or "")
        try:
            argv = shlex.split(hint)
        except ValueError:
            continue
        if argv[:2] == ["pnpm", "run"] and len(argv) == 3:
            return [
                "npm", "run", "--silent", argv[2],
            ], "configured-package-script"
    return None, "command-resolution-required"


def command_for_case(
    record: dict[str, Any],
    case_name: str,
    inventory: dict[str, Any],
) -> tuple[list[str] | None, str, str | None]:
    path = str(record.get("path") or "")
    repo = str(record.get("repo") or "")
    local_path = repo_local_path(path, repo)
    framework = str(record.get("framework") or "")
    asset = inventory_assets(inventory).get((repo, path))
    facts = case_facts(asset, case_name) or {}
    selector = str(facts.get("selector") or case_name)
    if framework == "pytest":
        selector = str(facts.get("selector") or case_name)
        return [
            "uv", "run", "--no-sync", "pytest",
            f"{local_path}::{selector}", "-q",
        ], "derived-case-command", selector
    if framework == "vitest":
        return [
            "node", "node_modules/vitest/vitest.mjs", "run", local_path,
            "-t", exact_name_pattern(selector),
        ], "derived-case-command", selector
    if framework == "playwright":
        start_line = facts.get("start_line")
        if not isinstance(start_line, int) or start_line < 1:
            return None, "case-location-required", selector
        location = f"{local_path}:{start_line}"
        return [
            "node", "node_modules/@playwright/test/cli.js", "test",
            location, "--workers=1",
        ], "derived-case-command", location
    if framework == "cdp":
        argv, source = configured_cdp_argv(repo, inventory)
        return argv, source, case_name
    return None, "unsupported-or-unconfigured-framework", None


def execution_layer(framework: str | None) -> str:
    return {
        "pytest": "backend",
        "vitest": "frontend",
        "playwright": "browser",
        "cdp": "browser-diagnostic",
    }.get(str(framework or ""), "unsupported")


def prerequisites_for(framework: str | None) -> list[str]:
    if framework == "playwright":
        return [
            "configured browser runtime",
            "application environment required by the selected Playwright config "
            "is already available; phase 2 does not start services",
        ]
    if framework == "cdp":
        return [
            "configured browser and CDP endpoint",
            "repository-owned CDP command",
        ]
    return []


def active_case(
    record: dict[str, Any],
    asset: dict[str, Any] | None,
    case_name: str,
) -> tuple[bool, str | None]:
    facts = case_facts(asset, case_name)
    if facts is not None:
        if facts.get("disabled"):
            return False, "selected test case is skipped, todo, fixme, or disabled"
        if record.get("framework") in {"playwright", "cdp"}:
            if not facts.get("has_machine_check"):
                return False, "selected browser case has no target-linked machine check"
        elif not facts.get("assertions"):
            return False, "selected test case has no active assertion"
        return True, None
    if case_name in set(record.get("disabled_tests", [])):
        return False, "selected test case is skipped, todo, fixme, or disabled"
    if not record.get("has_active_test_with_assertion"):
        return False, "selected test case has no active assertion"
    browser = record.get("browser_evidence") or {}
    if record.get("framework") in {"playwright", "cdp"} and not browser.get(
        "has_machine_check"
    ):
        return False, "selected browser case has no target-linked machine check"
    return True, None


def case_intersects_changed_hunk(
    case: dict[str, Any],
    changed_file: dict[str, Any],
) -> bool:
    """Return whether a concrete test declaration intersects the current diff."""
    case_start = case.get("start_line")
    case_end = case.get("end_line")
    if not isinstance(case_start, int) or not isinstance(case_end, int):
        return False
    for hunk in changed_file.get("diff_hunks", []):
        hunk_start = hunk.get("new_start")
        hunk_end = hunk.get("new_end")
        if not isinstance(hunk_start, int):
            continue
        if not isinstance(hunk_end, int) or hunk_end < hunk_start:
            hunk_end = hunk_start
        if case_start <= hunk_end and hunk_start <= case_end:
            return True
    return False


def completed_browser_cases(
    graph: dict[str, Any],
) -> set[tuple[str, str, str]]:
    nodes = {
        str(item.get("id") or ""): item
        for item in graph.get("nodes", [])
    }
    completed: set[tuple[str, str, str]] = set()
    for path in graph.get("paths", []):
        if not path.get("machine_check"):
            continue
        scenario = nodes.get(str(path.get("scenario") or ""))
        if not scenario:
            continue
        completed.add((
            str(scenario.get("repo") or ""),
            str(scenario.get("path") or ""),
            str(scenario.get("scenario_name") or ""),
        ))
    return completed


def candidate_record(
    relation: str,
    record: dict[str, Any],
    module_ref: dict[str, Any],
    case_name: str,
    behavior: str,
    tier: str,
    selection_reason: str,
    inventory: dict[str, Any],
) -> dict[str, Any]:
    command_argv, command_source, test_selector = command_for_case(
        record, case_name, inventory,
    )
    framework = str(record.get("framework") or "")
    effective_tier = tier if command_argv is not None else "not-runnable"
    return {
        "repo": str(record.get("repo") or ""),
        "path": str(record.get("path") or ""),
        "framework": framework,
        "execution_layer": execution_layer(framework),
        "relation": relation,
        "selection_tier": effective_tier,
        "intended_tier": tier,
        "required": tier == "must-run",
        "changed_behaviors": [behavior],
        "test_case": case_name,
        "test_selector": test_selector,
        "selected_test_cases": [case_name],
        "selection_reasons": [selection_reason],
        "relation_reasons": list(record.get("relation_reasons", [])),
        "related_files": list(record.get("related_files", [])),
        "related_symbols": list(record.get("related_symbols", [])),
        "assertion_linked_files": list(record.get("assertion_linked_files", [])),
        "assertion_linked_symbols": list(record.get("assertion_linked_symbols", [])),
        "command_hint": shlex.join(command_argv) if command_argv else None,
        "command_argv": command_argv,
        "command_source": command_source,
        "command_ready": command_argv is not None,
        "working_directory": str(record.get("repo") or ""),
        "environment_prerequisites": prerequisites_for(framework),
        "state_mutation_requirement": (
            "browser/application state may change; no reset is authorized"
            if framework in {"playwright", "cdp"}
            else "test-process artifacts only"
        ),
        "static_assertion_evidence": bool(
            record.get("has_active_test_with_assertion")
        ),
        "browser_evidence": record.get("browser_evidence"),
        "covers_changed_modules": [module_ref],
        "not_runnable_reason": (
            "no safe repository-native command could be resolved"
            if command_argv is None else None
        ),
        "execution_status": "not-run",
    }


def merge_unique(target: list[Any], values: Iterable[Any]) -> None:
    target.extend(value for value in values if value not in target)


def merge_candidate(
    candidates: dict[tuple[str, str, str, str], dict[str, Any]],
    candidate: dict[str, Any],
) -> None:
    key = (
        candidate["repo"],
        candidate["framework"],
        candidate["path"],
        candidate["test_case"],
    )
    previous = candidates.get(key)
    if previous is None:
        candidates[key] = candidate
        return
    for field in (
        "changed_behaviors",
        "selection_reasons",
        "relation_reasons",
        "related_files",
        "related_symbols",
        "assertion_linked_files",
        "assertion_linked_symbols",
        "covers_changed_modules",
    ):
        merge_unique(previous[field], candidate[field])
    if TIER_RANK[candidate["selection_tier"]] > TIER_RANK[previous["selection_tier"]]:
        previous["selection_tier"] = candidate["selection_tier"]
        previous["intended_tier"] = candidate["intended_tier"]
        previous["required"] = candidate["required"]
    if (
        RELATION_RANK.get(candidate["relation"], 0)
        > RELATION_RANK.get(previous["relation"], 0)
    ):
        previous["relation"] = candidate["relation"]
    previous["static_assertion_evidence"] = bool(
        previous["static_assertion_evidence"]
        or candidate["static_assertion_evidence"]
    )


def manifest_journey_paths(
    graph: dict[str, Any],
    field: str,
) -> list[dict[str, Any]]:
    nodes = {item.get("id"): item for item in graph.get("nodes", [])}
    edges = {item.get("id"): item for item in graph.get("edges", [])}
    records: list[dict[str, Any]] = []
    for path in graph.get(field, []):
        node_ids = list(path.get("nodes", []))
        edge_ids = list(path.get("edges", []))
        records.append({
            **path,
            "node_path": [
                nodes[node_id] for node_id in node_ids if node_id in nodes
            ],
            "edge_path": [
                edges[edge_id] for edge_id in edge_ids if edge_id in edges
            ],
            "execution_status": "not-run",
            "interpretation": (
                "Auditable static journey evidence only; runtime execution is "
                "reported separately."
            ),
        })
    return records


def planned_test_gaps(
    correspondence: dict[str, Any],
) -> list[dict[str, Any]]:
    gaps: dict[tuple[str, str, str], dict[str, Any]] = {}
    guidance_items = [
        item
        for module in correspondence.get("modules", [])
        for item in module.get("test_guidance", [])
        if item.get("action") == "add"
    ]
    guidance_items.extend(
        item
        for item in correspondence.get("browser_test_guidance", [])
        if item.get("action") == "add"
    )
    for item in guidance_items:
        repo = str(item.get("test_repo") or item.get("repo") or "")
        path = str(item.get("suggested_test_target") or "")
        behavior = str(item.get("target_behavior") or "unresolved behavior")
        key = (repo, path, behavior)
        gaps[key] = {
            "repo": repo,
            "path": path,
            "framework": item.get("recommended_framework"),
            "execution_layer": execution_layer(item.get("recommended_framework")),
            "selection_tier": "not-runnable",
            "intended_tier": "planned-test",
            "required": False,
            "changed_behaviors": [behavior],
            "test_case": None,
            "selected_test_cases": [],
            "selection_reasons": ["phase 1 recommends adding this behavior test"],
            "command_hint": None,
            "command_argv": None,
            "command_source": "test-not-implemented",
            "command_ready": False,
            "working_directory": repo,
            "environment_prerequisites": [],
            "state_mutation_requirement": "none; test is not implemented",
            "static_assertion_evidence": False,
            "not_runnable_reason": "suggested test does not exist yet",
            "execution_status": "not-run",
        }
    return sorted(
        gaps.values(),
        key=lambda item: (
            item["repo"], item["path"], item["changed_behaviors"][0],
        ),
    )


def build_execution_manifest(
    context: dict[str, Any],
    correspondence: dict[str, Any],
    inventory: dict[str, Any],
) -> dict[str, Any]:
    """Describe the precise tests Phase 2 may execute without running them."""
    repositories = repository_records(context)
    graph = correspondence.get("user_journey_graph", {})
    completed_browser = completed_browser_cases(graph)
    assets = inventory_assets(inventory)
    candidates: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    exclusions: Counter[str] = Counter()
    journey_evidence: list[dict[str, Any]] = []

    for relation, record, module_ref in iter_relations(correspondence):
        repo = str(record.get("repo") or "")
        path = str(record.get("path") or "")
        asset = assets.get((repo, path))
        strict = strict_relation_evidence(record, relation)
        selected: list[tuple[str, str, str, str]] = []
        if strict is not None:
            public = strict["record"]
            selected.extend(
                (
                    case_name,
                    str(public["target_behavior"]),
                    "must-run",
                    str(strict["selection_reason"]),
                )
                for case_name in public["relevant_test_cases"]
            )
        elif relation == "possible" and record.get("browser_evidence"):
            browser = record.get("browser_evidence") or {}
            exact_browser_object_link = bool(
                record.get("related_symbols")
                and browser.get("targets")
                and any(
                    target.get("machine_check_linked")
                    for target in browser.get("targets", [])
                )
            )
            if browser.get("has_machine_check") and exact_browser_object_link:
                for case_name in record.get("selected_test_cases", []):
                    completed = (repo, path, str(case_name)) in completed_browser
                    selected.append((
                        str(case_name),
                        ", ".join(record.get("related_symbols", [])[:3])
                        or Path(path).stem,
                        "must-run" if completed else "recommended",
                        (
                            "completed static browser path reaches this active "
                            "target-linked machine-checked scenario"
                            if completed else
                            "exact browser target has a machine check but no "
                            "completed static source-to-browser path"
                        ),
                    ))
            elif not browser.get("has_machine_check"):
                exclusions["browser-without-machine-check"] += 1
            else:
                exclusions["possible-browser-without-object-link"] += 1
        else:
            reasons = list(record.get("relation_reasons", []))
            if relation == "possible":
                exclusions["possible-search-clue"] += 1
            elif reasons and all(
                str(reason).startswith("configured module relation")
                for reason in reasons
            ):
                exclusions["configured-module-only"] += 1
            elif not record.get("has_active_test_with_assertion"):
                exclusions["assertion-free-or-disabled"] += 1
            else:
                exclusions["no-behavior-linked-case"] += 1

        for case_name, behavior, tier, reason in selected:
            active, inactive_reason = active_case(record, asset, case_name)
            candidate = candidate_record(
                relation,
                record,
                module_ref,
                case_name,
                behavior,
                tier,
                reason,
                inventory,
            )
            if not active:
                candidate["selection_tier"] = "not-runnable"
                candidate["not_runnable_reason"] = inactive_reason
                candidate["command_hint"] = None
                candidate["command_argv"] = None
                candidate["command_ready"] = False
                candidate["command_source"] = "inactive-or-assertion-free-case"
                exclusions["selected-case-not-runnable"] += 1
            merge_candidate(candidates, candidate)

        browser = record.get("browser_evidence")
        if browser:
            journey_evidence.append({
                "test_repo": repo,
                "test_path": path,
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

    changed_files = {
        str(item.get("path") or ""): item
        for item in context.get("changed_files", [])
        if item.get("path")
    }
    for (repo, path), asset in assets.items():
        changed_file = changed_files.get(path)
        if changed_file is None or asset.get("asset_kind") not in {
            "test-file", "browser-scenario",
        }:
            continue
        facts = asset.get("test_facts", {})
        record = {
            "repo": repo,
            "path": path,
            "framework": asset.get("framework"),
            "relation_reasons": ["test file changed in the analyzed diff"],
            "related_files": [path],
            "related_symbols": [],
            "assertion_linked_files": [path],
            "assertion_linked_symbols": [],
            "has_active_test_with_assertion": facts.get(
                "has_active_test_with_assertion", False,
            ),
            "browser_evidence": (
                {
                    "framework": facts.get("browser_framework"),
                    "has_machine_check": facts.get(
                        "browser_scenario_has_machine_check", False,
                    ),
                }
                if facts.get("browser_framework") else None
            ),
        }
        for case in facts.get("test_cases", []):
            case_name = str(case.get("name") or "")
            if not case_name:
                continue
            if not case_intersects_changed_hunk(case, changed_file):
                exclusions["unchanged-case-in-changed-test-file"] += 1
                continue
            record["has_active_test_with_assertion"] = bool(
                case.get("assertions")
            )
            active, inactive_reason = active_case(record, asset, case_name)
            if not active:
                exclusions["changed-test-case-not-runnable"] += 1
                continue
            merge_candidate(
                candidates,
                candidate_record(
                    "changed-test",
                    record,
                    {"repo": repo, "module_scope": "changed-test"},
                    case_name,
                    f"changed test file {path}",
                    "must-run",
                    "active asserted test case changed in the analyzed diff",
                    inventory,
                ),
            )

    ordered = sorted(
        candidates.values(),
        key=lambda item: (
            -TIER_RANK[item["selection_tier"]],
            item["execution_layer"],
            item["repo"],
            item["path"],
            item["test_case"],
        ),
    )
    must_run = [
        item for item in ordered if item["selection_tier"] == "must-run"
    ]
    recommended = [
        item for item in ordered if item["selection_tier"] == "recommended"
    ]
    not_runnable = [
        item for item in ordered if item["selection_tier"] == "not-runnable"
    ]
    not_runnable.extend(planned_test_gaps(correspondence))
    selection_summary = {
        "must_run": len(must_run),
        "recommended": len(recommended),
        "not_runnable": len(not_runnable),
        "excluded_raw_relations": sum(exclusions.values()),
    }
    return {
        "schema_version": 2,
        "phase": "phase-2-test-execution-handoff",
        "execution_status": "not-run",
        "analysis_complete": True,
        "analysis_mode": context.get("analysis_mode"),
        "requested_base_ref": context.get("requested_base_ref"),
        "workspace_change_fingerprint": workspace_fingerprint(repositories),
        "repositories": repositories,
        "selection_rule": (
            "Select active behavior/contract-asserted direct cases, result-linked "
            "behavior-asserted indirect cases, changed asserted test cases, and "
            "machine-checked completed browser paths. Raw configured/import-only/"
            "possible relations are diagnostic and do not become must-run."
        ),
        "selection_summary": selection_summary,
        "must_run": must_run,
        "recommended": recommended,
        "not_runnable": not_runnable,
        "excluded_summary": dict(sorted(exclusions.items())),
        # Compatibility aliases for existing consumers. These now expose the
        # strict behavior-scoped sets rather than every raw relation.
        "required_candidates": must_run,
        "optional_candidates": recommended,
        "required_commands_ready": bool(must_run) and all(
            item["command_ready"] for item in must_run
        ),
        "affected_user_journey_evidence": sorted(
            journey_evidence,
            key=lambda item: (
                item["changed_module"].get("repo") or "",
                item["changed_module"].get("module_scope") or "",
                item["test_path"],
            ),
        ),
        "user_journey_graph_schema_version": graph.get("schema_version"),
        "completed_user_journey_paths": manifest_journey_paths(graph, "paths"),
        "partial_user_journey_paths": manifest_journey_paths(
            graph, "partial_paths",
        ),
        "coverage_layers": {
            "must_run": sorted({
                item["execution_layer"] for item in must_run
            }),
            "recommended": sorted({
                item["execution_layer"] for item in recommended
            }),
        },
        "pre_execution_gates": [
            "obtain explicit authorization to execute selected tests",
            "recompute and match workspace_change_fingerprint immediately before execution",
            "validate repository containment and structured argv",
            "confirm dependencies and any browser application environment already exist",
            "do not install dependencies, start live-bench services, reset data, or query Phoenix",
        ],
        "boundary_note": (
            "This manifest is static guidance only. Phase 1 did not execute "
            "tests or mutate application state."
        ),
    }
