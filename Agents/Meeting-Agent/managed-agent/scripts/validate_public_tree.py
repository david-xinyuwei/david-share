"""Run all deterministic public-subtree validation gates."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATES = (
    "audit_no_send.py",
    "audit_public_package.py",
    "validate_evidence.py",
    "validate_readmes.py",
    "pre_delivery_check.py",
)


def main() -> int:
    for filename in GATES:
        path = ROOT / "scripts" / filename
        specification = importlib.util.spec_from_file_location(path.stem, path)
        assert specification is not None and specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        result = module.main()
        if result != 0:
            raise RuntimeError(f"Gate failed: {filename}")
    print(f"PUBLIC_TREE_VALIDATION=PASS gates={len(GATES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
