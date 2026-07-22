#!/usr/bin/env python3
"""Bootstrap deterministic external analyzers outside the BIC workspace."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_MANIFEST = SKILL_DIR / "config/analyzer-runtime.yaml"
INSTALL_TIMEOUT_SECONDS = 180
PROBE_TIMEOUT_SECONDS = 20
LOCK_TIMEOUT_SECONDS = 60
STALE_LOCK_SECONDS = 300


class AnalyzerRuntimeError(RuntimeError):
    """Raised when the required structural analyzer cannot be prepared."""


def load_runtime_manifest() -> dict[str, Any]:
    try:
        payload = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
        config = payload["ast_outline"]
        if not all(config.get(key) for key in ("package", "version", "python", "schema_version")):
            raise KeyError("incomplete ast_outline configuration")
        return config
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AnalyzerRuntimeError(f"Invalid analyzer runtime manifest: {exc}") from exc


def tool_cache_root() -> Path:
    override = os.environ.get("BIC_QUALITY_TOOL_CACHE")
    if override:
        root = Path(override).expanduser()
        if not root.is_absolute():
            raise AnalyzerRuntimeError("BIC_QUALITY_TOOL_CACHE must be an absolute path")
        return root.resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library/Caches/bic-quality/tools").resolve()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return (base / "bic-quality/Cache/tools").resolve()
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return (base / "bic-quality/tools").resolve()


def executable_for(environment: Path) -> Path:
    relative = Path("Scripts/ast-outline.exe") if sys.platform == "win32" else Path("bin/ast-outline")
    return environment / "venv" / relative


def marker_for(environment: Path) -> Path:
    return environment / "install.json"


def run_checked(
    args: list[str],
    *,
    timeout: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AnalyzerRuntimeError(f"Required analyzer command failed: {type(exc).__name__}") from exc


def probe_ast_outline(executable: Path, expected_schema: int) -> None:
    if not executable.is_file():
        raise AnalyzerRuntimeError(f"Required ast-outline executable is missing: {executable}")
    with tempfile.TemporaryDirectory(prefix="bic-quality-ast-probe-") as temp_dir:
        source = Path(temp_dir) / "probe.py"
        source.write_text("def probe_value():\n    return 1\n", encoding="utf-8")
        proc = run_checked(
            [str(executable), "outline", str(source), "--json"],
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    if proc.returncode != 0:
        raise AnalyzerRuntimeError("Required ast-outline capability probe failed")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AnalyzerRuntimeError("Required ast-outline did not emit valid JSON") from exc
    if payload.get("tool") != "ast-outline" or payload.get("command") != "outline":
        raise AnalyzerRuntimeError("Required ast-outline emitted an unexpected JSON envelope")
    if payload.get("schema_version") != expected_schema:
        raise AnalyzerRuntimeError(
            "Required ast-outline JSON schema is incompatible: "
            f"expected {expected_schema}, got {payload.get('schema_version')!r}"
        )
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise AnalyzerRuntimeError("Required ast-outline probe returned no parsed file")


def valid_managed_runtime(environment: Path, config: dict[str, Any]) -> Path | None:
    executable = executable_for(environment)
    marker = marker_for(environment)
    try:
        metadata = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if metadata != {
        "package": config["package"],
        "version": config["version"],
        "python": config["python"],
        "schema_version": config["schema_version"],
    }:
        return None
    try:
        probe_ast_outline(executable, int(config["schema_version"]))
    except AnalyzerRuntimeError:
        return None
    return executable


@contextmanager
def installation_lock(root: Path) -> Iterator[None]:
    """Serialize first-use installation and recover locks left by dead installers."""
    lock = root / ".ast-outline-install.lock"
    owner = lock / "owner.json"
    root.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock.mkdir()
            owner.write_text(
                json.dumps({"pid": os.getpid(), "created_at": time.time()}),
                encoding="utf-8",
            )
            break
        except FileExistsError:
            stale = False
            try:
                metadata = json.loads(owner.read_text(encoding="utf-8"))
                pid = int(metadata["pid"])
                float(metadata["created_at"])
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    stale = True
                except (PermissionError, OSError):
                    pass
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                try:
                    stale = time.time() - lock.stat().st_mtime > STALE_LOCK_SECONDS
                except OSError:
                    pass
            if stale:
                shutil.rmtree(lock, ignore_errors=True)
                continue
            if time.monotonic() >= deadline:
                raise AnalyzerRuntimeError("Timed out waiting for the ast-outline installation lock")
            time.sleep(0.1)
    try:
        yield
    finally:
        shutil.rmtree(lock, ignore_errors=True)


def install_managed_runtime(environment: Path, config: dict[str, Any]) -> Path:
    uv = shutil.which("uv")
    if not uv:
        raise AnalyzerRuntimeError("uv is required to install the pinned ast-outline analyzer")
    environment.parent.mkdir(parents=True, exist_ok=True)
    if environment.exists():
        shutil.rmtree(environment)
    environment.mkdir(parents=True)
    try:
        venv = environment / "venv"
        common_env = {**os.environ, "UV_NO_PROGRESS": "1"}
        create = run_checked(
            [uv, "venv", str(venv), "--python", str(config["python"]), "--no-config"],
            timeout=INSTALL_TIMEOUT_SECONDS,
            env=common_env,
        )
        if create.returncode != 0:
            raise AnalyzerRuntimeError("Could not create the managed ast-outline environment")
        install = run_checked(
            [
                uv,
                "pip",
                "install",
                "--python",
                str(venv),
                "--no-config",
                f"{config['package']}=={config['version']}",
            ],
            timeout=INSTALL_TIMEOUT_SECONDS,
            env=common_env,
        )
        if install.returncode != 0:
            raise AnalyzerRuntimeError(
                "Could not install the pinned ast-outline analyzer: "
                f"{install.stderr.strip()[:300]}"
            )
        executable = executable_for(environment)
        probe_ast_outline(executable, int(config["schema_version"]))
        marker_for(environment).write_text(
            json.dumps(
                {
                    "package": config["package"],
                    "version": config["version"],
                    "python": config["python"],
                    "schema_version": config["schema_version"],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        probe_ast_outline(executable, int(config["schema_version"]))
        return executable_for(environment)
    except Exception:
        shutil.rmtree(environment, ignore_errors=True)
        raise


def ensure_ast_outline() -> Path:
    """Return the pinned analyzer, installing it on first use when necessary."""
    config = load_runtime_manifest()
    explicit = os.environ.get("BIC_QUALITY_AST_OUTLINE")
    if explicit:
        executable = Path(explicit).expanduser().resolve()
        probe_ast_outline(executable, int(config["schema_version"]))
        return executable

    root = tool_cache_root()
    environment = root / "ast-outline" / str(config["version"])
    executable = valid_managed_runtime(environment, config)
    if executable is not None:
        return executable
    with installation_lock(root):
        executable = valid_managed_runtime(environment, config)
        if executable is not None:
            return executable
        return install_managed_runtime(environment, config)


if __name__ == "__main__":
    try:
        print(ensure_ast_outline())
    except AnalyzerRuntimeError as exc:
        print(f"BIC quality analyzer runtime unavailable: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
