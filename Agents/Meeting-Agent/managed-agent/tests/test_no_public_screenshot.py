import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_private_live_screenshot_is_not_public() -> None:
    builder_path = ROOT / "scripts" / "build_customer_package.py"
    spec = importlib.util.spec_from_file_location("builder", builder_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    paths = {path.relative_to(ROOT).as_posix() for path in module.package_files()}
    assert "evidence/managed-live/ui-live-desktop.png" not in paths
