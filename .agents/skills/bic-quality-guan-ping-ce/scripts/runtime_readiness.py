#!/usr/bin/env python3
"""Cross-platform readiness checks for phase-two BIC test execution."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


SETUP_COMMAND = "make quality-test-setup"
RUNTIME_ERROR_MARKERS = (
    "environment is missing",
    "dependency is missing",
    "browser executable is missing",
    "browser could not launch",
    "playwright chromium",
    "required executable",
)


def source_meta_root() -> Path:
    """Return the BIC-meta checkout containing the source Skill."""
    root = Path(__file__).resolve().parents[5]
    if not (
        (root / "Makefile").is_file()
        and (root / "tools/bic-quality-kit").is_dir()
    ):
        raise RuntimeError(
            "runtime doctor must run from tools/bic-quality-kit inside BIC-meta"
        )
    return root


def is_runtime_setup_error(reason: str | None) -> bool:
    lowered = str(reason or "").lower()
    return any(marker in lowered for marker in RUNTIME_ERROR_MARKERS)


@lru_cache(maxsize=16)
def playwright_browser_status(portal_value: str) -> tuple[bool, str | None]:
    portal = Path(portal_value)
    node = shutil.which("node")
    cli = portal / "node_modules/@playwright/test/cli.js"
    if node is None:
        return False, "required executable 'node' is missing"
    if not cli.is_file():
        return False, "Playwright dependency is missing"
    probe = subprocess.run(
        [
            node,
            "-e",
            (
                "const { chromium } = require('@playwright/test');"
                "(async()=>{"
                "const browser=await chromium.launch({headless:true});"
                "await browser.close();"
                "process.stdout.write(chromium.executablePath());"
                "})().catch(error=>{"
                "process.stderr.write(String(error));"
                "process.exit(1);"
                "});"
            ),
        ],
        cwd=str(portal),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=10,
    )
    if probe.returncode != 0:
        detail = probe.stderr.strip().splitlines()
        suffix = f": {detail[0][:240]}" if detail else ""
        return False, f"Playwright browser could not launch{suffix}"
    executable = Path(probe.stdout.strip()).expanduser()
    if not executable.is_file():
        return False, "Playwright browser executable is missing"
    return True, str(executable)


def configured_cdp_scripts(portal: Path) -> list[str]:
    package_path = portal / "package.json"
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return sorted(
        str(name)
        for name, command in package.get("scripts", {}).items()
        if "cdp" in f"{name} {command}".lower()
    )


def check(
    name: str,
    ready: bool,
    detail: str,
    fix: str | None = None,
    *,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "name": name,
        "ready": ready,
        "required": required,
        "detail": detail,
        "fix": fix,
    }


def meta_readiness(meta_root: Path) -> dict[str, Any]:
    root = meta_root.resolve()
    service = root / "BIC-agent-service"
    portal = root / "BIC-agent-portal"
    checks: list[dict[str, Any]] = []

    for executable in ("python3", "uv", "node", "npm"):
        location = shutil.which(executable)
        checks.append(check(
            f"executable:{executable}",
            location is not None,
            location or f"{executable} was not found on PATH",
            f"Install {executable} and re-run {SETUP_COMMAND}",
        ))

    pnpm = shutil.which("pnpm")
    corepack = shutil.which("corepack")
    checks.append(check(
        "installer:pnpm",
        pnpm is not None or corepack is not None,
        pnpm or corepack or "neither pnpm nor Corepack was found on PATH",
        "Install Node.js with Corepack support, then re-run the setup command",
    ))

    checks.extend([
        check(
            "repository:BIC-agent-service",
            service.is_dir(),
            str(service),
            "Clone BIC-agent-service directly under this BIC-meta checkout",
        ),
        check(
            "repository:BIC-agent-portal",
            portal.is_dir(),
            str(portal),
            "Clone BIC-agent-portal directly under this BIC-meta checkout",
        ),
    ])
    pytest_path = service / ".venv/bin/pytest"
    checks.append(check(
        "runtime:pytest",
        pytest_path.is_file(),
        str(pytest_path),
        SETUP_COMMAND,
    ))
    vitest_path = portal / "node_modules/vitest/vitest.mjs"
    checks.append(check(
        "runtime:vitest",
        vitest_path.is_file(),
        str(vitest_path),
        SETUP_COMMAND,
    ))
    playwright_path = portal / "node_modules/@playwright/test/cli.js"
    checks.append(check(
        "runtime:playwright",
        playwright_path.is_file(),
        str(playwright_path),
        SETUP_COMMAND,
    ))
    browser_ready, browser_detail = playwright_browser_status(str(portal))
    checks.append(check(
        "runtime:chromium",
        browser_ready,
        browser_detail or "Playwright Chromium is unavailable",
        SETUP_COMMAND,
    ))
    cdp_scripts = configured_cdp_scripts(portal)
    checks.append(check(
        "runtime:standalone-cdp-command",
        bool(cdp_scripts),
        ", ".join(cdp_scripts) if cdp_scripts else (
            "no repository-owned standalone CDP package script is configured; "
            "Playwright tests may still use CDP sessions"
        ),
        None,
        required=False,
    ))
    missing = [
        item for item in checks
        if item["required"] and not item["ready"]
    ]
    return {
        "schema_version": 1,
        "meta_root": str(root),
        "ready": not missing,
        "checks": checks,
        "missing_required": missing,
        "setup_command": SETUP_COMMAND,
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "BIC quality test runtime doctor",
        f"BIC-meta: {report['meta_root']}",
        "",
    ]
    for item in report["checks"]:
        marker = "OK" if item["ready"] else "WARN" if not item["required"] else "MISSING"
        lines.append(f"[{marker}] {item['name']}: {item['detail']}")
        if not item["ready"] and item.get("fix"):
            lines.append(f"  Fix: {item['fix']}")
    lines.extend([
        "",
        "READY" if report["ready"] else (
            f"NOT READY: run `{report['setup_command']}` after reviewing the changes."
        ),
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = meta_readiness(source_meta_root())
    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(render_text(report))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
