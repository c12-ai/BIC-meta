#!/usr/bin/env python3
"""Read-only correspondence analysis between changed objects and tests."""

from __future__ import annotations

import posixpath
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from symbol_extraction import extract_source_references


TOKEN_STOPWORDS = {
    "app", "src", "lib", "test", "tests", "unit", "integration", "index",
    "main", "service", "services", "component", "components", "py", "ts",
    "tsx", "js", "jsx", "pages", "api", "routers",
}
NON_SOURCE_TEST_MODULES = {"portal/tests", "agent/tests", "meta/docs", "meta/test-config"}


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
        for size in range(len(parts), 0, -1):
            base = repo_root.joinpath(*parts[:size])
            for candidate in (base.with_suffix(".py"), base / "__init__.py"):
                if candidate.is_file():
                    return candidate
        return None

    imported = javascript_import_path(import_value, importing_path, repo)
    bases = [repo_root / imported]
    if not imported.startswith(("src/", "app/")):
        bases.extend([repo_root / "src" / imported, repo_root / "app" / imported])
    extensions = (".ts", ".tsx", ".js", ".jsx")
    for base in bases:
        for extension in extensions:
            candidate = base.with_suffix(extension)
            if candidate.is_file():
                return candidate
            index = base / f"index{extension}"
            if index.is_file():
                return index
    return None


def workspace_path(path: Path, workspace_root: Path) -> str:
    return path.resolve().relative_to(workspace_root.resolve()).as_posix()


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


def relation_record(
    asset: dict[str, Any], reasons: list[str], related_files: Iterable[str],
    related_symbols: Iterable[str], relation_proves_object_path: bool = False,
) -> dict[str, Any]:
    facts = asset.get("test_facts", {})
    test_names = facts.get("test_names", [])
    disabled = facts.get("disabled_tests", [])
    related_identifiers = {
        name.rsplit(".", 1)[-1]
        for name in related_symbols
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name.rsplit(".", 1)[-1])
    }
    test_cases = facts.get("test_cases", [])
    if relation_proves_object_path:
        has_active_assertion = bool(facts.get("has_active_test_with_assertion"))
    elif related_identifiers and test_cases:
        has_active_assertion = any(
            not case.get("disabled")
            and bool(case.get("assertions"))
            and bool(related_identifiers & set(case.get("referenced_identifiers", [])))
            for case in test_cases
        )
    else:
        has_active_assertion = bool(facts.get("has_active_test_with_assertion"))
    return {
        "repo": asset["repo"], "path": asset["path"], "framework": asset.get("framework"),
        "relation_reasons": sorted(set(reasons)),
        "related_files": sorted(set(related_files)),
        "related_symbols": sorted(set(related_symbols)),
        "imports": facts.get("imports", []),
        "test_names": test_names,
        "assertions": facts.get("assertions", []),
        "disabled_tests": disabled,
        "has_active_test_with_assertion": has_active_assertion,
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

    test_assets = [asset for asset in discovered_assets if asset.get("asset_kind") == "test-file"]
    inventory_by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in inventory:
        for path in entry.get("matching_discovered_assets", []):
            inventory_by_asset[path].append(entry)
    source_reference_cache: dict[Path, dict[str, list[str]]] = {}

    module_results: list[dict[str, Any]] = []
    for key in sorted(module_files):
        repo, module = key
        changed = module_files[key]
        module_symbol_items = [symbols_by_path[item["path"]] for item in changed if item["path"] in symbols_by_path]
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
            related_files: set[str] = set()
            related_symbols: set[str] = set()
            reasons: list[str] = []
            configured_entries = [
                entry for entry in inventory_by_asset[asset["path"]]
                if key in configured_targets(entry)
            ]
            configured = [entry["id"] for entry in configured_entries]
            if asset["repo"] == repo:
                for source in module_symbol_items:
                    matching_imports = [value for value in imports if import_matches(value, asset["path"], source["path"], repo)]
                    if not matching_imports:
                        continue
                    related_files.add(source["path"])
                    reasons.append(f"imports changed file via {', '.join(matching_imports)}")
                    for symbol in source["symbols"]:
                        identifier = symbol_identifier(symbol)
                        if identifier and identifier in identifiers:
                            related_symbols.add(symbol["name"])
                            reasons.append(f"references {identifier} from the imported changed file")
            if related_files:
                direct.append(relation_record(asset, reasons, related_files, related_symbols))
                continue

            if asset["repo"] == repo:
                one_hop_files: set[str] = set()
                one_hop_symbols: set[str] = set()
                one_hop_reasons: list[str] = []
                for test_import in imports:
                    entry_path = resolve_imported_source(
                        workspace_root, test_import, asset["path"], repo,
                    )
                    if not entry_path:
                        continue
                    entry_workspace_path = workspace_path(entry_path, workspace_root)
                    if entry_workspace_path in {source["path"] for source in module_symbol_items}:
                        continue
                    if entry_path not in source_reference_cache:
                        source_reference_cache[entry_path] = extract_source_references(entry_path)
                    references = source_reference_cache[entry_path]
                    for source in module_symbol_items:
                        matching_source_imports = [
                            value for value in references["imports"]
                            if import_matches(value, entry_workspace_path, source["path"], repo)
                        ]
                        if not matching_source_imports:
                            continue
                        one_hop_files.add(source["path"])
                        one_hop_reasons.append(
                            f"imports {entry_workspace_path}, which imports the changed file via "
                            f"{', '.join(matching_source_imports)}"
                        )
                        identifiers = set(references["identifiers"])
                        for symbol in source["symbols"]:
                            identifier = symbol_identifier(symbol)
                            if identifier and identifier in identifiers:
                                one_hop_symbols.add(symbol["name"])
                if one_hop_files:
                    indirect.append(relation_record(
                        asset, one_hop_reasons, one_hop_files, one_hop_symbols,
                        relation_proves_object_path=True,
                    ))
                    continue

            if configured:
                indirect.append(relation_record(
                    asset, [f"configured module relation {entry_id}" for entry_id in configured],
                    [item["path"] for item in changed],
                    set().union(*(configured_objects(entry, key) for entry in configured_entries)),
                    relation_proves_object_path=True,
                ))
                continue

            if asset["repo"] != repo:
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

        add_tests: list[str] = []
        strengthen_tests: list[str] = []
        no_gaps: list[str] = []
        if module not in NON_SOURCE_TEST_MODULES:
            for symbol in flattened_symbols:
                name = symbol["name"]
                direct_for_object = [
                    relation for relation in direct
                    if name in relation["related_symbols"]
                    or (
                        symbol["kind"] in {"file", "changed-file"}
                        and symbol["path"] in relation["related_files"]
                    )
                ]
                indirect_for_object = [
                    relation for relation in indirect
                    if name in relation["related_symbols"]
                ]
                active_direct = any(
                    relation["has_active_test_with_assertion"]
                    and (name in relation["related_symbols"] or symbol["kind"] == "file")
                    for relation in direct_for_object
                )
                active_indirect = any(
                    relation["has_active_test_with_assertion"]
                    for relation in indirect_for_object
                )
                possible_for_object = any(
                    symbol["path"] in relation["related_files"]
                    for relation in possible
                )
                needs_strengthening = bool(
                    direct_for_object or indirect_for_object or possible_for_object
                )
                observation = "declared in an added file" if "added" in symbol.get("change_types", []) else "declared in a changed file (diff-hunk attribution unavailable)"
                subject = f"{symbol['kind']} {name} in {symbol['path']} ({observation})"
                if active_direct or active_indirect:
                    no_gaps.append(f"No obvious static gap for {subject}: an active object-related test contains an assertion.")
                elif needs_strengthening:
                    strengthen_tests.append(f"Strengthen tests for {subject}: related evidence is only structural/scenario-based, disabled, or has no assertion.")
                else:
                    add_tests.append(f"Add a test for {subject}: no related test was found by imports, identifiers, configured relations, filename, or module structure.")

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
            "symbol_scope_note": "Added/untracked files expose best-effort declarations; modified, renamed, or deleted files use one file-level changed object because diff-hunk symbol attribution is unavailable.",
            "directly_related_tests": direct,
            "indirectly_related_tests": indirect,
            "possibly_related_tests": possible,
            "add_tests": add_tests,
            "strengthen_tests": strengthen_tests,
            "no_obvious_test_gaps": no_gaps,
        })

    return {
        "modules": module_results,
        "analysis_note": "Static correspondence only. Tests were not executed, and assertions do not prove passing behavior or complete coverage.",
    }
