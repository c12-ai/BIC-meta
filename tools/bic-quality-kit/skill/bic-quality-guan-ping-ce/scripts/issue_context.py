#!/usr/bin/env python3
"""Read-only GitHub/local issue context collection."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
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
ISSUE_METADATA_SCAN_LIMIT = 100
ISSUE_SHORTLIST_LIMIT = 10
STRONG_CANDIDATE_PRIORITY_MAX = 3
SEARCH_STOP_WORDS = {
    "app", "apps", "src", "source", "lib", "libs", "service", "services",
    "api", "test", "tests", "issue", "feature", "change", "update", "repo",
    "repository", "bic", "meta",
}


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
    return {
        token.lower()
        for token in re.split(r"[^A-Za-z0-9]+", expanded)
        if len(token) >= 3 and not token.isdigit() and token.lower() not in SEARCH_STOP_WORDS
    }


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
    repository: str, cwd: Path, limit: int = ISSUE_METADATA_SCAN_LIMIT,
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


def collect_issue_snapshot(repositories: list[dict[str, Any]]) -> dict[str, Any]:
    """Collect one bounded, read-only metadata snapshot for affected repositories."""
    strong_candidates: list[dict[str, Any]] = []
    repository_candidates: list[dict[str, Any]] = []
    repository_issue_counts: dict[str, int] = {}
    scan_warnings: list[str] = []
    affected_repositories: list[str] = []
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

        issues, warning = list_repository_issues(
            repository, repo, limit=ISSUE_METADATA_SCAN_LIMIT,
        )
        if warning:
            scan_warnings.append(warning)
        repository_issue_counts[repository] = len(issues)
        repository_candidates.extend(repository_issue_candidates(issues, repository))

    return {
        "metadata_limit_per_repository": ISSUE_METADATA_SCAN_LIMIT,
        "affected_repositories": sorted(set(affected_repositories)),
        "strong_candidates": strong_candidates,
        "repository_candidates": repository_candidates,
        "repository_issue_counts": repository_issue_counts,
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
    for changed in changed_objects:
        repo = str(changed.get("repo") or "")
        terms = object_terms_by_repo.setdefault(repo, set())
        for symbol in changed.get("symbols") or []:
            if isinstance(symbol, dict):
                terms.update(search_terms(str(symbol.get("name") or "")))

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
        candidate_terms = title_terms | label_terms
        module_matches = sorted(candidate_terms & module_terms_by_repo.get(local_repo, set()))
        object_matches = sorted(candidate_terms & object_terms_by_repo.get(local_repo, set()))
        matching_labels = sorted(
            str(label) for label in labels
            if search_terms(str(label)) & (set(module_matches) | set(object_matches))
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
        if matching_labels:
            reasons.append(f"label-match:{','.join(matching_labels)}")
        if not module_matches and not object_matches and item.get("priority", 99) > STRONG_CANDIDATE_PRIORITY_MAX:
            reasons.append("repository-fallback")
        item.update({
            "repository_match": repository_match,
            "module_matches": module_matches,
            "object_matches": object_matches,
            "matching_labels": matching_labels,
            "shortlist_reasons": [reason for reason in reasons if reason],
        })
        enriched.append(item)

    def ranking_key(item: dict[str, Any]) -> tuple[Any, ...]:
        return (
            item.get("priority", 99),
            0 if item.get("repository_match") else 1,
            -len(item.get("object_matches", [])),
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

    # Reserve one candidate per affected repository before filling globally.
    for repository in snapshot.get("affected_repositories", []):
        if len(selected) >= limit:
            break
        if any(item.get("repository") == repository for item in selected):
            continue
        candidate = next(
            (
                item for item in ordinary
                if item.get("repository") == repository and item["reference"] not in selected_refs
            ),
            None,
        )
        if candidate:
            selected.append(candidate)
            selected_refs.add(candidate["reference"])

    for candidate in ordinary:
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
        elif not item.get("module_matches") and not item.get("object_matches"):
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
        "strong_candidate_count": len(strong),
        "strong_candidate_overflow_count": max(0, len(strong) - limit),
        "strong_overflow_references": [item["reference"] for item in strong[limit:]],
    }


def hydrate_issue_candidates(
    candidates: list[dict[str, Any]], workspace_root: Path,
) -> dict[str, Any]:
    """Attempt a full read for every shortlisted candidate without a second cutoff."""
    hydrated: list[dict[str, Any]] = []
    warnings: list[str] = []
    succeeded = 0
    for candidate in candidates:
        resolved = resolve_github_issue(candidate["reference"], workspace_root)
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
        "warnings": warnings,
    }


def finalized_auto_issue_context(
    workspace_root: Path,
    snapshot: dict[str, Any],
    modules_by_repository: dict[str, list[dict[str, Any]]] | None = None,
    changed_objects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    shortlist = shortlist_issue_candidates(
        snapshot, modules_by_repository, changed_objects, ISSUE_SHORTLIST_LIMIT,
    )
    hydration = hydrate_issue_candidates(shortlist["candidates"], workspace_root)
    selected, strong_ordered = select_issue_candidate(snapshot.get("strong_candidates", []))
    hydrated_by_reference = {
        candidate["reference"]: candidate for candidate in hydration["candidates"]
    }

    if selected is None:
        if strong_ordered:
            warning = (
                "Multiple equally strong Issue references were found; compare them with the Diff or provide --issue"
            )
            discovery_mode = "auto-ambiguous"
        elif hydration["candidates"]:
            warning = (
                "No strong Issue reference was found; shortlisted Issues require semantic comparison with "
                "changed modules and objects"
            )
            discovery_mode = "affected-repository-scan"
        else:
            warning = "No open Issue was found for the affected repositories"
            discovery_mode = "affected-repository-scan"
        result = unresolved(None, "auto-discovery", warning)
        result.update({
            "discovery_mode": discovery_mode,
            "selection_reason": None,
            "analysis_status": "semantic-review-required" if hydration["candidates"] else "no-candidates",
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
        "metadata_limit_per_repository": snapshot.get("metadata_limit_per_repository", ISSUE_METADATA_SCAN_LIMIT),
        "scanned_count": sum(snapshot.get("repository_issue_counts", {}).values()),
        "shortlist_limit": shortlist["shortlist_limit"],
        "shortlisted_count": shortlist["shortlisted_count"],
        "hydration_attempted_count": hydration["attempted_count"],
        "hydration_succeeded_count": hydration["succeeded_count"],
        "hydration_failed_count": hydration["failed_count"],
        "deduplicated_candidate_count": shortlist["deduplicated_candidate_count"],
        "duplicate_reference_count": shortlist["duplicate_reference_count"],
        "excluded_count": shortlist["excluded_count"],
        "exclusion_reasons": shortlist["exclusion_reasons"],
        "shortlisted_by_repository": shortlist["shortlisted_by_repository"],
        "excluded_by_repository": shortlist["excluded_by_repository"],
        "strong_candidate_count": shortlist["strong_candidate_count"],
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
    snapshot = collect_issue_snapshot(repositories)
    return finalized_auto_issue_context(
        workspace_root, snapshot, modules_by_repository, changed_objects,
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
    return resolve_github_issue(issue_ref, workspace_root)
