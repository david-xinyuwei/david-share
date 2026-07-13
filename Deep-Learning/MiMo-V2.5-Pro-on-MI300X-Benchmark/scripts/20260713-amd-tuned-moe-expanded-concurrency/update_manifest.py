#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parent
    manifest = root / "SHA256SUMS.txt"
    files = sorted(
        path for path in root.iterdir() if path.is_file() and path != manifest
    )
    manifest.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files),
        encoding="utf-8",
    )
    print(f"Wrote {len(files)} entries to {manifest}")


if __name__ == "__main__":
    main()