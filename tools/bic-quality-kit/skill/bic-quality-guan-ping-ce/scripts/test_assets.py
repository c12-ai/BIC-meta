#!/usr/bin/env python3
"""Deterministic, read-only test asset discovery and content parsing."""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Iterable

from content_safety import redact_text, safe_repository_file


DISCOVERY_EXCLUDES = {
    ".agents", ".claude", ".codex", ".git", ".trellis", ".venv",
    "node_modules", "__pycache__", ".pytest_cache", ".pnpm-store",
    "artifacts",
}
TEST_FILE_RE = re.compile(
    r"(^|/)(test_[^/]+\.py|[^/]+_test\.py|[^/]+\.(test|spec)\.[^.\/]+)$",
    re.IGNORECASE,
)
BROWSER_SOURCE_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
PLAYWRIGHT_ACTION_RE = re.compile(
    r"(?:\b(?:page|locator|browser|context|request)|\))\s*\.\s*"
    r"(goto|click|fill|type|press|check|uncheck|selectOption|hover|dragTo|"
    r"setInputFiles|reload|goBack|goForward|newPage|newContext|fetch|get|post|put|delete)\s*\("
)
PLAYWRIGHT_TEST_FIXTURE_RE = re.compile(
    r"\b(?:test|it)(?:\.(?:skip|todo|fixme|only))?\s*\("
    r"(?:(?!\)\s*;).)*?,\s*(?:async\s*)?\(\s*\{[^}]*"
    r"\b(?:page|context|browser|request)\b",
    re.DOTALL,
)
PLAYWRIGHT_OBSERVATION_RE = re.compile(
    r"(?:\b(?:page|locator|context|response|request)|\))\s*\.\s*"
    r"(screenshot|textContent|innerText|inputValue|isVisible|waitForURL|"
    r"waitForResponse|waitForRequest|waitForSelector|status|json|body)\s*\("
)
CDP_RE = re.compile(
    r"\b(?:connectOverCDP|newCDPSession|CDPSession|chrome-remote-interface|"
    r"(?:client|session|cdp)\.send)\b",
    re.IGNORECASE,
)
BROWSER_TARGET_RE = re.compile(
    r"\b(page|request)\s*\.\s*(goto|get|post|put|patch|delete)\s*"
    r"\(\s*(['\"])([^'\"]+)\3",
    re.IGNORECASE,
)
CDP_FAILURE_RE = re.compile(
    r"(?:\bif\s*\([^)]*\)\s*\{?[^{}]{0,500}?throw\s+new\s+Error\s*\(|"
    r"process\.exitCode\s*=\s*[1-9]\d*|"
    r"process\.exit\s*\(\s*[1-9]\d*\s*\)|assert\.fail\s*\()",
    re.IGNORECASE | re.DOTALL,
)
JS_IMPORT_RE = re.compile(
    r"(?:import\s+(?:type\s+)?(?:[^;]*?\s+from\s+)?|require\s*\()"
    r"['\"]([^'\"]+)['\"]"
)
JS_TEST_RE = re.compile(
    r"\b(describe|test|it)(?:\.(skip|todo|fixme|only))?\s*\(\s*['\"]([^'\"]+)['\"]"
)
JS_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")
JS_FUNCTION_DECLARATION_RE = re.compile(
    r"\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{"
)
JS_RENDER_COMPONENT_RE = re.compile(
    r"\brender\s*\(\s*<\s*([A-Z][A-Za-z0-9_$]*)\b",
    re.DOTALL,
)
JS_DOM_ASSERTION_RE = re.compile(
    r"\b(?:screen|within)\s*\."
    r"|\b(?:get|query|find)By(?:Role|Text|LabelText|TestId|PlaceholderText|Title)\b"
    r"|\.toBe(?:Visible|InTheDocument)\s*\("
    r"|\.toHave(?:Attribute|TextContent|Value|Class)\s*\("
)
JS_NAMED_IMPORT_RE = re.compile(
    r"import\s+(?:type\s+)?\{(?P<names>[^}]*)\}\s+from",
    re.DOTALL,
)
JS_NONCODE_RE = re.compile(
    r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`"
    r"|//[^\n]*|/\*.*?\*/",
    re.DOTALL,
)


def iter_repo_files(
    repo: Path,
    excluded_roots: Iterable[Path] = (),
    skipped: list[dict[str, str]] | None = None,
) -> Iterable[Path]:
    excluded = {path.resolve() for path in excluded_roots}
    for root, dirs, files in os.walk(repo):
        root_path = Path(root)
        dirs[:] = [
            name for name in dirs
            if name not in DISCOVERY_EXCLUDES
            and not name.startswith(".git")
            and not (root_path / name).is_symlink()
            and (root_path / name).resolve() not in excluded
        ]
        for filename in files:
            path = root_path / filename
            safe_path, reason = safe_repository_file(path, repo)
            if safe_path is not None:
                yield safe_path
            elif skipped is not None and TEST_FILE_RE.search(path.relative_to(repo).as_posix()):
                skipped.append({
                    "path": path.relative_to(repo).as_posix(),
                    "reason": reason or "unsafe-file",
                })


def asset_type_for_path(relative: str) -> tuple[str, str]:
    lowered = relative.lower()
    if "playwright" in lowered or "/e2e/" in f"/{lowered}/":
        return "frontend-smoke", "playwright/e2e path"
    if "/integration/" in f"/{lowered}/":
        return "service-integration", "integration test path"
    return "unit", "unit test filename convention"


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def python_import_name(node: ast.ImportFrom, alias: ast.alias) -> str:
    prefix = "." * node.level
    module = f"{prefix}{node.module or ''}"
    if alias.name == "*":
        return module
    separator = "" if not module or module.endswith(".") else "."
    return f"{module}{separator}{alias.name}"


def javascript_import_aliases(content: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for match in JS_NAMED_IMPORT_RE.finditer(content):
        for raw_name in match.group("names").split(","):
            item = raw_name.strip().removeprefix("type ").strip()
            if not item:
                continue
            parts = re.split(r"\s+as\s+", item, maxsplit=1)
            original = parts[0].strip()
            alias = parts[1].strip() if len(parts) == 2 else original
            if original and alias:
                aliases[alias] = original
    return aliases


def javascript_braced_body_range(content: str, open_brace: int) -> tuple[int, int]:
    """Return one balanced JS block body while ignoring strings and comments."""
    if open_brace < 0 or open_brace >= len(content) or content[open_brace] != "{":
        return open_brace, open_brace
    depth = 0
    index = open_brace
    quote: str | None = None
    while index < len(content):
        char = content[index]
        next_char = content[index + 1] if index + 1 < len(content) else ""
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in {"'", '"', "`"}:
            quote = char
        elif char == "/" and next_char == "/":
            newline = content.find("\n", index + 2)
            index = len(content) if newline < 0 else newline
            continue
        elif char == "/" and next_char == "*":
            close = content.find("*/", index + 2)
            index = len(content) if close < 0 else close + 2
            continue
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return open_brace + 1, index
        index += 1
    return open_brace + 1, len(content)


def js_test_body_range(content: str, start: int) -> tuple[int, int]:
    """Locate a best-effort callback body for one JS test declaration."""
    next_declaration = JS_TEST_RE.search(content, start)
    arrow = content.find("=>", start)
    if arrow >= 0 and (not next_declaration or arrow < next_declaration.start()):
        open_brace = content.find("{", arrow + 2)
    else:
        open_brace = content.find("{", start)
    if open_brace < 0 or (next_declaration and next_declaration.start() < open_brace):
        line_end = content.find("\n", start)
        end = line_end if line_end >= 0 else len(content)
        return start, end
    return javascript_braced_body_range(content, open_brace)


def js_test_body(content: str, start: int) -> str:
    body_start, body_end = js_test_body_range(content, start)
    return content[body_start:body_end]


def javascript_render_helpers(content: str) -> dict[str, set[str]]:
    """Map local test helpers to React components they render, transitively."""
    bodies: dict[str, str] = {}
    for match in JS_FUNCTION_DECLARATION_RE.finditer(content):
        body_start, body_end = javascript_braced_body_range(content, match.end() - 1)
        bodies[match.group(1)] = content[body_start:body_end]

    direct = {
        name: set(JS_RENDER_COMPONENT_RE.findall(body))
        for name, body in bodies.items()
    }
    helper_names = set(bodies)
    calls = {
        name: {
            helper for helper in helper_names
            if helper != name and re.search(rf"\b{re.escape(helper)}\s*\(", body)
        }
        for name, body in bodies.items()
    }

    resolved: dict[str, set[str]] = {}

    def visit(name: str, stack: tuple[str, ...] = ()) -> set[str]:
        if name in resolved:
            return set(resolved[name])
        if name in stack:
            return set()
        rendered = set(direct.get(name, set()))
        for helper in calls.get(name, set()):
            rendered.update(visit(helper, (*stack, name)))
        resolved[name] = rendered
        return set(rendered)

    for name in bodies:
        visit(name)
    return resolved


def javascript_case_rendered_identifiers(
    body: str,
    render_helpers: dict[str, set[str]],
) -> set[str]:
    """Find components rendered directly or through a local test helper."""
    rendered = set(JS_RENDER_COMPONENT_RE.findall(body))
    for helper, components in render_helpers.items():
        if re.search(rf"\b{re.escape(helper)}\s*\(", body):
            rendered.update(components)
    return rendered


def mask_javascript_noncode(content: str) -> str:
    """Mask strings/comments while preserving offsets and line boundaries."""
    return JS_NONCODE_RE.sub(
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
        content,
    )


def mask_javascript_comments(content: str) -> str:
    """Mask JS comments while preserving strings, offsets, and newlines."""
    chars = list(content)
    index = 0
    quote: str | None = None
    while index < len(chars):
        char = chars[index]
        next_char = chars[index + 1] if index + 1 < len(chars) else ""
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char == "/" and next_char == "/":
            while index < len(chars) and chars[index] != "\n":
                chars[index] = " "
                index += 1
            continue
        if char == "/" and next_char == "*":
            chars[index] = chars[index + 1] = " "
            index += 2
            while index < len(chars):
                if index + 1 < len(chars) and chars[index] == "*" and chars[index + 1] == "/":
                    chars[index] = chars[index + 1] = " "
                    index += 2
                    break
                if chars[index] != "\n":
                    chars[index] = " "
                index += 1
            continue
        index += 1
    return "".join(chars)


def javascript_position_is_code(content: str, position: int) -> bool:
    """Return whether an offset is outside a quoted JavaScript string."""
    quote: str | None = None
    index = 0
    while index < min(position, len(content)):
        char = content[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in {"'", '"', "`"}:
            quote = char
        index += 1
    return quote is None


def javascript_assertion_snippets(body: str, max_length: int = 2000) -> list[str]:
    """Extract bounded, balanced assertion calls without requiring a JS runtime."""
    masked = mask_javascript_noncode(body)
    starts = list(re.finditer(
        r"\b(?:expect(?:\.(?:poll|soft))?|assert(?:\.[A-Za-z_$][A-Za-z0-9_$]*)?)\s*\(",
        masked,
    ))
    snippets: list[str] = []
    for match in starts:
        open_paren = masked.find("(", match.start(), match.end())
        if open_paren < 0:
            continue
        depth = 0
        end = min(len(masked), open_paren + max_length)
        close_paren = None
        for index in range(open_paren, end):
            char = masked[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    close_paren = index
                    break
        if close_paren is None:
            continue
        assertion_name = masked[match.start():open_paren].strip()
        if assertion_name.startswith("expect"):
            suffix = masked[close_paren + 1:min(len(masked), close_paren + 501)]
            matcher = re.match(
                r"\s*(?:\.\s*(?:not|resolves|rejects)\s*)*"
                r"\.\s*to[A-Z][A-Za-z0-9_$]*\s*\(",
                suffix,
            )
            if matcher is None:
                continue
            matcher_open = close_paren + 1 + suffix.find("(", matcher.start(), matcher.end())
            matcher_depth = 0
            matcher_end = None
            for index in range(matcher_open, min(len(masked), matcher_open + max_length)):
                if masked[index] == "(":
                    matcher_depth += 1
                elif masked[index] == ")":
                    matcher_depth -= 1
                    if matcher_depth == 0:
                        matcher_end = index
                        break
            if matcher_end is None:
                continue
            snippets.append(body[match.start():matcher_end + 1])
        else:
            snippets.append(body[match.start():close_paren + 1])
    return snippets


def javascript_browser_targets(body: str, case_key: str) -> list[dict[str, Any]]:
    """Return literal browser targets plus a simple result binding when present."""
    targets: list[dict[str, Any]] = []
    searchable = mask_javascript_comments(body)
    matches = [
        match for match in BROWSER_TARGET_RE.finditer(searchable)
        if javascript_position_is_code(searchable, match.start())
    ]
    for index, match in enumerate(matches):
        statement_start = max(body.rfind("\n", 0, match.start()), body.rfind(";", 0, match.start())) + 1
        prefix = body[statement_start:match.start()]
        binding_match = re.search(
            r"(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:await\s*)?$",
            prefix,
        )
        targets.append({
            "id": f"target-{case_key}-{index + 1}",
            "receiver": match.group(1).lower(),
            "method": match.group(2).upper(),
            "target": match.group(4),
            "result_binding": binding_match.group(1) if binding_match else None,
            "machine_check_linked": False,
            "source_start": match.start(),
            "source_end": match.end(),
        })
    return targets


def javascript_machine_checks(
    body: str,
    targets: list[dict[str, Any]],
    browser_actions: list[str],
    uses_cdp: bool,
) -> list[dict[str, Any]]:
    """Find machine checks statically linked to a browser target or action.

    Generic assertions are deliberately excluded. A check must consume a
    request/action result, inspect the page/locator, or enforce a CDP failure
    condition. This keeps ``expect(true)`` from upgrading an unrelated journey.
    """
    checks: list[dict[str, Any]] = []
    cdp_bindings = {
        match.group(1)
        for match in re.finditer(
            r"(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
            r"(?:await\s*)?[^;\n]*?(?:newCDPSession|connectOverCDP)\s*\(",
            body,
        )
    }

    assertion_search_start = 0
    for assertion in javascript_assertion_snippets(body):
        assertion_start = body.find(assertion, assertion_search_start)
        if assertion_start < 0:
            assertion_start = body.find(assertion)
        assertion_start = max(assertion_start, 0)
        assertion_end = assertion_start + len(assertion)
        assertion_search_start = assertion_end
        eligible_targets = [
            target for target in targets
            if int(target.get("source_end", 0)) <= assertion_start
            or (
                int(target.get("source_start", -1)) >= assertion_start
                and int(target.get("source_end", 0)) <= assertion_end
            )
        ]
        line = mask_javascript_noncode(assertion).strip()
        target_ids = {
            str(target["id"])
            for target in eligible_targets
            if target.get("result_binding")
            and re.search(rf"\b{re.escape(str(target['result_binding']))}\b", line)
        }
        direct_target = next(
            (
                match for match in BROWSER_TARGET_RE.finditer(mask_javascript_comments(assertion))
                if javascript_position_is_code(assertion, match.start())
            ),
            None,
        )
        if direct_target:
            for target in eligible_targets:
                if (
                    target["receiver"] == direct_target.group(1).lower()
                    and target["method"] == direct_target.group(2).upper()
                    and target["target"] == direct_target.group(4)
                ):
                    target_ids.add(str(target["id"]))
        dom_check = bool(re.search(
            r"\b(?:page|locator)\b|\.getBy(?:Role|Text|Label|TestId|Placeholder|Title)\s*\(",
            line,
        ))
        if dom_check:
            # A page assertion observes the latest navigation state, not every
            # URL visited earlier in the case. Inline targets were already
            # linked above through ``direct_target``.
            preceding_page_targets = [
                target for target in eligible_targets
                if target.get("receiver") == "page"
                and int(target.get("source_end", 0)) <= assertion_start
            ]
            if preceding_page_targets:
                latest_page_target = max(
                    preceding_page_targets,
                    key=lambda target: int(target.get("source_end", 0)),
                )
                target_ids.add(str(latest_page_target["id"]))
        cdp_action_check = bool(
            uses_cdp
            and any(re.search(rf"\b{re.escape(binding)}\b", line) for binding in cdp_bindings)
        )
        if not target_ids and not dom_check and not cdp_action_check:
            continue
        kind = (
            "request-result" if target_ids and any(
                target["id"] in target_ids and target.get("receiver") == "request"
                for target in eligible_targets
            )
            else "dom-assertion" if dom_check
            else "cdp-action-result"
        )
        checks.append({
            "kind": kind,
            "expression": " ".join(assertion.split()),
            "target_ids": sorted(target_ids),
            "actions": sorted(set(browser_actions)) if dom_check or cdp_action_check else [],
            "source_start": assertion_start,
            "source_end": assertion_end,
        })

    if uses_cdp:
        for match in CDP_FAILURE_RE.finditer(mask_javascript_noncode(body)):
            expression = " ".join(match.group(0).split())
            checks.append({
                "kind": "cdp-pass-fail",
                "expression": expression,
                "target_ids": [
                    str(target["id"]) for target in targets
                    if int(target.get("source_end", 0)) <= match.start()
                ],
                "actions": sorted(set(browser_actions)),
                "source_start": match.start(),
                "source_end": match.end(),
            })

    unique: dict[tuple[str, str, tuple[str, ...], tuple[str, ...], int], dict[str, Any]] = {}
    for check in checks:
        key = (
            str(check["kind"]), str(check["expression"]),
            tuple(check["target_ids"]), tuple(check["actions"]), int(check["source_start"]),
        )
        unique[key] = check
    linked_target_ids = {
        target_id for check in unique.values() for target_id in check["target_ids"]
    }
    for target in targets:
        target["machine_check_linked"] = target["id"] in linked_target_ids
    return list(unique.values())


def safe_static_path(
    node: ast.AST,
    test_path: Path,
    path_values: dict[str, Path],
) -> Path | None:
    """Resolve a deliberately small subset of local Path expressions."""
    if isinstance(node, ast.Name):
        if node.id == "__file__":
            return test_path
        return path_values.get(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return Path(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = safe_static_path(node.left, test_path, path_values)
        if left is None or not isinstance(node.right, ast.Constant) or not isinstance(node.right.value, str):
            return None
        return left / node.right.value
    if isinstance(node, ast.Attribute):
        base = safe_static_path(node.value, test_path, path_values)
        if base is not None and node.attr == "parent":
            return base.parent
        return None
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
        base = safe_static_path(node.value.value, test_path, path_values)
        index = node.slice.value if isinstance(node.slice, ast.Constant) else None
        if base is not None and node.value.attr == "parents" and isinstance(index, int) and index >= 0:
            try:
                return base.parents[index]
            except IndexError:
                return None
    if isinstance(node, ast.Call):
        called = dotted_name(node.func)
        if called in {"Path", "pathlib.Path"} and len(node.args) == 1:
            return safe_static_path(node.args[0], test_path, path_values)
        if called == "str" and len(node.args) == 1:
            return safe_static_path(node.args[0], test_path, path_values)
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"resolve", "absolute"} and not node.args:
            base = safe_static_path(node.func.value, test_path, path_values)
            return base.resolve() if base is not None else None
    return None


def module_static_paths(tree: ast.Module, test_path: Path) -> dict[str, Path]:
    values: dict[str, Path] = {}
    for statement in tree.body:
        target: ast.Name | None = None
        value: ast.AST | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            target, value = statement.target, statement.value
        if target is None or value is None:
            continue
        resolved = safe_static_path(value, test_path, values)
        if resolved is not None:
            if not resolved.is_absolute():
                resolved = (test_path.parent / resolved).resolve()
            values[target.id] = resolved
    return values


def dynamic_module_paths(
    tree: ast.Module,
    test_path: Path,
    path_values: dict[str, Path],
) -> dict[str, Path]:
    specs: dict[str, Path] = {}
    modules: dict[str, Path] = {}
    for statement in tree.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name) or not isinstance(statement.value, ast.Call):
            continue
        called = dotted_name(statement.value.func)
        if called.endswith("spec_from_file_location") and len(statement.value.args) >= 2:
            resolved = safe_static_path(statement.value.args[1], test_path, path_values)
            if resolved is not None:
                specs[target.id] = resolved.resolve()
        elif called.endswith("module_from_spec") and statement.value.args:
            spec_arg = statement.value.args[0]
            if isinstance(spec_arg, ast.Name) and spec_arg.id in specs:
                modules[target.id] = specs[spec_arg.id]
    return modules


def static_argument(node: ast.AST, bindings: dict[str, str]) -> str | dict[str, str] | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool)):
        return str(node.value)
    if isinstance(node, ast.Name):
        return bindings.get(node.id, {"parameter": node.id})
    return None


def function_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    """Return nodes in one function body without descending into nested scopes."""
    nodes: list[ast.AST] = []
    pending = list(reversed(node.body))
    while pending:
        current = pending.pop()
        nodes.append(current)
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        pending.extend(reversed(list(ast.iter_child_nodes(current))))
    return nodes


def call_site(node: ast.Call) -> tuple[int, int]:
    return node.lineno, node.col_offset


def assertion_link_evidence(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[set[tuple[int, int]], set[str]]:
    """Find calls and identifiers consumed by a local assertion or raises block."""
    nodes = function_nodes(node)
    asserted_names: set[str] = set()
    linked_calls: set[tuple[int, int]] = set()

    def consume(expression: ast.AST) -> None:
        asserted_names.update(
            child.id for child in ast.walk(expression) if isinstance(child, ast.Name)
        )
        linked_calls.update(
            call_site(child) for child in ast.walk(expression) if isinstance(child, ast.Call)
        )

    for child in nodes:
        if isinstance(child, ast.Assert):
            consume(child.test)
        elif isinstance(child, ast.Call):
            called = dotted_name(child.func)
            if called.rsplit(".", 1)[-1].startswith("assert"):
                consume(child)
        elif isinstance(child, (ast.With, ast.AsyncWith)):
            has_raises_context = any(
                isinstance(item.context_expr, ast.Call)
                and dotted_name(item.context_expr.func).endswith(("pytest.raises", "raises"))
                for item in child.items
            )
            if has_raises_context:
                for statement in child.body:
                    consume(statement)

    assignments: list[tuple[set[str], ast.AST]] = []
    for child in nodes:
        if isinstance(child, ast.Assign):
            names = {
                target.id for target in child.targets if isinstance(target, ast.Name)
            }
            if names:
                assignments.append((names, child.value))
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name) and child.value:
            assignments.append(({child.target.id}, child.value))

    changed = True
    while changed:
        changed = False
        for names, value in assignments:
            if not names & asserted_names:
                continue
            before_names = len(asserted_names)
            before_calls = len(linked_calls)
            asserted_names.update(
                child.id for child in ast.walk(value) if isinstance(child, ast.Name)
            )
            linked_calls.update(
                call_site(child) for child in ast.walk(value) if isinstance(child, ast.Call)
            )
            changed = changed or before_names != len(asserted_names) or before_calls != len(linked_calls)
    linked_identifiers = set(asserted_names)
    for child in nodes:
        if not isinstance(child, ast.Call) or call_site(child) not in linked_calls:
            continue
        called = dotted_name(child.func)
        if called:
            linked_identifiers.add(called)
            linked_identifiers.add(called.split(".", 1)[0])
            linked_identifiers.add(called.rsplit(".", 1)[-1])
    return linked_calls, linked_identifiers


def assertion_linked_call_sites(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[tuple[int, int]]:
    """Return call locations whose values flow into an assertion."""
    return assertion_link_evidence(node)[0]


class FunctionStaticFacts(ast.NodeVisitor):
    """Collect calls from one function body without descending into nested defs."""

    def __init__(
        self,
        test_path: Path,
        path_values: dict[str, Path],
        module_paths: dict[str, Path],
        known_helpers: set[str],
        assertion_linked_calls: set[tuple[int, int]],
    ) -> None:
        self.test_path = test_path
        self.path_values = path_values
        self.module_paths = module_paths
        self.known_helpers = known_helpers
        self.assertion_linked_calls = assertion_linked_calls
        self.targets: list[dict[str, Any]] = []
        self.helpers: list[dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            module_path = self.module_paths.get(node.func.value.id)
            if module_path is not None:
                self.targets.append({
                    "path": str(module_path),
                    "symbols": [node.func.attr],
                    "argv": [],
                    "source": "dynamic-module",
                    "assertion_linked": call_site(node) in self.assertion_linked_calls,
                })

        called = dotted_name(node.func)
        if called == "subprocess.run" and node.args and isinstance(node.args[0], (ast.List, ast.Tuple)):
            command = list(node.args[0].elts)
            for index, item in enumerate(command):
                if isinstance(item, ast.Starred):
                    continue
                target = safe_static_path(item, self.test_path, self.path_values)
                if target is None or target.suffix.lower() != ".py":
                    continue
                if not target.is_absolute():
                    target = (self.test_path.parent / target).resolve()
                argv = [
                    value
                    for value in (
                        static_argument(arg, {})
                        for arg in command[index + 1:]
                        if not isinstance(arg, ast.Starred)
                    )
                    if value is not None
                ]
                self.targets.append({
                    "path": str(target.resolve()),
                    "symbols": [],
                    "argv": argv,
                    "source": "subprocess-entrypoint",
                    "assertion_linked": call_site(node) in self.assertion_linked_calls,
                })
                break

        helper_name = ""
        if isinstance(node.func, ast.Name):
            helper_name = node.func.id
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {"self", "cls"}
        ):
            helper_name = node.func.attr
        if helper_name in self.known_helpers:
            self.helpers.append({
                "name": helper_name,
                "args": [static_argument(arg, {}) for arg in node.args],
                "assertion_linked": call_site(node) in self.assertion_linked_calls,
            })
        self.generic_visit(node)


def function_target_calls(tree: ast.Module, test_path: Path) -> dict[str, list[dict[str, Any]]]:
    path_values = module_static_paths(tree, test_path)
    module_paths = dynamic_module_paths(tree, test_path, path_values)
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    summaries: dict[str, dict[str, Any]] = {}
    for name, node in functions.items():
        linked_calls, _ = assertion_link_evidence(node)
        visitor = FunctionStaticFacts(
            test_path,
            path_values,
            module_paths,
            set(functions),
            linked_calls,
        )
        for statement in node.body:
            visitor.visit(statement)
        parameters = [arg.arg for arg in node.args.args if arg.arg not in {"self", "cls"}]
        summaries[name] = {
            "parameters": parameters,
            "targets": visitor.targets,
            "helpers": visitor.helpers,
        }

    def resolve(
        name: str,
        bindings: dict[str, str],
        stack: tuple[str, ...] = (),
        inherited_assertion_link: bool = False,
    ) -> list[dict[str, Any]]:
        if name in stack or name not in summaries:
            return []
        summary = summaries[name]
        resolved: list[dict[str, Any]] = []
        for target in summary["targets"]:
            argv: list[str] = []
            for value in target.get("argv", []):
                if isinstance(value, dict) and value.get("parameter"):
                    bound = bindings.get(value["parameter"])
                    if bound is not None:
                        argv.append(bound)
                elif isinstance(value, str):
                    argv.append(value)
            resolved.append({
                **target,
                "argv": argv,
                "assertion_linked": bool(
                    inherited_assertion_link or target.get("assertion_linked")
                ),
            })
        for helper in summary["helpers"]:
            callee = summaries[helper["name"]]
            callee_bindings: dict[str, str] = {}
            for parameter, value in zip(callee["parameters"], helper["args"]):
                if isinstance(value, str):
                    callee_bindings[parameter] = value
                elif isinstance(value, dict) and value.get("parameter") in bindings:
                    callee_bindings[parameter] = bindings[value["parameter"]]
            resolved.extend(resolve(
                helper["name"],
                callee_bindings,
                (*stack, name),
                bool(inherited_assertion_link or helper.get("assertion_linked")),
            ))
        unique: dict[tuple[str, tuple[str, ...], tuple[str, ...], str], dict[str, Any]] = {}
        for item in resolved:
            key = (
                item["path"], tuple(item.get("symbols", [])),
                tuple(item.get("argv", [])), item.get("source", ""),
            )
            if key in unique:
                unique[key]["assertion_linked"] = bool(
                    unique[key].get("assertion_linked") or item.get("assertion_linked")
                )
            else:
                unique[key] = item
        return list(unique.values())

    return {name: resolve(name, {}) for name in functions}


def parse_python_test(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {
            "imports": [], "referenced_identifiers": [], "test_names": [],
            "scenario_names": [], "assertions": [], "disabled_tests": [],
            "test_cases": [], "has_active_test_with_assertion": False,
            "target_calls": [],
            "parse_warning": "python syntax could not be parsed",
        }

    imports: set[str] = set()
    identifiers: set[str] = set()
    import_aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
                if alias.asname:
                    import_aliases[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported = python_import_name(node, alias)
                if imported:
                    imports.add(imported)
                identifiers.add(alias.name)
                if alias.asname:
                    identifiers.add(alias.asname)
                    import_aliases[alias.asname] = alias.name
        elif isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)

    targets_by_function = function_target_calls(tree, path)
    test_cases: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test"):
            continue
        decorators = {
            dotted_name(item.func if isinstance(item, ast.Call) else item)
            for item in node.decorator_list
        }
        disabled = any(name.endswith(("skip", "skipif", "xfail")) for name in decorators)
        assertions: list[str] = []
        case_identifiers: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                case_identifiers.add(child.id)
            elif isinstance(child, ast.Attribute):
                case_identifiers.add(child.attr)
            elif isinstance(child, ast.Assert):
                assertions.append(f"assert at line {child.lineno}")
            elif isinstance(child, ast.Call):
                called = dotted_name(child.func)
                assert_method = called.rsplit(".", 1)[-1].startswith("assert")
                if called.endswith(("pytest.raises", "raises")) or assert_method:
                    assertions.append(f"{called} at line {child.lineno}")
                if called.endswith(("pytest.skip", "pytest.xfail")):
                    disabled = True
        for alias, original in import_aliases.items():
            if alias in case_identifiers:
                case_identifiers.add(original)
        _, linked_identifiers = assertion_link_evidence(node)
        for alias, original in import_aliases.items():
            for identifier in list(linked_identifiers):
                if identifier == alias or identifier.startswith(f"{alias}."):
                    linked_identifiers.add(f"{original}{identifier[len(alias):]}")
        test_cases.append({
            "name": node.name,
            "assertions": assertions,
            "disabled": disabled,
            "referenced_identifiers": sorted(case_identifiers),
            "assertion_linked_identifiers": sorted(linked_identifiers),
            "target_calls": targets_by_function.get(node.name, []),
        })

    test_names = sorted({case["name"] for case in test_cases})
    disabled_tests = sorted(case["name"] for case in test_cases if case["disabled"])
    assertions = [item for case in test_cases for item in case["assertions"]]
    return {
        "imports": sorted(item for item in imports if item),
        "referenced_identifiers": sorted(identifiers),
        "test_names": test_names,
        "scenario_names": test_names,
        "assertions": assertions,
        "disabled_tests": disabled_tests,
        "test_cases": test_cases,
        "target_calls": [
            target for case in test_cases for target in case.get("target_calls", [])
        ],
        "has_active_test_with_assertion": any(
            not case["disabled"] and bool(case["assertions"])
            for case in test_cases
        ),
    }


def parse_javascript_test(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    test_matches = list(JS_TEST_RE.finditer(content))
    import_aliases = javascript_import_aliases(content)
    render_helpers = javascript_render_helpers(content)
    executable_code = JS_NONCODE_RE.sub(" ", content)
    test_names = sorted({match.group(3) for match in test_matches if match.group(1) in {"test", "it"}})
    scenario_names = sorted({match.group(3) for match in test_matches})
    disabled_suite_ranges = [
        js_test_body_range(content, match.end())
        for match in test_matches
        if match.group(1) == "describe" and match.group(2) in {"skip", "todo", "fixme"}
    ]
    test_cases: list[dict[str, Any]] = []

    def browser_case(
        name: str,
        body: str,
        *,
        case_index: int,
        disabled: bool,
    ) -> dict[str, Any]:
        executable_body = JS_NONCODE_RE.sub(" ", body)
        case_identifiers = set(JS_IDENTIFIER_RE.findall(executable_body))
        for alias, original in import_aliases.items():
            if alias in case_identifiers:
                case_identifiers.add(original)
        assertion_snippets = javascript_assertion_snippets(body)
        case_assertions = [
            f"{snippet.split('(', 1)[0].strip()} in {name}"
            for snippet in assertion_snippets
        ]
        browser_actions = [item.group(1) for item in PLAYWRIGHT_ACTION_RE.finditer(executable_body)]
        browser_observations = [
            item.group(1) for item in PLAYWRIGHT_OBSERVATION_RE.finditer(executable_body)
        ]
        uses_cdp = bool(CDP_RE.search(executable_body))
        case_key = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower() or "scenario"
        case_key = f"{case_index}-{case_key}"
        browser_targets = javascript_browser_targets(body, case_key)
        machine_checks = javascript_machine_checks(
            body, browser_targets, browser_actions, uses_cdp,
        )
        assertion_linked_identifiers: set[str] = set()
        for assertion in assertion_snippets:
            assertion_linked_identifiers.update(
                JS_IDENTIFIER_RE.findall(mask_javascript_noncode(assertion))
            )
        rendered_identifiers = javascript_case_rendered_identifiers(body, render_helpers)
        if any(JS_DOM_ASSERTION_RE.search(assertion) for assertion in assertion_snippets):
            assertion_linked_identifiers.update(rendered_identifiers)
        assignments: list[tuple[str, str]] = []
        for raw_line in body.splitlines():
            assignment = re.search(
                r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(.+)$",
                JS_NONCODE_RE.sub(" ", raw_line),
            )
            if assignment:
                assignments.append((assignment.group(1), assignment.group(2)))
        changed = True
        while changed:
            changed = False
            for binding, expression in assignments:
                if binding not in assertion_linked_identifiers:
                    continue
                before = len(assertion_linked_identifiers)
                assertion_linked_identifiers.update(JS_IDENTIFIER_RE.findall(expression))
                changed = changed or len(assertion_linked_identifiers) != before
        for alias, original in import_aliases.items():
            if alias in assertion_linked_identifiers:
                assertion_linked_identifiers.add(original)
        if any(check["kind"] == "cdp-pass-fail" for check in machine_checks):
            case_assertions.append(f"explicit CDP pass/fail condition in {name}")
        return {
            "name": name,
            "assertions": case_assertions,
            "disabled": disabled,
            "referenced_identifiers": sorted(case_identifiers),
            "assertion_linked_identifiers": sorted(assertion_linked_identifiers),
            "rendered_identifiers": sorted(rendered_identifiers),
            "browser_actions": sorted(browser_actions),
            "browser_observations": sorted(browser_observations),
            "uses_cdp": uses_cdp,
            "browser_targets": browser_targets,
            "machine_checks": machine_checks,
            "has_machine_check": bool(machine_checks),
        }

    for case_index, match in enumerate(test_matches, start=1):
        if match.group(1) not in {"test", "it"}:
            continue
        body = js_test_body(content, match.end())
        test_cases.append(browser_case(
            match.group(3),
            body,
            case_index=case_index,
            disabled=match.group(2) in {"skip", "todo", "fixme"} or any(
                start <= match.start() <= end for start, end in disabled_suite_ranges
            ),
        ))

    # Standalone CDP diagnostics often export a probe function instead of using
    # a test runner. Preserve them as one explicit scenario and require a real
    # failure condition before claiming a machine check.
    standalone_browser_scenario = not test_cases and bool(CDP_RE.search(executable_code))
    if standalone_browser_scenario:
        test_cases.append(browser_case("standalone-cdp", content, case_index=1, disabled=False))
        scenario_names = ["standalone-cdp"]
    assertions = [item for case in test_cases for item in case["assertions"]]
    disabled = {case["name"] for case in test_cases if case["disabled"]}
    imports = sorted(set(JS_IMPORT_RE.findall(content)))
    uses_cdp = bool(CDP_RE.search(executable_code))
    uses_playwright = any("playwright" in item.lower() for item in imports) or bool(
        PLAYWRIGHT_TEST_FIXTURE_RE.search(executable_code)
    )
    browser_framework = "cdp" if uses_cdp else "playwright" if uses_playwright else None
    return {
        "imports": imports,
        "referenced_identifiers": sorted(set(JS_IDENTIFIER_RE.findall(executable_code))),
        "test_names": test_names,
        "scenario_names": scenario_names,
        "assertions": assertions,
        "disabled_tests": sorted(disabled),
        "test_cases": test_cases,
        "browser_framework": browser_framework,
        "standalone_browser_scenario": standalone_browser_scenario,
        "uses_cdp": uses_cdp,
        "browser_actions": sorted({
            action for case in test_cases for action in case.get("browser_actions", [])
        }),
        "browser_observations": sorted({
            observation
            for case in test_cases
            for observation in case.get("browser_observations", [])
        }),
        "browser_targets": [
            {**target, "case_name": case["name"]}
            for case in test_cases
            for target in case.get("browser_targets", [])
        ],
        "browser_machine_checks": [
            {**check, "case_name": case["name"]}
            for case in test_cases
            for check in case.get("machine_checks", [])
        ],
        "browser_scenario_has_machine_check": any(
            not case["disabled"] and case.get("has_machine_check")
            for case in test_cases
        ),
        "has_active_test_with_assertion": any(
            not case["disabled"] and bool(case["assertions"])
            for case in test_cases
        ),
    }


def parse_test_file(path: Path) -> dict[str, Any]:
    facts = parse_python_test(path) if path.suffix == ".py" else parse_javascript_test(path)
    facts["has_assertions"] = bool(facts["assertions"])
    facts["has_disabled_tests"] = bool(facts["disabled_tests"])
    facts.setdefault("has_active_test_with_assertion", False)
    return facts


def classify_test_candidate(path: Path, facts: dict[str, Any]) -> str:
    """Require parsed test cases before a test-like filename becomes evidence."""
    if facts.get("standalone_browser_scenario"):
        return "browser-scenario"
    if facts.get("test_cases"):
        if path.suffix != ".py":
            return "test-file"
        in_test_directory = any(
            part.lower() in {"test", "tests", "__tests__"}
            for part in path.parts[:-1]
        )
        imported_roots = {
            value.lstrip(".").split(".", 1)[0]
            for value in facts.get("imports", [])
        }
        if in_test_directory or facts.get("has_assertions") or imported_roots & {"pytest", "unittest"}:
            return "test-file"
    if facts.get("parse_warning"):
        return "test-candidate"
    if facts.get("uses_cdp"):
        return "browser-scenario"
    return "not-a-test"


def javascript_framework(facts: dict[str, Any]) -> str:
    browser_framework = facts.get("browser_framework")
    if browser_framework:
        return str(browser_framework)
    imports = {str(item).lower() for item in facts.get("imports", [])}
    if any("vitest" in item for item in imports):
        return "vitest"
    if any("jest" in item for item in imports):
        return "jest"
    return "js-test-runner"


def discover_test_assets(
    repositories: list[dict[str, Any]],
    is_ignored: Callable[[str], bool],
    scan_warnings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    repository_roots = {Path(item["path"]).resolve() for item in repositories}
    for repo_info in repositories:
        repo = Path(repo_info["path"]).resolve()
        repo_rel = repo_info["relative_path"]
        nested_repositories = repository_roots - {repo}

        def workspace_path(path: Path) -> str:
            local = path.relative_to(repo).as_posix()
            return local if repo_rel == "." else f"{repo_rel}/{local}"

        test_dirs: set[str] = set()
        skipped: list[dict[str, str]] = []
        for path in iter_repo_files(repo, nested_repositories, skipped):
            local = path.relative_to(repo).as_posix()
            output_path = workspace_path(path)
            browser_candidate = (
                path.suffix.lower() in BROWSER_SOURCE_SUFFIXES
                and any(part.lower() in {"e2e", "test", "tests"} for part in path.parts[:-1])
            )
            if is_ignored(output_path) or not (TEST_FILE_RE.search(local) or browser_candidate):
                continue
            facts = parse_test_file(path)
            asset_kind = classify_test_candidate(path, facts)
            if asset_kind == "not-a-test":
                continue
            test_type, reason = asset_type_for_path(local)
            if asset_kind in {"test-file", "browser-scenario"}:
                test_dirs.add(workspace_path(path.parent))
            assets.append({
                "id": f"discovered:{output_path}", "repo": repo_info["name"],
                "path": output_path, "asset_kind": asset_kind, "type": test_type,
                "framework": "pytest" if path.suffix == ".py" else javascript_framework(facts),
                "discovery_source": "filesystem",
                "reason": (
                    reason
                    if asset_kind == "test-file"
                    else "CDP browser scenario discovered by static API usage"
                    if asset_kind == "browser-scenario"
                    else "test-like filename could not be parsed into executable test cases"
                ),
                "test_facts": facts,
            })

        if scan_warnings is not None:
            scan_warnings.extend({
                "repo": repo_info["name"],
                "path": redact_text(
                    item["path"] if repo_rel == "." else f"{repo_rel}/{item['path']}"
                ),
                "reason": item["reason"],
            } for item in skipped)

        config_candidates = {
            "pytest.ini": ("pytest-config", "unit"), "tox.ini": ("pytest-config", "unit"),
            "playwright.config.ts": ("playwright-config", "frontend-smoke"),
            "playwright.config.js": ("playwright-config", "frontend-smoke"),
            "vitest.config.ts": ("vitest-config", "unit"),
            "vitest.config.js": ("vitest-config", "unit"),
            "jest.config.ts": ("jest-config", "unit"), "jest.config.js": ("jest-config", "unit"),
        }
        for name, (kind, test_type) in config_candidates.items():
            path = repo / name
            safe_path, _ = safe_repository_file(path, repo)
            if safe_path is not None:
                assets.append({
                    "id": f"discovered:{workspace_path(safe_path)}", "repo": repo_info["name"],
                    "path": workspace_path(safe_path), "asset_kind": kind, "type": test_type,
                    "framework": kind.removesuffix("-config"), "discovery_source": "filesystem",
                    "reason": f"found {name}",
                })

        pyproject = repo / "pyproject.toml"
        safe_pyproject, _ = safe_repository_file(pyproject, repo)
        if (
            safe_pyproject is not None
            and "pytest" in safe_pyproject.read_text(encoding="utf-8", errors="ignore").lower()
        ):
            assets.append({
                "id": f"discovered:{workspace_path(safe_pyproject)}:pytest", "repo": repo_info["name"],
                "path": workspace_path(safe_pyproject), "asset_kind": "pytest-config", "type": "unit",
                "framework": "pytest", "discovery_source": "config-inspection",
                "reason": "pyproject.toml declares pytest configuration or dependency",
                "command_hint": "uv run pytest",
            })

        package_json = repo / "package.json"
        safe_package_json, _ = safe_repository_file(package_json, repo)
        if safe_package_json is not None:
            try:
                package = json.loads(safe_package_json.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                package = {}
            for name, command in package.get("scripts", {}).items():
                if "test" not in name.lower() and not any(tool in str(command).lower() for tool in ("vitest", "jest", "playwright")):
                    continue
                test_type = "frontend-smoke" if "playwright" in str(command).lower() or "e2e" in name.lower() else "unit"
                assets.append({
                    "id": f"discovered:{workspace_path(safe_package_json)}:script:{name}",
                    "repo": repo_info["name"], "path": workspace_path(safe_package_json),
                    "asset_kind": "test-command", "type": test_type, "framework": "package-script",
                    "discovery_source": "config-inspection", "reason": f"package.json script {name!r}",
                    "command_hint": f"pnpm run {name}",
                })

        for directory in sorted(test_dirs):
            assets.append({
                "id": f"discovered:{directory}:directory", "repo": repo_info["name"],
                "path": directory, "asset_kind": "test-directory", "type": "mixed",
                "framework": None, "discovery_source": "derived-from-test-files",
                "reason": "contains at least one concrete test file",
            })
    return sorted({asset["id"]: asset for asset in assets}.values(), key=lambda item: (item["repo"], item["path"], item["id"]))
