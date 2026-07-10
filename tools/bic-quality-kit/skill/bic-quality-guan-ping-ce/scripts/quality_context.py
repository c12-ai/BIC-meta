#!/usr/bin/env python3
"""Read-only BIC change, module, and test-context analyzer.

The configuration files are JSON-compatible YAML so the analyzer has no
third-party runtime dependencies. It reads local Git refs and files only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from symbol_extraction import extract_changed_symbols
from issue_context import collect_issue_context
from risk_assessment import assess_pretest_risk
from test_assets import discover_test_assets as discover_assets
from test_relations import analyze_test_relations


SKILL_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = SKILL_DIR / "config"

DEFAULT_IGNORE_PATTERNS = [
    ".DS_Store",
    ".phoenix/**",
    ".pnpm-store/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/node_modules/**",
    "**/.venv/**",
    "artifacts/**",
]
DISCOVERY_EXCLUDES = {
    ".agents",
    ".claude",
    ".codex",
    ".git",
    ".phoenix",
    ".pnpm-store",
    ".trellis",
    ".venv",
    "artifacts",
    "node_modules",
}
SOURCE_ROOTS = {"app", "src", "packages", "services", "lib", "bic_shared_types"}
THREE_LEVEL_ROOT_SECTIONS = {"api", "pages", "features", "modules"}


def is_bic_workspace(path: Path) -> bool:
    return (path / "Production-PRD.md").exists() and (
        (path / "CLAUDE.md").exists() or (path / "AGENTS.md").exists()
    )


def find_workspace_root() -> Path:
    starts: list[Path] = []
    if os.environ.get("BIC_WORKSPACE_ROOT"):
        starts.append(Path(os.environ["BIC_WORKSPACE_ROOT"]).expanduser().resolve())
    starts.extend([Path.cwd().resolve(), SKILL_DIR.resolve()])
    seen: set[Path] = set()
    for start in starts:
        for candidate in [start, *start.parents]:
            if candidate in seen:
                continue
            seen.add(candidate)
            if is_bic_workspace(candidate):
                return candidate
    raise SystemExit(
        "Could not locate BIC-meta workspace root. "
        "Run from inside BIC-meta or set BIC_WORKSPACE_ROOT."
    )


WORKSPACE_ROOT = find_workspace_root()


def run_git(args: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    output = proc.stdout if proc.returncode == 0 else proc.stderr
    return proc.returncode, output.strip()


def run_git_bytes(args: list[str], cwd: Path) -> tuple[int, bytes, str]:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", errors="replace").strip()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(WORKSPACE_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def is_ignored(path: str) -> bool:
    return matches_any(path, DEFAULT_IGNORE_PATTERNS)


def discover_repositories() -> list[dict[str, Any]]:
    """Discover the root repo and immediate independent child repositories."""
    candidates = [WORKSPACE_ROOT]
    for child in sorted(WORKSPACE_ROOT.iterdir(), key=lambda item: item.name):
        if child.name in DISCOVERY_EXCLUDES or not child.is_dir():
            continue
        candidates.append(child)

    repositories: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for candidate in candidates:
        code, top = run_git(["rev-parse", "--show-toplevel"], candidate)
        if code != 0:
            continue
        top_path = Path(top).resolve()
        # A normal child directory resolves to the root repo; it is not a repo.
        if candidate.resolve() != top_path:
            continue
        if top_path in seen:
            continue
        seen.add(top_path)
        repositories.append(
            {
                "name": "BIC-meta" if candidate.resolve() == WORKSPACE_ROOT.resolve() else candidate.name,
                "path": str(top_path),
                "relative_path": "." if candidate.resolve() == WORKSPACE_ROOT.resolve() else candidate.name,
            }
        )
    return repositories


def ref_exists(repo: Path, ref: str) -> bool:
    return run_git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], repo)[0] == 0


def resolve_base(repo: Path, explicit_base: str | None, worktree_only: bool) -> dict[str, Any]:
    warnings: list[str] = []
    if worktree_only:
        return {"base_ref": None, "merge_base": None, "base_resolution": "worktree-only", "warnings": warnings}

    if explicit_base:
        if not ref_exists(repo, explicit_base):
            warnings.append(f"Explicit base ref {explicit_base!r} was not found; committed changes were not analyzed.")
            return {"base_ref": None, "merge_base": None, "base_resolution": "explicit-missing", "warnings": warnings}
        candidates = [(explicit_base, "explicit")]
    else:
        candidates: list[tuple[str, str]] = []
        for env_name in ("GITHUB_BASE_REF", "CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "CHANGE_TARGET"):
            value = os.environ.get(env_name)
            if value:
                candidates.extend([(f"origin/{value}", f"env:{env_name}"), (value, f"env:{env_name}")])
        candidates.extend(
            (ref, f"auto:{ref}")
            for ref in ("origin/main", "main", "origin/master", "master")
        )

    selected: tuple[str, str] | None = None
    for candidate, source in candidates:
        if ref_exists(repo, candidate):
            selected = (candidate, source)
            break
    if not selected:
        warnings.append("No local base ref was found; only worktree changes were analyzed.")
        return {"base_ref": None, "merge_base": None, "base_resolution": "auto-missing", "warnings": warnings}

    base_ref, source = selected
    code, merge_base = run_git(["merge-base", base_ref, "HEAD"], repo)
    if code != 0:
        warnings.append(f"No merge base exists between {base_ref!r} and HEAD; committed changes were not analyzed.")
        return {"base_ref": base_ref, "merge_base": None, "base_resolution": f"{source}:no-merge-base", "warnings": warnings}
    return {"base_ref": base_ref, "merge_base": merge_base, "base_resolution": source, "warnings": warnings}


def parse_name_status(data: bytes) -> list[tuple[str, str, str | None]]:
    """Parse `git diff --name-status -z` into status, path, old_path."""
    tokens = data.decode("utf-8", errors="surrogateescape").split("\0")
    if tokens and not tokens[-1]:
        tokens.pop()
    records: list[tuple[str, str, str | None]] = []
    index = 0
    while index < len(tokens):
        status = tokens[index]
        index += 1
        if index >= len(tokens):
            break
        if status.startswith(("R", "C")):
            if index + 1 >= len(tokens):
                break
            old_path, path = tokens[index], tokens[index + 1]
            index += 2
            records.append((status, path, old_path))
        else:
            path = tokens[index]
            index += 1
            records.append((status, path, None))
    return records


def change_type(status: str) -> str:
    return {
        "A": "added", "M": "modified", "D": "deleted", "R": "renamed",
        "C": "copied", "T": "type-changed", "U": "unmerged", "?": "untracked",
    }.get(status[:1], "modified")


def collect_repository_changes(
    repo_info: dict[str, Any], explicit_base: str | None, worktree_only: bool,
    child_repo_paths: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    repo = Path(repo_info["path"])
    branch = run_git(["branch", "--show-current"], repo)[1] or None
    head = run_git(["rev-parse", "HEAD"], repo)[1] or None
    comparison = resolve_base(repo, explicit_base, worktree_only)
    changes: dict[str, dict[str, Any]] = {}

    def workspace_path(local_path: str) -> str:
        return local_path if repo == WORKSPACE_ROOT else f"{repo_info['relative_path']}/{local_path}"

    def suppressed(path: str) -> bool:
        if repo != WORKSPACE_ROOT:
            return False
        clean = path.rstrip("/")
        return any(clean == child or clean.startswith(f"{child}/") for child in child_repo_paths)

    def add(status: str, local_path: str, source: str, old_local_path: str | None = None) -> None:
        path = workspace_path(local_path)
        if suppressed(path) or is_ignored(path):
            return
        item = changes.setdefault(
            path,
            {
                "path": path,
                "repo": repo_info["name"],
                "repo_relative_path": repo_info["relative_path"],
                "status": change_type(status),
                "change_sources": [],
                "change_types": [],
            },
        )
        ctype = change_type(status)
        if source not in item["change_sources"]:
            item["change_sources"].append(source)
        if ctype not in item["change_types"]:
            item["change_types"].append(ctype)
        if old_local_path:
            item["old_path"] = workspace_path(old_local_path)
        # Keep the most destructive/specific status for compatibility.
        priority = {"untracked": 0, "modified": 1, "added": 2, "copied": 3, "renamed": 4, "deleted": 5}
        if priority.get(ctype, 1) > priority.get(item["status"], 1):
            item["status"] = ctype

    if comparison["merge_base"]:
        code, data, error = run_git_bytes(
            ["diff", "--name-status", "-z", "--find-renames", f"{comparison['merge_base']}..HEAD"], repo
        )
        if code == 0:
            for status, path, old_path in parse_name_status(data):
                add(status, path, "committed", old_path)
        else:
            comparison["warnings"].append(f"Could not read committed diff: {error}")

    for args, source in (
        (["diff", "--name-status", "-z", "--find-renames"], "worktree"),
        (["diff", "--cached", "--name-status", "-z", "--find-renames"], "staged"),
    ):
        code, data, error = run_git_bytes(args, repo)
        if code == 0:
            for status, path, old_path in parse_name_status(data):
                add(status, path, source, old_path)
        else:
            comparison["warnings"].append(f"Could not read {source} diff: {error}")

    code, data, error = run_git_bytes(["ls-files", "--others", "--exclude-standard", "-z"], repo)
    if code == 0:
        for path in data.decode("utf-8", errors="surrogateescape").split("\0"):
            if path:
                add("?", path, "untracked")
    else:
        comparison["warnings"].append(f"Could not read untracked files: {error}")

    metadata = {
        **repo_info,
        "branch": branch,
        "head": head,
        **comparison,
        "change_count": len(changes),
    }
    return metadata, sorted(changes.values(), key=lambda item: item["path"])


def collect_context(
    base_ref: str | None = None,
    worktree_only: bool = False,
    issue_ref: str | None = None,
    issue_file: str | None = None,
) -> dict[str, Any]:
    discovered = discover_repositories()
    child_paths = {repo["relative_path"] for repo in discovered if repo["relative_path"] != "."}
    repositories: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for repo in discovered:
        metadata, repo_changes = collect_repository_changes(repo, base_ref, worktree_only, child_paths)
        repositories.append(metadata)
        changed.extend(repo_changes)

    _, branch = run_git(["branch", "--show-current"], WORKSPACE_ROOT)
    _, root_status = run_git(["status", "--short"], WORKSPACE_ROOT)
    _, root_diff_stat = run_git(["diff", "--stat"], WORKSPACE_ROOT)
    return {
        "workspace_root": str(WORKSPACE_ROOT),
        "branch": branch or None,
        "analysis_mode": "worktree-only" if worktree_only else "complete-local-changeset",
        "requested_base_ref": base_ref,
        "issue_context": collect_issue_context(
            WORKSPACE_ROOT, issue_ref, issue_file, repositories,
        ),
        "repositories": repositories,
        "changed_files": sorted(changed, key=lambda item: item["path"]),
        "root_git_status_short": root_status.splitlines() if root_status else [],
        "root_diff_stat": root_diff_stat.splitlines() if root_diff_stat else [],
    }


def load_json_yaml(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON-compatible YAML: {path}: {exc}") from exc


def repository_relative_path(path: str, repo: str) -> str:
    if repo != "BIC-meta" and path.startswith(f"{repo}/"):
        return path[len(repo) + 1:]
    return path


def derive_structural_module(path: str, repo: str) -> str | None:
    """Derive a stable source-tree module without guessing business meaning."""
    local_path = repository_relative_path(path, repo)
    directories = list(Path(local_path).parts[:-1])
    root_index = next((index for index, part in enumerate(directories) if part in SOURCE_ROOTS), None)
    if root_index is None:
        return None
    rooted = directories[root_index:]
    if not rooted:
        return None
    root = rooted[0]
    depth = 1
    if len(rooted) >= 2:
        depth = 2
    if root in {"app", "src"} and len(rooted) >= 3 and rooted[1] in THREE_LEVEL_ROOT_SECTIONS:
        depth = 3
    return "/".join(rooted[:depth])


def map_modules(context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or collect_context()
    scopes = load_json_yaml(CONFIG_DIR / "scope-taxonomy.yaml")
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    unmatched: list[str] = []
    file_mappings: list[dict[str, Any]] = []

    for changed in context["changed_files"]:
        path = changed["path"]
        repo = changed["repo"]
        explicit = next((scope for scope in scopes if matches_any(path, scope.get("paths", []))), None)
        if explicit:
            mapping = {
                "id": explicit["id"], "name": explicit.get("name"),
                "repo": repo, "module_scope": explicit["module_scope"],
                "mapping_source": "explicit",
                "mapping_reason": f"matched module rule {explicit['id']}",
            }
        else:
            module = derive_structural_module(path, repo)
            if module:
                mapping = {
                    "id": f"structural:{repo}:{module}", "name": module,
                    "repo": repo, "module_scope": module,
                    "mapping_source": "structural",
                    "mapping_reason": f"derived from repository-relative source tree {module}",
                }
            else:
                mapping = {
                    "id": f"unmapped:{repo}", "name": "Unmapped",
                    "repo": repo, "module_scope": None,
                    "mapping_source": "unmapped",
                    "mapping_reason": "no explicit rule or stable source-root module",
                }
                unmatched.append(path)

        file_mappings.append({"path": path, "repo": repo, "mapping": mapping})
        key = (repo, mapping["id"], mapping["mapping_source"])
        if key not in grouped:
            grouped[key] = {**mapping, "evidence": []}
        grouped[key]["evidence"].append(path)

    modules = sorted(grouped.values(), key=lambda item: (item["repo"], item["module_scope"] or "", item["id"]))
    affected_repositories = sorted({item["repo"] for item in context["changed_files"]})
    modules_by_repository = {
        repo: [module for module in modules if module["repo"] == repo]
        for repo in affected_repositories
    }
    return {
        "workspace_root": str(WORKSPACE_ROOT),
        "changed_files": context["changed_files"],
        "affected_repositories": affected_repositories,
        "modules_by_repository": modules_by_repository,
        "direct_cross_repository": len(affected_repositories) > 1,
        "file_mappings": file_mappings,
        "unmatched_files": unmatched,
    }


def discover_test_assets(repositories: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    repositories = repositories or discover_repositories()
    return discover_assets(repositories, is_ignored)


def inspect_tests(context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or collect_context()
    inventory = load_json_yaml(CONFIG_DIR / "test-inventory.yaml")
    discovered = discover_test_assets(context["repositories"])
    discovered_paths = {asset["path"] for asset in discovered}
    entries = []
    for entry in inventory:
        matching_assets = sorted(
            path for path in discovered_paths if matches_any(path, entry.get("paths", []))
        )
        enriched = dict(entry)
        enriched.update(
            {
                "matching_discovered_assets": matching_assets,
                "present": bool(matching_assets),
                "mapping_source": "configured",
            }
        )
        entries.append(enriched)
    return {"workspace_root": str(WORKSPACE_ROOT), "tests": entries, "discovered_assets": discovered}


def recommend_tests(context: dict[str, Any], scope: dict[str, Any], tests: dict[str, Any]) -> dict[str, Any]:
    test_paths = {
        asset["path"] for asset in tests["discovered_assets"]
        if asset.get("asset_kind") == "test-file"
    }
    changed_sources = [item for item in context["changed_files"] if item["path"] not in test_paths]
    symbols = extract_changed_symbols(WORKSPACE_ROOT, changed_sources)
    return analyze_test_relations(WORKSPACE_ROOT, scope, symbols, tests["discovered_assets"], tests["tests"])


def suggest_scope(
    base_ref: str | None = None,
    worktree_only: bool = False,
    issue_ref: str | None = None,
    issue_file: str | None = None,
) -> dict[str, Any]:
    context = collect_context(base_ref, worktree_only, issue_ref, issue_file)
    scope = map_modules(context)
    tests = inspect_tests(context)
    return {
        "workspace_root": str(WORKSPACE_ROOT),
        "context": context,
        "scope": scope,
        "test_inventory": tests,
        "test_correspondence": recommend_tests(context, scope, tests),
    }


def assess_quality(
    base_ref: str | None = None,
    worktree_only: bool = False,
    issue_ref: str | None = None,
    issue_file: str | None = None,
) -> dict[str, Any]:
    payload = suggest_scope(base_ref, worktree_only, issue_ref, issue_file)
    payload["risk_assessment"] = assess_pretest_risk(
        payload["context"],
        payload["scope"],
        payload["test_correspondence"],
        payload["context"]["issue_context"],
        load_json_yaml(CONFIG_DIR / "risk-model.yaml"),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["collect", "impact", "inventory", "suggest", "assess"])
    parser.add_argument("--base-ref", help="Compare checked-out HEAD to this local base ref in every repository.")
    parser.add_argument("--worktree-only", action="store_true", help="Skip committed branch comparison.")
    parser.add_argument("--issue", help="Read this GitHub issue number, URL, or owner/repo#number with the local gh CLI.")
    parser.add_argument("--issue-file", help="Read issue context from a local JSON or Markdown file.")
    args = parser.parse_args()
    if args.base_ref and args.worktree_only:
        parser.error("--base-ref and --worktree-only are mutually exclusive")
    if args.issue and args.issue_file:
        parser.error("--issue and --issue-file are mutually exclusive")

    if args.command == "collect":
        payload = collect_context(args.base_ref, args.worktree_only, args.issue, args.issue_file)
    elif args.command == "impact":
        payload = map_modules(collect_context(args.base_ref, args.worktree_only, args.issue, args.issue_file))
    elif args.command == "inventory":
        payload = inspect_tests(collect_context(args.base_ref, args.worktree_only, args.issue, args.issue_file))
    elif args.command == "suggest":
        payload = suggest_scope(args.base_ref, args.worktree_only, args.issue, args.issue_file)
    else:
        payload = assess_quality(args.base_ref, args.worktree_only, args.issue, args.issue_file)
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
