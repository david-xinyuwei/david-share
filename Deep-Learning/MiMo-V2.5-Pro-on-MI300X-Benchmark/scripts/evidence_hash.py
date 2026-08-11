from __future__ import annotations

import hashlib
from pathlib import Path


TEXT_SUFFIXES = {".csv", ".json", ".md", ".py", ".sh", ".tsv", ".txt"}


def verify_sha256(path: Path, expected: str) -> str:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() == expected:
        return "raw"

    if path.suffix.lower() not in TEXT_SUFFIXES or b"\x00" in payload:
        raise ValueError(f"SHA mismatch: {path}")
    payload.decode("utf-8")
    if payload.count(b"\r") != payload.count(b"\r\n"):
        raise ValueError(f"SHA mismatch: {path}")

    normalized = payload.replace(b"\r\n", b"\n")
    if hashlib.sha256(normalized).hexdigest() != expected:
        raise ValueError(f"SHA mismatch: {path}")
    return "canonical_lf"