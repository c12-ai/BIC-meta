#!/usr/bin/env python3
"""Run isolated with-Skill/no-Skill Codex eval pairs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fixtures import build_fixture, fixture_manifest
from grade_agent_eval import grade_results, render_markdown


EVAL_DIR = Path(__file__).resolve().parent
KIT_DIR = EVAL_DIR.parent
CASES_FILE = EVAL_DIR / "cases.json"
SKILL_SOURCE = KIT_DIR / "skill/bic-quality-guan-ping-ce"


def load_config() -> dict[str, Any]:
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))


def select_cases(config: dict[str, Any], suite: str, case_ids: list[str]) -> list[dict[str, Any]]:
    cases = config["cases"]
    if case_ids:
        wanted = set(case_ids)
        selected = [case for case in cases if case["id"] in wanted]
        missing = wanted - {case["id"] for case in selected}
        if missing:
            raise ValueError(f"Unknown case(s): {', '.join(sorted(missing))}")
        return selected
    return [case for case in cases if suite in case["suites"]]


def selected_modes(case: dict[str, Any], requested: str) -> list[str]:
    if requested == "both":
        return list(case["modes"])
    return [requested] if requested in case["modes"] else []


def run_one(
    case: dict[str, Any],
    mode: str,
    repetition: int,
    output_dir: Path,
    forbidden_commands: list[str],
    model: str | None,
    timeout_seconds: int,
    dry_run: bool,
) -> None:
    run_dir = output_dir / case["id"] / mode / f"run-{repetition:02d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"bic-quality-eval-{case['id']}-") as temp:
        workspace = Path(temp) / "BIC-meta"
        env_overrides = build_fixture(workspace, case["fixture"], mode, SKILL_SOURCE)
        manifest = fixture_manifest(workspace)
        command = [
            "codex", "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox", "read-only",
            "--json",
            "--cd", str(workspace),
            "--output-last-message", str(run_dir / "final.md"),
        ]
        if model:
            command.extend(["--model", model])
        command.append(case["prompt"])
        metadata: dict[str, Any] = {
            "case": case,
            "mode": mode,
            "repetition": repetition,
            "fixture_manifest": manifest,
            "forbidden_commands": forbidden_commands,
            "command": command,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
        }
        if dry_run:
            (run_dir / "final.md").write_text("", encoding="utf-8")
            (run_dir / "events.jsonl").write_text("", encoding="utf-8")
            metadata.update({"exit_code": None, "duration_seconds": 0.0})
        else:
            env = {**os.environ, **env_overrides}
            started = time.monotonic()
            try:
                result = subprocess.run(
                    command,
                    cwd=workspace,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                    check=False,
                )
                metadata["exit_code"] = result.returncode
                (run_dir / "events.jsonl").write_text(result.stdout, encoding="utf-8")
                (run_dir / "stderr.log").write_text(result.stderr, encoding="utf-8")
            except subprocess.TimeoutExpired as exc:
                metadata["exit_code"] = 124
                metadata["timed_out"] = True
                stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                (run_dir / "events.jsonl").write_text(stdout, encoding="utf-8")
                (run_dir / "stderr.log").write_text(stderr, encoding="utf-8")
                if not (run_dir / "final.md").exists():
                    (run_dir / "final.md").write_text("", encoding="utf-8")
            metadata["duration_seconds"] = round(time.monotonic() - started, 3)
        (run_dir / "run.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--case", action="append", default=[], dest="case_ids")
    parser.add_argument("--mode", choices=["both", "with_skill", "no_skill"], default="both")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--model")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

    config = load_config()
    cases = select_cases(config, args.suite, args.case_ids)
    if args.list:
        for case in cases:
            print(f"{case['id']}: fixture={case['fixture']} modes={','.join(case['modes'])}")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = (args.output_dir or EVAL_DIR / "results" / stamp).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for case in cases:
        for mode in selected_modes(case, args.mode):
            for repetition in range(1, args.repetitions + 1):
                print(f"[{case['id']}] {mode} run {repetition}/{args.repetitions}", flush=True)
                run_one(
                    case,
                    mode,
                    repetition,
                    output_dir,
                    config["forbidden_commands"],
                    args.model,
                    args.timeout_seconds,
                    args.dry_run,
                )

    if args.dry_run:
        print(f"Dry-run artifacts: {output_dir}")
        return 0
    report = grade_results(output_dir)
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    print(f"Artifacts: {output_dir}")
    return 0 if report["with_skill_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
