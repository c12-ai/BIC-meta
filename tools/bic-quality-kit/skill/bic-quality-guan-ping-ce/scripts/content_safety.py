#!/usr/bin/env python3
"""Filesystem containment and output-redaction helpers for quality analysis."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


REDACTED_SECRET = "[REDACTED]"
REDACTED_PATH = "[REDACTED_SENSITIVE_PATH]"

SENSITIVE_EXACT_NAMES = {
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "service-account.json",
    "service_account.json",
}
SENSITIVE_DIRECTORIES = {
    ".aws",
    ".azure",
    ".gnupg",
    ".kube",
    ".secrets",
    ".ssh",
}
SENSITIVE_ROOT_DIRECTORIES = {
    "credentials",
    "secrets",
}
SENSITIVE_SUFFIXES = {
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
}
SAFE_ENV_VARIANTS = {"dist", "example", "sample", "template"}

PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_.@+:/\\-]+")
PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----.*?"
    r"-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
    re.DOTALL,
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<prefix>[\"']?(?:api[_-]?key|access[_-]?key|access[_-]?token|"
    r"auth[_-]?token|client[_-]?secret|password|passwd|private[_-]?key|"
    r"secret|secret[_-]?key|token)[\"']?\s*[:=]\s*[\"']?)"
    r"(?P<value>[^\s,;\"']+)",
    re.IGNORECASE,
)
BEARER_RE = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+")
KNOWN_TOKEN_RE = re.compile(
    r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"AKIA[0-9A-Z]{16})\b"
)
URL_CREDENTIAL_RE = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)"
    r"(?P<user>[^:/\s]+):(?P<password>[^@\s]+)@"
)


def normalized_parts(value: str | Path) -> tuple[str, ...]:
    text = str(value).replace("\\", "/")
    return tuple(part.lower() for part in text.split("/") if part not in {"", "."})


def is_sensitive_path(
    value: str | Path,
    *,
    allow_workspace_prefix: bool = True,
) -> bool:
    """Return whether a repository-relative path is likely to hold credentials."""
    parts = normalized_parts(value)
    if not parts:
        return False
    name = parts[-1]
    if name == ".env":
        return True
    if name.startswith(".env."):
        variant = name.removeprefix(".env.")
        if variant in SAFE_ENV_VARIANTS or variant.rsplit(".", 1)[-1] in SAFE_ENV_VARIANTS:
            return False
        return True
    if name in SENSITIVE_EXACT_NAMES or Path(name).suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    if any(part in SENSITIVE_DIRECTORIES for part in parts[:-1]):
        return True
    return bool(
        parts[0] in SENSITIVE_ROOT_DIRECTORIES
        or (
            allow_workspace_prefix
            and any(part in SENSITIVE_ROOT_DIRECTORIES for part in parts[:-1])
        )
    )


def lexical_relative(path: Path, repository_root: Path) -> Path | None:
    root = Path(os.path.abspath(repository_root))
    candidate = Path(os.path.abspath(path))
    try:
        return candidate.relative_to(root)
    except ValueError:
        return None


def safe_repository_file(
    path: Path,
    repository_root: Path,
) -> tuple[Path | None, str | None]:
    """Resolve a regular, non-sensitive file without crossing repository boundaries."""
    root = Path(os.path.abspath(repository_root))
    relative = lexical_relative(path, root)
    if relative is None:
        return None, "outside-repository"

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return None, "symlink"

    if is_sensitive_path(relative, allow_workspace_prefix=False):
        return None, "sensitive-path"

    try:
        resolved_root = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError):
        return None, "outside-repository-or-unavailable"
    if not resolved.is_file():
        return None, "not-a-regular-file"
    return resolved, None


def redact_sensitive_paths(text: str) -> str:
    """Replace sensitive path tokens without hiding ordinary source paths."""
    return PATH_TOKEN_RE.sub(
        lambda match: REDACTED_PATH if is_sensitive_path(match.group(0)) else match.group(0),
        text,
    )


def redact_text(text: str) -> str:
    """Redact common credential forms and sensitive paths from public output."""
    redacted = PRIVATE_KEY_RE.sub(REDACTED_SECRET, text)
    redacted = SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTED_SECRET}",
        redacted,
    )
    redacted = BEARER_RE.sub(rf"\1{REDACTED_SECRET}", redacted)
    redacted = KNOWN_TOKEN_RE.sub(REDACTED_SECRET, redacted)
    redacted = URL_CREDENTIAL_RE.sub(
        lambda match: (
            f"{match.group('scheme')}{match.group('user')}:{REDACTED_SECRET}@"
        ),
        redacted,
    )
    return redact_sensitive_paths(redacted)


def sanitize_for_output(value: Any) -> Any:
    """Recursively sanitize strings immediately before JSON serialization."""
    if isinstance(value, dict):
        return {key: sanitize_for_output(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_for_output(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_output(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
