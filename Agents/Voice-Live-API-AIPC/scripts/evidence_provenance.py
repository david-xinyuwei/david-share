"""Deterministic source and artifact hashing for public validation evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

_EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}
_EXCLUDED_RELATIVE_PATHS = {
    "evidence/publication-validation.json",
    "self_check.txt",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_git_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if b"\0" in data:
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_sha256_file(path: Path) -> str:
    return hashlib.sha256(canonical_git_bytes(path)).hexdigest()


def source_snapshot(root: Path) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in _EXCLUDED_RELATIVE_PATHS:
            continue
        if any(part in _EXCLUDED_DIRECTORY_NAMES for part in path.relative_to(root).parts):
            continue
        canonical = canonical_git_bytes(path)
        entries.append(
            {
                "path": relative,
                "bytes": len(canonical),
                "sha256": hashlib.sha256(canonical).hexdigest(),
            }
        )

    canonical = json.dumps(entries, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return {
        "algorithm": "sha256(path,canonical_git_bytes,file_sha256)",
        "file_count": len(entries),
        "sha256": hashlib.sha256(canonical.encode("ascii")).hexdigest(),
    }
