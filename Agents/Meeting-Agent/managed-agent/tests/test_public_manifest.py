import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_customer_package.py"


def test_public_allowlist_excludes_private_and_legacy_files() -> None:
    specification = importlib.util.spec_from_file_location("builder", BUILDER)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    paths = {path.relative_to(ROOT).as_posix() for path in module.package_files()}

    assert "password.txt" not in paths
    assert not any(path.startswith(("logs/", "runtime/", ".azure/")) for path in paths)
    assert "evidence/aoai-live-validation.json" not in paths
    assert "evidence/managed-live/ui-live-desktop.png" not in paths
    assert "evidence/managed-live/toolbox-skill-response.json" not in paths
    assert "images/meeting-agent-demo-preview.gif" not in paths
    assert "scripts/build_ppt_template.py" not in paths
    assert "images/meeting-agent-architecture.svg" in paths
    assert "tests/e2e_server.py" in paths
