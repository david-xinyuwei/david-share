#!/usr/bin/env python3
"""Reject Git LFS pointer text in small deterministic project artifacts."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POINTER_HEADER = b"version https://git-lfs.github.com/spec/v1"
SCAN_ROOTS = (ROOT / "data", ROOT / "evidence", ROOT / "images")


def main() -> int:
    pointers = [
        path.relative_to(ROOT).as_posix()
        for scan_root in SCAN_ROOTS
        for path in scan_root.rglob("*")
        if path.is_file() and path.read_bytes().startswith(POINTER_HEADER)
    ]
    if pointers:
        for pointer in pointers:
            print(f"ERROR: deterministic artifact is a Git LFS pointer: {pointer}")
        return 1
    print("PASS: deterministic project artifacts are materialized regular files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
