import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "audit_public_package.py"


def test_public_package_audit_passes_allowlisted_tree() -> None:
    specification = importlib.util.spec_from_file_location("public_audit", MODULE_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    assert module.main() == 0
