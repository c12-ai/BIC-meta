#!/usr/bin/env python3
"""Read-only GitHub/local issue context collection."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")
ACCEPTANCE_HEADINGS = ("acceptance", "criteria", "验收", "完成条件", "成功标准")
REPO_ISSUE_RE = re.compile(r"^(?P<repo>[^#\s]+/[^#\s]+)#(?P<number>\d+)$")
ISSUE_URL_RE = re.compile(
    r"https://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/issues/(?P<number>\d+)"
)
ISSUE_TOKEN_RE = re.compile(
    r"https://github\.com/[^/\s]+/[^/\s]+/issues/\d+"
    r"|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#\d+|#\d+"
)
CLOSING_KEYWORD_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b", re.IGNORECASE)
BRANCH_ISSUE_RE = re.compile(r"(?:^|[/_-])issues?[-_/]?(?P<number>\d+)(?:$|[/_-])", re.IGNORECASE)


def normalize_labels(labels: Any) -> list[str]:
    if not isinstance(labels, list):
        return []
    normalized = []
    for label in labels:
        if isinstance(label, str):
            normalized.append(label)
        elif isinstance(label, dict) and label.get("name"):
            normalized.append(str(label["name"]))
    return sorted(set(normalized))


def extract_acceptance_items(body: str) -> list[dict[str, Any]]:
    checkboxes = []
    for line in body.splitlines():
        match = CHECKBOX_RE.match(line)
        if match:
            checkboxes.append({
                "text": match.group(2).strip(),
                "checked": match.group(1).lower() == "x",
                "source": "checkbox",
            })
    if checkboxes:
        return checkboxes

    items: list[dict[str, Any]] = []
    in_acceptance_section = False
    for line in body.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            title = heading.group(1).strip().lower()
            in_acceptance_section = any(token in title for token in ACCEPTANCE_HEADINGS)
            continue
        if not in_acceptance_section:
            continue
        bullet = BULLET_RE.match(line)
        if bullet:
            items.append({
                "text": bullet.group(1).strip(),
                "checked": None,
                "source": "acceptance-section",
            })
    return items


def repository_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = [part for part in urlparse(url).path.split("/") if part]
    return "/".join(parts[:2]) if len(parts) >= 2 else None


def github_repository(repo: Path) -> str | None:
    proc = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"], cwd=repo,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    remote = proc.stdout.strip()
    if not remote:
        return None
    match = re.search(r"github\.com[/:](?P<repo>[^\s]+?)(?:\.git)?$", remote)
    return match.group("repo") if match else None


def normalize_reference(token: str, default_repo: str | None) -> str | None:
    url_match = ISSUE_URL_RE.fullmatch(token)
    if url_match:
        return f"{url_match.group('repo')}#{url_match.group('number')}"
    if REPO_ISSUE_RE.fullmatch(token):
        return token
    if token.startswith("#") and token[1:].isdigit() and default_repo:
        return f"{default_repo}#{token[1:]}"
    return None


def closing_reference_candidates(
    text: str,
    default_repo: str | None,
    source: str,
    priority: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not CLOSING_KEYWORD_RE.search(line):
            continue
        for match in ISSUE_TOKEN_RE.finditer(line):
            reference = normalize_reference(match.group(0), default_repo)
            if reference:
                candidates.append({
                    "reference": reference,
                    "source": source,
                    "priority": priority,
                    "evidence": line.strip(),
                })
    return candidates


def branch_reference_candidates(branch: str | None, repository: str | None) -> list[dict[str, Any]]:
    if not branch or not repository:
        return []
    return [
        {
            "reference": f"{repository}#{match.group('number')}",
            "source": "branch-name",
            "priority": 3,
            "evidence": branch,
        }
        for match in BRANCH_ISSUE_RE.finditer(branch)
    ]


def pr_reference_candidates(payload: dict[str, Any], repository: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in payload.get("closingIssuesReferences") or []:
        item_repo = None
        repo_payload = item.get("repository") if isinstance(item, dict) else None
        if isinstance(repo_payload, dict):
            item_repo = repo_payload.get("nameWithOwner")
        item_url = item.get("url") if isinstance(item, dict) else None
        item_repo = item_repo or repository_from_url(item_url) or repository
        number = item.get("number") if isinstance(item, dict) else None
        if item_repo and number:
            candidates.append({
                "reference": f"{item_repo}#{number}",
                "source": "current-pr-linked-issue",
                "priority": 0,
                "evidence": payload.get("url") or payload.get("title") or "current PR",
            })
    candidates.extend(closing_reference_candidates(
        str(payload.get("body") or ""), repository, "current-pr-body", 1,
    ))
    return candidates


def repository_issue_candidates(
    payloads: list[dict[str, Any]], repository: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for payload in payloads:
        number = payload.get("number")
        if not number:
            continue
        candidates.append({
            "reference": f"{repository}#{number}",
            "source": "affected-repository-open-issue",
            "priority": 4,
            "evidence": f"open Issue in affected repository {repository}",
            "repository": repository,
            "number": number,
            "title": str(payload.get("title") or "").strip() or None,
            "url": payload.get("url"),
            "state": payload.get("state"),
            "labels": normalize_labels(payload.get("labels")),
            "updated_at": payload.get("updatedAt"),
        })
    return candidates


def merge_issue_candidates(
    primary: list[dict[str, Any]], secondary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge candidate details while keeping primary source precedence."""
    merged = {
        candidate["reference"]: dict(candidate)
        for candidate in secondary
    }
    for candidate in primary:
        details = merged.get(candidate["reference"], {})
        details.update(candidate)
        merged[candidate["reference"]] = details
    return sorted(
        merged.values(),
        key=lambda item: (item.get("priority", 99), item["reference"]),
    )


def select_issue_candidate(
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    deduplicated: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        current = deduplicated.get(candidate["reference"])
        if current is None or candidate["priority"] < current["priority"]:
            deduplicated[candidate["reference"]] = candidate
    ordered = sorted(deduplicated.values(), key=lambda item: (item["priority"], item["reference"]))
    if not ordered:
        return None, []
    best_priority = ordered[0]["priority"]
    strongest = [item for item in ordered if item["priority"] == best_priority]
    return (strongest[0] if len(strongest) == 1 else None), ordered


def current_pr_payload(repo: Path) -> dict[str, Any] | None:
    if not shutil.which("gh"):
        return None
    proc = subprocess.run(
        [
            "gh", "pr", "view", "--json",
            "number,title,body,url,state,headRefName,baseRefName,closingIssuesReferences",
        ],
        cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def list_repository_issues(
    repository: str, cwd: Path, limit: int = 100,
) -> tuple[list[dict[str, Any]], str | None]:
    if not shutil.which("gh"):
        return [], "GitHub CLI `gh` is not available; affected repository Issues were not scanned"
    proc = subprocess.run(
        [
            "gh", "issue", "list", "--repo", repository,
            "--state", "open", "--limit", str(limit),
            "--json", "number,title,url,state,labels,updatedAt",
        ],
        cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or "GitHub CLI could not list Issues"
        return [], f"Could not scan open Issues for {repository}: {detail}"
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return [], f"Could not scan open Issues for {repository}: invalid JSON: {exc}"
    if not isinstance(payload, list):
        return [], f"Could not scan open Issues for {repository}: GitHub CLI returned a non-list payload"
    return [item for item in payload if isinstance(item, dict)], None


def commit_messages(repo: Path, merge_base: str | None) -> str:
    if not merge_base:
        return ""
    proc = subprocess.run(
        ["git", "log", "--format=%B", f"{merge_base}..HEAD"], cwd=repo,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    return proc.stdout if proc.returncode == 0 else ""


def normalize_issue(payload: dict[str, Any], reference: str, source: str) -> dict[str, Any]:
    body = str(payload.get("body") or "")
    url = str(payload.get("url") or "") or None
    state = payload.get("state")
    item_type = "pull-request" if (url and "/pull/" in url) or state == "MERGED" else "issue"
    return {
        "requested": True,
        "resolved": True,
        "reference": reference,
        "source": source,
        "repository": payload.get("repository") or repository_from_url(url),
        "item_type": item_type,
        "number": payload.get("number"),
        "title": str(payload.get("title") or "").strip() or None,
        "body": body,
        "state": state,
        "url": url,
        "labels": normalize_labels(payload.get("labels")),
        "acceptance_items": extract_acceptance_items(body),
        "discovery_mode": "explicit",
        "selection_reason": source,
        "candidates": [],
        "repository_issue_counts": {},
        "analysis_status": "explicit-selected",
        "warnings": ["Reference resolved to a pull request, not an Issue"]
        if item_type == "pull-request" else [],
    }


def unresolved(reference: str | None, source: str | None, warning: str | None = None) -> dict[str, Any]:
    return {
        "requested": bool(reference),
        "resolved": False,
        "reference": reference,
        "source": source,
        "repository": None,
        "item_type": None,
        "number": None,
        "title": None,
        "body": "",
        "state": None,
        "url": None,
        "labels": [],
        "acceptance_items": [],
        "discovery_mode": "none",
        "selection_reason": None,
        "candidates": [],
        "repository_issue_counts": {},
        "analysis_status": "not-started",
        "warnings": [warning] if warning else [],
    }


def load_issue_file(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise ValueError("issue JSON must contain an object")
    else:
        lines = content.splitlines()
        title = next((line.lstrip("# ").strip() for line in lines if line.strip()), path.stem)
        payload = {"title": title, "body": content}
    return normalize_issue(payload, str(path), "local-file")


def gh_issue_command(reference: str) -> list[str]:
    match = REPO_ISSUE_RE.match(reference)
    if match:
        return [
            "gh", "issue", "view", match.group("number"),
            "--repo", match.group("repo"),
            "--json", "number,title,body,url,state,labels",
        ]
    return [
        "gh", "issue", "view", reference,
        "--json", "number,title,body,url,state,labels",
    ]


def resolve_github_issue(reference: str, cwd: Path) -> dict[str, Any]:
    if not shutil.which("gh"):
        return unresolved(reference, "github-cli", "GitHub CLI `gh` is not available")
    proc = subprocess.run(
        gh_issue_command(reference), cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if proc.returncode != 0:
        warning = proc.stderr.strip() or "GitHub CLI could not resolve the issue"
        return unresolved(reference, "github-cli", warning)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return unresolved(reference, "github-cli", f"GitHub CLI returned invalid JSON: {exc}")
    if not isinstance(payload, dict):
        return unresolved(reference, "github-cli", "GitHub CLI returned a non-object payload")
    return normalize_issue(payload, reference, "github-cli")


def auto_discover_issue(
    workspace_root: Path,
    repositories: list[dict[str, Any]],
) -> dict[str, Any]:
    strong_candidates: list[dict[str, Any]] = []
    repository_candidates: list[dict[str, Any]] = []
    repository_issue_counts: dict[str, int] = {}
    scan_warnings: list[str] = []
    for repo_info in repositories:
        if not repo_info.get("change_count"):
            continue
        repo = Path(repo_info["path"])
        repository = github_repository(repo)
        if not repository:
            scan_warnings.append(
                f"Could not identify a GitHub repository for affected repository {repo_info.get('name') or repo}"
            )
            continue
        pr_payload = current_pr_payload(repo)
        if pr_payload:
            strong_candidates.extend(pr_reference_candidates(pr_payload, repository))
        strong_candidates.extend(closing_reference_candidates(
            commit_messages(repo, repo_info.get("merge_base")),
            repository,
            "commit-message",
            2,
        ))
        strong_candidates.extend(branch_reference_candidates(repo_info.get("branch"), repository))

        issues, warning = list_repository_issues(repository, repo)
        if warning:
            scan_warnings.append(warning)
        repository_issue_counts[repository] = len(issues)
        repository_candidates.extend(repository_issue_candidates(issues, repository))

    selected, strong_ordered = select_issue_candidate(strong_candidates)
    ordered = merge_issue_candidates(strong_ordered, repository_candidates)
    if selected is None:
        if strong_ordered:
            warning = (
                "Multiple equally strong Issue references were found; compare them with the Diff or provide --issue"
            )
            discovery_mode = "auto-ambiguous"
        elif repository_candidates:
            warning = (
                "No strong Issue reference was found; open Issues from affected repositories require semantic "
                "comparison with changed modules and objects"
            )
            discovery_mode = "affected-repository-scan"
        else:
            warning = "No open Issue was found for the affected repositories"
            discovery_mode = "affected-repository-scan"
        result = unresolved(None, "auto-discovery", warning)
        result.update({
            "discovery_mode": discovery_mode,
            "selection_reason": None,
            "candidates": ordered,
            "repository_issue_counts": repository_issue_counts,
            "analysis_status": "semantic-review-required" if ordered else "no-candidates",
            "warnings": [warning, *scan_warnings],
        })
        return result

    result = resolve_github_issue(selected["reference"], workspace_root)
    result["requested"] = False
    result["discovery_mode"] = "auto"
    result["selection_reason"] = selected["source"]
    result["candidates"] = ordered
    result["repository_issue_counts"] = repository_issue_counts
    result["analysis_status"] = "strong-link-selected" if result.get("resolved") else "resolution-failed"
    result["warnings"] = [*result.get("warnings", []), *scan_warnings]
    return result


def collect_issue_context(
    workspace_root: Path,
    issue_ref: str | None = None,
    issue_file: str | None = None,
    repositories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if issue_ref and issue_file:
        return unresolved(issue_ref, None, "--issue and --issue-file are mutually exclusive")
    if issue_file:
        path = Path(issue_file).expanduser()
        if not path.is_absolute():
            path = workspace_root / path
        try:
            return load_issue_file(path.resolve())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return unresolved(str(path), "local-file", f"Could not read issue file: {exc}")
    if not issue_ref:
        return auto_discover_issue(workspace_root, repositories or [])
    return resolve_github_issue(issue_ref, workspace_root)
