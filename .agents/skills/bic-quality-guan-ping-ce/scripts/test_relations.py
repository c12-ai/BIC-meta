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
JOURNEY_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
JOURNEY_SCAN_EXCLUDES = {
    ".git", ".agents", ".claude", ".trellis", ".venv", "node_modules",
    "__pycache__", ".pytest_cache", ".pnpm-store", "artifacts", "dist", "build",
}
MAX_JOURNEY_EDGES = 2000
MAX_JOURNEY_PATHS = 40
MAX_JOURNEY_PATH_DEPTH = 7
MAX_JOURNEY_OUTPUT_NODES = MAX_JOURNEY_EDGES * 2 + MAX_JOURNEY_PATHS


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

    pending = [str(root) for root in roots if str(root) in by_identifier]
    reachable: set[str] = set()
    safe_path, _ = safe_repository_file(path, repository_root)
    if safe_path is None:
        return reachable
    try:
        lines = safe_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return reachable

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
                        reachable_names = (
                            reachable_changed_declarations(
                                source_path, source["symbols"], source_root_identifiers,
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
                            if identifier and (
                                identifier in source_root_identifiers
                                or str(symbol["name"]) in reachable_names
                            ):
                                related_symbols.add(symbol["name"])
                                if identifier in source_root_identifiers:
                                    reasons.append(f"references {identifier} from the imported changed file")
                                else:
                                    reasons.append(
                                        f"reaches {identifier} from a referenced declaration in the imported changed file"
                                    )
                                if (
                                    identifier in linked_root_identifiers
                                    or str(symbol["name"]) in assertion_reachable_names
                                ):
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
                    symbol["kind"] in {"file", "changed-file", "module-scope"}
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
                        symbol["kind"] in {"file", "changed-file", "module-scope"}
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
            if "added" in symbol.get("change_types", []):
                observation = "declared in an added file"
            elif symbol["kind"] == "module-scope":
                observation = "changed outside a declaration"
            else:
                observation = "selected by a changed diff hunk"
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
            "symbol_scope_note": "Supported source files use ast-outline Diff-hunk declarations; legitimate module-level changes remain module-scope objects.",
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

    journey_graph = build_user_journey_graph(
        workspace_root, scope, changed_symbols, discovered_assets,
    )
    return {
        "modules": module_results,
        "user_journey_graph": journey_graph,
        "analysis_note": "Static correspondence only. Tests were not executed, and assertions do not prove passing behavior or complete coverage.",
    }
