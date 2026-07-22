#!/usr/bin/env python3
"""Read-only GitHub/local issue context collection."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
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
CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
CJK_SEQUENCE_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
ISSUE_METADATA_SCAN_LIMIT = 100
ISSUE_SHORTLIST_LIMIT = 10
GH_METADATA_TIMEOUT_SECONDS = 15
GH_BODY_TIMEOUT_SECONDS = 10
GH_TOTAL_TIMEOUT_SECONDS = 60
ISSUE_HYDRATION_MAX_WORKERS = 3
STRONG_CANDIDATE_PRIORITY_MAX = 3
AUTHORITATIVE_CANDIDATE_PRIORITY_MAX = 1
SEARCH_STOP_WORDS = {
    "app", "apps", "src", "source", "lib", "libs", "service", "services",
    "api", "test", "tests", "issue", "feature", "change", "update", "repo",
    "repository", "bic", "meta",
}
SEARCH_TERM_ALIASES = {
    "workflow": {"工作流"},
    "runtime": {"运行时"},
    "session": {"会话"},
    "database": {"数据库"},
    "persistence": {"持久化"},
    "dispatch": {"派发", "调度"},
    "event": {"事件"},
    "events": {"事件"},
    "stream": {"流式"},
    "streaming": {"流式"},
    "feedback": {"反馈"},
    "contract": {"契约"},
    "contracts": {"契约"},
}


def github_deadline() -> float:
    """Return the monotonic deadline shared by one complete GitHub analysis."""
    return time.monotonic() + GH_TOTAL_TIMEOUT_SECONDS


def bounded_github_timeout(default_seconds: float, deadline: float | None) -> float | None:
    """Bound one request by both its local timeout and the shared deadline."""
    if deadline is None:
        return default_seconds
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    return min(default_seconds, remaining)


def github_deadline_exceeded(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


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


def reference_repository(reference: str) -> str | None:
    match = REPO_ISSUE_RE.match(reference)
    return match.group("repo") if match else None


def search_terms(value: str | None) -> set[str]:
    if not value:
        return set()
    expanded = CAMEL_BOUNDARY_RE.sub(" ", value)
    terms = {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+", expanded)
        if len(token) >= 3 and not token.isdigit() and token.lower() not in SEARCH_STOP_WORDS
    }
    for sequence in CJK_SEQUENCE_RE.findall(value):
        for size in range(2, min(4, len(sequence)) + 1):
            terms.update(
                sequence[index:index + size]
                for index in range(0, len(sequence) - size + 1)
            )
    for canonical, aliases in SEARCH_TERM_ALIASES.items():
        if canonical in terms:
            terms.update(aliases)
        if terms & aliases:
            terms.add(canonical)
    return terms


def updated_timestamp(value: Any) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def merge_issue_candidates(
    primary: list[dict[str, Any]], secondary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge candidate details while keeping primary source precedence."""
    merged: dict[str, dict[str, Any]] = {}
    for candidate in [*secondary, *primary]:
        reference = candidate["reference"]
        details = merged.setdefault(reference, {"reference": reference})
        sources = details.setdefault("candidate_sources", [])
        if candidate.get("source") and candidate["source"] not in sources:
            sources.append(candidate["source"])
        evidence_items = details.setdefault("candidate_evidence", [])
        if candidate.get("evidence") and candidate["evidence"] not in evidence_items:
            evidence_items.append(candidate["evidence"])

        current_priority = details.get("priority", 99)
        candidate_priority = candidate.get("priority", 99)
        if candidate_priority < current_priority:
            details.update({
                "source": candidate.get("source"),
                "priority": candidate_priority,
                "evidence": candidate.get("evidence"),
            })
        for key, value in candidate.items():
            if key in {"source", "priority", "evidence", "candidate_sources", "candidate_evidence"}:
                continue
            if value is not None and (key not in details or details[key] in (None, "", [])):
                details[key] = value
        details.setdefault("repository", reference_repository(reference))
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


def current_pr_payload(
    repo: Path,
    warnings: list[str] | None = None,
    deadline: float | None = None,
) -> dict[str, Any] | None:
    if not shutil.which("gh"):
        return None
    timeout = bounded_github_timeout(GH_METADATA_TIMEOUT_SECONDS, deadline)
    if timeout is None:
        if warnings is not None:
            warnings.append(f"Current PR lookup skipped after total GitHub analysis deadline for {repo}")
        return None
    try:
        proc = subprocess.run(
            [
                "gh", "pr", "view", "--json",
                "number,title,body,url,state,headRefName,baseRefName,closingIssuesReferences",
            ],
            cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        if warnings is not None:
            if github_deadline_exceeded(deadline):
                warnings.append(f"Current PR lookup reached the total GitHub analysis deadline for {repo}")
            else:
                warnings.append(
                    f"Current PR lookup timed out after {GH_METADATA_TIMEOUT_SECONDS} seconds for {repo}"
                )
        return None
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def list_repository_issues(
    repository: str,
    cwd: Path,
    limit: int = ISSUE_METADATA_SCAN_LIMIT,
    deadline: float | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    if not shutil.which("gh"):
        return [], "GitHub CLI `gh` is not available; affected repository Issues were not scanned"
    timeout = bounded_github_timeout(GH_METADATA_TIMEOUT_SECONDS, deadline)
    if timeout is None:
        return [], f"Could not scan open Issues for {repository}: total GitHub analysis deadline exceeded"
    try:
        proc = subprocess.run(
            [
                "gh", "issue", "list", "--repo", repository,
                "--state", "open", "--limit", str(limit),
                "--json", "number,title,url,state,labels,updatedAt",
            ],
            cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        if github_deadline_exceeded(deadline):
            return [], (
                f"Could not scan open Issues for {repository}: total GitHub analysis deadline exceeded"
            )
        return [], (
            f"Could not scan open Issues for {repository}: timed out after "
            f"{GH_METADATA_TIMEOUT_SECONDS} seconds"
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


def resolve_github_issue(
    reference: str, cwd: Path, deadline: float | None = None,
) -> dict[str, Any]:
    if not shutil.which("gh"):
        return unresolved(reference, "github-cli", "GitHub CLI `gh` is not available")
    timeout = bounded_github_timeout(GH_BODY_TIMEOUT_SECONDS, deadline)
    if timeout is None:
        return unresolved(
            reference,
            "github-cli",
            "GitHub Issue lookup skipped after total GitHub analysis deadline",
        )
    try:
        proc = subprocess.run(
            gh_issue_command(reference), cwd=cwd, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        if github_deadline_exceeded(deadline):
            return unresolved(
                reference,
                "github-cli",
                "GitHub Issue lookup reached the total GitHub analysis deadline",
            )
        return unresolved(
            reference,
            "github-cli",
            f"GitHub Issue lookup timed out after {GH_BODY_TIMEOUT_SECONDS} seconds",
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


def graphql_issue_batch_command(references: list[str]) -> list[str] | None:
    """Build one read-only GraphQL request for repository-qualified Issue references."""
    matches = [REPO_ISSUE_RE.match(reference) for reference in references]
    if not references or any(match is None for match in matches):
        return None

    declarations: list[str] = []
    selections: list[str] = []
    command = ["gh", "api", "graphql"]
    for index, match in enumerate(matches):
        assert match is not None
        owner, name = match.group("repo").split("/", 1)
        declarations.extend([
            f"$owner_{index}: String!",
            f"$name_{index}: String!",
            f"$number_{index}: Int!",
        ])
        selections.append(
            f"issue_{index}: repository(owner: $owner_{index}, name: $name_{index}) {{ "
            f"issue(number: $number_{index}) {{ number title body url state "
            "labels(first: 100) { nodes { name } } repository { nameWithOwner } } }"
        )
        command.extend([
            "-F", f"owner_{index}={owner}",
            "-F", f"name_{index}={name}",
            "-F", f"number_{index}={match.group('number')}",
        ])
    query = f"query({', '.join(declarations)}) {{ {' '.join(selections)} }}"
    command.extend(["-f", f"query={query}"])
    return command


def normalize_graphql_issue(payload: dict[str, Any], reference: str) -> dict[str, Any]:
    labels_payload = payload.get("labels")
    label_nodes = labels_payload.get("nodes", []) if isinstance(labels_payload, dict) else []
    repository_payload = payload.get("repository")
    repository = (
        repository_payload.get("nameWithOwner")
        if isinstance(repository_payload, dict) else reference_repository(reference)
    )
    return normalize_issue(
        {
            **payload,
            "labels": label_nodes,
            "repository": repository,
        },
        reference,
        "github-graphql-batch",
    )


def batch_resolve_github_issues(
    references: list[str], cwd: Path, deadline: float | None = None,
) -> dict[str, Any]:
    """Resolve multiple Issue bodies in one read-only GraphQL request."""
    command = graphql_issue_batch_command(references)
    if command is None:
        return {
            "results": {},
            "attempted": False,
            "warning": "Issue batch lookup requires repository-qualified references",
            "deadline_exceeded": github_deadline_exceeded(deadline),
        }
    if not shutil.which("gh"):
        return {
            "results": {},
            "attempted": False,
            "warning": "GitHub CLI `gh` is not available",
            "deadline_exceeded": False,
        }
    timeout = bounded_github_timeout(GH_BODY_TIMEOUT_SECONDS, deadline)
    if timeout is None:
        return {
            "results": {},
            "attempted": False,
            "warning": "GitHub Issue batch lookup skipped after total GitHub analysis deadline",
            "deadline_exceeded": True,
        }
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        deadline_hit = github_deadline_exceeded(deadline)
        return {
            "results": {},
            "attempted": True,
            "warning": (
                "GitHub Issue batch lookup reached the total GitHub analysis deadline"
                if deadline_hit else
                f"GitHub Issue batch lookup timed out after {GH_BODY_TIMEOUT_SECONDS} seconds"
            ),
            "deadline_exceeded": deadline_hit,
        }
    if proc.returncode != 0:
        return {
            "results": {},
            "attempted": True,
            "warning": proc.stderr.strip() or "GitHub Issue batch lookup failed",
            "deadline_exceeded": github_deadline_exceeded(deadline),
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {
            "results": {},
            "attempted": True,
            "warning": f"GitHub Issue batch lookup returned invalid JSON: {exc}",
            "deadline_exceeded": github_deadline_exceeded(deadline),
        }
    if not isinstance(payload, dict):
        return {
            "results": {},
            "attempted": True,
            "warning": "GitHub Issue batch lookup returned a non-object payload",
            "deadline_exceeded": github_deadline_exceeded(deadline),
        }

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    results: dict[str, dict[str, Any]] = {}
    for index, reference in enumerate(references):
        repository_payload = data.get(f"issue_{index}")
        issue_payload = (
            repository_payload.get("issue")
            if isinstance(repository_payload, dict) else None
        )
        if isinstance(issue_payload, dict):
            results[reference] = normalize_graphql_issue(issue_payload, reference)
    errors = payload.get("errors")
    warning = None
    if errors:
        warning = f"GitHub Issue batch lookup returned partial GraphQL errors: {errors}"
    elif len(results) != len(references):
        warning = "GitHub Issue batch lookup did not return every requested Issue"
    return {
        "results": results,
        "attempted": True,
        "warning": warning,
        "deadline_exceeded": github_deadline_exceeded(deadline),
    }


def collect_issue_snapshot(
    repositories: list[dict[str, Any]], deadline: float | None = None,
) -> dict[str, Any]:
    """Collect one bounded, read-only metadata snapshot for affected repositories."""
    strong_candidates: list[dict[str, Any]] = []
    repository_candidates: list[dict[str, Any]] = []
    repository_issue_counts: dict[str, int] = {}
    repository_scans: dict[str, dict[str, Any]] = {}
    scan_warnings: list[str] = []
    affected_repositories: list[str] = []
    affected_repo_records: list[tuple[str, Path]] = []
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
        affected_repositories.append(repository)
        affected_repo_records.append((repository, repo))
        pr_payload = current_pr_payload(repo, scan_warnings, deadline)
        if pr_payload:
            strong_candidates.extend(pr_reference_candidates(pr_payload, repository))
        strong_candidates.extend(closing_reference_candidates(
            commit_messages(repo, repo_info.get("merge_base")),
            repository,
            "commit-message",
            2,
        ))
        strong_candidates.extend(branch_reference_candidates(repo_info.get("branch"), repository))

    authoritative_candidates = [
        item for item in strong_candidates
        if item.get("priority", 99) <= AUTHORITATIVE_CANDIDATE_PRIORITY_MAX
    ]
    authoritative_references = sorted({
        item["reference"] for item in authoritative_candidates
    })
    affected_repository_set = sorted(set(affected_repositories))
    authoritative_scope_complete = len(affected_repository_set) == 1
    pr_lookup_incomplete = any(
        warning.startswith("Current PR lookup") for warning in scan_warnings
    )
    authoritative_fast_path_reference = (
        authoritative_references[0]
        if (
            authoritative_scope_complete
            and len(authoritative_references) == 1
            and not pr_lookup_incomplete
        )
        else None
    )

    if authoritative_fast_path_reference:
        for repository, _repo in affected_repo_records:
            repository_scans[repository] = {
                "status": "skipped-authoritative",
                "scanned_count": 0,
                "warning": None,
            }
    else:
        for repository, repo in affected_repo_records:
            issues, warning = list_repository_issues(
                repository, repo, limit=ISSUE_METADATA_SCAN_LIMIT, deadline=deadline,
            )
            if warning:
                scan_warnings.append(warning)
            repository_scans[repository] = {
                "status": "failed" if warning else "succeeded",
                "scanned_count": len(issues),
                "warning": warning,
            }
            repository_issue_counts[repository] = len(issues)
            repository_candidates.extend(repository_issue_candidates(issues, repository))

    return {
        "metadata_limit_per_repository": ISSUE_METADATA_SCAN_LIMIT,
        "affected_repositories": affected_repository_set,
        "strong_candidates": strong_candidates,
        "repository_candidates": repository_candidates,
        "repository_issue_counts": repository_issue_counts,
        "repository_scans": repository_scans,
        "authoritative_fast_path_reference": authoritative_fast_path_reference,
        "authoritative_scope_complete": authoritative_scope_complete,
        "deadline_exceeded": github_deadline_exceeded(deadline),
        "warnings": scan_warnings,
    }


def shortlist_issue_candidates(
    snapshot: dict[str, Any],
    modules_by_repository: dict[str, list[dict[str, Any]]] | None = None,
    changed_objects: list[dict[str, Any]] | None = None,
    limit: int = ISSUE_SHORTLIST_LIMIT,
) -> dict[str, Any]:
    """Reduce metadata candidates deterministically without claiming Issue alignment."""
    modules_by_repository = modules_by_repository or {}
    changed_objects = changed_objects or []
    strong_candidates = snapshot.get("strong_candidates", [])
    repository_candidates = snapshot.get("repository_candidates", [])
    merged = merge_issue_candidates(strong_candidates, repository_candidates)

    module_terms_by_repo: dict[str, set[str]] = {}
    for repo, modules in modules_by_repository.items():
        terms = module_terms_by_repo.setdefault(repo, set())
        for module in modules:
            for key in ("module_scope", "name"):
                terms.update(search_terms(str(module.get(key) or "")))

    object_terms_by_repo: dict[str, set[str]] = {}
    path_terms_by_repo: dict[str, set[str]] = {}
    for changed in changed_objects:
        repo = str(changed.get("repo") or "")
        terms = object_terms_by_repo.setdefault(repo, set())
        for symbol in changed.get("symbols") or []:
            if isinstance(symbol, dict):
                for key in ("name", "symbol", "qualified_name", "route_path", "route_method"):
                    terms.update(search_terms(str(symbol.get(key) or "")))
        path_terms = path_terms_by_repo.setdefault(repo, set())
        path = Path(str(changed.get("path") or ""))
        path_terms.update(search_terms(path.stem))
        for part in path.parts[-3:-1]:
            path_terms.update(search_terms(part))

    enriched: list[dict[str, Any]] = []
    affected_repositories = set(snapshot.get("affected_repositories", []))
    for candidate in merged:
        item = dict(candidate)
        repository = item.get("repository") or reference_repository(item["reference"])
        item["repository"] = repository
        local_repo = str(repository or "").rsplit("/", 1)[-1]
        title_terms = search_terms(str(item.get("title") or ""))
        labels = item.get("labels", [])
        label_terms = set().union(*(search_terms(str(label)) for label in labels)) if labels else set()
        module_terms = module_terms_by_repo.get(local_repo, set())
        object_terms = object_terms_by_repo.get(local_repo, set())
        path_terms = path_terms_by_repo.get(local_repo, set())
        module_matches = sorted(title_terms & module_terms)
        object_matches = sorted(title_terms & object_terms)
        path_matches = sorted(title_terms & path_terms)
        all_change_terms = module_terms | object_terms | path_terms
        matching_labels = sorted(
            str(label) for label in labels
            if search_terms(str(label)) & all_change_terms
        )
        repository_match = repository in affected_repositories
        reasons: list[str] = []
        if item.get("priority", 99) <= STRONG_CANDIDATE_PRIORITY_MAX:
            reasons.extend(item.get("candidate_sources") or [item.get("source")])
        if repository_match:
            reasons.append("affected-repository")
        if module_matches:
            reasons.append(f"module-match:{','.join(module_matches)}")
        if object_matches:
            reasons.append(f"object-match:{','.join(object_matches)}")
        if path_matches:
            reasons.append(f"path-match:{','.join(path_matches)}")
        if matching_labels:
            reasons.append(f"label-match:{','.join(matching_labels)}")
        has_search_signal = bool(module_matches or object_matches or path_matches or matching_labels)
        if not has_search_signal and item.get("priority", 99) > STRONG_CANDIDATE_PRIORITY_MAX:
            reasons.append("repository-fallback")
        item.update({
            "repository_match": repository_match,
            "module_matches": module_matches,
            "object_matches": object_matches,
            "path_matches": path_matches,
            "matching_labels": matching_labels,
            "has_search_signal": has_search_signal,
            "shortlist_reasons": [reason for reason in reasons if reason],
        })
        enriched.append(item)

    def ranking_key(item: dict[str, Any]) -> tuple[Any, ...]:
        return (
            item.get("priority", 99),
            0 if item.get("repository_match") else 1,
            -len(item.get("object_matches", [])),
            -len(item.get("path_matches", [])),
            -len(item.get("module_matches", [])),
            -len(item.get("matching_labels", [])),
            -updated_timestamp(item.get("updated_at")),
            item["reference"],
        )

    ordered = sorted(enriched, key=ranking_key)
    strong = [
        item for item in ordered
        if item.get("priority", 99) <= STRONG_CANDIDATE_PRIORITY_MAX
    ]
    ordinary = [
        item for item in ordered
        if item.get("priority", 99) > STRONG_CANDIDATE_PRIORITY_MAX
    ]
    selected = strong[:limit]
    selected_refs = {item["reference"] for item in selected}
    fallback_selected_refs: set[str] = set()
    signaled = [item for item in ordinary if item.get("has_search_signal")]
    fallback = [item for item in ordinary if not item.get("has_search_signal")]

    # Reserve one candidate per affected repository. Prefer a real search signal;
    # otherwise allow exactly one repository fallback without filling the budget
    # with unrelated recent Issues.
    for repository in snapshot.get("affected_repositories", []):
        if len(selected) >= limit:
            break
        if any(item.get("repository") == repository for item in selected):
            continue
        candidate = next(
            (
                item for item in signaled
                if item.get("repository") == repository and item["reference"] not in selected_refs
            ),
            None,
        )
        if candidate is None:
            candidate = next(
                (
                    item for item in fallback
                    if item.get("repository") == repository and item["reference"] not in selected_refs
                ),
                None,
            )
        if candidate:
            selected.append(candidate)
            selected_refs.add(candidate["reference"])
            if not candidate.get("has_search_signal"):
                fallback_selected_refs.add(candidate["reference"])

    for candidate in signaled:
        if len(selected) >= limit:
            break
        if candidate["reference"] not in selected_refs:
            selected.append(candidate)
            selected_refs.add(candidate["reference"])

    selected = sorted(selected, key=ranking_key)
    excluded = [item for item in ordered if item["reference"] not in selected_refs]
    exclusion_reasons: dict[str, int] = {}
    for item in excluded:
        if item.get("priority", 99) <= STRONG_CANDIDATE_PRIORITY_MAX:
            reason = "strong-reference-overflow"
        elif not item.get("has_search_signal"):
            reason = "no-module-or-object-signal"
        else:
            reason = "shortlist-budget"
        exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1

    raw_candidate_count = len(strong_candidates) + len(repository_candidates)
    shortlisted_by_repository: dict[str, int] = {}
    for item in selected:
        repository = str(item.get("repository") or "unknown")
        shortlisted_by_repository[repository] = shortlisted_by_repository.get(repository, 0) + 1
    excluded_by_repository: dict[str, int] = {}
    for item in excluded:
        repository = str(item.get("repository") or "unknown")
        excluded_by_repository[repository] = excluded_by_repository.get(repository, 0) + 1
    return {
        "candidates": selected,
        "shortlist_limit": limit,
        "shortlisted_count": len(selected),
        "deduplicated_candidate_count": len(ordered),
        "duplicate_reference_count": max(0, raw_candidate_count - len(ordered)),
        "excluded_count": len(excluded),
        "exclusion_reasons": exclusion_reasons,
        "shortlisted_by_repository": shortlisted_by_repository,
        "excluded_by_repository": excluded_by_repository,
        "signal_candidate_count": len(signaled),
        "fallback_selected_count": len(fallback_selected_refs),
        "strong_candidate_count": len(strong),
        "strong_candidate_overflow_count": max(0, len(strong) - limit),
        "strong_overflow_references": [item["reference"] for item in strong[limit:]],
    }


def hydrate_issue_candidates(
    candidates: list[dict[str, Any]],
    workspace_root: Path,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Hydrate the shortlist with one batch request and a bounded fallback."""
    hydrated: list[dict[str, Any]] = []
    warnings: list[str] = []
    succeeded = 0
    resolved_by_reference: dict[str, dict[str, Any]] = {}
    batch_request_count = 0
    fallback_request_count = 0
    max_workers = 0
    mode = "none"

    if candidates and github_deadline_exceeded(deadline):
        mode = "deadline-exceeded"
        warning = "Issue hydration skipped after total GitHub analysis deadline"
        warnings.append(warning)
        for candidate in candidates:
            resolved_by_reference[candidate["reference"]] = unresolved(
                candidate["reference"], "github-cli", warning,
            )

    if len(candidates) > 1 and not resolved_by_reference:
        batch = batch_resolve_github_issues(
            [candidate["reference"] for candidate in candidates],
            workspace_root,
            deadline,
        )
        batch_request_count = 1 if batch.get("attempted") else 0
        resolved_by_reference.update(batch.get("results", {}))
        if batch.get("warning"):
            warnings.append(str(batch["warning"]))
        if len(resolved_by_reference) == len(candidates):
            mode = "batch"

    def resolve_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        try:
            if deadline is None:
                return resolve_github_issue(candidate["reference"], workspace_root)
            return resolve_github_issue(candidate["reference"], workspace_root, deadline)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            return unresolved(
                candidate["reference"], "github-cli",
                f"GitHub Issue lookup failed unexpectedly: {exc}",
            )

    fallback_candidates = [
        candidate for candidate in candidates
        if candidate["reference"] not in resolved_by_reference
    ]
    if fallback_candidates and not github_deadline_exceeded(deadline):
        fallback_request_count = len(fallback_candidates)
        max_workers = min(ISSUE_HYDRATION_MAX_WORKERS, len(fallback_candidates))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            fallback_results = list(executor.map(resolve_candidate, fallback_candidates))
        resolved_by_reference.update({
            candidate["reference"]: resolved
            for candidate, resolved in zip(fallback_candidates, fallback_results)
        })
        mode = "batch-fallback" if batch_request_count else "single" if len(candidates) == 1 else "fallback"
    elif fallback_candidates:
        mode = "deadline-exceeded"
        warning = "Issue hydration stopped at total GitHub analysis deadline"
        if warning not in warnings:
            warnings.append(warning)
        for candidate in fallback_candidates:
            resolved_by_reference[candidate["reference"]] = unresolved(
                candidate["reference"], "github-cli", warning,
            )

    for candidate in candidates:
        resolved = resolved_by_reference.get(candidate["reference"]) or unresolved(
            candidate["reference"], "github-cli", "Issue body lookup did not produce a result",
        )
        item = dict(candidate)
        item.update({
            "hydration_status": "succeeded" if resolved.get("resolved") else "failed",
            "body": resolved.get("body", "") if resolved.get("resolved") else "",
            "acceptance_items": resolved.get("acceptance_items", []) if resolved.get("resolved") else [],
            "hydration_warnings": resolved.get("warnings", []),
        })
        if resolved.get("resolved"):
            succeeded += 1
            for key in ("repository", "item_type", "number", "title", "state", "url", "labels"):
                if resolved.get(key) is not None:
                    item[key] = resolved[key]
        else:
            detail = "; ".join(resolved.get("warnings", [])) or "Issue body lookup failed"
            warnings.append(f"Could not hydrate {candidate['reference']}: {detail}")
        hydrated.append(item)
    return {
        "candidates": hydrated,
        "attempted_count": len(candidates),
        "succeeded_count": succeeded,
        "failed_count": len(candidates) - succeeded,
        "max_workers": max_workers,
        "mode": mode,
        "batch_request_count": batch_request_count,
        "fallback_request_count": fallback_request_count,
        "deadline_exceeded": github_deadline_exceeded(deadline),
        "warnings": warnings,
    }


def issue_scan_status(snapshot: dict[str, Any]) -> tuple[str, dict[str, dict[str, Any]]]:
    scans = snapshot.get("repository_scans") or {
        repository: {
            "status": "succeeded",
            "scanned_count": snapshot.get("repository_issue_counts", {}).get(repository, 0),
            "warning": None,
        }
        for repository in snapshot.get("affected_repositories", [])
    }
    statuses = {scan.get("status") for scan in scans.values()}
    if not statuses:
        return "not-run", scans
    if statuses == {"skipped-authoritative"}:
        return "skipped-authoritative", scans
    if statuses == {"failed"}:
        return "failed", scans
    if "failed" in statuses:
        return "partial", scans
    return "succeeded", scans


def finalized_auto_issue_context(
    workspace_root: Path,
    snapshot: dict[str, Any],
    modules_by_repository: dict[str, list[dict[str, Any]]] | None = None,
    changed_objects: list[dict[str, Any]] | None = None,
    deadline: float | None = None,
) -> dict[str, Any]:
    reference_candidates = snapshot.get("strong_candidates", [])
    authoritative_candidates = [
        item for item in reference_candidates
        if item.get("priority", 99) <= AUTHORITATIVE_CANDIDATE_PRIORITY_MAX
    ]
    authoritative_scope_complete = snapshot.get(
        "authoritative_scope_complete",
        len(set(snapshot.get("affected_repositories", []))) == 1,
    )
    selectable_authoritative_candidates = (
        authoritative_candidates if authoritative_scope_complete else []
    )
    repository_local_authoritative_candidates = (
        [] if authoritative_scope_complete else authoritative_candidates
    )
    reference_hints = [
        item for item in reference_candidates
        if AUTHORITATIVE_CANDIDATE_PRIORITY_MAX < item.get("priority", 99)
        <= STRONG_CANDIDATE_PRIORITY_MAX
    ]
    selected, authoritative_ordered = select_issue_candidate(
        selectable_authoritative_candidates,
    )
    fast_path_reference = snapshot.get("authoritative_fast_path_reference")
    shortlist_snapshot = snapshot
    if selected and fast_path_reference == selected["reference"]:
        shortlist_snapshot = {
            **snapshot,
            "strong_candidates": [
                candidate for candidate in reference_candidates
                if candidate["reference"] == fast_path_reference
            ],
            "repository_candidates": [],
        }
    shortlist = shortlist_issue_candidates(
        shortlist_snapshot, modules_by_repository, changed_objects, ISSUE_SHORTLIST_LIMIT,
    )
    hydration = hydrate_issue_candidates(
        shortlist["candidates"], workspace_root, deadline,
    )
    scan_status, repository_scans = issue_scan_status(snapshot)
    hydrated_by_reference = {
        candidate["reference"]: candidate for candidate in hydration["candidates"]
    }

    if selected is None:
        if repository_local_authoritative_candidates:
            warning = (
                "Current-PR Issue references are repository-local, but multiple affected repositories "
                "were found; all affected repositories were scanned and workspace Issue alignment "
                "requires semantic review"
            )
            discovery_mode = "affected-repository-scan"
            analysis_status = "semantic-review-required"
        elif authoritative_ordered:
            warning = (
                "Multiple equally authoritative Issue references were found; compare them with the Diff or provide --issue"
            )
            discovery_mode = "auto-ambiguous"
            analysis_status = "semantic-review-required"
        elif reference_hints:
            warning = (
                "Commit or branch Issue references are search hints only; compare their full content with "
                "the changed modules and objects before selecting an Issue"
            )
            discovery_mode = "auto-reference-hint"
            analysis_status = "semantic-review-required"
        elif scan_status == "failed":
            warning = (
                "Issue scanning failed for every affected GitHub repository; open-Issue availability is unknown"
            )
            discovery_mode = "affected-repository-scan"
            analysis_status = "scan-failed"
        elif scan_status == "partial":
            warning = (
                "Issue scanning succeeded for only some affected GitHub repositories; candidate analysis is incomplete"
            )
            discovery_mode = "affected-repository-scan"
            analysis_status = "partial-scan"
        elif hydration["candidates"]:
            warning = (
                "No strong Issue reference was found; shortlisted Issues require semantic comparison with "
                "changed modules and objects"
            )
            discovery_mode = "affected-repository-scan"
            analysis_status = "semantic-review-required"
        elif scan_status == "not-run":
            warning = "Issue scanning did not run because no affected GitHub repository was identified"
            discovery_mode = "affected-repository-scan"
            analysis_status = "scan-not-run"
        else:
            warning = "No open Issue was found for the affected repositories"
            discovery_mode = "affected-repository-scan"
            analysis_status = "no-candidates"
        result = unresolved(None, "auto-discovery", warning)
        result.update({
            "discovery_mode": discovery_mode,
            "selection_reason": None,
            "analysis_status": analysis_status,
        })
        base_warnings = []
    else:
        candidate = hydrated_by_reference.get(selected["reference"])
        resolved = bool(candidate and candidate.get("hydration_status") == "succeeded")
        result = unresolved(selected["reference"], "auto-discovery")
        result.update({
            "requested": False,
            "resolved": resolved,
            "reference": selected["reference"],
            "source": "auto-discovery",
            "repository": candidate.get("repository") if candidate else reference_repository(selected["reference"]),
            "item_type": candidate.get("item_type") if candidate else None,
            "number": candidate.get("number") if candidate else None,
            "title": candidate.get("title") if candidate else None,
            "body": candidate.get("body", "") if candidate else "",
            "state": candidate.get("state") if candidate else None,
            "url": candidate.get("url") if candidate else None,
            "labels": candidate.get("labels", []) if candidate else [],
            "acceptance_items": candidate.get("acceptance_items", []) if candidate else [],
            "discovery_mode": "auto",
            "selection_reason": selected["source"],
            "analysis_status": "strong-link-selected" if resolved else "resolution-failed",
        })
        base_warnings = []

    if shortlist["strong_candidate_overflow_count"]:
        base_warnings.append(
            f"Strong Issue references exceeded the shortlist limit by "
            f"{shortlist['strong_candidate_overflow_count']}; provide --issue to resolve the ambiguity"
        )
    result["candidates"] = hydration["candidates"]
    result["repository_issue_counts"] = snapshot.get("repository_issue_counts", {})
    result["issue_scan"] = {
        "scan_status": scan_status,
        "repository_scans": repository_scans,
        "metadata_limit_per_repository": snapshot.get("metadata_limit_per_repository", ISSUE_METADATA_SCAN_LIMIT),
        "scanned_count": sum(snapshot.get("repository_issue_counts", {}).values()),
        "shortlist_limit": shortlist["shortlist_limit"],
        "shortlisted_count": shortlist["shortlisted_count"],
        "hydration_attempted_count": hydration["attempted_count"],
        "hydration_succeeded_count": hydration["succeeded_count"],
        "hydration_failed_count": hydration["failed_count"],
        "hydration_max_workers": hydration["max_workers"],
        "hydration_mode": hydration["mode"],
        "hydration_batch_request_count": hydration["batch_request_count"],
        "hydration_fallback_request_count": hydration["fallback_request_count"],
        "metadata_timeout_seconds": GH_METADATA_TIMEOUT_SECONDS,
        "body_timeout_seconds": GH_BODY_TIMEOUT_SECONDS,
        "total_timeout_seconds": GH_TOTAL_TIMEOUT_SECONDS,
        "deadline_exceeded": snapshot.get("deadline_exceeded", False) or hydration["deadline_exceeded"],
        "authoritative_fast_path": bool(fast_path_reference),
        "authoritative_scope_complete": authoritative_scope_complete,
        "deduplicated_candidate_count": shortlist["deduplicated_candidate_count"],
        "duplicate_reference_count": shortlist["duplicate_reference_count"],
        "excluded_count": shortlist["excluded_count"],
        "exclusion_reasons": shortlist["exclusion_reasons"],
        "shortlisted_by_repository": shortlist["shortlisted_by_repository"],
        "excluded_by_repository": shortlist["excluded_by_repository"],
        "signal_candidate_count": shortlist["signal_candidate_count"],
        "fallback_selected_count": shortlist["fallback_selected_count"],
        "strong_candidate_count": shortlist["strong_candidate_count"],
        "authoritative_candidate_count": len(authoritative_candidates),
        "reference_hint_count": len(reference_hints),
        "strong_candidate_overflow_count": shortlist["strong_candidate_overflow_count"],
        "strong_overflow_references": shortlist["strong_overflow_references"],
    }
    result["warnings"] = [
        *result.get("warnings", []),
        *base_warnings,
        *snapshot.get("warnings", []),
        *hydration["warnings"],
    ]
    return result


def auto_discover_issue(
    workspace_root: Path,
    repositories: list[dict[str, Any]],
    modules_by_repository: dict[str, list[dict[str, Any]]] | None = None,
    changed_objects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    deadline = github_deadline()
    snapshot = collect_issue_snapshot(repositories, deadline)
    return finalized_auto_issue_context(
        workspace_root, snapshot, modules_by_repository, changed_objects, deadline,
    )


def collect_issue_context(
    workspace_root: Path,
    issue_ref: str | None = None,
    issue_file: str | None = None,
    repositories: list[dict[str, Any]] | None = None,
    modules_by_repository: dict[str, list[dict[str, Any]]] | None = None,
    changed_objects: list[dict[str, Any]] | None = None,
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
        return auto_discover_issue(
            workspace_root,
            repositories or [],
            modules_by_repository,
            changed_objects,
        )
    return resolve_github_issue(issue_ref, workspace_root, github_deadline())
