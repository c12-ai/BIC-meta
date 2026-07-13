#!/usr/bin/env python3
"""Deterministic, read-only test asset discovery and content parsing."""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Iterable


DISCOVERY_EXCLUDES = {
    ".agents", ".claude", ".codex", ".git", ".trellis", ".venv",
    "node_modules", "__pycache__", ".pytest_cache", ".pnpm-store",
    "artifacts",
}
TEST_FILE_RE = re.compile(
    r"(^|/)(test_[^/]+\.py|[^/]+_test\.py|[^/]+\.(test|spec)\.[^.\/]+)$",
    re.IGNORECASE,
)
JS_IMPORT_RE = re.compile(
    r"(?:import\s+(?:type\s+)?(?:[^;]*?\s+from\s+)?|require\s*\()"
    r"['\"]([^'\"]+)['\"]"
)
JS_TEST_RE = re.compile(
    r"\b(describe|test|it)(?:\.(skip|todo|only))?\s*\(\s*['\"]([^'\"]+)['\"]"
)
JS_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")
JS_NAMED_IMPORT_RE = re.compile(
    r"import\s+(?:type\s+)?\{(?P<names>[^}]*)\}\s+from",
    re.DOTALL,
)
JS_NONCODE_RE = re.compile(
    r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`"
    r"|//[^\n]*|/\*.*?\*/",
    re.DOTALL,
)


def iter_repo_files(repo: Path, excluded_roots: Iterable[Path] = ()) -> Iterable[Path]:
    excluded = {path.resolve() for path in excluded_roots}
    for root, dirs, files in os.walk(repo):
        root_path = Path(root)
        dirs[:] = [
            name for name in dirs
            if name not in DISCOVERY_EXCLUDES
            and not name.startswith(".git")
            and (root_path / name).resolve() not in excluded
        ]
        for filename in files:
            yield root_path / filename


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


def js_test_body_range(content: str, start: int) -> tuple[int, int]:
    """Locate a best-effort callback body for one JS test declaration."""
    open_brace = content.find("{", start)
    next_declaration = JS_TEST_RE.search(content, start)
    if open_brace < 0 or (next_declaration and next_declaration.start() < open_brace):
        line_end = content.find("\n", start)
        end = line_end if line_end >= 0 else len(content)
        return start, end
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


def js_test_body(content: str, start: int) -> str:
    body_start, body_end = js_test_body_range(content, start)
    return content[body_start:body_end]


def parse_python_test(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {
            "imports": [], "referenced_identifiers": [], "test_names": [],
            "scenario_names": [], "assertions": [], "disabled_tests": [],
            "test_cases": [], "has_active_test_with_assertion": False,
            "parse_warning": "python syntax could not be parsed",
        }

    imports: set[str] = set()
    identifiers: set[str] = set()
    import_aliases: dict[str, str] = {}
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
                    import_aliases[alias.asname] = alias.name
        elif isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)

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
        test_cases.append({
            "name": node.name,
            "assertions": assertions,
            "disabled": disabled,
            "referenced_identifiers": sorted(case_identifiers),
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
        "has_active_test_with_assertion": any(
            not case["disabled"] and bool(case["assertions"])
            for case in test_cases
        ),
    }


def parse_javascript_test(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    test_matches = list(JS_TEST_RE.finditer(content))
    import_aliases = javascript_import_aliases(content)
    executable_code = JS_NONCODE_RE.sub(" ", content)
    test_names = sorted({match.group(3) for match in test_matches if match.group(1) in {"test", "it"}})
    scenario_names = sorted({match.group(3) for match in test_matches})
    disabled_suite_ranges = [
        js_test_body_range(content, match.end())
        for match in test_matches
        if match.group(1) == "describe" and match.group(2) in {"skip", "todo"}
    ]
    test_cases: list[dict[str, Any]] = []
    for match in test_matches:
        if match.group(1) not in {"test", "it"}:
            continue
        body = js_test_body(content, match.end())
        executable_body = JS_NONCODE_RE.sub(" ", body)
        case_identifiers = set(JS_IDENTIFIER_RE.findall(executable_body))
        for alias, original in import_aliases.items():
            if alias in case_identifiers:
                case_identifiers.add(original)
        case_assertions = [
            f"{item.group(1)} in {match.group(3)}"
            for item in re.finditer(
                r"\b(expect|assert(?:\.[A-Za-z_$][A-Za-z0-9_$]*)?)\s*\(",
                executable_body,
            )
        ]
        test_cases.append({
            "name": match.group(3),
            "assertions": case_assertions,
            "disabled": match.group(2) in {"skip", "todo"} or any(
                start <= match.start() <= end for start, end in disabled_suite_ranges
            ),
            "referenced_identifiers": sorted(case_identifiers),
        })
    assertions = [item for case in test_cases for item in case["assertions"]]
    disabled = {case["name"] for case in test_cases if case["disabled"]}
    return {
        "imports": sorted(set(JS_IMPORT_RE.findall(content))),
        "referenced_identifiers": sorted(set(JS_IDENTIFIER_RE.findall(executable_code))),
        "test_names": test_names,
        "scenario_names": scenario_names,
        "assertions": assertions,
        "disabled_tests": sorted(disabled),
        "test_cases": test_cases,
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
    return "not-a-test"


def discover_test_assets(
    repositories: list[dict[str, Any]],
    is_ignored: Callable[[str], bool],
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
        for path in iter_repo_files(repo, nested_repositories):
            local = path.relative_to(repo).as_posix()
            output_path = workspace_path(path)
            if is_ignored(output_path) or not TEST_FILE_RE.search(local):
                continue
            facts = parse_test_file(path)
            asset_kind = classify_test_candidate(path, facts)
            if asset_kind == "not-a-test":
                continue
            test_type, reason = asset_type_for_path(local)
            if asset_kind == "test-file":
                test_dirs.add(workspace_path(path.parent))
            assets.append({
                "id": f"discovered:{output_path}", "repo": repo_info["name"],
                "path": output_path, "asset_kind": asset_kind, "type": test_type,
                "framework": "pytest" if path.suffix == ".py" else "js-test-runner",
                "discovery_source": "filesystem",
                "reason": reason if asset_kind == "test-file" else "test-like filename could not be parsed into executable test cases",
                "test_facts": facts,
            })

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
            if path.is_file():
                assets.append({
                    "id": f"discovered:{workspace_path(path)}", "repo": repo_info["name"],
                    "path": workspace_path(path), "asset_kind": kind, "type": test_type,
                    "framework": kind.removesuffix("-config"), "discovery_source": "filesystem",
                    "reason": f"found {name}",
                })

        pyproject = repo / "pyproject.toml"
        if pyproject.is_file() and "pytest" in pyproject.read_text(encoding="utf-8", errors="ignore").lower():
            assets.append({
                "id": f"discovered:{workspace_path(pyproject)}:pytest", "repo": repo_info["name"],
                "path": workspace_path(pyproject), "asset_kind": "pytest-config", "type": "unit",
                "framework": "pytest", "discovery_source": "config-inspection",
                "reason": "pyproject.toml declares pytest configuration or dependency",
                "command_hint": "uv run pytest",
            })

        package_json = repo / "package.json"
        if package_json.is_file():
            try:
                package = json.loads(package_json.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                package = {}
            for name, command in package.get("scripts", {}).items():
                if "test" not in name.lower() and not any(tool in str(command).lower() for tool in ("vitest", "jest", "playwright")):
                    continue
                test_type = "frontend-smoke" if "playwright" in str(command).lower() or "e2e" in name.lower() else "unit"
                assets.append({
                    "id": f"discovered:{workspace_path(package_json)}:script:{name}",
                    "repo": repo_info["name"], "path": workspace_path(package_json),
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
