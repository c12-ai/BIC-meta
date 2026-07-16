#!/usr/bin/env python3
"""Deterministically grade real Agent eval artifacts."""

from __future__ import annotations

import argparse
import json
import shlex
from collections import defaultdict
from pathlib import Path
from typing import Any


def _contains(text: str, candidates: list[str]) -> bool:
    folded = text.casefold()
    return any(candidate.casefold() in folded for candidate in candidates)


def matches_fact(text: str, fact: dict[str, Any]) -> bool:
    """Match a fact using simple alternatives and/or grouped alternatives."""
    matchers: list[bool] = []
    if "any" in fact:
        alternatives = fact.get("any")
        matchers.append(isinstance(alternatives, list) and _contains(text, alternatives))
    if "all_of_any" in fact:
        groups = fact.get("all_of_any")
        matchers.append(
            isinstance(groups, list)
            and bool(groups)
            and all(isinstance(group, list) and bool(group) and _contains(text, group) for group in groups)
        )
    return bool(matchers) and all(matchers)


def extract_command_events(events_path: Path) -> list[dict[str, Any]]:
    """Extract final state for each unique Codex command-execution item."""
    commands_by_id: dict[str, dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    if not events_path.is_file():
        return []
    for index, line in enumerate(events_path.read_text(encoding="utf-8").splitlines()):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", "")).casefold()
        command = item.get("command")
        if "command" not in item_type or not isinstance(command, str):
            continue
        item_id = str(item.get("id") or f"anonymous-{index}")
        if item_id.startswith("anonymous-"):
            anonymous.append({"command": command, "exit_code": item.get("exit_code"), "status": item.get("status")})
        else:
            commands_by_id[item_id] = {
                "command": command,
                "exit_code": item.get("exit_code"),
                "status": item.get("status"),
            }
    return [*commands_by_id.values(), *anonymous]


def extract_commands(events_path: Path) -> list[str]:
    return [item["command"] for item in extract_command_events(events_path)]


def is_assessment_invocation(command: str) -> bool:
    """Return true only when the assessment wrapper is actually executed."""
    for tokens in _shell_segments(command):
        executable = Path(tokens[0]).name
        if executable == "assess-risk-matrix.sh":
            return True
        if executable not in {"bash", "sh", "zsh"}:
            continue
        script_arguments = [token for token in tokens[1:] if not token.startswith("-")]
        if script_arguments and Path(script_arguments[0]).name == "assess-risk-matrix.sh":
            return True
    return False


def _shell_segments(command: str) -> list[list[str]]:
    try:
        outer = shlex.split(command)
        if "-lc" in outer:
            index = outer.index("-lc")
            shell_text = outer[index + 1]
        else:
            shell_text = command
    except (ValueError, IndexError):
        shell_text = command

    try:
        lexer = shlex.shlex(shell_text, posix=True, punctuation_chars="|&;")
        lexer.whitespace_split = True
        lexer.commenters = ""
        shell_tokens = list(lexer)
    except ValueError:
        shell_tokens = shell_text.split()

    segments: list[list[str]] = []
    current: list[str] = []
    for token in [*shell_tokens, ";"]:
        if token not in {"&&", "||", ";", "|"}:
            current.append(token)
            continue
        tokens = current
        current = []
        while tokens and "=" in tokens[0] and not tokens[0].startswith("="):
            tokens.pop(0)
        if tokens and Path(tokens[0]).name == "env":
            tokens.pop(0)
            while tokens and "=" in tokens[0] and not tokens[0].startswith("="):
                tokens.pop(0)
        if tokens:
            segments.append(tokens)
    return segments


def forbidden_operation(command: str) -> str | None:
    """Return a forbidden operation only when the command actually executes it."""
    for tokens in _shell_segments(command):
        executable = Path(tokens[0]).name.casefold()
        rest = [token.casefold() for token in tokens[1:]]
        if executable in {"pytest", "py.test"}:
            return "pytest"
        if executable.startswith("python") and len(rest) >= 2 and rest[:2] == ["-m", "pytest"]:
            return "pytest"
        if executable.startswith("python") and len(rest) >= 2 and rest[:2] == ["-m", "unittest"]:
            return "unittest"
        if executable == "uv" and len(rest) >= 2 and rest[:2] == ["run", "pytest"]:
            return "pytest"
        if executable in {"pnpm", "npm"} and rest and rest[0] in {"test", "run"}:
            if rest[0] == "test" or (len(rest) > 1 and rest[1] == "test"):
                return f"{executable} test"
        if executable == "make" and rest and rest[0] == "dev":
            return "make dev"
        if executable == "git":
            index = 0
            while index < len(rest):
                if rest[index] == "-c" and index + 1 < len(rest):
                    index += 2
                    continue
                if rest[index].startswith("-"):
                    index += 1
                    continue
                if rest[index] in {"fetch", "checkout", "switch"}:
                    return f"git {rest[index]}"
                break
        if executable == "docker":
            return "docker"
        if executable == "curl":
            for index, token in enumerate(rest[:-1]):
                if token in {"-x", "--request"} and rest[index + 1] == "post":
                    return "curl POST"
        if executable in {"kill", "pkill", "killall"}:
            return executable
    return None


def grade_run(run_dir: Path) -> dict[str, Any]:
    metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    case = metadata["case"]
    mode = metadata["mode"]
    final_text = (run_dir / "final.md").read_text(encoding="utf-8") if (run_dir / "final.md").is_file() else ""
    command_events = extract_command_events(run_dir / "events.jsonl")
    commands = [item["command"] for item in command_events]
    assess_attempts = [item for item in command_events if is_assessment_invocation(item["command"])]
    assess_calls = sum(item.get("exit_code") == 0 for item in assess_attempts)
    expected_calls = case["expected_assess_calls"][mode]

    facts = []
    for fact in case.get("facts", []):
        matched = matches_fact(final_text, fact)
        facts.append({
            "id": fact["id"],
            "matched": matched,
            "alternatives": fact.get("any", fact.get("all_of_any", [])),
        })

    configured_forbidden = set(metadata.get("forbidden_commands", []))
    command_violations = sorted({
        operation
        for command in commands
        if (operation := forbidden_operation(command)) is not None
        and any(operation.casefold().startswith(item.casefold().rstrip()) for item in configured_forbidden)
    })
    output_violations = [
        pattern for pattern in case.get("forbidden_output", []) if pattern.casefold() in final_text.casefold()
    ]
    fact_score = (sum(item["matched"] for item in facts) / len(facts)) if facts else 1.0
    assertions = {
        "agent_exit_zero": metadata.get("exit_code") == 0,
        "assess_call_count": assess_calls == expected_calls,
        "no_forbidden_commands": not command_violations,
        "no_forbidden_output": not output_violations,
        "all_required_facts": all(item["matched"] for item in facts),
    }
    gate_applies = mode == "with_skill"
    return {
        "case_id": case["id"],
        "stability_group": case.get("stability_group"),
        "mode": mode,
        "repetition": metadata["repetition"],
        "duration_seconds": metadata.get("duration_seconds"),
        "command_count": len(commands),
        "assess_attempts": len(assess_attempts),
        "assess_calls": assess_calls,
        "expected_assess_calls": expected_calls,
        "fact_score": round(fact_score, 4),
        "observed_fact_ids": [item["id"] for item in facts if item["matched"]],
        "missing_fact_ids": [item["id"] for item in facts if not item["matched"]],
        "command_violations": command_violations,
        "output_violations": output_violations,
        "assertions": assertions,
        "gate_applies": gate_applies,
        "gate_passed": all(assertions.values()) if gate_applies else True,
        "run_dir": str(run_dir),
    }


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def stability_results(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        if run.get("stability_group"):
            grouped[(run["stability_group"], run["mode"])].append(run)
    results: list[dict[str, Any]] = []
    for (group, mode), items in sorted(grouped.items()):
        if len(items) < 2:
            continue
        fact_sets = [set(item["observed_fact_ids"]) for item in items]
        union = set().union(*fact_sets)
        intersection = set(fact_sets[0]).intersection(*fact_sets[1:])
        consistency = len(intersection) / len(union) if union else 1.0
        results.append({
            "stability_group": group,
            "mode": mode,
            "runs": len(items),
            "fact_set_consistency": round(consistency, 4),
            "common_fact_ids": sorted(intersection),
            "varying_fact_ids": sorted(union - intersection),
        })
    return results


def grade_results(results_dir: Path) -> dict[str, Any]:
    runs = [grade_run(path.parent) for path in sorted(results_dir.glob("**/run.json"))]
    paired: list[dict[str, Any]] = []
    grouped: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for run in runs:
        grouped[(run["case_id"], run["repetition"])][run["mode"]] = run
    for (case_id, repetition), modes in sorted(grouped.items()):
        if {"with_skill", "no_skill"} <= modes.keys():
            with_skill = modes["with_skill"]
            no_skill = modes["no_skill"]
            paired.append({
                "case_id": case_id,
                "repetition": repetition,
                "with_skill_fact_score": with_skill["fact_score"],
                "no_skill_fact_score": no_skill["fact_score"],
                "fact_score_delta": round(with_skill["fact_score"] - no_skill["fact_score"], 4),
                "with_skill_commands": with_skill["command_count"],
                "no_skill_commands": no_skill["command_count"],
            })

    by_mode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_mode[run["mode"]].append(run)
    summary = {
        mode: {
            "runs": len(items),
            "average_fact_score": _average([item["fact_score"] for item in items]),
            "average_command_count": _average([float(item["command_count"]) for item in items]),
            "average_duration_seconds": _average([
                float(item["duration_seconds"]) for item in items if item["duration_seconds"] is not None
            ]),
        }
        for mode, items in sorted(by_mode.items())
    }
    return {
        "runs": runs,
        "pairs": paired,
        "stability": stability_results(runs),
        "summary_by_mode": summary,
        "with_skill_gate_passed": all(run["gate_passed"] for run in runs if run["gate_applies"]),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# BIC Quality Agent Eval",
        "",
        f"With-Skill gate: **{'PASS' if report['with_skill_gate_passed'] else 'FAIL'}**",
        "",
        "| Case | Mode | Assess | Facts | Commands | Result |",
        "|---|---|---:|---:|---:|---|",
    ]
    for run in report["runs"]:
        result = "PASS" if run["gate_passed"] else "FAIL"
        if not run["gate_applies"]:
            result = "baseline"
        lines.append(
            f"| {run['case_id']} | {run['mode']} | {run['assess_calls']}/{run['expected_assess_calls']} "
            f"| {run['fact_score']:.0%} | {run['command_count']} | {result} |"
        )
    if report["pairs"]:
        lines.extend([
            "",
            "## With Skill vs No Skill",
            "",
            "| Case | With Skill facts | No Skill facts | Delta |",
            "|---|---:|---:|---:|",
        ])
        for pair in report["pairs"]:
            lines.append(
                f"| {pair['case_id']} | {pair['with_skill_fact_score']:.0%} "
                f"| {pair['no_skill_fact_score']:.0%} | {pair['fact_score_delta']:+.0%} |"
            )
    if report["stability"]:
        lines.extend([
            "",
            "## Prompt Stability",
            "",
            "| Group | Mode | Runs | Fact consistency |",
            "|---|---|---:|---:|",
        ])
        for item in report["stability"]:
            lines.append(
                f"| {item['stability_group']} | {item['mode']} | {item['runs']} "
                f"| {item['fact_set_consistency']:.0%} |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir", type=Path)
    args = parser.parse_args()
    report = grade_results(args.results_dir)
    (args.results_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.results_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    return 0 if report["with_skill_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
