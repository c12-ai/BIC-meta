#!/usr/bin/env python3
"""Canonical local Git Diff hunks for changed-object attribution."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from content_safety import is_sensitive_path, safe_repository_file


HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)


def parse_unified_hunks(diff_text: str) -> list[dict[str, int]]:
    hunks: list[dict[str, int]] = []
    for line in diff_text.splitlines():
        match = HUNK_RE.match(line)
        if not match:
            continue
        old_start = int(match.group(1))
        old_count = int(match.group(2) or 1)
        new_start = int(match.group(3))
        new_count = int(match.group(4) or 1)
        hunks.append(
            {
                "old_start": old_start,
                "old_end": old_start + old_count - 1,
                "old_count": old_count,
                "new_start": new_start,
                "new_end": new_start + new_count - 1,
                "new_count": new_count,
            }
        )
    return hunks


def merge_hunks(hunks: list[dict[str, int]]) -> list[dict[str, int]]:
    """Deduplicate exact hunks while preserving Git's stable order."""
    seen: set[tuple[int, int, int, int]] = set()
    result: list[dict[str, int]] = []
    for hunk in hunks:
        key = (
            hunk["old_start"],
            hunk["old_count"],
            hunk["new_start"],
            hunk["new_count"],
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(hunk)
    return result


def canonical_hunks(
    repo: Path,
    comparison_base: str,
    current_local_path: str,
    old_local_path: str | None,
    *,
    untracked: bool,
) -> tuple[list[dict[str, int]], str | None]:
    if is_sensitive_path(Path(current_local_path), allow_workspace_prefix=False) or (
        old_local_path
        and is_sensitive_path(Path(old_local_path), allow_workspace_prefix=False)
    ):
        return [], "canonical diff content inspection skipped: sensitive-path"
    if untracked:
        path, reason = safe_repository_file(repo / current_local_path, repo)
        if path is None:
            return [], f"untracked line attribution skipped: {reason or 'unsafe-file'}"
        try:
            line_count = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
        except OSError as exc:
            return [], f"could not read untracked source for line attribution: {exc}"
        if line_count == 0:
            return [], None
        return [
            {
                "old_start": 0,
                "old_end": -1,
                "old_count": 0,
                "new_start": 1,
                "new_end": line_count,
                "new_count": line_count,
            }
        ], None

    paths = [current_local_path]
    if old_local_path and old_local_path != current_local_path:
        paths.append(old_local_path)
    try:
        proc = subprocess.run(
            [
                "git",
                "-c",
                "core.quotePath=false",
                "diff",
                "--unified=0",
                "--find-renames",
                "--no-ext-diff",
                "--no-color",
                comparison_base,
                "--",
                *paths,
            ],
            cwd=str(repo),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"canonical diff failed: {type(exc).__name__}"
    if proc.returncode != 0:
        return [], f"canonical diff failed: {proc.stderr.strip()[:200]}"
    parsed = merge_hunks(parse_unified_hunks(proc.stdout))
    if not parsed and old_local_path and old_local_path != current_local_path:
        try:
            new_path, reason = safe_repository_file(repo / current_local_path, repo)
            if new_path is None:
                return [], f"rename attribution skipped: {reason or 'unsafe-file'}"
            new_count = len(new_path.read_text(
                encoding="utf-8", errors="ignore",
            ).splitlines())
            old_proc = subprocess.run(
                ["git", "show", f"{comparison_base}:{old_local_path}"],
                cwd=str(repo),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            old_count = len(old_proc.stdout.splitlines()) if old_proc.returncode == 0 else 0
        except (OSError, subprocess.TimeoutExpired) as exc:
            return [], f"rename attribution failed: {type(exc).__name__}"
        if old_count or new_count:
            parsed = [{
                "old_start": 1 if old_count else 0,
                "old_end": old_count if old_count else -1,
                "old_count": old_count,
                "new_start": 1 if new_count else 0,
                "new_end": new_count if new_count else -1,
                "new_count": new_count,
            }]
    return parsed, None


def attach_canonical_hunks(
    repo: Path,
    repo_relative_path: str,
    comparison_base: str,
    changes: list[dict[str, Any]],
) -> None:
    prefix = "" if repo_relative_path == "." else f"{repo_relative_path}/"
    for changed in changes:
        current_local = changed["path"][len(prefix):] if prefix and changed["path"].startswith(prefix) else changed["path"]
        old_workspace = changed.get("old_path")
        old_local = (
            old_workspace[len(prefix):]
            if old_workspace and prefix and old_workspace.startswith(prefix)
            else old_workspace
        )
        hunks, warning = canonical_hunks(
            repo,
            comparison_base,
            current_local,
            old_local,
            untracked="untracked" in changed.get("change_types", []),
        )
        changed["diff_hunks"] = hunks
        changed["comparison_base"] = comparison_base
        if warning:
            changed.setdefault("analysis_warnings", []).append(warning)
