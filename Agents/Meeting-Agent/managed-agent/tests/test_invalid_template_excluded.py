import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_old_pptx_template_extension_is_excluded_from_public_tree() -> None:
    path = ROOT / "scripts" / "build_customer_package.py"
    spec = importlib.util.spec_from_file_location("builder", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    public = {item.relative_to(ROOT).as_posix() for item in module.package_files()}
    assert "src/meeting_agent/templates/meeting-agent-template.zip" in public
    assert "src/meeting_agent/templates/meeting-agent-template.pptx" not in public
