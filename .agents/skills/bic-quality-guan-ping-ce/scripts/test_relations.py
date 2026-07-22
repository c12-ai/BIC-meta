#!/usr/bin/env python3
"""Read-only correspondence analysis between changed objects and tests."""

from __future__ import annotations

import ast
import posixpath
import re
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


def relation_record(
    asset: dict[str, Any], reasons: list[str], related_files: Iterable[str],
    related_symbols: Iterable[str], relation_proves_object_path: bool = False,
    related_case_names: Iterable[str] | None = None,
    assertion_linked_symbols: Iterable[str] | None = None,
    assertion_linked_files: Iterable[str] | None = None,
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
    case_names = None if related_case_names is None else set(related_case_names)
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
    reachable_symbol_cache: dict[tuple[Path, Path, tuple[str, ...], tuple[str, ...]], set[str]] = {}

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

    module_results: list[dict[str, Any]] = []
    for key in sorted(module_files):
        repo, module = key
        repo_root = workspace_root if repo == "BIC-meta" else workspace_root / repo
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
                        linked_identifiers = {
                            identifier
                            for case in facts.get("test_cases", [])
                            if case.get("name") in source_linked_cases
                            for identifier in case.get("assertion_linked_identifiers", [])
                        }
                        if source_linked_cases:
                            direct_assertion_files.add(source["path"])
                        for symbol in source["symbols"]:
                            identifier = symbol_identifier(symbol)
                            if identifier and identifier in identifiers:
                                related_symbols.add(symbol["name"])
                                reasons.append(f"references {identifier} from the imported changed file")
                                if identifier in linked_identifiers:
                                    direct_assertion_symbols.add(symbol["name"])

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
                ))

            asset_has_indirect_relation = False
            if asset["repo"] == repo:
                one_hop_files: set[str] = set()
                one_hop_symbols: set[str] = set()
                one_hop_reasons: list[str] = []
                one_hop_cases: set[str] = set()
                one_hop_assertion_files: set[str] = set()
                one_hop_assertion_symbols: set[str] = set()
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
                        source_roots: set[str] = set()
                        source_related_symbols: set[str] = set()
                        for symbol in source["symbols"]:
                            identifier = symbol_identifier(symbol)
                            if identifier and identifier in entry_identifiers:
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
                        if linked_cases:
                            one_hop_assertion_files.add(source["path"])
                            one_hop_assertion_symbols.update(source_related_symbols)
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
                    ))

            if configured and not related_files and not asset_has_indirect_relation:
                asset_has_indirect_relation = True
                indirect.append(relation_record(
                    asset, [f"configured module relation {entry_id}" for entry_id in configured],
                    [item["path"] for item in changed],
                    set().union(*(configured_objects(entry, key) for entry in configured_entries)),
                    relation_proves_object_path=True,
                ))

            if related_files or asset_has_indirect_relation or asset["repo"] != repo:
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
        non_testable_changes: dict[str, str] = {}
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
                and (
                    name in relation["assertion_linked_symbols"]
                    or (
                        symbol["kind"] in {"file", "changed-file"}
                        and symbol["path"] in relation["assertion_linked_files"]
                    )
                )
                for relation in direct_for_object
            )
            active_indirect = any(
                relation["has_active_test_with_assertion"]
                and name in relation["assertion_linked_symbols"]
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
            "non_testable_changes": [
                {"path": path, "reason": reason}
                for path, reason in sorted(non_testable_changes.items())
            ],
        })

    return {
        "modules": module_results,
        "analysis_note": "Static correspondence only. Tests were not executed, and assertions do not prove passing behavior or complete coverage.",
    }
