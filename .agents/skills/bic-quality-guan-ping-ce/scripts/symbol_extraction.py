#!/usr/bin/env python3
"""Deterministic diff-hunk declaration extraction across supported languages."""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path
from typing import Any

from content_safety import safe_repository_file
from ast_outline_adapter import (
    StructuralAnalysisError,
    analyze_file,
    analyze_source_text,
    managed_analyzer_metadata,
)


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
STRUCTURAL_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".kt", ".kts",
    ".rs", ".php", ".rb", ".cs", ".cpp", ".cc", ".cxx", ".h", ".hpp",
    ".swift", ".lua", ".ex", ".exs", ".scala", ".sc",
}


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
    analyzer = managed_analyzer_metadata()
    executable = analyzer["executable"]
    results: list[dict[str, Any]] = []
    for changed in changed_files:
        path = changed["path"]
        suffix = Path(path).suffix.lower()
        supported = suffix in STRUCTURAL_SUFFIXES
        absolute = workspace_root / path
        repo_relative = changed.get("repo_relative_path", ".")
        repository_root = workspace_root if repo_relative == "." else workspace_root / repo_relative
        warning: str | None = None
        symbols: list[dict[str, Any]] = []
        change_types = set(changed.get("change_types", []))
        is_new_file = bool({"added", "untracked"} & change_types)
        if not supported:
            symbols = [{"name": Path(path).name, "kind": "changed-file", "line": None}]
            warning = f"file-level object used because {suffix or 'extensionless'} parsing is unsupported"
        else:
            new_analysis: dict[str, Any] | None = None
            old_analysis: dict[str, Any] | None = None
            safe_path, unsafe_reason = safe_repository_file(absolute, repository_root)
            if safe_path is not None:
                try:
                    new_analysis = analyze_file(safe_path, executable)
                except StructuralAnalysisError as exc:
                    raise StructuralAnalysisError(f"Complete changed-object analysis failed for {path}: {exc}") from exc
            elif unsafe_reason in {"symlink", "outside-repository", "sensitive-path"}:
                symbols = [{"name": Path(path).stem, "kind": "changed-file", "line": None}]
                warning = f"content inspection skipped: {unsafe_reason}"

            if symbols:
                result = {
                    "repo": changed["repo"], "path": path,
                    "change_types": changed.get("change_types", []), "symbols": symbols,
                    "symbol_scope": "file-level",
                }
                if warning:
                    result["parse_warning"] = warning
                if changed.get("old_path"):
                    result["old_path"] = changed["old_path"]
                results.append(result)
                continue

            comparison_base = changed.get("comparison_base")
            old_workspace_path = changed.get("old_path") or path
            prefix = "" if repo_relative == "." else f"{repo_relative}/"
            old_local_path = (
                old_workspace_path[len(prefix):]
                if prefix and old_workspace_path.startswith(prefix)
                else old_workspace_path
            )
            if comparison_base and any(hunk.get("old_count", 0) for hunk in changed.get("diff_hunks", [])):
                try:
                    proc = subprocess.run(
                        ["git", "show", f"{comparison_base}:{old_local_path}"],
                        cwd=str(repository_root),
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        timeout=30,
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    raise StructuralAnalysisError(
                        f"Complete old-source analysis failed for {old_workspace_path}: {type(exc).__name__}"
                    ) from exc
                if proc.returncode == 0:
                    try:
                        old_analysis = analyze_source_text(proc.stdout, suffix, executable)
                    except StructuralAnalysisError as exc:
                        raise StructuralAnalysisError(
                            f"Complete old-source analysis failed for {old_workspace_path}: {exc}"
                        ) from exc
                elif "deleted" in change_types or "renamed" in change_types:
                    raise StructuralAnalysisError(
                        f"Complete old-source analysis could not read {old_workspace_path} from {comparison_base}"
                    )

            def selected_declarations(
                analysis: dict[str, Any] | None,
                side: str,
            ) -> list[dict[str, Any]]:
                if analysis is None:
                    return []
                selected: list[dict[str, Any]] = []
                for hunk in changed.get("diff_hunks", []):
                    count = int(hunk.get(f"{side}_count", 0))
                    if count <= 0:
                        continue
                    start = int(hunk[f"{side}_start"])
                    end = int(hunk[f"{side}_end"])
                    candidates = [
                        declaration for declaration in analysis["declarations"]
                        if declaration["start_line"] <= end and declaration["end_line"] >= start
                    ]
                    leaf_candidates = [
                        candidate for candidate in candidates
                        if not any(
                            other is not candidate
                            and candidate["start_line"] <= other["start_line"]
                            and candidate["end_line"] >= other["end_line"]
                            and (
                                candidate["start_line"] < other["start_line"]
                                or candidate["end_line"] > other["end_line"]
                            )
                            for other in candidates
                        )
                    ]
                    selected.extend(leaf_candidates or candidates)
                unique: dict[tuple[str, str, int, int], dict[str, Any]] = {}
                for declaration in selected:
                    key = (
                        declaration["qualified_name"], declaration["kind"],
                        declaration["start_line"], declaration["end_line"],
                    )
                    unique[key] = declaration
                return list(unique.values())

            new_symbols = selected_declarations(new_analysis, "new")
            old_symbols = selected_declarations(old_analysis, "old")
            merged: dict[tuple[str, str], dict[str, Any]] = {}
            for side, declarations in (("old", old_symbols), ("new", new_symbols)):
                for declaration in declarations:
                    key = (declaration["qualified_name"], declaration["kind"])
                    entry = merged.setdefault(key, {**declaration, "sides": []})
                    entry["sides"].append(side)
                    entry[f"{side}_start_line"] = declaration["start_line"]
                    entry[f"{side}_end_line"] = declaration["end_line"]
            for declaration in merged.values():
                sides = set(declaration.pop("sides"))
                if sides == {"old", "new"}:
                    declaration["change_kind"] = "renamed" if "renamed" in change_types else "modified"
                elif sides == {"old"}:
                    declaration["change_kind"] = "deleted"
                else:
                    declaration["change_kind"] = "added" if is_new_file else "modified"
                # The first merged record may come from the base-side AST.  A
                # modified declaration must expose the current range when the
                # current file is what downstream relationship analysis reads;
                # otherwise inserted lines can truncate the declaration body
                # and hide nested component/function references.
                active_side = "new" if "new" in sides else "old"
                declaration["start_line"] = declaration.get(f"{active_side}_start_line")
                declaration["end_line"] = declaration.get(f"{active_side}_end_line")
                declaration["line"] = declaration.get("new_start_line", declaration.get("old_start_line"))
                symbols.append(declaration)

            if not symbols:
                symbols = [{
                    "name": Path(path).stem,
                    "symbol": Path(path).stem,
                    "qualified_name": Path(path).stem,
                    "kind": "module-scope",
                    "native_kind": "module",
                    "line": None,
                    "start_line": None,
                    "end_line": None,
                    "change_kind": "renamed" if "renamed" in change_types else "modified",
                }]
        if not symbols:
            symbols = [{"name": Path(path).stem, "kind": "file", "line": None}]
        result = {
            "repo": changed["repo"], "path": path,
            "change_types": changed.get("change_types", []), "symbols": symbols,
            "symbol_scope": "diff-hunk-declarations" if supported else "file-level",
            "analyzer": {
                "name": analyzer["name"],
                "version": analyzer["version"],
                "schema_version": analyzer["schema_version"],
            } if supported else None,
        }
        if warning:
            result["parse_warning"] = warning
        if changed.get("old_path"):
            result["old_path"] = changed["old_path"]
        results.append(result)
    return results
