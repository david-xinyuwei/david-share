#!/usr/bin/env python3
"""Run installed CLI smoke tests outside the source checkout."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*arguments: str, cwd: Path) -> None:
    subprocess.run(arguments, cwd=cwd, check=True)


def main() -> int:
    script_name = "lra-evidence.exe" if sys.platform == "win32" else "lra-evidence"
    lra_evidence = Path(sys.executable).parent / script_name
    if not lra_evidence.is_file():
        raise FileNotFoundError(
            f"installed console script not found next to the active Python: {lra_evidence}"
        )
    with tempfile.TemporaryDirectory(prefix="lra-package-smoke-") as temporary_directory:
        clean_directory = Path(temporary_directory)
        run(str(lra_evidence), "--help", cwd=clean_directory)
        run(
            str(lra_evidence),
            "validate",
            "--matrix",
            str(ROOT / "data" / "validation-matrix.json"),
            cwd=clean_directory,
        )
        run(
            str(lra_evidence),
            "manifest",
            "--root",
            str(ROOT),
            "--manifest",
            str(ROOT / "evidence" / "manifest.json"),
            cwd=clean_directory,
        )
    print("PASS: installed CLI works outside the source checkout with explicit evidence paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
