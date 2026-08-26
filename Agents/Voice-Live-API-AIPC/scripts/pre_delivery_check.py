"""Run the deterministic public-repository gates in fail-fast order."""

from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATES = (
    "scripts/audit_public_content.py",
    "scripts/demo_code_validator.py",
    "scripts/validate_evidence.py",
    "scripts/validate_readmes.py",
)


def main() -> int:
    if not compileall.compile_dir(ROOT / "src", quiet=1):
        raise SystemExit("Python source compilation failed")
    if not compileall.compile_file(ROOT / "app.py", quiet=1):
        raise SystemExit("app.py compilation failed")

    for relative in GATES:
        print(f"RUN {relative}")
        subprocess.run([sys.executable, str(ROOT / relative)], cwd=ROOT, check=True)

    print("RUN pytest")
    subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=True)

    print("PRE_DELIVERY_CHECK=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
