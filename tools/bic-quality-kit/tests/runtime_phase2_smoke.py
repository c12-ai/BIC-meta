#!/usr/bin/env python3
"""Run real Playwright and CDP commands through the phase-two executor."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = (
    WORKSPACE_ROOT
    / "tools/bic-quality-kit/skill/bic-quality-guan-ping-ce/scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import test_executor


def playwright_manifest() -> dict[str, object]:
    path = "tests/destructive-bench-guard.spec.ts"
    line = 55
    return {
        "workspace_change_fingerprint": "runtime-smoke",
        "repositories": [{
            "repo": "BIC-agent-portal",
            "relative_path": "BIC-agent-portal",
        }],
        "must_run": [{
            "repo": "BIC-agent-portal",
            "path": f"BIC-agent-portal/{path}",
            "framework": "playwright",
            "execution_layer": "browser",
            "test_case": (
                "destructive Lab helpers fail closed without an explicit "
                "isolated profile"
            ),
            "test_selector": f"{path}:{line}",
            "changed_behaviors": ["runtime Playwright command smoke"],
            "selection_tier": "must-run",
            "intended_tier": "must-run",
            "required": True,
            "command_argv": [
                "node",
                "node_modules/@playwright/test/cli.js",
                "test",
                f"{path}:{line}",
                "--workers=1",
            ],
        }],
        "recommended": [],
        "not_runnable": [],
    }


def cdp_manifest(runtime_root: Path, playwright_module: Path) -> dict[str, object]:
    repo = runtime_root / "runtime-cdp"
    repo.mkdir()
    (repo / "package.json").write_text(
        json.dumps({
            "private": True,
            "scripts": {"cdp:probe": "node cdp-probe.cjs"},
        }),
        encoding="utf-8",
    )
    (repo / "cdp-probe.cjs").write_text(
        f"""const {{ chromium }} = require({json.dumps(str(playwright_module))});
(async () => {{
  const browser = await chromium.launch({{ headless: true }});
  const page = await browser.newPage();
  const session = await page.context().newCDPSession(page);
  const value = await session.send('Runtime.evaluate', {{
    expression: '6 * 7',
    returnByValue: true,
  }});
  if (value.result.value !== 42) throw new Error('unexpected CDP result');
  await session.detach();
  await browser.close();
  console.log('1 passed - real CDP Runtime.evaluate returned 42');
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
""",
        encoding="utf-8",
    )
    return {
        "workspace_change_fingerprint": "runtime-smoke",
        "repositories": [{"repo": "runtime-cdp", "relative_path": "runtime-cdp"}],
        "must_run": [{
            "repo": "runtime-cdp",
            "path": "runtime-cdp/cdp-probe.cjs",
            "framework": "cdp",
            "execution_layer": "browser-diagnostic",
            "test_case": "standalone-cdp",
            "test_selector": "standalone-cdp",
            "changed_behaviors": ["runtime CDP command smoke"],
            "selection_tier": "must-run",
            "intended_tier": "must-run",
            "required": True,
            "command_argv": ["npm", "run", "--silent", "cdp:probe"],
        }],
        "recommended": [],
        "not_runnable": [],
    }


def main() -> int:
    playwright_report = test_executor.execute_manifest(
        playwright_manifest(),
        WORKSPACE_ROOT,
        verify_fingerprint=False,
    )
    playwright_module = (
        WORKSPACE_ROOT
        / "BIC-agent-portal/node_modules/@playwright/test"
    )
    with tempfile.TemporaryDirectory() as directory:
        runtime_root = Path(directory)
        cdp_report = test_executor.execute_manifest(
            cdp_manifest(runtime_root, playwright_module),
            runtime_root,
            verify_fingerprint=False,
        )
    result = {
        "playwright": playwright_report,
        "cdp": cdp_report,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    statuses = {
        playwright_report.get("execution_status"),
        cdp_report.get("execution_status"),
    }
    return 0 if statuses == {"passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
