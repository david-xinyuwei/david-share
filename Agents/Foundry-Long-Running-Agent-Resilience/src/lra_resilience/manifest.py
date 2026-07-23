"""Build and verify a deterministic manifest for sanitized public evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any


def _file_metadata(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(handle.fileno())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OSError(f"artifact changed while hashing: {path}")
    return before.st_size, digest.hexdigest()


def _resolve_regular_file(root: Path, relative: str) -> Path:
    normalized = relative.strip()
    if not normalized:
        raise ValueError("artifact path is empty")
    if "\\" in normalized:
        raise ValueError(f"artifact path must use POSIX separators: {relative}")
    pure_path = PurePosixPath(normalized)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        raise ValueError(f"unsafe artifact path: {relative}")

    root_resolved = root.resolve(strict=True)
    candidate = root.joinpath(*pure_path.parts)
    current = root
    for part in pure_path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"artifact path contains a symlink: {relative}")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root_resolved):
        raise ValueError(f"artifact path escapes root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"artifact is not a regular file: {relative}")
    return resolved


def evidence_paths(root: Path) -> list[Path]:
    paths = list((root / "evidence" / "sanitized-runs").glob("*.json"))
    matrix = root / "data" / "validation-matrix.json"
    if matrix.is_file():
        paths.append(matrix)
    for path in paths:
        _resolve_regular_file(root, path.relative_to(root).as_posix())
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def build_manifest(root: Path) -> dict[str, Any]:
    artifacts = []
    for path in evidence_paths(root):
        relative = path.relative_to(root).as_posix()
        resolved = _resolve_regular_file(root, relative)
        byte_count, sha256 = _file_metadata(resolved)
        artifacts.append(
            {
                "path": relative,
                "bytes": byte_count,
                "sha256": sha256,
            }
        )
    return {
        "schema_version": 1,
        "disclosure": "public-sanitized-attestation",
        "artifacts": artifacts,
    }


def validate_manifest(root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("manifest.schema_version must equal 1")
    if manifest.get("disclosure") != "public-sanitized-attestation":
        errors.append("manifest.disclosure must be public-sanitized-attestation")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return errors + ["manifest.artifacts must be a non-empty list"]

    seen: set[str] = set()
    for index, artifact in enumerate(artifacts, start=1):
        if not isinstance(artifact, dict):
            errors.append(f"manifest artifact {index} must be an object")
            continue
        relative = str(artifact.get("path", "")).strip()
        if relative in seen:
            errors.append(f"duplicate manifest path: {relative}")
        seen.add(relative)
        try:
            path = _resolve_regular_file(root, relative)
            byte_count, sha256 = _file_metadata(path)
        except (OSError, ValueError) as error:
            errors.append(f"manifest artifact {index} is inaccessible: {relative}: {error}")
            continue
        if artifact.get("bytes") != byte_count:
            errors.append(f"manifest byte count mismatch: {relative}")
        if artifact.get("sha256") != sha256:
            errors.append(f"manifest SHA-256 mismatch: {relative}")

    try:
        expected = {path.relative_to(root).as_posix() for path in evidence_paths(root)}
    except (OSError, ValueError) as error:
        errors.append(f"cannot enumerate expected evidence: {error}")
        expected = set()
    if seen != expected:
        missing = sorted(expected - seen)
        extra = sorted(seen - expected)
        if missing:
            errors.append(f"manifest missing paths: {', '.join(missing)}")
        if extra:
            errors.append(f"manifest has unexpected paths: {', '.join(extra)}")
    return errors


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
