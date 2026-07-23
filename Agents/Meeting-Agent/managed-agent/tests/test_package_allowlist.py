import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_customer_package.py"


def test_package_builder_uses_explicit_public_roots() -> None:
    specification = importlib.util.spec_from_file_location("builder", BUILDER)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    assert module.PUBLIC_ROOT_FILES
    assert module.PUBLIC_DIRS
    assert "evidence/managed-live" not in module.PUBLIC_DIRS
