#!/usr/bin/env python3
"""Safe machine-JSON adapter for the pinned ast-outline runtime."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tool_runtime import AnalyzerRuntimeError, ensure_ast_outline, load_runtime_manifest


ANALYZER_TIMEOUT_SECONDS = 30
MAX_ANALYZER_OUTPUT_BYTES = 8 * 1024 * 1024
ROUTE_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
ROUTE_RE = re.compile(
    r"(?:@|\b)(?:[A-Za-z_$][\w$]*\.)?(get|post|put|patch|delete|options|head)"
    r"\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


class StructuralAnalysisError(RuntimeError):
    """Raised when an affected source cannot be structurally analyzed."""


def run_outline(path: Path, executable: Path | None = None) -> dict[str, Any]:
    executable = executable or ensure_ast_outline()
    try:
        proc = subprocess.run(
            [str(executable), "outline", str(path), "--json"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=ANALYZER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StructuralAnalysisError(f"ast-outline failed for {path.name}: {type(exc).__name__}") from exc
    if proc.returncode != 0:
        raise StructuralAnalysisError(f"ast-outline failed for {path.name}")
    if len(proc.stdout.encode("utf-8", errors="replace")) > MAX_ANALYZER_OUTPUT_BYTES:
        raise StructuralAnalysisError(f"ast-outline output exceeded the limit for {path.name}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise StructuralAnalysisError(f"ast-outline returned invalid JSON for {path.name}") from exc
    config = load_runtime_manifest()
    if (
        payload.get("tool") != "ast-outline"
        or payload.get("command") != "outline"
        or payload.get("schema_version") != config["schema_version"]
    ):
        raise StructuralAnalysisError(f"ast-outline returned an incompatible envelope for {path.name}")
    files = payload.get("files")
    if not isinstance(files, list) or len(files) != 1:
        raise StructuralAnalysisError(f"ast-outline returned an unexpected file set for {path.name}")
    parsed = files[0]
    if not isinstance(parsed, dict) or not isinstance(parsed.get("declarations"), list):
        raise StructuralAnalysisError(f"ast-outline declarations are invalid for {path.name}")
    if parsed.get("error_count"):
        raise StructuralAnalysisError(f"ast-outline found syntax errors in {path.name}")
    return parsed


def classify_declaration(
    declaration: dict[str, Any],
    path: Path,
    qualified_name: str,
) -> tuple[str, dict[str, str]]:
    kind = str(declaration.get("kind") or declaration.get("native_kind") or "declaration")
    name = str(declaration.get("name") or qualified_name)
    signature = str(declaration.get("signature") or "")
    suffix = path.suffix.lower()
    metadata: dict[str, str] = {}

    route = ROUTE_RE.search(" ".join([signature, *map(str, declaration.get("attrs", []))]))
    if route and route.group(1).upper() in ROUTE_METHODS:
        metadata = {"route_method": route.group(1).upper(), "route_path": route.group(2)}
        return "route", metadata
    if suffix in {".tsx", ".jsx"} and name[:1].isupper() and kind in {"function", "method", "field"}:
        return "component", metadata
    if suffix in {".ts", ".tsx", ".js", ".jsx"} and re.fullmatch(r"use[A-Z][A-Za-z0-9_$]*", name):
        return "hook", metadata
    lowered_path = "/".join(part.lower() for part in path.parts)
    if suffix in {".ts", ".tsx", ".js", ".jsx"} and any(
        token in lowered_path for token in ("/stores/", "/store/")
    ) and kind in {"function", "method", "field", "class"}:
        return "store-or-action", metadata
    if suffix in {".ts", ".tsx", ".js", ".jsx"} and any(
        token in lowered_path for token in ("/client/", "/clients/", "-client", "/api/")
    ) and kind in {"function", "method", "field", "class"}:
        return "api-client", metadata
    mapped = {
        "type": "class",
        "class": "class",
        "interface": "type",
        "enum": "type",
        "type_alias": "type",
        "function": "function",
        "method": "method",
        "field": "event-or-constant" if name.isupper() or "EVENT" in name.upper() else "field",
    }
    return mapped.get(kind, kind), metadata


def flatten_declarations(
    declarations: list[dict[str, Any]],
    path: Path,
    ancestors: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for declaration in declarations:
        if not isinstance(declaration, dict):
            raise StructuralAnalysisError(f"ast-outline declaration is not an object for {path.name}")
        name = str(declaration.get("name") or "").strip()
        start = declaration.get("start_line")
        end = declaration.get("end_line")
        if not name or not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
            raise StructuralAnalysisError(f"ast-outline declaration range is invalid for {path.name}")
        qualified = ".".join((*ancestors, name))
        kind, metadata = classify_declaration(declaration, path, qualified)
        item = {
            "name": qualified,
            "symbol": name,
            "qualified_name": qualified,
            "kind": kind,
            "native_kind": declaration.get("native_kind") or declaration.get("kind") or "",
            "signature": declaration.get("signature") or "",
            "start_line": start,
            "end_line": end,
            **metadata,
        }
        result.append(item)
        children = declaration.get("children") or []
        if not isinstance(children, list):
            raise StructuralAnalysisError(f"ast-outline child declarations are invalid for {path.name}")
        result.extend(flatten_declarations(children, path, (*ancestors, name)))
    return result


def analyze_file(path: Path, executable: Path | None = None) -> dict[str, Any]:
    parsed = run_outline(path, executable)
    return {
        "language": parsed.get("language") or path.suffix.lstrip("."),
        "imports": parsed.get("imports") or [],
        "line_count": parsed.get("line_count") or 0,
        "declarations": flatten_declarations(parsed["declarations"], path),
    }


def analyze_source_text(
    source: str,
    suffix: str,
    executable: Path | None = None,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="bic-quality-old-source-") as temp_dir:
        path = Path(temp_dir) / f"old-source{suffix}"
        path.write_text(source, encoding="utf-8")
        return analyze_file(path, executable)


def managed_analyzer_metadata() -> dict[str, Any]:
    config = load_runtime_manifest()
    try:
        executable = ensure_ast_outline()
    except AnalyzerRuntimeError as exc:
        raise StructuralAnalysisError(str(exc)) from exc
    return {
        "name": "ast-outline",
        "version": config["version"],
        "schema_version": config["schema_version"],
        "executable": executable,
    }
