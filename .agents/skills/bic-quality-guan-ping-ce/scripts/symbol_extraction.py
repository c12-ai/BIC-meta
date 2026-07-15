#!/usr/bin/env python3
"""Deterministic symbol extraction for changed Python and JS/TS files."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from content_safety import safe_repository_file


JS_DECLARATION_RE = re.compile(
    r"(?m)^\s*(?P<export>export\s+(?:default\s+)?)?"
    r"(?:(?:declare|abstract|async)\s+)*"
    r"(?P<kind>function|class|const|let|var|interface|type|enum)\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
)
JS_ROUTE_RE = re.compile(
    r"\b(?:router|app)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
JS_EVENT_RE = re.compile(r"\b(?:emit|dispatch)\s*\(\s*['\"]([^'\"]+)['\"]")
JS_IMPORT_RE = re.compile(
    r"(?:import\s+(?:type\s+)?(?:[^;]*?\s+from\s+)?|require\s*\()"
    r"['\"]([^'\"]+)['\"]"
)
JS_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")


def decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = decorator_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def python_import_name(node: ast.ImportFrom, alias: ast.alias) -> str:
    prefix = "." * node.level
    module = f"{prefix}{node.module or ''}"
    if alias.name == "*":
        return module
    separator = "" if not module or module.endswith(".") else "."
    return f"{module}{separator}{alias.name}"


def parse_python(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [], "python syntax could not be parsed"
    symbols: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append({"name": node.name, "kind": "function", "line": node.lineno})
            for decorator in node.decorator_list:
                call = decorator if isinstance(decorator, ast.Call) else None
                name = decorator_name(call.func if call else decorator)
                method = name.rsplit(".", 1)[-1].upper()
                if call and method in {"GET", "POST", "PUT", "PATCH", "DELETE"} and call.args:
                    value = call.args[0]
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        symbols.append({"name": f"{method} {value.value}", "kind": "route", "line": node.lineno})
        elif isinstance(node, ast.ClassDef):
            symbols.append({"name": node.name, "kind": "class", "line": node.lineno})
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append({"name": f"{node.name}.{child.name}", "kind": "method", "line": child.lineno})
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and ("EVENT" in target.id.upper() or target.id.isupper()):
                    symbols.append({"name": target.id, "kind": "event-or-constant", "line": node.lineno})
    return symbols, None


def parse_javascript(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    symbols: list[dict[str, Any]] = []
    kind_map = {"interface": "type", "type": "type", "enum": "type"}
    for match in JS_DECLARATION_RE.finditer(content):
        kind = kind_map.get(match.group("kind"), match.group("kind"))
        symbols.append({
            "name": match.group("name"), "kind": kind,
            "exported": bool(match.group("export")),
            "line": content.count("\n", 0, match.start()) + 1,
        })
    for match in JS_ROUTE_RE.finditer(content):
        symbols.append({
            "name": f"{match.group(1).upper()} {match.group(2)}", "kind": "route",
            "line": content.count("\n", 0, match.start()) + 1,
        })
    for match in JS_EVENT_RE.finditer(content):
        symbols.append({
            "name": match.group(1), "kind": "event",
            "line": content.count("\n", 0, match.start()) + 1,
        })
    return symbols, None


def extract_source_references(path: Path) -> dict[str, list[str]]:
    """Read source imports and identifiers without importing project code."""
    content = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() == ".py":
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return {"imports": [], "identifiers": []}
        imports: set[str] = set()
        identifiers: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported = python_import_name(node, alias)
                    if imported:
                        imports.add(imported)
                    identifiers.add(alias.name)
                    if alias.asname:
                        identifiers.add(alias.asname)
            elif isinstance(node, ast.Name):
                identifiers.add(node.id)
            elif isinstance(node, ast.Attribute):
                identifiers.add(node.attr)
        return {"imports": sorted(imports), "identifiers": sorted(identifiers)}
    return {
        "imports": sorted(set(JS_IMPORT_RE.findall(content))),
        "identifiers": sorted(set(JS_IDENTIFIER_RE.findall(content))),
    }


def extract_changed_symbols(
    workspace_root: Path,
    changed_files: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for changed in changed_files:
        path = changed["path"]
        suffix = Path(path).suffix.lower()
        supported = suffix in {".py", ".js", ".jsx", ".ts", ".tsx"}
        absolute = workspace_root / path
        repo_relative = changed.get("repo_relative_path", ".")
        repository_root = workspace_root if repo_relative == "." else workspace_root / repo_relative
        warning: str | None = None
        symbols: list[dict[str, Any]] = []
        is_new_file = bool({"added", "untracked"} & set(changed.get("change_types", [])))
        if not supported:
            symbols = [{"name": Path(path).name, "kind": "changed-file", "line": None}]
            warning = f"file-level object used because {suffix or 'extensionless'} parsing is unsupported"
        elif not is_new_file:
            symbols = [{"name": Path(path).stem, "kind": "changed-file", "line": None}]
            warning = "file-level object used because diff-hunk symbol attribution is unavailable"
        else:
            safe_path, unsafe_reason = safe_repository_file(absolute, repository_root)
            if safe_path is not None:
                symbols, warning = parse_python(safe_path) if suffix == ".py" else parse_javascript(safe_path)
            elif unsafe_reason in {"symlink", "outside-repository", "sensitive-path"}:
                warning = f"content inspection skipped: {unsafe_reason}"
            else:
                warning = "changed file is unavailable (possibly deleted)"
        if not symbols:
            symbols = [{"name": Path(path).stem, "kind": "file", "line": None}]
        result = {
            "repo": changed["repo"], "path": path,
            "change_types": changed.get("change_types", []), "symbols": symbols,
            "symbol_scope": "declarations" if is_new_file and supported else "file-level",
        }
        if warning:
            result["parse_warning"] = warning
        results.append(result)
    return results
