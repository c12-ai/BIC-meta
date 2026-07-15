#!/usr/bin/env python3
"""Build isolated Git workspaces for real BIC quality Agent evals."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


COMMON_AGENTS = """# Fixture instructions

This is an isolated BIC quality evaluation fixture. Keep all inspection read-only.
Do not execute tests, start services, modify files, fetch refs, or change Git state.
"""


def _run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def _git(repo: Path, *args: str) -> str:
    return _run(["git", *args], repo)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "quality-eval@example.invalid")
    _git(path, "config", "user.name", "BIC Quality Eval")


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)


def _install_skill(workspace: Path, skill_source: Path) -> None:
    target = workspace / ".agents/skills/bic-quality-guan-ping-ce"
    shutil.copytree(
        skill_source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    route = """

## SOP Index

Use `.agents/skills/bic-quality-guan-ping-ce/SKILL.md` for BIC quality review,
current-diff module/test analysis, missing-test review, or pre-test risk assessment.
"""
    _write(workspace / "AGENTS.md", COMMON_AGENTS + route)


def _write_issue(workspace: Path) -> None:
    issue = {
        "number": 42,
        "title": "Keep SSE workflow and disconnect payloads aligned",
        "body": (
            "## Acceptance Criteria\n"
            "- [ ] SSE payloads include the workflow event name\n"
            "- [ ] Disconnect payloads expose a structured reason\n"
            "- [ ] Tests cover both changed behaviors\n"
        ),
        "state": "OPEN",
        "url": "https://github.com/c12-ai/BIC-agent-service/issues/42",
        "labels": [{"name": "agent-api"}],
    }
    _write(workspace / "issue.json", json.dumps(issue, ensure_ascii=False, indent=2) + "\n")


def _build_agent_repo(workspace: Path, scan_failed: bool) -> Path:
    repo = workspace / "BIC-agent-service"
    _init_repo(repo)
    _write(
        repo / "app/api/routers/sse.py",
        """def stream(payload: dict) -> dict:
    return {"id": payload["id"]}


def disconnect(reason: str) -> str:
    return reason
""",
    )
    _write(
        repo / "tests/unit/test_sse.py",
        """from app.api.routers.sse import stream


def test_stream_keeps_id():
    result = stream({"id": "run-1"})
    assert result["id"] == "run-1"
""",
    )
    _write(repo / "pyproject.toml", "[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n")
    _commit_all(repo, "baseline")
    if scan_failed:
        _git(repo, "remote", "add", "origin", "https://github.com/c12-ai/BIC-agent-service.git")
    _git(repo, "switch", "-c", "feature/sse-payload")
    _write(
        repo / "app/api/routers/sse.py",
        """def stream(payload: dict) -> dict:
    return {"event": "workflow", "id": payload["id"]}


def disconnect(reason: str) -> dict:
    return {"reason": reason}
""",
    )
    _commit_all(repo, "change SSE payload contract")
    return repo


def _install_failing_gh(workspace: Path) -> Path:
    bin_dir = workspace / ".eval-bin"
    gh = bin_dir / "gh"
    _write(gh, "#!/usr/bin/env bash\necho 'fixture GitHub query failed' >&2\nexit 1\n")
    gh.chmod(0o755)
    return bin_dir


def build_fixture(
    destination: Path,
    fixture_name: str,
    mode: str,
    skill_source: Path,
) -> dict[str, str]:
    """Create one fresh workspace and return environment overrides."""
    if mode not in {"with_skill", "no_skill"}:
        raise ValueError(f"Unsupported mode: {mode}")
    if fixture_name not in {"resolved_issue", "scan_failed", "multi_repo_unrelated"}:
        raise ValueError(f"Unsupported fixture: {fixture_name}")

    workspace = destination.resolve()
    _init_repo(workspace)
    _write(workspace / ".gitignore", "/BIC-agent-service/\n/.eval-bin/\n")
    _write(workspace / "Production-PRD.md", "# Fixture PRD\n")
    if mode == "with_skill":
        _install_skill(workspace, skill_source)
    else:
        _write(workspace / "AGENTS.md", COMMON_AGENTS)

    bin_dir: Path | None = None
    if fixture_name == "scan_failed":
        bin_dir = _install_failing_gh(workspace)
        with (workspace / "AGENTS.md").open("a", encoding="utf-8") as agents:
            agents.write(
                "\nFor this deterministic fixture, prefix commands that may call `gh` with "
                "`PATH=\"$PWD/.eval-bin:$PATH\"`; the fixture `gh` always returns a local failure.\n"
            )

    if fixture_name != "scan_failed":
        _write_issue(workspace)
    _commit_all(workspace, "fixture infrastructure")
    _build_agent_repo(workspace, scan_failed=fixture_name == "scan_failed")

    if fixture_name == "multi_repo_unrelated":
        _git(workspace, "switch", "-c", "feature/local-quality-helper")
        _write(
            workspace / "tools/local_quality_helper.py",
            "def format_local_note(value: str) -> str:\n    return value.strip()\n",
        )
        _commit_all(workspace, "add unrelated local quality helper")

    env = {
        "BIC_WORKSPACE_ROOT": str(workspace),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if bin_dir is not None:
        env["PATH"] = os.pathsep.join([str(bin_dir), os.environ.get("PATH", "")])
    return env


def fixture_manifest(workspace: Path) -> dict[str, object]:
    """Return bounded facts useful for debugging without preserving the workspace."""
    repos = [workspace, workspace / "BIC-agent-service"]
    return {
        "workspace": workspace.name,
        "repositories": [
            {
                "name": repo.name,
                "branch": _git(repo, "branch", "--show-current"),
                "status": _git(repo, "status", "--short"),
                "diff_stat": _git(repo, "diff", "main...HEAD", "--stat") if repo.name != "BIC-meta" or _git(repo, "branch", "--show-current") != "main" else "",
            }
            for repo in repos
        ],
        "has_skill": (workspace / ".agents/skills/bic-quality-guan-ping-ce/SKILL.md").is_file(),
    }
