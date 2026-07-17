import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_customer_package.py"


def _package_builder():
    specification = importlib.util.spec_from_file_location("customer_package_builder", MODULE_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_customer_package_excludes_test_tree() -> None:
    builder = _package_builder()
    packaged_paths = {
        path.relative_to(ROOT).as_posix()
        for path in builder.package_files()
    }

    assert not any(path.startswith("tests/") for path in packaged_paths)