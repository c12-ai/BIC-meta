#!/usr/bin/env python3
"""Execute a frozen behavior-scoped BIC test manifest in framework layers."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from content_safety import sanitize_for_output
from execution_manifest import repository_records, workspace_fingerprint
from runtime_readiness import (
    SETUP_COMMAND,
    is_runtime_setup_error,
    playwright_browser_status,
)


FOUNDATION_LAYERS = {"backend", "frontend"}
LAYER_ORDER = ("backend", "frontend", "browser", "browser-diagnostic")
ALLOWED_PREFIXES = {
    "pytest": ("uv", "run", "--no-sync", "pytest"),
    "vitest": ("node", "node_modules/vitest/vitest.mjs"),
    "playwright": ("node", "node_modules/@playwright/test/cli.js"),
    "cdp": ("npm", "run", "--silent"),
}
SKIPPED_RE = re.compile(
    r"\b[1-9]\d*\s+(?:skipped|skip|pending)\b",
    re.IGNORECASE,
)
PASSED_RE = re.compile(
    r"\b[1-9]\d*\s+passed\b",
    re.IGNORECASE,
)
NO_TESTS_RE = re.compile(
    r"\b(?:no tests (?:ran|found|collected)|collected 0 items)\b",
    re.IGNORECASE,
)
MAX_CAPTURE_CHARS = 20_000


def load_manifest(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    manifest = payload.get("test_execution_manifest", payload)
    if not isinstance(manifest, dict):
        raise ValueError("assessment does not contain a test_execution_manifest object")
    if manifest.get("schema_version") != 2:
        raise ValueError(
            "phase 2 requires test_execution_manifest schema_version 2"
        )
    return payload, manifest


def repo_roots(
    manifest: dict[str, Any],
    workspace_root: Path,
) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    workspace = workspace_root.resolve()
    for item in manifest.get("repositories", []):
        repo = str(item.get("repo") or "")
        relative = str(item.get("relative_path") or ".")
        root = (workspace / relative).resolve()
        if root != workspace and workspace not in root.parents:
            raise ValueError(f"repository path leaves workspace: {relative}")
        roots[repo] = root
    return roots


def has_symlink_component(path: Path, repository_root: Path) -> bool:
    current = repository_root
    try:
        relative = path.relative_to(repository_root)
    except ValueError:
        return True
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def validate_candidate(
    candidate: dict[str, Any],
    roots: dict[str, Path],
) -> tuple[Path | None, str | None]:
    repo = str(candidate.get("repo") or "")
    root = roots.get(repo)
    if root is None:
        return None, f"unknown repository {repo!r}"
    workspace_path = str(candidate.get("path") or "")
    prefix = f"{repo}/"
    local_path = (
        workspace_path[len(prefix):]
        if workspace_path.startswith(prefix) else workspace_path
    )
    if not local_path or Path(local_path).is_absolute():
        return None, "test path is empty or absolute"
    test_path = root / local_path
    resolved = test_path.resolve()
    if resolved != root and root not in resolved.parents:
        return None, "test path leaves its repository"
    if has_symlink_component(test_path, root):
        return None, "test path contains a symbolic link"
    if not test_path.is_file():
        return None, "test file does not exist"

    argv = candidate.get("command_argv")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(value, str) and value for value in argv)
    ):
        return None, "structured command argv is missing or invalid"
    framework = str(candidate.get("framework") or "")
    allowed = ALLOWED_PREFIXES.get(framework)
    if allowed is None or tuple(argv[:len(allowed)]) != allowed:
        return None, f"command argv is not allowed for {framework or 'unknown framework'}"
    case_name = str(candidate.get("test_case") or "")
    selector = str(candidate.get("test_selector") or case_name)
    if not case_name:
        return None, "manifest test case is missing"
    if framework == "pytest":
        expected = [
            "uv", "run", "--no-sync", "pytest",
            f"{local_path}::{selector}", "-q",
        ]
        if argv != expected:
            return None, "pytest argv does not exactly select the manifest test case"
        if not (root / ".venv/bin/pytest").is_file():
            return None, "pytest environment is missing; phase 2 will not install dependencies"
    elif framework == "vitest":
        expected = [
            "node", "node_modules/vitest/vitest.mjs", "run", local_path,
            "-t", f"^{re.escape(selector)}$",
        ]
        if argv != expected:
            return None, "Vitest argv does not exactly select the manifest test case"
        if not (root / "node_modules/vitest/vitest.mjs").is_file():
            return None, "Vitest dependency is missing; phase 2 will not install dependencies"
    elif framework == "playwright":
        location = str(candidate.get("test_selector") or "")
        expected = [
            "node", "node_modules/@playwright/test/cli.js", "test",
            location, "--workers=1",
        ]
        if (
            argv != expected
            or re.fullmatch(rf"{re.escape(local_path)}:[1-9]\d*", location) is None
        ):
            return None, "Playwright argv does not exactly select the manifest test case"
        if not (root / "node_modules/@playwright/test/cli.js").is_file():
            return None, "Playwright dependency is missing; phase 2 will not install dependencies"
        browser_ready, browser_detail = playwright_browser_status(str(root))
        if not browser_ready:
            return None, (
                f"{browser_detail or 'Playwright browser executable is missing'}; "
                "phase 2 will not install dependencies"
            )
    elif framework == "cdp":
        if len(argv) != 4 or not re.fullmatch(r"[A-Za-z0-9:_-]+", argv[3]):
            return None, "CDP argv must select one repository-owned CDP package script"
        package_path = root / "package.json"
        if not package_path.is_file() or package_path.is_symlink():
            return None, "repository package.json for the CDP command is unavailable"
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, "repository package.json for the CDP command is invalid"
        script_value = package.get("scripts", {}).get(argv[3])
        if not isinstance(script_value, str):
            return None, "CDP package script is no longer configured"
        if "cdp" not in f"{argv[3]} {script_value}".lower():
            return None, "configured package script is not a CDP diagnostic"
        if re.search(
            r"\b(?:pnpm|npm|yarn|npx|bunx)\s+(?:install|add|i|dlx)\b",
            script_value,
            re.IGNORECASE,
        ):
            return None, "CDP package script may install dependencies"
    if shutil.which(argv[0]) is None:
        return None, f"required executable {argv[0]!r} is not installed"
    return root, None


def recompute_fingerprint(
    manifest: dict[str, Any],
    workspace_root: Path,
) -> str:
    os.environ["BIC_WORKSPACE_ROOT"] = str(workspace_root.resolve())
    import quality_context

    quality_context.WORKSPACE_ROOT = workspace_root.resolve()
    context = quality_context.collect_context(
        manifest.get("requested_base_ref"),
        manifest.get("analysis_mode") == "worktree-only",
        collect_issues=False,
    )
    return workspace_fingerprint(repository_records(context))


def command_status(returncode: int, stdout: str, stderr: str) -> str:
    combined = f"{stdout}\n{stderr}"
    if returncode != 0:
        return "blocked" if NO_TESTS_RE.search(combined) else "failed"
    if PASSED_RE.search(combined):
        return "passed"
    if SKIPPED_RE.search(combined):
        return "skipped"
    return "passed"


def truncate(value: str) -> str:
    if len(value) <= MAX_CAPTURE_CHARS:
        return value
    return f"{value[:MAX_CAPTURE_CHARS]}\n... output truncated ..."


def run_command(
    argv: list[str],
    cwd: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        process = subprocess.run(
            argv,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "returncode": None,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout": truncate(str(exc.stdout or "")),
            "stderr": truncate(str(exc.stderr or "")),
            "failure_reason": f"test command timed out after {timeout_seconds} seconds",
        }
    return {
        "status": command_status(
            process.returncode, process.stdout, process.stderr,
        ),
        "returncode": process.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout": truncate(process.stdout),
        "stderr": truncate(process.stderr),
        "failure_reason": (
            None if process.returncode == 0
            else f"test command exited with {process.returncode}"
        ),
    }


def blocked_result(
    candidate: dict[str, Any],
    status: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "repo": candidate.get("repo"),
        "path": candidate.get("path"),
        "framework": candidate.get("framework"),
        "execution_layer": candidate.get("execution_layer"),
        "test_case": candidate.get("test_case"),
        "changed_behaviors": candidate.get("changed_behaviors", []),
        "selection_tier": candidate.get("selection_tier"),
        "intended_tier": candidate.get("intended_tier"),
        "required": bool(candidate.get("required")),
        "command_argv": candidate.get("command_argv"),
        "status": status,
        "returncode": None,
        "duration_seconds": 0,
        "stdout": "",
        "stderr": "",
        "failure_reason": reason,
    }


def behavior_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        for behavior in result.get("changed_behaviors", []):
            grouped[str(behavior)].append(result)
    records: list[dict[str, Any]] = []
    for behavior, items in sorted(grouped.items()):
        statuses = {str(item.get("status")) for item in items}
        if "failed" in statuses:
            verdict = "failed"
        elif statuses == {"passed"}:
            verdict = "passed"
        else:
            verdict = "incomplete"
        records.append({
            "changed_behavior": behavior,
            "verdict": verdict,
            "tests": [
                {
                    "repo": item.get("repo"),
                    "path": item.get("path"),
                    "test_case": item.get("test_case"),
                    "framework": item.get("framework"),
                    "status": item.get("status"),
                }
                for item in items
            ],
        })
    return records


def conclusion_for(
    must_results: list[dict[str, Any]],
    executed_results: list[dict[str, Any]],
) -> tuple[str, str]:
    statuses = Counter(str(item.get("status")) for item in must_results)
    if statuses["failed"]:
        return (
            "failed",
            "发现必须执行的测试失败，不能判断本次变更大概率正常。",
        )
    if not must_results:
        return (
            "incomplete",
            "没有可执行的必须测试，暂时不能形成测试后的质量结论。",
        )
    if any(statuses[value] for value in ("skipped", "blocked", "not-run")):
        return (
            "incomplete",
            "必须测试存在跳过、阻塞或未执行项，暂时不能形成完整结论。",
        )
    if any(item.get("status") == "failed" for item in executed_results):
        return (
            "failed",
            "执行的补充回归测试发现失败，不能判断本次变更大概率正常。",
        )
    return (
        "passed",
        "本次选中的后端、前端和浏览器行为测试均已执行通过；"
        "在本次测试覆盖范围内未发现明显问题。",
    )


def build_execution_report(
    manifest: dict[str, Any],
    results: list[dict[str, Any]],
    *,
    expected_fingerprint: str,
    current_fingerprint: str,
    include_recommended: bool,
    runtime_readiness: dict[str, Any],
    conclusion_override: str | None = None,
) -> dict[str, Any]:
    must_results = [
        result for result in results
        if result.get("selection_tier") == "must-run" or result.get("required")
    ]
    status, conclusion = conclusion_for(must_results, results)
    layer_summary = {
        layer: dict(Counter(
            str(result.get("status"))
            for result in results
            if result.get("execution_layer") == layer
        ))
        for layer in LAYER_ORDER
    }
    return {
        "schema_version": 1,
        "execution_status": status,
        "workspace_change_fingerprint": expected_fingerprint,
        "current_workspace_change_fingerprint": current_fingerprint,
        "include_recommended": include_recommended,
        "layer_order": list(LAYER_ORDER),
        "layer_summary": layer_summary,
        "result_counts": dict(Counter(
            str(result.get("status")) for result in results
        )),
        "results": results,
        "behavior_results": behavior_results(results),
        "not_runnable": manifest.get("not_runnable", []),
        "runtime_readiness": runtime_readiness,
        "final_conclusion": conclusion_override or conclusion,
        "boundary_note": (
            "Phase 2 did not install dependencies, start the live bench, reset "
            "data, invoke bic-e2e-runner, or query Phoenix."
        ),
    }


def execute_manifest(
    manifest: dict[str, Any],
    workspace_root: Path,
    *,
    include_recommended: bool = False,
    timeout_seconds: int = 600,
    verify_fingerprint: bool = True,
    command_runner: Callable[[list[str], Path, int], dict[str, Any]] = run_command,
) -> dict[str, Any]:
    workspace = workspace_root.resolve()
    expected_fingerprint = str(
        manifest.get("workspace_change_fingerprint") or ""
    )
    if verify_fingerprint:
        current_fingerprint = recompute_fingerprint(manifest, workspace)
        if current_fingerprint != expected_fingerprint:
            return {
                "schema_version": 1,
                "execution_status": "blocked",
                "workspace_change_fingerprint": expected_fingerprint,
                "current_workspace_change_fingerprint": current_fingerprint,
                "results": [],
                "behavior_results": [],
                "runtime_readiness": {
                    "ready": False,
                    "checked": False,
                    "missing": [],
                    "user_confirmation_required": False,
                    "setup_command": None,
                },
                "final_conclusion": (
                    "工作区代码已经变化，第二阶段拒绝执行；请重新运行第一阶段。"
                ),
            }
    else:
        current_fingerprint = expected_fingerprint

    roots = repo_roots(manifest, workspace)
    candidates = list(manifest.get("must_run", []))
    if include_recommended:
        candidates.extend(manifest.get("recommended", []))
    blocking_unresolved = [
        item
        for item in manifest.get("not_runnable", [])
        if item.get("required") or item.get("intended_tier") == "must-run"
    ]
    results = [
        blocked_result(
            item,
            "blocked",
            str(item.get("not_runnable_reason") or "required command is unresolved"),
        )
        for item in blocking_unresolved
    ]
    preflight: dict[int, tuple[Path | None, str | None]] = {
        id(candidate): validate_candidate(candidate, roots)
        for candidate in candidates
    }
    preflight_errors = [
        (candidate, error)
        for candidate in candidates
        for _cwd, error in [preflight[id(candidate)]]
        if error
    ]
    if blocking_unresolved or preflight_errors:
        for candidate in candidates:
            _cwd, error = preflight[id(candidate)]
            results.append(blocked_result(
                candidate,
                "blocked" if error else "not-run",
                error or "phase-two preflight did not pass; no tests were executed",
            ))
        missing_runtime = [
            {
                "repo": candidate.get("repo"),
                "framework": candidate.get("framework"),
                "reason": error,
            }
            for candidate, error in preflight_errors
            if is_runtime_setup_error(error)
        ]
        readiness = {
            "ready": False,
            "checked": True,
            "missing": missing_runtime,
            "user_confirmation_required": bool(missing_runtime),
            "setup_command": SETUP_COMMAND if missing_runtime else None,
        }
        conclusion = None
        if missing_runtime:
            conclusion = (
                "测试运行环境尚未准备好，本次没有执行任何测试；"
                f"请在用户明确同意后运行 `{SETUP_COMMAND}`。"
            )
        return build_execution_report(
            manifest,
            results,
            expected_fingerprint=expected_fingerprint,
            current_fingerprint=current_fingerprint,
            include_recommended=include_recommended,
            runtime_readiness=readiness,
            conclusion_override=conclusion,
        )

    foundation_blocked = any(
        item.get("execution_layer") in FOUNDATION_LAYERS
        for item in blocking_unresolved
    )

    for layer in LAYER_ORDER:
        layer_candidates = [
            candidate for candidate in candidates
            if candidate.get("execution_layer") == layer
        ]
        for candidate in layer_candidates:
            if layer not in FOUNDATION_LAYERS and foundation_blocked:
                results.append(blocked_result(
                    candidate,
                    "not-run",
                    "foundation pytest/Vitest layer did not complete successfully",
                ))
                continue
            cwd, error = preflight[id(candidate)]
            if error or cwd is None:
                result = blocked_result(
                    candidate, "blocked", error or "candidate validation failed",
                )
            else:
                execution = command_runner(
                    list(candidate["command_argv"]), cwd, timeout_seconds,
                )
                result = {
                    "repo": candidate.get("repo"),
                    "path": candidate.get("path"),
                    "framework": candidate.get("framework"),
                    "execution_layer": candidate.get("execution_layer"),
                    "test_case": candidate.get("test_case"),
                    "changed_behaviors": candidate.get("changed_behaviors", []),
                    "selection_tier": candidate.get("selection_tier"),
                    "intended_tier": candidate.get("intended_tier"),
                    "required": bool(candidate.get("required")),
                    "command_argv": candidate.get("command_argv"),
                    **execution,
                }
            results.append(result)
            if (
                layer in FOUNDATION_LAYERS
                and candidate.get("selection_tier") == "must-run"
                and result["status"] != "passed"
            ):
                foundation_blocked = True

    return build_execution_report(
        manifest,
        results,
        expected_fingerprint=expected_fingerprint,
        current_fingerprint=current_fingerprint,
        include_recommended=include_recommended,
        runtime_readiness={
            "ready": True,
            "checked": True,
            "missing": [],
            "user_confirmation_required": False,
            "setup_command": None,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "assessment",
        help="Path to a phase-one assessment JSON or schema-v2 manifest JSON.",
    )
    parser.add_argument(
        "--workspace-root",
        help="BIC workspace root. Defaults to the assessment workspace_root.",
    )
    parser.add_argument(
        "--include-recommended",
        action="store_true",
        help="Execute recommended regression cases in addition to must-run cases.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help="Per-test-case timeout. Defaults to 600 seconds.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required explicit authorization flag for test execution.",
    )
    args = parser.parse_args()
    if not args.execute:
        parser.error("phase 2 requires the explicit --execute flag")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")

    assessment_path = Path(args.assessment).expanduser().resolve()
    payload, manifest = load_manifest(assessment_path)
    workspace_value = (
        args.workspace_root
        or payload.get("workspace_root")
        or payload.get("context", {}).get("workspace_root")
    )
    if not workspace_value:
        parser.error("workspace root is missing; pass --workspace-root")
    report = execute_manifest(
        manifest,
        Path(str(workspace_value)),
        include_recommended=args.include_recommended,
        timeout_seconds=args.timeout_seconds,
    )
    json.dump(sanitize_for_output(report), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if report["execution_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
